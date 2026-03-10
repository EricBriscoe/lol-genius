from __future__ import annotations

import functools
import logging
import os
import sys
from datetime import UTC, datetime

import click

from lol_genius.config import load_config

log = logging.getLogger(__name__)


def cli_error_handler(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except SystemExit:
            raise
        except Exception:
            log.exception("Command failed")
            sys.exit(1)

    return wrapper


_DOCKER = os.environ.get("LOL_GENIUS_DOCKER") == "1"


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S" if _DOCKER else "%H:%M:%S"
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt)
    logging.getLogger("httpx").setLevel(logging.WARNING)


@click.group()
@click.option("--config", "config_path", default="config.yaml", help="Path to config file")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx, config_path, verbose):
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["verbose"] = verbose


def _get_config(ctx):
    return load_config(ctx.obj["config_path"])


def _make_api(config):
    if config.proxy_url:
        from lol_genius.api.proxy_client import ProxyClient

        return ProxyClient(config.proxy_url)

    from lol_genius.api.client import RiotHTTPClient
    from lol_genius.api.riot_api import RiotAPI
    from lol_genius.config import make_key_loader

    key_loader = make_key_loader() if _DOCKER else None
    client = RiotHTTPClient(
        config.riot_api_key, key_loader=key_loader, rate_scale=config.rate_scale
    )
    return RiotAPI(client, config.region, config.routing, priority="low")


@cli.command("init-db")
@click.option("--wait", is_flag=True, help="Wait for database to become available first")
@click.pass_context
@cli_error_handler
def init_db(ctx, wait):
    """Run database migrations via dbmate."""
    import subprocess

    from lol_genius.db.connection import dbmate_url

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        config = _get_config(ctx)
        database_url = config.database_url
    env = {**os.environ, "DATABASE_URL": dbmate_url(database_url)}

    if wait:
        subprocess.run(["dbmate", "wait"], env=env, check=True)

    subprocess.run(["dbmate", "up"], env=env, check=True)
    click.echo("Database migrations applied.")


@cli.command("fetch-ddragon")
@click.pass_context
@cli_error_handler
def fetch_ddragon(ctx):
    """Download/update Data Dragon champion data."""
    config = _get_config(ctx)

    from lol_genius.api.ddragon import DataDragon

    dd = DataDragon(config.ddragon_cache)
    version = dd.get_latest_version()
    champions = dd.fetch_champion_data(version)
    click.echo(f"Downloaded {len(champions)} champions for patch {version}")


@cli.command()
@click.pass_context
@cli_error_handler
def seed(ctx):
    """Seed crawl queue with accounts from League-V4 entries."""
    config = _get_config(ctx)

    from lol_genius.crawler.seed import seed_accounts
    from lol_genius.db.queries import MatchDB

    api = _make_api(config)
    db = MatchDB(config.database_url)

    try:
        added = seed_accounts(api, db, config)
        click.echo(f"Seeded {added} accounts")
    finally:
        api.close()
        db.close()


class _EventStopper:
    def __init__(self, event):
        self._event = event

    def should_stop(self) -> bool:
        return self._event.is_set()


def _decide_action(db) -> str:
    enrichment = db.get_enrichment_stats()
    if enrichment["enriched"] < enrichment["total"]:
        return "enrich"
    stats = db.get_timeline_stats()
    if stats["fetched"] < stats["total"]:
        return "fetch_timelines"
    return "crawl"


