import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings


def _connection() -> sqlite3.Connection:
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(Path(settings.data_dir) / "n3xus-api.db")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS requests (
          id TEXT PRIMARY KEY, route TEXT NOT NULL, idempotency_key TEXT UNIQUE,
          response_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memory_files (
          path TEXT PRIMARY KEY, content TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS email_drafts (
          id TEXT PRIMARY KEY, recipient TEXT NOT NULL, subject TEXT NOT NULL,
          text TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS email_identities (
          id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
          is_default INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS email_messages (
          id TEXT PRIMARY KEY, identity_id TEXT, recipient TEXT NOT NULL, subject TEXT NOT NULL,
          text TEXT NOT NULL, sent_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS email_domains (
          id TEXT PRIMARY KEY, domain TEXT UNIQUE NOT NULL, token TEXT NOT NULL,
          verified INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        );
        """
    )
    return connection


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def save_request(request_id: str, route: str, idempotency_key: str | None, response: dict) -> None:
    with _connection() as connection:
        connection.execute(
            "INSERT INTO requests VALUES (?, ?, ?, ?, ?)",
            (request_id, route, idempotency_key, json.dumps(response), utcnow()),
        )


def find_idempotent(key: str) -> dict | None:
    with _connection() as connection:
        row = connection.execute("SELECT response_json FROM requests WHERE idempotency_key = ?", (key,)).fetchone()
    return json.loads(row["response_json"]) if row else None


def get_request(request_id: str) -> dict | None:
    with _connection() as connection:
        row = connection.execute("SELECT response_json FROM requests WHERE id = ?", (request_id,)).fetchone()
    return json.loads(row["response_json"]) if row else None


def list_requests(limit: int) -> list[dict]:
    with _connection() as connection:
        rows = connection.execute("SELECT response_json FROM requests ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [json.loads(row["response_json"]) for row in rows]


def list_memory() -> list[dict]:
    with _connection() as connection:
        rows = connection.execute("SELECT path, content, version, updated_at FROM memory_files ORDER BY path").fetchall()
    return [{"path": row["path"], "sizeBytes": len(row["content"].encode()), "version": row["version"], "updatedAt": row["updated_at"]} for row in rows]


def get_memory(path: str) -> dict | None:
    with _connection() as connection:
        row = connection.execute("SELECT content, version, updated_at FROM memory_files WHERE path = ?", (path,)).fetchone()
    return dict(row) if row else None


def write_memory(path: str, content: str, expected_version: int | None) -> tuple[dict | None, bool]:
    current = get_memory(path)
    if current and expected_version != current["version"]:
        return None, False
    version = (current["version"] if current else 0) + 1
    updated_at = utcnow()
    with _connection() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO memory_files VALUES (?, ?, ?, ?)", (path, content, version, updated_at)
        )
    return {"path": path, "content": content, "version": version, "updated_at": updated_at}, True


def delete_memory(path: str) -> bool:
    with _connection() as connection:
        return connection.execute("DELETE FROM memory_files WHERE path = ?", (path,)).rowcount > 0


def list_email_identities() -> list[dict]:
    with _connection() as connection:
        rows = connection.execute("SELECT id, email, display_name, is_default, created_at FROM email_identities ORDER BY is_default DESC, created_at").fetchall()
    return [{"emailIdentityId": row["id"], "email": row["email"], "displayName": row["display_name"], "default": bool(row["is_default"]), "createdAt": row["created_at"]} for row in rows]


def update_email_identity(identity_id: str, display_name: str) -> dict | None:
    with _connection() as connection:
        if connection.execute("UPDATE email_identities SET display_name = ? WHERE id = ?", (display_name, identity_id)).rowcount == 0:
            return None
    return next(item for item in list_email_identities() if item["emailIdentityId"] == identity_id)


def create_email_identity(email: str, display_name: str) -> dict:
    from uuid import uuid4
    identity_id = f"local_email_{uuid4().hex}"
    with _connection() as connection:
        connection.execute("UPDATE email_identities SET is_default = 0")
        connection.execute("INSERT INTO email_identities VALUES (?, ?, ?, 1, ?)", (identity_id, email, display_name, utcnow()))
    return next(item for item in list_email_identities() if item["emailIdentityId"] == identity_id)


def save_email_draft(recipient: str, subject: str, text: str) -> dict:
    from uuid import uuid4
    draft_id = f"local_draft_{uuid4().hex}"
    created_at = utcnow()
    with _connection() as connection:
        connection.execute("INSERT INTO email_drafts VALUES (?, ?, ?, ?, ?)", (draft_id, recipient, subject, text, created_at))
    return {"draftId": draft_id, "to": recipient, "subject": subject, "text": text, "createdAt": created_at}


def list_email_drafts() -> list[dict]:
    with _connection() as connection:
        rows = connection.execute("SELECT id, recipient, subject, text, created_at FROM email_drafts ORDER BY created_at DESC").fetchall()
    return [{"draftId": row["id"], "to": row["recipient"], "subject": row["subject"], "text": row["text"], "createdAt": row["created_at"]} for row in rows]


def get_email_draft(draft_id: str) -> dict | None:
    return next((item for item in list_email_drafts() if item["draftId"] == draft_id), None)


def remove_email_draft(draft_id: str) -> None:
    with _connection() as connection:
        connection.execute("DELETE FROM email_drafts WHERE id = ?", (draft_id,))


def save_email_message(recipient: str, subject: str, text: str, identity_id: str | None) -> dict:
    from uuid import uuid4
    message_id = f"local_message_{uuid4().hex}"
    sent_at = utcnow()
    with _connection() as connection:
        connection.execute("INSERT INTO email_messages VALUES (?, ?, ?, ?, ?, ?)", (message_id, identity_id, recipient, subject, text, sent_at))
    return {"messageId": message_id, "to": recipient, "subject": subject, "text": text, "sentAt": sent_at}


def list_email_domains() -> list[dict]:
    with _connection() as connection:
        rows = connection.execute("SELECT id, domain, token, verified, created_at FROM email_domains ORDER BY created_at DESC").fetchall()
    return [{"domainId": row["id"], "domain": row["domain"], "verified": bool(row["verified"]), "dnsRecords": [{"type": "TXT", "name": f"_n3xus-api.{row['domain']}", "value": row["token"]}], "createdAt": row["created_at"]} for row in rows]


def create_email_domain(domain: str, token: str) -> dict:
    from uuid import uuid4
    domain_id = f"local_domain_{uuid4().hex}"
    with _connection() as connection:
        connection.execute("INSERT INTO email_domains VALUES (?, ?, ?, 0, ?)", (domain_id, domain, token, utcnow()))
    return next(item for item in list_email_domains() if item["domainId"] == domain_id)


def get_email_domain(domain_id: str) -> dict | None:
    return next((item for item in list_email_domains() if item["domainId"] == domain_id), None)


def set_email_domain_verified(domain_id: str) -> dict | None:
    with _connection() as connection:
        if connection.execute("UPDATE email_domains SET verified = 1 WHERE id = ?", (domain_id,)).rowcount == 0:
            return None
    return get_email_domain(domain_id)


def delete_email_domain(domain_id: str) -> bool:
    with _connection() as connection:
        return connection.execute("DELETE FROM email_domains WHERE id = ?", (domain_id,)).rowcount > 0


def list_email_messages() -> list[dict]:
    with _connection() as connection:
        rows = connection.execute("SELECT id, recipient, subject, text, sent_at FROM email_messages ORDER BY sent_at DESC").fetchall()
    return [{"messageId": row["id"], "to": row["recipient"], "subject": row["subject"], "text": row["text"], "sentAt": row["sent_at"]} for row in rows]
