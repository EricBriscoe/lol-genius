-- migrate:up
ALTER TABLE match_timelines ADD COLUMN IF NOT EXISTS blue_cs         INT NOT NULL DEFAULT 0;
ALTER TABLE match_timelines ADD COLUMN IF NOT EXISTS red_cs          INT NOT NULL DEFAULT 0;
ALTER TABLE match_timelines ADD COLUMN IF NOT EXISTS blue_inhibitors INT NOT NULL DEFAULT 0;
ALTER TABLE match_timelines ADD COLUMN IF NOT EXISTS red_inhibitors  INT NOT NULL DEFAULT 0;
ALTER TABLE match_timelines ADD COLUMN IF NOT EXISTS blue_elder      INT NOT NULL DEFAULT 0;
ALTER TABLE match_timelines ADD COLUMN IF NOT EXISTS red_elder       INT NOT NULL DEFAULT 0;
DELETE FROM match_timelines;

-- migrate:down
ALTER TABLE match_timelines DROP COLUMN IF EXISTS blue_cs;
ALTER TABLE match_timelines DROP COLUMN IF EXISTS red_cs;
ALTER TABLE match_timelines DROP COLUMN IF EXISTS blue_inhibitors;
ALTER TABLE match_timelines DROP COLUMN IF EXISTS red_inhibitors;
ALTER TABLE match_timelines DROP COLUMN IF EXISTS blue_elder;
ALTER TABLE match_timelines DROP COLUMN IF EXISTS red_elder;
