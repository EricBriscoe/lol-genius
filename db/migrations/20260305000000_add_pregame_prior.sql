-- migrate:up
ALTER TABLE matches ADD COLUMN IF NOT EXISTS pregame_blue_win_prob FLOAT;

-- migrate:down
ALTER TABLE matches DROP COLUMN IF EXISTS pregame_blue_win_prob;
