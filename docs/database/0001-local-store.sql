-- Local SQLite schema for n3xusAPI.
-- Why: persist request idempotency, request results, drafts and local memory across restarts.
-- Apply: sqlite3 data/n3xus-api.db < docs/database/0001-local-store.sql
-- Verify: sqlite3 data/n3xus-api.db '.tables'

CREATE TABLE IF NOT EXISTS requests (
  id TEXT PRIMARY KEY,
  route TEXT NOT NULL,
  idempotency_key TEXT UNIQUE,
  response_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_files (
  path TEXT PRIMARY KEY,
  content TEXT NOT NULL,
  version INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_drafts (
  id TEXT PRIMARY KEY,
  recipient TEXT NOT NULL,
  subject TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);
