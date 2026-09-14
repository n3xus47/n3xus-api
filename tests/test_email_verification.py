import httpx
import pytest
from uuid import uuid4

from app.email_verification import (
    DELIVERABILITY_UNAVAILABLE,
    POLICY_DOC,
    SYNTAX_ADAPTER_ID,
    verify_email_address,
)
from app.main import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


def test_syntax_invalid_does_not_claim_mailbox_verdict():
    payload = verify_email_address("not-an-email")
    assert payload["checkKind"] == "syntax_only"
    assert payload["syntax"]["valid"] is False
    assert payload["syntax"]["adapterId"] == SYNTAX_ADAPTER_ID
    assert payload["mailboxVerification"]["performed"] is False
    assert payload["mailboxVerification"]["verdict"] is None
    assert payload["mailboxVerification"]["unavailableReason"] == DELIVERABILITY_UNAVAILABLE
    assert "verdict" not in payload
    assert "score" not in payload


def test_syntax_valid_still_skips_deliverability():
    payload = verify_email_address("person@example.com")
    assert payload["syntax"]["valid"] is True
    assert payload["mailboxVerification"]["performed"] is False
    assert payload["policy"]["deliverabilityApproved"] is False
    assert payload["policy"]["documentation"] == POLICY_DOC


async def test_verify_endpoint_returns_syntax_envelope(client):
    response = await client.post(
        "/v1/email/verify",
        headers={"Idempotency-Key": f"verify-{uuid4()}"},
        json={"email": "person@example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["output"]["checkKind"] == "syntax_only"
    assert body["source"]["name"] == SYNTAX_ADAPTER_ID


async def test_capabilities_describe_syntax_only(client):
    response = await client.get("/v1/capabilities", params={"capability": "email.verify"})
    assert response.status_code == 200
    item = response.json()["output"]
    assert item["supportLevel"] == "best_effort"
    assert item["adapter"] == "rfc5322-pragmatic-syntax"
    assert "syntax_only" in item["limitations"][0]
