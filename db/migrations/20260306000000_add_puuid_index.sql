-- migrate:up
CREATE INDEX IF NOT EXISTS idx_participants_puuid ON participants(puuid);
CREATE INDEX IF NOT EXISTS idx_crawl_queue_status_added ON crawl_queue(status, added_at);

-- migrate:down
DROP INDEX IF EXISTS idx_participants_puuid;
DROP INDEX IF EXISTS idx_crawl_queue_status_added;
