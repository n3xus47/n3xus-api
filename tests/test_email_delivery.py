from app.email import EmailError, build_delivery_record, smtp_endpoint, DELIVERY_LIMITATION
from app.config import settings
import pytest


def test_build_delivery_record_includes_limitation():
    record = build_delivery_record(
        state="accepted",
        endpoint={"scheme": "smtp", "host": "smtp.example.com", "port": 587},
    )
    assert record["state"] == "accepted"
    assert record["smtpHost"] == "smtp.example.com"
    assert record["limitation"] == DELIVERY_LIMITATION


def test_smtp_endpoint_requires_configuration(monkeypatch):
    monkeypatch.setattr(settings, "smtp_url", None)
    with pytest.raises(EmailError, match="SMTP is not configured"):
        smtp_endpoint()
