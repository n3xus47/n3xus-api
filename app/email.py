"""Local email delivery. SMTP is opt-in; drafts always work without it."""
import asyncio
import smtplib
import secrets
from datetime import UTC, datetime

import httpx
from email.message import EmailMessage
from urllib.parse import unquote, urlparse

from app.config import settings
from app.store import save_email_message

DELIVERY_LIMITATION = (
    "Local SMTP handoff only. Delivery acceptance by your relay is recorded; "
    "inbox placement, bounces, opens, and replies are not tracked."
)


class EmailError(Exception):
    pass


def smtp_endpoint() -> dict:
    if not settings.smtp_url:
        raise EmailError("SMTP is not configured; create a draft or set N3XUS_API_SMTP_URL.")
    parsed = urlparse(settings.smtp_url)
    if parsed.scheme not in {"smtp", "smtps"} or not parsed.hostname:
        raise EmailError("N3XUS_API_SMTP_URL must use smtp:// or smtps://")
    return {"scheme": parsed.scheme, "host": parsed.hostname, "port": parsed.port or (465 if parsed.scheme == "smtps" else 587)}


def build_delivery_record(*, state: str, endpoint: dict, detail: str | None = None) -> dict:
    record = {
        "state": state,
        "smtpScheme": endpoint["scheme"],
        "smtpHost": endpoint["host"],
        "smtpPort": endpoint["port"],
        "observedAt": datetime.now(UTC).isoformat(),
        "limitation": DELIVERY_LIMITATION,
    }
    if detail:
        record["detail"] = detail
    return record


def _send(sender: str, recipient: str, subject: str, text: str) -> dict:
    endpoint = smtp_endpoint()
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text)
    client_type = smtplib.SMTP_SSL if endpoint["scheme"] == "smtps" else smtplib.SMTP
    try:
        with client_type(endpoint["host"], endpoint["port"], timeout=30) as client:
            if endpoint["scheme"] == "smtp":
                client.starttls()
            parsed = urlparse(settings.smtp_url or "")
            if parsed.username:
                client.login(unquote(parsed.username), unquote(parsed.password or ""))
            refused = client.send_message(message)
    except smtplib.SMTPException as error:
        raise EmailError(str(error)) from error
    detail = None
    if refused:
        detail = f"SMTP refused recipients: {refused}"
        return build_delivery_record(state="rejected", endpoint=endpoint, detail=detail)
    return build_delivery_record(state="accepted", endpoint=endpoint)


def domain_token() -> str:
    return f"n3xus-api-verify={secrets.token_urlsafe(24)}"


async def dns_has_token(domain: str, token: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://cloudflare-dns.com/dns-query", params={"name": f"_n3xus-api.{domain}", "type": "TXT"}, headers={"Accept": "application/dns-json"})
            response.raise_for_status()
            answers = response.json().get("Answer", [])
    except (httpx.HTTPError, ValueError) as error:
        raise EmailError("Public DNS verification is unavailable") from error
    return any(token in str(answer.get("data", "")) for answer in answers)


async def send_email(identity: dict, recipient: str, subject: str, text: str) -> dict:
    delivery = await asyncio.to_thread(_send, identity["email"], recipient, subject, text)
    saved = save_email_message(recipient, subject, text, identity["emailIdentityId"], delivery)
    return {**saved, "delivery": delivery}
