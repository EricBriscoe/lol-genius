-- migrate:up
ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS time_window_metrics TEXT;

-- migrate:down
ALTER TABLE model_runs DROP COLUMN IF EXISTS time_window_metrics;
