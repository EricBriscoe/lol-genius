# lol-genius

Pre-game League of Legends match outcome predictor. Crawls ranked match data from the Riot Games API, engineers features from player/champion/team/draft dimensions, and trains an XGBoost binary classifier with SHAP interpretability.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy `.env.example` to `.env` and add your [Riot API key](https://developer.riotgames.com/):

```bash
cp .env.example .env
# Edit .env with your RIOT_API_KEY
```

Edit `config.yaml` to configure your target region, elo bracket, and match count.

## Usage

The pipeline runs in stages:

```bash
# 1. Initialize the database
lol-genius init-db

# 2. Download champion static data
lol-genius fetch-ddragon

# 3. Seed the crawl queue with accounts at target elo
lol-genius seed

# 4. Crawl matches (snowball from seeded accounts)
lol-genius crawl
lol-genius crawl --limit 1000  # smaller run for testing

# 5. Enrich participants with rank, mastery, and recent stats
lol-genius enrich

# 6. Build the feature matrix
lol-genius build-features

# 7. Train the model
lol-genius train
lol-genius train --tune  # with hyperparameter search

# 8. Evaluate
lol-genius evaluate

# 9. Generate SHAP explanations
lol-genius explain

# 10. Predict a specific match
lol-genius predict NA1_1234567890
```

Check progress at any time:

```bash
lol-genius status
```

## Rate Limits

With a personal Riot API key (20 req/s, 100 req/2min), expect:
- **Seeding**: ~5 minutes
- **Crawling 50k matches**: ~12 hours
- **Enrichment**: 1-3 days (heavily cached across overlapping players)

The crawler is fully resumable: you can stop and restart at any time.

## Feature Taxonomy

~160 features across four dimensions, all pre-game knowable (no target leakage):

- **Player-level** (×10): rank, winrate, champion proficiency, mastery, KDA, CS/min, vision, damage share, autofill flag
- **Champion-level** (×10): base stats, scaling, damage type, role tags
- **Team-level** (×2): average rank, rank spread, damage mix, composition profile
- **Draft-level**: per-lane matchup differentials, blue/red side
