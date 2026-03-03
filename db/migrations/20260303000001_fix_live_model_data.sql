-- migrate:up

-- Remove end-of-game snapshots created by build_timelines_from_db.
-- Valid snapshots are only at 5-minute marks (300, 600, ..., 3000).
DELETE FROM match_timelines
WHERE snapshot_seconds NOT IN (300, 600, 900, 1200, 1500, 1800, 2100, 2400, 2700, 3000);

-- Change time_window_metrics from TEXT to JSONB for proper JSON handling.
ALTER TABLE model_runs
  ALTER COLUMN time_window_metrics TYPE JSONB USING time_window_metrics::jsonb;

-- migrate:down
ALTER TABLE model_runs
  ALTER COLUMN time_window_metrics TYPE TEXT USING time_window_metrics::text;
