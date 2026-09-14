-- Changes: add local email identities, sent-message history and draft persistence.
-- Why: support local draft and SMTP email endpoints across API restarts.
-- Apply: sqlite3 data/n3xus-api.db < docs/database/0002-local-email.sql
-- Verify: sqlite3 data/n3xus-api.db '.tables'  # includes email_identities and email_messages

CREATE TABLE IF NOT EXISTS email_identities (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  is_default INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_messages (
  id TEXT PRIMARY KEY,
  identity_id TEXT,
  recipient TEXT NOT NULL,
  subject TEXT NOT NULL,
  text TEXT NOT NULL,
  sent_at TEXT NOT NULL
);
