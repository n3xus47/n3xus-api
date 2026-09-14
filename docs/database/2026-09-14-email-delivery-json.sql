-- Add persisted SMTP delivery observability to sent messages.
-- Why: record relay handoff state without pretending to track inbox lifecycle events.
-- Apply: run against the local n3xus-api SQLite database after deploying the matching app version.
-- Verify: send with configured SMTP, then GET /v1/email/messages and confirm a delivery block with smtpHost and limitation.

ALTER TABLE email_messages ADD COLUMN delivery_json TEXT;
