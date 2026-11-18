-- Add text_hash to chunks so make seed can skip embedding unchanged chunks.

ALTER TABLE chunks
    ADD COLUMN IF NOT EXISTS text_hash TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS chunks_hash_idx ON chunks (policy_id, version, text_hash);
