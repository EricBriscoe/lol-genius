-- migrate:up
CREATE TABLE IF NOT EXISTS timeline_raw_json (
    match_id    TEXT PRIMARY KEY,
    raw_json    JSONB NOT NULL,
    stored_at   TIMESTAMP NOT NULL DEFAULT current_timestamp
);

ALTER TABLE match_timelines ADD COLUMN IF NOT EXISTS blue_avg_level REAL NOT NULL DEFAULT 1.0;
ALTER TABLE match_timelines ADD COLUMN IF NOT EXISTS red_avg_level REAL NOT NULL DEFAULT 1.0;
ALTER TABLE match_timelines ADD COLUMN IF NOT EXISTS blue_max_level INT NOT NULL DEFAULT 1;
ALTER TABLE match_timelines ADD COLUMN IF NOT EXISTS red_max_level INT NOT NULL DEFAULT 1;
DELETE FROM match_timelines;

-- migrate:down
ALTER TABLE match_timelines DROP COLUMN IF EXISTS blue_avg_level;
ALTER TABLE match_timelines DROP COLUMN IF EXISTS red_avg_level;
ALTER TABLE match_timelines DROP COLUMN IF EXISTS blue_max_level;
ALTER TABLE match_timelines DROP COLUMN IF EXISTS red_max_level;
DROP TABLE IF EXISTS timeline_raw_json;
