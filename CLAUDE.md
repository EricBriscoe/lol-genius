# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

lol-genius is a League of Legends pre-game match outcome predictor. It crawls ranked match data from the Riot Games API, engineers features from player/champion/team/draft dimensions, and trains an XGBoost binary classifier predicting blue team win probability. SHAP provides model interpretability.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e .
brew install dbmate          # Migration tool (local dev)

# CLI (all commands)
lol-genius init-db          # Run database migrations (dbmate up)
lol-genius init-db --wait   # Wait for DB, then migrate (Docker)
lol-genius fetch-ddragon    # Download champion static data
lol-genius seed             # Seed crawl queue from League-V4 entries
lol-genius crawl            # Snowball match crawler
lol-genius enrich           # Enrich participants with rank/mastery/history
lol-genius build-features   # Build feature matrix from enriched data
lol-genius train            # Train XGBoost model (--tune for hyperparam search)
lol-genius evaluate         # Evaluate model metrics
lol-genius explain          # Generate SHAP analysis
lol-genius predict MATCH_ID # Predict + explain a single match
lol-genius status           # Show crawler progress

# Tests
pytest tests/
pytest tests/test_features.py -k "test_rank_to_numeric"

# Migrations
dbmate new add_foo_column   # Create new migration file in db/migrations/

# Config
# Set RIOT_API_KEY in .env (see .env.example)
# Adjust region, tier, match_count in config.yaml
```

## Architecture

### Pipeline Flow
```
seed → crawl → enrich → build-features → train → evaluate/explain
```

1. **Seed** (`crawler/seed.py`): Populates crawl_queue from League-V4 entries at target elo
2. **Crawl** (`crawler/snowball.py`): Snowball match collection: each match yields 9 new PUUIDs to crawl. Resumable via `crawl_queue` table.
3. **Enrich** (`crawler/enrich.py`): Second pass fetching rank, mastery, recent stats per participant. Heavily cached to avoid redundant API calls.
4. **Features** (`features/build.py`): Orchestrates player/champion/team/draft feature extraction into flat DataFrame. Feature naming: `{side}_{position}_{feature}`.
5. **Model** (`model/train.py`): XGBoost binary:logistic with early stopping. Target: `blue_win`.

### Key Modules
- `api/client.py`: Rate-limited HTTP client. Sliding-window rate limiter reads `X-App-Rate-Limit` response headers. Handles 429 (Retry-After) and 5xx (exponential backoff).
- `api/riot_api.py`: Thin wrappers for Match-V5, League-V4, Summoner-V4, Champion Mastery endpoints. Regional vs routing URLs.
- `api/ddragon.py`: Data Dragon static champion data with disk caching.
- `db/queries.py`: `MatchDB` class with all DB operations. Crawl queue management for resumable crawling.
- `config.py`: Loads `config.yaml` + env vars into frozen dataclass.

### Data Storage
- PostgreSQL managed by dbmate. Migrations in `db/migrations/`. Schema tracked in `schema_migrations` table.
- Data Dragon cache at `data/ddragon/`
- Model artifacts at `data/models/`

## Critical Constraints
- **No target leakage**: Features must be pre-game knowable only. Never use in-game stats (gold, kills, first blood) as model inputs. Post-game stats stored in `participants` are for validation only.
- **Patch segmentation**: Champion balance shifts between patches. Train on current patch ±1.
- **Rate limits**: Personal API key = 20 req/1s, 100 req/2min. The client.py rate limiter handles this; never bypass it.
- **Riot API routing**: Summoner/League/Mastery use regional URLs (na1, euw1). Match-V5 uses routing URLs (americas, europe, asia).

## Feature Taxonomy (~160 features)
- **Player-level** (×10): rank_numeric, winrate, champ-specific WR, mastery, KDA, CS/min, vision, damage share, autofill flag
- **Champion-level** (×10): base stats, scaling, damage type, tags one-hot, range
- **Team-level** (×2): avg rank, rank spread, AD/AP ratio, melee count, comp archetype
- **Draft-level**: lane matchup differentials (rank/mastery/WR diff per position), blue_side
