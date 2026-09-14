"""Local email delivery. SMTP is opt-in; drafts always work without it."""
import asyncio
import smtplib
import secrets

import httpx
from email.message import EmailMessage
from urllib.parse import unquote, urlparse

from app.config import settings
from app.store import save_email_message


class EmailError(Exception):
    pass


def _send(sender: str, recipient: str, subject: str, text: str) -> None:
    if not settings.smtp_url:
        raise EmailError("SMTP is not configured; create a draft or set N3XUS_API_SMTP_URL.")
    parsed = urlparse(settings.smtp_url)
    if parsed.scheme not in {"smtp", "smtps"} or not parsed.hostname:
        raise EmailError("N3XUS_API_SMTP_URL must use smtp:// or smtps://")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text)
    client_type = smtplib.SMTP_SSL if parsed.scheme == "smtps" else smtplib.SMTP
    with client_type(parsed.hostname, parsed.port or (465 if parsed.scheme == "smtps" else 587), timeout=30) as client:
        if parsed.scheme == "smtp":
            client.starttls()
        if parsed.username:
            client.login(unquote(parsed.username), unquote(parsed.password or ""))
        client.send_message(message)


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
    await asyncio.to_thread(_send, identity["email"], recipient, subject, text)
    return save_email_message(recipient, subject, text, identity["emailIdentityId"])
