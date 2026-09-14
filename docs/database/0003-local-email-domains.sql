-- Changes: store locally verified SMTP sending domains and their DNS proof token.
-- Why: support free custom-domain email setup without a hosted provider.
-- Apply: sqlite3 data/n3xus-api.db < docs/database/0003-local-email-domains.sql
-- Verify: sqlite3 data/n3xus-api.db '.tables'  # includes email_domains

CREATE TABLE IF NOT EXISTS email_domains (
  id TEXT PRIMARY KEY,
  domain TEXT UNIQUE NOT NULL,
  token TEXT NOT NULL,
  verified INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
