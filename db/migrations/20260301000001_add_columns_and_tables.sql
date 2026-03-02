-- migrate:up
ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS model_type TEXT NOT NULL DEFAULT 'pregame';

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

DROP TABLE IF EXISTS player_recent_stats;

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

DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'match_raw_json' AND column_name = 'raw_json'
        AND data_type <> 'jsonb'
    ) THEN
        ALTER TABLE match_raw_json ALTER COLUMN raw_json TYPE JSONB USING raw_json::jsonb;
    END IF;
END $$;

DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'mastery_raw_json' AND column_name = 'raw_json'
        AND data_type <> 'jsonb'
    ) THEN
        ALTER TABLE mastery_raw_json ALTER COLUMN raw_json TYPE JSONB USING raw_json::jsonb;
    END IF;
END $$;

DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'league_raw_json' AND column_name = 'raw_json'
        AND data_type <> 'jsonb'
    ) THEN
        ALTER TABLE league_raw_json ALTER COLUMN raw_json TYPE JSONB USING raw_json::jsonb;
    END IF;
END $$;

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
ALTER TABLE champion_mastery DROP COLUMN IF EXISTS last_play_time;
ALTER TABLE champion_mastery DROP COLUMN IF EXISTS champion_points_until_next_level;
ALTER TABLE summoner_ranks DROP COLUMN IF EXISTS veteran;
ALTER TABLE summoner_ranks DROP COLUMN IF EXISTS inactive;
ALTER TABLE summoner_ranks DROP COLUMN IF EXISTS fresh_blood;
ALTER TABLE summoner_ranks DROP COLUMN IF EXISTS hot_streak;
ALTER TABLE participants DROP COLUMN IF EXISTS summoner1_id;
ALTER TABLE participants DROP COLUMN IF EXISTS summoner2_id;
ALTER TABLE participants DROP COLUMN IF EXISTS summoner_level;
ALTER TABLE participants DROP COLUMN IF EXISTS perks_primary_style;
ALTER TABLE participants DROP COLUMN IF EXISTS perks_sub_style;
ALTER TABLE participants DROP COLUMN IF EXISTS perks_keystone;
ALTER TABLE participants DROP COLUMN IF EXISTS perks_offense;
ALTER TABLE participants DROP COLUMN IF EXISTS perks_flex;
ALTER TABLE participants DROP COLUMN IF EXISTS perks_defense;
ALTER TABLE participants DROP COLUMN IF EXISTS magic_damage_to_champions;
ALTER TABLE participants DROP COLUMN IF EXISTS physical_damage_to_champions;
ALTER TABLE participants DROP COLUMN IF EXISTS true_damage_to_champions;
ALTER TABLE participants DROP COLUMN IF EXISTS total_damage_taken;
ALTER TABLE participants DROP COLUMN IF EXISTS damage_self_mitigated;
ALTER TABLE participants DROP COLUMN IF EXISTS wards_placed;
ALTER TABLE participants DROP COLUMN IF EXISTS wards_killed;
ALTER TABLE participants DROP COLUMN IF EXISTS detector_wards_placed;
ALTER TABLE participants DROP COLUMN IF EXISTS gold_spent;
ALTER TABLE participants DROP COLUMN IF EXISTS time_ccing_others;
ALTER TABLE participants DROP COLUMN IF EXISTS total_heal;
ALTER TABLE participants DROP COLUMN IF EXISTS total_heals_on_teammates;
ALTER TABLE participants DROP COLUMN IF EXISTS double_kills;
ALTER TABLE participants DROP COLUMN IF EXISTS triple_kills;
ALTER TABLE participants DROP COLUMN IF EXISTS quadra_kills;
ALTER TABLE participants DROP COLUMN IF EXISTS penta_kills;
ALTER TABLE participants DROP COLUMN IF EXISTS largest_killing_spree;
ALTER TABLE participants DROP COLUMN IF EXISTS item0;
ALTER TABLE participants DROP COLUMN IF EXISTS item1;
ALTER TABLE participants DROP COLUMN IF EXISTS item2;
ALTER TABLE participants DROP COLUMN IF EXISTS item3;
ALTER TABLE participants DROP COLUMN IF EXISTS item4;
ALTER TABLE participants DROP COLUMN IF EXISTS item5;
ALTER TABLE participants DROP COLUMN IF EXISTS item6;
ALTER TABLE participants DROP COLUMN IF EXISTS neutral_minions_killed;
ALTER TABLE participants DROP COLUMN IF EXISTS total_minions_killed;
ALTER TABLE participants DROP COLUMN IF EXISTS champion_level;
ALTER TABLE matches DROP COLUMN IF EXISTS game_start_timestamp;
ALTER TABLE matches DROP COLUMN IF EXISTS game_end_timestamp;
ALTER TABLE matches DROP COLUMN IF EXISTS platform_id;
DROP INDEX IF EXISTS idx_match_timelines_match_id;
DROP TABLE IF EXISTS match_timelines CASCADE;
ALTER TABLE model_runs DROP COLUMN IF EXISTS model_type;
