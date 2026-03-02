SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS matches (
    match_id        TEXT PRIMARY KEY,
    game_version    TEXT NOT NULL,
    patch           TEXT NOT NULL,
    game_duration   INTEGER NOT NULL,
    queue_id        INTEGER NOT NULL,
    blue_win        INTEGER NOT NULL,
    game_creation   BIGINT NOT NULL,
    crawled_at      TIMESTAMP NOT NULL DEFAULT current_timestamp,
    game_start_timestamp BIGINT,
    game_end_timestamp   BIGINT,
    platform_id     TEXT
);

CREATE TABLE IF NOT EXISTS participants (
    match_id        TEXT NOT NULL REFERENCES matches(match_id),
    puuid           TEXT NOT NULL,
    summoner_id     TEXT,
    team_id         INTEGER NOT NULL,
    champion_id     INTEGER NOT NULL,
    champion_name   TEXT NOT NULL,
    team_position   TEXT NOT NULL,
    win             INTEGER NOT NULL,
    kills           INTEGER,
    deaths          INTEGER,
    assists         INTEGER,
    total_damage    INTEGER,
    cs              INTEGER,
    vision_score    INTEGER,
    gold_earned     INTEGER,
    summoner1_id    INTEGER,
    summoner2_id    INTEGER,
    summoner_level  INTEGER,
    perks_primary_style INTEGER,
    perks_sub_style     INTEGER,
    perks_keystone      INTEGER,
    perks_offense       INTEGER,
    perks_flex          INTEGER,
    perks_defense       INTEGER,
    magic_damage_to_champions   INTEGER,
    physical_damage_to_champions INTEGER,
    true_damage_to_champions    INTEGER,
    total_damage_taken          INTEGER,
    damage_self_mitigated       INTEGER,
    wards_placed        INTEGER,
    wards_killed        INTEGER,
    detector_wards_placed INTEGER,
    gold_spent          INTEGER,
    time_ccing_others   INTEGER,
    total_heal          INTEGER,
    total_heals_on_teammates INTEGER,
    double_kills        INTEGER,
    triple_kills        INTEGER,
    quadra_kills        INTEGER,
    penta_kills         INTEGER,
    largest_killing_spree INTEGER,
    item0 INTEGER,
    item1 INTEGER,
    item2 INTEGER,
    item3 INTEGER,
    item4 INTEGER,
    item5 INTEGER,
    item6 INTEGER,
    neutral_minions_killed INTEGER,
    total_minions_killed   INTEGER,
    champion_level  INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_participants_unique ON participants(match_id, puuid);
CREATE INDEX IF NOT EXISTS idx_participants_puuid ON participants(puuid);
CREATE INDEX IF NOT EXISTS idx_participants_match ON participants(match_id);

CREATE TABLE IF NOT EXISTS summoner_ranks (
    puuid           TEXT NOT NULL,
    summoner_id     TEXT NOT NULL,
    queue_type      TEXT NOT NULL,
    tier            TEXT NOT NULL,
    rank            TEXT NOT NULL,
    league_points   INTEGER NOT NULL,
    wins            INTEGER NOT NULL,
    losses          INTEGER NOT NULL,
    fetched_at      TIMESTAMP NOT NULL DEFAULT current_timestamp,
    veteran         INTEGER,
    inactive        INTEGER,
    fresh_blood     INTEGER,
    hot_streak      INTEGER,
    PRIMARY KEY (puuid, queue_type, fetched_at)
);
CREATE INDEX IF NOT EXISTS idx_ranks_puuid ON summoner_ranks(puuid);

CREATE TABLE IF NOT EXISTS champion_mastery (
    puuid           TEXT NOT NULL,
    champion_id     INTEGER NOT NULL,
    mastery_level   INTEGER NOT NULL,
    mastery_points  INTEGER NOT NULL,
    fetched_at      TIMESTAMP NOT NULL DEFAULT current_timestamp,
    last_play_time  BIGINT,
    champion_points_until_next_level INTEGER,
    PRIMARY KEY (puuid, champion_id)
);

CREATE TABLE IF NOT EXISTS match_enrichment_status (
    match_id        TEXT PRIMARY KEY REFERENCES matches(match_id),
    enriched        INTEGER NOT NULL DEFAULT 0,
    enriched_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS player_recent_stats (
    puuid           TEXT PRIMARY KEY,
    computed_at     TIMESTAMP NOT NULL DEFAULT current_timestamp,
    games_played    INTEGER NOT NULL,
    wins            INTEGER NOT NULL,
    avg_kills       DOUBLE PRECISION,
    avg_deaths      DOUBLE PRECISION,
    avg_assists     DOUBLE PRECISION,
    avg_cs_per_min  DOUBLE PRECISION,
    avg_vision      DOUBLE PRECISION,
    avg_damage_share DOUBLE PRECISION,
    avg_wards_placed DOUBLE PRECISION,
    avg_wards_killed DOUBLE PRECISION,
    avg_damage_taken DOUBLE PRECISION,
    avg_gold_spent   DOUBLE PRECISION,
    avg_cc_score     DOUBLE PRECISION,
    avg_heal_total   DOUBLE PRECISION,
    avg_magic_dmg_share  DOUBLE PRECISION,
    avg_phys_dmg_share   DOUBLE PRECISION,
    avg_multikill_rate   DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS crawl_queue (
    puuid           TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'pending',
    seed_tier       TEXT NOT NULL DEFAULT 'UNKNOWN',
    added_at        TIMESTAMP NOT NULL DEFAULT current_timestamp,
    processed_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_crawl_status ON crawl_queue(status);
CREATE INDEX IF NOT EXISTS idx_crawl_tier ON crawl_queue(seed_tier);

CREATE TABLE IF NOT EXISTS model_runs (
    run_id            TEXT PRIMARY KEY,
    created_at        TIMESTAMP NOT NULL DEFAULT current_timestamp,
    total_matches     INTEGER NOT NULL,
    train_count       INTEGER NOT NULL,
    test_count        INTEGER NOT NULL,
    feature_count     INTEGER NOT NULL,
    patch_min         TEXT,
    patch_max         TEXT,
    target_mean       DOUBLE PRECISION,
    hyperparameters   TEXT NOT NULL,
    best_iteration    INTEGER,
    best_train_score  DOUBLE PRECISION,
    training_seconds  DOUBLE PRECISION,
    accuracy          DOUBLE PRECISION,
    auc_roc           DOUBLE PRECISION,
    log_loss          DOUBLE PRECISION,
    tn                INTEGER,
    fp                INTEGER,
    fn                INTEGER,
    tp                INTEGER,
    top_features      TEXT,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS match_raw_json (
    match_id    TEXT PRIMARY KEY,
    raw_json    JSONB NOT NULL,
    stored_at   TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS league_raw_json (
    puuid       TEXT NOT NULL,
    raw_json    JSONB NOT NULL,
    fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (puuid, fetched_at)
);

CREATE TABLE IF NOT EXISTS mastery_raw_json (
    puuid       TEXT NOT NULL,
    champion_id INTEGER NOT NULL,
    raw_json    JSONB NOT NULL,
    fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (puuid, champion_id)
);

CREATE TABLE IF NOT EXISTS match_bans (
    match_id    TEXT NOT NULL REFERENCES matches(match_id),
    team_id     INTEGER NOT NULL,
    champion_id INTEGER NOT NULL,
    pick_turn   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bans_match ON match_bans(match_id);
CREATE INDEX IF NOT EXISTS idx_bans_champion ON match_bans(champion_id);

CREATE TABLE IF NOT EXISTS match_team_objectives (
    match_id    TEXT NOT NULL REFERENCES matches(match_id),
    team_id     INTEGER NOT NULL,
    objective   TEXT NOT NULL,
    first       INTEGER NOT NULL DEFAULT 0,
    kills       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, team_id, objective)
);
""";

MIGRATION_SQL = """
ALTER TABLE matches ADD COLUMN IF NOT EXISTS game_start_timestamp BIGINT;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS game_end_timestamp BIGINT;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS platform_id TEXT;

ALTER TABLE participants ADD COLUMN IF NOT EXISTS summoner1_id INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS summoner2_id INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS summoner_level INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS perks_primary_style INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS perks_sub_style INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS perks_keystone INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS perks_offense INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS perks_flex INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS perks_defense INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS magic_damage_to_champions INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS physical_damage_to_champions INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS true_damage_to_champions INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS total_damage_taken INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS damage_self_mitigated INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS wards_placed INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS wards_killed INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS detector_wards_placed INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS gold_spent INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS time_ccing_others INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS total_heal INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS total_heals_on_teammates INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS double_kills INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS triple_kills INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS quadra_kills INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS penta_kills INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS largest_killing_spree INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS item0 INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS item1 INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS item2 INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS item3 INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS item4 INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS item5 INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS item6 INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS neutral_minions_killed INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS total_minions_killed INTEGER;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS champion_level INTEGER;

ALTER TABLE summoner_ranks ADD COLUMN IF NOT EXISTS veteran INTEGER;
ALTER TABLE summoner_ranks ADD COLUMN IF NOT EXISTS inactive INTEGER;
ALTER TABLE summoner_ranks ADD COLUMN IF NOT EXISTS fresh_blood INTEGER;
ALTER TABLE summoner_ranks ADD COLUMN IF NOT EXISTS hot_streak INTEGER;

ALTER TABLE champion_mastery ADD COLUMN IF NOT EXISTS last_play_time BIGINT;
ALTER TABLE champion_mastery ADD COLUMN IF NOT EXISTS champion_points_until_next_level INTEGER;

ALTER TABLE player_recent_stats ADD COLUMN IF NOT EXISTS avg_wards_placed DOUBLE PRECISION;
ALTER TABLE player_recent_stats ADD COLUMN IF NOT EXISTS avg_wards_killed DOUBLE PRECISION;
ALTER TABLE player_recent_stats ADD COLUMN IF NOT EXISTS avg_damage_taken DOUBLE PRECISION;
ALTER TABLE player_recent_stats ADD COLUMN IF NOT EXISTS avg_gold_spent DOUBLE PRECISION;
ALTER TABLE player_recent_stats ADD COLUMN IF NOT EXISTS avg_cc_score DOUBLE PRECISION;
ALTER TABLE player_recent_stats ADD COLUMN IF NOT EXISTS avg_heal_total DOUBLE PRECISION;
ALTER TABLE player_recent_stats ADD COLUMN IF NOT EXISTS avg_magic_dmg_share DOUBLE PRECISION;
ALTER TABLE player_recent_stats ADD COLUMN IF NOT EXISTS avg_phys_dmg_share DOUBLE PRECISION;
ALTER TABLE player_recent_stats ADD COLUMN IF NOT EXISTS avg_multikill_rate DOUBLE PRECISION;

CREATE TABLE IF NOT EXISTS match_raw_json (
    match_id    TEXT PRIMARY KEY,
    raw_json    JSONB NOT NULL,
    stored_at   TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS league_raw_json (
    puuid       TEXT NOT NULL,
    raw_json    JSONB NOT NULL,
    fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (puuid, fetched_at)
);

CREATE TABLE IF NOT EXISTS mastery_raw_json (
    puuid       TEXT NOT NULL,
    champion_id INTEGER NOT NULL,
    raw_json    JSONB NOT NULL,
    fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (puuid, champion_id)
);

ALTER TABLE match_raw_json ALTER COLUMN raw_json TYPE JSONB USING raw_json::jsonb;
ALTER TABLE mastery_raw_json ALTER COLUMN raw_json TYPE JSONB USING raw_json::jsonb;
ALTER TABLE league_raw_json ALTER COLUMN raw_json TYPE JSONB USING raw_json::jsonb;

CREATE TABLE IF NOT EXISTS match_bans (
    match_id    TEXT NOT NULL REFERENCES matches(match_id),
    team_id     INTEGER NOT NULL,
    champion_id INTEGER NOT NULL,
    pick_turn   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bans_match ON match_bans(match_id);
CREATE INDEX IF NOT EXISTS idx_bans_champion ON match_bans(champion_id);

CREATE TABLE IF NOT EXISTS match_team_objectives (
    match_id    TEXT NOT NULL REFERENCES matches(match_id),
    team_id     INTEGER NOT NULL,
    objective   TEXT NOT NULL,
    first       INTEGER NOT NULL DEFAULT 0,
    kills       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, team_id, objective)
);
""";