@cli.command()
@click.pass_context
@cli_error_handler
def crawl(ctx):
    """Supervisor loop: auto-prioritizes timeline fetching over crawling when behind."""
    import signal
    import threading
    import time
    from dataclasses import replace

    config = _get_config(ctx)

    from lol_genius.api.ddragon import DataDragon
    from lol_genius.crawler.snowball import crawl_matches, drain_unenriched
    from lol_genius.db.queries import MatchDB

    api = _make_api(config)
    ddragon = DataDragon(config.ddragon_cache)
    db = MatchDB(config.database_url)

    _stop = threading.Event()
    stopper = _EventStopper(_stop)

    def _handle_stop(signum, frame):
        _stop.set()

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    try:
        while not _stop.is_set():
            db.conn.rollback()
            action = _decide_action(db)

            if action == "enrich":
                drain_unenriched(api, config.database_url, config, stopper, batch_size=200)
            elif action == "fetch_timelines":
                from lol_genius.crawler.fetch_timelines import fetch_match_timelines

                fetch_match_timelines(api, db, limit=50)
            else:
                current = db.get_match_count()
                batch_config = replace(config, match_count=current + 200, continuous=False)
                crawl_matches(api, config.database_url, batch_config, ddragon)

            if not _stop.is_set():
                time.sleep(2)
    finally:
        api.close()
        db.close()


