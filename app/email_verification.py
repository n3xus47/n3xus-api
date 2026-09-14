"""Policy-governed email checks: syntax locally; deliverability only when approved."""

import re
from dataclasses import dataclass
from typing import Literal

Approval = Literal["approved", "candidate"]
CheckKind = Literal["syntax_only", "syntax_and_deliverability"]

POLICY_DOC = "docs/email-verification-policy.md"
SYNTAX_ADAPTER_ID = "rfc5322-pragmatic-syntax"
DELIVERABILITY_UNAVAILABLE = "no_approved_deliverability_source"

SYNTAX_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class DeliverabilityAdapterDefinition:
    id: str
    approval: Approval
    license_summary: str
    privacy_summary: str
    env_vars: tuple[str, ...]


DELIVERABILITY_ADAPTERS: tuple[DeliverabilityAdapterDefinition, ...] = (
    DeliverabilityAdapterDefinition(
        id="smtp-rcpt-probe",
        approval="candidate",
        license_summary="Operator responsibility; anti-spam and CFAA-style laws vary by jurisdiction.",
        privacy_summary="Contacts recipient MX servers; may log the probe address.",
        env_vars=("N3XUS_API_EMAIL_SMTP_PROBE_ENABLED",),
    ),
    DeliverabilityAdapterDefinition(
        id="commercial-verify-api",
        approval="candidate",
        license_summary="Vendor API agreement (e.g. Hunter, ZeroBounce).",
        privacy_summary="Full email address sent to vendor.",
        env_vars=("N3XUS_API_EMAIL_VERIFY_API_URL", "N3XUS_API_EMAIL_VERIFY_API_KEY"),
    ),
)

APPROVED_DELIVERABILITY_IDS = frozenset(item.id for item in DELIVERABILITY_ADAPTERS if item.approval == "approved")


def list_deliverability_adapters() -> list[dict]:
    return [
        {
            "id": item.id,
            "approval": item.approval,
            "envVars": list(item.env_vars),
            "licenseSummary": item.license_summary,
            "privacySummary": item.privacy_summary,
        }
        for item in DELIVERABILITY_ADAPTERS
    ]


def verify_email_address(email: str) -> dict:
    syntax_valid = bool(SYNTAX_PATTERN.fullmatch(email))
    check_kind: CheckKind = "syntax_only"
    mailbox_block = {
        "performed": False,
        "verdict": None,
        "adapterId": None,
        "unavailableReason": DELIVERABILITY_UNAVAILABLE,
    }
    if APPROVED_DELIVERABILITY_IDS:
        raise RuntimeError("Deliverability adapter approved but not implemented.")
    return {
        "email": email,
        "checkKind": check_kind,
        "syntax": {"valid": syntax_valid, "adapterId": SYNTAX_ADAPTER_ID},
        "mailboxVerification": mailbox_block,
        "policy": {
            "documentation": POLICY_DOC,
            "consentRequiredForDeliverability": True,
            "deliverabilityApproved": False,
        },
    }
