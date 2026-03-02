-- migrate:up
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
    model_type        TEXT NOT NULL DEFAULT 'pregame',
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

CREATE TABLE IF NOT EXISTS match_timelines (
    match_id          TEXT NOT NULL REFERENCES matches(match_id),
    snapshot_seconds  INT NOT NULL,
    blue_gold         INT NOT NULL DEFAULT 0,
    red_gold          INT NOT NULL DEFAULT 0,
    blue_kills        INT NOT NULL DEFAULT 0,
    red_kills         INT NOT NULL DEFAULT 0,
    blue_towers       INT NOT NULL DEFAULT 0,
    red_towers        INT NOT NULL DEFAULT 0,
    blue_dragons      INT NOT NULL DEFAULT 0,
    red_dragons       INT NOT NULL DEFAULT 0,
    blue_barons       INT NOT NULL DEFAULT 0,
    red_barons        INT NOT NULL DEFAULT 0,
    blue_heralds      INT NOT NULL DEFAULT 0,
    red_heralds       INT NOT NULL DEFAULT 0,
    first_blood_blue  INT NOT NULL DEFAULT 0,
    first_tower_blue  INT NOT NULL DEFAULT 0,
    first_dragon_blue INT NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, snapshot_seconds)
);
CREATE INDEX IF NOT EXISTS idx_match_timelines_match_id ON match_timelines(match_id);

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

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);
INSERT INTO settings (key, value) VALUES ('crawler_mode', 'crawl') ON CONFLICT DO NOTHING;

-- migrate:down
DROP TABLE IF EXISTS settings CASCADE;
DROP TABLE IF EXISTS match_team_objectives CASCADE;
DROP TABLE IF EXISTS match_bans CASCADE;
DROP TABLE IF EXISTS mastery_raw_json CASCADE;
DROP TABLE IF EXISTS league_raw_json CASCADE;
DROP TABLE IF EXISTS match_raw_json CASCADE;
DROP TABLE IF EXISTS match_timelines CASCADE;
DROP TABLE IF EXISTS model_runs CASCADE;
DROP TABLE IF EXISTS crawl_queue CASCADE;
DROP TABLE IF EXISTS match_enrichment_status CASCADE;
DROP TABLE IF EXISTS champion_mastery CASCADE;
DROP TABLE IF EXISTS summoner_ranks CASCADE;
DROP TABLE IF EXISTS participants CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