@cli.command("build-features")
@click.option("--patch", default=None, help="Filter to specific patch")
@click.pass_context
@cli_error_handler
def build_features(ctx, patch):
    """Build feature matrix from enriched data."""
    config = _get_config(ctx)

    from lol_genius.api.ddragon import DataDragon
    from lol_genius.db.queries import MatchDB
    from lol_genius.features.build import build_feature_matrix

    db = MatchDB(config.database_url)
    ddragon = DataDragon(config.ddragon_cache)

    try:
        X, y, patches, timestamps, match_ids = build_feature_matrix(
            db, ddragon, patch or config.patch_filter
        )
        if X.empty:
            click.echo("No enriched matches found. Run 'crawl' first.")
            return

        from pathlib import Path

        out_dir = Path(config.model_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        X.to_parquet(out_dir / "features.parquet")
        y.to_frame().to_parquet(out_dir / "targets.parquet")
        patches.to_frame().to_parquet(out_dir / "patches.parquet")
        timestamps.to_frame().to_parquet(out_dir / "timestamps.parquet")
        match_ids.to_frame().to_parquet(out_dir / "match_ids.parquet")
        click.echo(f"Feature matrix: {X.shape[0]} matches, {X.shape[1]} features")
        click.echo(f"Saved to {out_dir}")
    finally:
        db.close()


@cli.command("fetch-timelines")
@click.pass_context
@cli_error_handler
def fetch_timelines(ctx):
    """Fetch match timelines for enriched matches."""
    config = _get_config(ctx)

    from lol_genius.crawler.fetch_timelines import fetch_match_timelines
    from lol_genius.db.queries import MatchDB

    api = _make_api(config)
    db = MatchDB(config.database_url)

    try:
        fetch_match_timelines(api, db)
    finally:
        api.close()
        db.close()


@cli.command("backfill-timelines")
@click.pass_context
@cli_error_handler
def backfill_timelines(ctx):
    """Re-extract timeline snapshots from stored raw JSON (no API calls)."""
    config = _get_config(ctx)

    from lol_genius.crawler.fetch_timelines import backfill_timelines_from_raw
    from lol_genius.db.queries import MatchDB

    db = MatchDB(config.database_url)
    try:
        backfill_timelines_from_raw(db)
    finally:
        db.close()


@cli.command()
@click.option("--tune/--no-tune", default=False, help="Run hyperparameter tuning")
@click.option("--live/--no-live", default=False, help="Train on timeline features (live model)")
@click.option("--notes", default=None, help="Notes for this training run")
@click.pass_context
@cli_error_handler
def train(ctx, tune, live, notes):
    """Train XGBoost model."""
    import pandas as pd

    config = _get_config(ctx)
    from pathlib import Path

    model_type = "live" if live else "pregame"

    if live:
        from lol_genius.api.ddragon import DataDragon
        from lol_genius.db.queries import MatchDB
        from lol_genius.features.timeline import build_timeline_feature_matrix

        db = MatchDB(config.database_url)
        try:
            X, y, match_ids, game_creations = build_timeline_feature_matrix(
                db, model_type="live", ddragon=DataDragon(config.ddragon_cache)
            )
        finally:
            db.close()

        if X.empty:
            click.echo("No timeline data found. Run 'fetch-timelines' first.")
            return

        patches = None
        timestamps = None
    else:
        model_dir = Path(config.model_dir)
        feat_path = model_dir / "features.parquet"
        target_path = model_dir / "targets.parquet"
        patches_path = model_dir / "patches.parquet"
        timestamps_path = model_dir / "timestamps.parquet"
        match_ids_path = model_dir / "match_ids.parquet"

        if not feat_path.exists():
            click.echo("No feature matrix found. Run 'build-features' first.")
            return

        X = pd.read_parquet(feat_path)
        y = pd.read_parquet(target_path).squeeze()
        patches = pd.read_parquet(patches_path).squeeze() if patches_path.exists() else None
        timestamps = (
            pd.read_parquet(timestamps_path).squeeze() if timestamps_path.exists() else None
        )
        match_ids = pd.read_parquet(match_ids_path).squeeze() if match_ids_path.exists() else None
        game_creations = None

    click.echo(f"Training {model_type} model on {len(X)} samples with {X.shape[1]} features")
    click.echo(f"Target distribution: {y.mean():.2%} blue wins")

    from lol_genius.model.train import train_model, tune_hyperparameters

    if tune:
        click.echo("Running hyperparameter tuning...")
        best_params = tune_hyperparameters(X, y)
        click.echo(f"Best params: {best_params}")

    train_kwargs = dict(
        patches=patches,
        timestamps=timestamps,
        database_url=config.database_url,
        model_type=model_type,
    )
    if live:
        train_kwargs["match_ids"] = match_ids
        train_kwargs["game_creations"] = game_creations

    model, run_id = train_model(X, y, config.model_dir, **train_kwargs)

    _run_evaluation(config, model_type, model=model, run_id=run_id)

    if not live and match_ids is not None:
        import xgboost as xgb

        from lol_genius.db.queries import MatchDB
        from lol_genius.model.train import load_model as _load_model

        try:
            m, feat_names = _load_model(config.model_dir, "pregame")
            feat_df = X[[c for c in feat_names if c in X.columns]]
            dmat = xgb.DMatrix(feat_df, feature_names=feat_names)
            probs = m.predict(dmat)
            pairs = list(zip(match_ids.tolist(), probs.tolist()))
            db2 = MatchDB(config.database_url)
            try:
                db2.bulk_update_pregame_probs(pairs)
                click.echo(f"Stored pregame probs for {len(pairs)} matches")
            finally:
                db2.close()
        except Exception as e:
            log.warning("Could not store pregame probs: %s", e)

    if notes:
        from lol_genius.db.queries import MatchDB

        db = MatchDB(config.database_url)
        try:
            db.update_model_run(run_id, {"notes": notes})
        finally:
            db.close()

    click.echo(f"Training complete. Run ID: {run_id}")


def _run_evaluation(config, model_type: str, *, model=None, run_id: str | None = None):
    from pathlib import Path

    import pandas as pd

    from lol_genius.model.evaluate import evaluate_model

    type_dir = Path(config.model_dir) / model_type

    if model is None:
        from lol_genius.model.train import load_model

        model, _ = load_model(config.model_dir, model_type)

    if run_id is None:
        run_id_path = type_dir / "run_id.txt"
        run_id = run_id_path.read_text().strip() if run_id_path.exists() else None

    X_test = pd.read_parquet(type_dir / "X_test.parquet")
    y_test = pd.read_parquet(type_dir / "y_test.parquet").squeeze()

    evaluate_model(
        model,
        X_test,
        y_test,
        str(type_dir),
        database_url=config.database_url,
        run_id=run_id,
    )


@cli.command()
@click.option("--live/--no-live", default=False, help="Evaluate live model instead of pregame")
@click.pass_context
@cli_error_handler
def evaluate(ctx, live):
    """Evaluate trained model and generate reports."""
    config = _get_config(ctx)
    _run_evaluation(config, "live" if live else "pregame")


@cli.command()
@click.pass_context
@cli_error_handler
def explain(ctx):
    """Generate SHAP analysis and plots."""
    import pandas as pd

    config = _get_config(ctx)
    from pathlib import Path

    model_dir = Path(config.model_dir)

    from lol_genius.model.explain import explain_model
    from lol_genius.model.train import load_model

    model, feature_names = load_model(config.model_dir)
    X = pd.read_parquet(model_dir / "features.parquet")
    X = X[[c for c in feature_names if c in X.columns]]

    run_id_path = model_dir / "run_id.txt"
    run_id = run_id_path.read_text().strip() if run_id_path.exists() else None

    explain_model(model, X, config.model_dir, database_url=config.database_url, run_id=run_id)
    click.echo(f"SHAP plots saved to {model_dir}")


@cli.command()
@click.argument("match_id")
@click.pass_context
@cli_error_handler
def predict(ctx, match_id):
    """Predict outcome for a specific match and show SHAP explanation."""
    config = _get_config(ctx)

    import pandas as pd

    from lol_genius.api.ddragon import DataDragon
    from lol_genius.db.queries import MatchDB
    from lol_genius.features.build import _build_match_features
    from lol_genius.model.explain import explain_single_match
    from lol_genius.model.train import load_model

    model, feature_names = load_model(config.model_dir)
    db = MatchDB(config.database_url)
    ddragon = DataDragon(config.ddragon_cache)

    try:
        match = db.get_match(match_id)
        if not match:
            click.echo(f"Match {match_id} not found in database.")
            return

        participants = db.get_participants_for_match(match_id)
        blue = [p for p in participants if p["team_id"] == 100]
        red = [p for p in participants if p["team_id"] == 200]

        global_champ_wr = db.get_champion_patch_winrates(match.get("patch"))
        features = _build_match_features(
            db,
            ddragon,
            blue,
            red,
            patch_str=match.get("patch", ""),
            match_id=match_id,
            game_creation=match.get("game_creation"),
            global_champ_wr=global_champ_wr,
        )
        if not features:
            click.echo("Could not build features for this match.")
            return

        X = pd.DataFrame([features])
        for col in feature_names:
            if col not in X.columns:
                X[col] = 0.0
        X = X[feature_names]

        explain_single_match(model, X, config.model_dir)
        actual = "Blue" if match["blue_win"] else "Red"
        click.echo(f"\nActual winner: {actual}")
    finally:
        db.close()


@cli.command()
@click.option("--limit", default=10, help="Number of runs to show")
@click.option("--detail", default=None, help="Show full detail for a run ID")
@click.option("--note", nargs=2, default=None, help="Set notes: RUN_ID 'note text'")
@click.pass_context
@cli_error_handler
def runs(ctx, limit, detail, note):
    """List and compare model training runs."""
    import json

    config = _get_config(ctx)
    from lol_genius.db.queries import MatchDB

    db = MatchDB(config.database_url)
    try:
        if note:
            run_id, note_text = note
            db.update_model_run(run_id, {"notes": note_text})
            click.echo(f"Updated notes for {run_id}")
            return

        if detail:
            run = db.get_model_run(detail)
            if not run:
                click.echo(f"Run {detail} not found.")
                return
            click.echo(f"\n{'=' * 60}")
            click.echo(f"  Run: {run['run_id']}")
            click.echo(f"{'=' * 60}")
            click.echo(f"  Created:        {run['created_at']}")
            train, test = run["train_count"], run["test_count"]
            click.echo(
                f"  Matches:        {run['total_matches']:,} (train={train:,}, test={test:,})"
            )
            click.echo(f"  Features:       {run['feature_count']}")
            click.echo(f"  Patches:        {run['patch_min']} - {run['patch_max']}")
            click.echo(f"  Target mean:    {run['target_mean']:.4f}")
            click.echo(f"  Training time:  {run['training_seconds']:.1f}s")
            click.echo(f"  Best iteration: {run['best_iteration']}")
            params = json.loads(run["hyperparameters"])
            click.echo("\n  Hyperparameters:")
            for k, v in params.items():
                click.echo(f"    {k:24s} {v}")
            if run.get("accuracy") is not None:
                click.echo("\n  Metrics:")
                click.echo(f"    Accuracy:  {run['accuracy']:.4f}")
                click.echo(f"    AUC-ROC:   {run['auc_roc']:.4f}")
                click.echo(f"    Log Loss:  {run['log_loss']:.4f}")
                click.echo(f"    CM: TN={run['tn']} FP={run['fp']} FN={run['fn']} TP={run['tp']}")
            if run.get("top_features"):
                feats = json.loads(run["top_features"])
                click.echo("\n  Top SHAP Features:")
                for f in feats[:10]:
                    click.echo(f"    {f['name']:40s} {f['importance']:.6f}")
            if run.get("notes"):
                click.echo(f"\n  Notes: {run['notes']}")
            click.echo()
            return

        all_runs = db.get_model_runs(limit)
        if not all_runs:
            click.echo("No training runs recorded yet.")
            return

        hdr = (
            f"  {'Run ID':<18s} {'Matches':>8s} {'Feats':>6s}"
            f" {'Acc':>7s} {'AUC':>7s} {'LogL':>7s}"
            f" {'Iter':>5s} {'Time':>7s}  Notes"
        )
        sep = (
            f"  {'-' * 18} {'-' * 8} {'-' * 6}"
            f" {'-' * 7} {'-' * 7} {'-' * 7}"
            f" {'-' * 5} {'-' * 7}  {'-' * 20}"
        )
        click.echo(f"\n{'=' * 100}")
        click.echo(hdr)
        click.echo(sep)
        for r in all_runs:
            acc = f"{r['accuracy']:.4f}" if r.get("accuracy") is not None else "   -   "
            auc = f"{r['auc_roc']:.4f}" if r.get("auc_roc") is not None else "   -   "
            ll = f"{r['log_loss']:.4f}" if r.get("log_loss") is not None else "   -   "
            it = str(r["best_iteration"]) if r.get("best_iteration") is not None else "  -  "
            tm = (
                f"{r['training_seconds']:.0f}s"
                if r.get("training_seconds") is not None
                else "   -   "
            )
            nt = (r.get("notes") or "")[:20]
            rid = r["run_id"]
            mtch = r["total_matches"]
            fc = r["feature_count"]
            click.echo(
                f"  {rid:<18s} {mtch:>8,} {fc:>6}"
                f" {acc:>7s} {auc:>7s} {ll:>7s}"
                f" {it:>5s} {tm:>7s}  {nt}"
            )
        click.echo(f"{'=' * 100}")
        click.echo(f"  {len(all_runs)} runs shown. Use --detail RUN_ID for full info.\n")
    finally:
        db.close()


@cli.command()
@click.pass_context
@cli_error_handler
def status(ctx):
    """Show crawler progress: matches collected, queue size, enrichment status."""
    config = _get_config(ctx)

    from lol_genius.db.queries import MatchDB

    db = MatchDB(config.database_url)

    try:
        match_count = db.get_match_count()
        queue_stats = db.get_queue_stats()
        enrichment = db.get_enrichment_stats()

        click.echo(f"\n{'=' * 50}")
        click.echo("  lol-genius Status")
        click.echo(f"{'=' * 50}")
        click.echo(f"  Matches collected:  {match_count:,}")
        click.echo(f"  Target:             {config.match_count:,}")
        click.echo(f"  Progress:           {match_count / max(config.match_count, 1):.1%}")

        click.echo("\n  Crawl Queue:")
        for status_name, count in sorted(queue_stats.items()):
            click.echo(f"    {status_name:12s} {count:,}")

        click.echo("\n  Enrichment:")
        click.echo(f"    Enriched:  {enrichment['enriched']:,} / {enrichment['total']:,}")
        if enrichment["total"] > 0:
            click.echo(f"    Progress:  {enrichment['enriched'] / enrichment['total']:.1%}")

        tier_stats = db.get_queue_stats_by_tier()
        if tier_stats:
            click.echo("\n  Seed Distribution by Tier:")
            tier_order = [
                "IRON",
                "BRONZE",
                "SILVER",
                "GOLD",
                "PLATINUM",
                "EMERALD",
                "DIAMOND",
                "MASTER",
                "GRANDMASTER",
                "CHALLENGER",
                "UNKNOWN",
            ]
            for tier in tier_order:
                if tier in tier_stats:
                    stats = tier_stats[tier]
                    total = sum(stats.values())
                    done = stats.get("done", 0)
                    click.echo(f"    {tier:14s} {total:>6,} seeded  ({done:,} crawled)")

        rank_dist = db.get_rank_distribution()
        if rank_dist:
            click.echo("\n  Matches by Player Rank (mid laner):")
            for tier, count in rank_dist.items():
                click.echo(f"    {tier:14s} {count:>6,}")

        age_range = db.get_match_age_range()
        if age_range:
            oldest = datetime.fromtimestamp(age_range[0] / 1000, tz=UTC)
            newest = datetime.fromtimestamp(age_range[1] / 1000, tz=UTC)
            span = newest - oldest
            click.echo("\n  Data Freshness:")
            click.echo(f"    Oldest match:  {oldest:%Y-%m-%d %H:%M} UTC")
            click.echo(f"    Newest match:  {newest:%Y-%m-%d %H:%M} UTC")
            click.echo(f"    Time span:     {span.days}d {span.seconds // 3600}h")

        patch_dist = db.get_patch_distribution()
        if patch_dist:
            total_matches = sum(patch_dist.values())
            click.echo("\n  Matches by Patch:")
            for patch, count in patch_dist.items():
                pct = count / total_matches if total_matches else 0
                click.echo(f"    {patch:14s} {count:>6,}  ({pct:>5.1%})")

        click.echo()
    finally:
        db.close()


@cli.command("export-model")
@click.option(
    "--format",
    "fmt",
    default="onnx",
    type=click.Choice(["onnx"]),
    help="Export format",
)
@click.option(
    "--type",
    "model_type",
    default="live",
    type=click.Choice(["pregame", "live"]),
    help="Model type to export",
)
@click.pass_context
@cli_error_handler
def export_model(ctx, fmt, model_type):
    """Export trained model to ONNX format with feature importance."""
    config = _get_config(ctx)

    from lol_genius.model.export import export_onnx

    out_path = export_onnx(config.model_dir, model_type)
    click.echo(f"Exported {model_type} model to {out_path}")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Proxy bind host")
@click.option("--port", default=8080, type=int, help="Proxy bind port")
@click.pass_context
@cli_error_handler
def proxy(ctx, host, port):
    """Start the Riot API proxy server."""
    os.environ.setdefault("PROXY_HOST", host)
    os.environ.setdefault("PROXY_PORT", str(port))
    config = _get_config(ctx)
    os.environ.setdefault("RIOT_API_KEY", config.riot_api_key)
    os.environ.setdefault("LOL_GENIUS_REGION", config.region)
    os.environ.setdefault("LOL_GENIUS_ROUTING", config.routing)
    os.environ.setdefault("LOL_GENIUS_RATE_SCALE", str(config.rate_scale))

    from lol_genius.proxy.run import main

    main()


@cli.command()
@click.option("--host", default="0.0.0.0", help="Dashboard API bind host")
@click.option("--port", default=8081, type=int, help="Dashboard API bind port")
@click.pass_context
@cli_error_handler
def dashboard(ctx, host, port):
    """Start the dashboard API server."""
    config = _get_config(ctx)
    os.environ.setdefault("DASHBOARD_HOST", host)
    os.environ.setdefault("DASHBOARD_PORT", str(port))
    os.environ.setdefault("DATABASE_URL", config.database_url)
    os.environ.setdefault("MODEL_DIR", config.model_dir)
    os.environ.setdefault("DDRAGON_CACHE", config.ddragon_cache)
    if config.proxy_url:
        os.environ.setdefault("PROXY_URL", config.proxy_url)

    from lol_genius.dashboard.run import main

    main()


if __name__ == "__main__":
    cli()
