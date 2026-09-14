# Email verification policy (issue #17)

n3xusAPI separates **syntax validation** from **mailbox / deliverability verification**. Callers must not treat a syntax-only response as proof that mail can be delivered.

## Consent and lawful use

| Check type | Default | Data leaves host? | Consent model |
| --- | --- | --- | --- |
| Syntax (RFC5322-pragmatic) | Enabled locally | No third-party API; address processed in-process only | Caller supplies the address; no mailbox is contacted |
| SMTP RCPT probe | Not implemented | Would contact recipient MX | Requires explicit operator approval + documented retention |
| Commercial verify APIs (Hunter, ZeroBounce, etc.) | Not implemented | Vendor processes the address | Requires operator API key, vendor ToS review, and registry approval |

Deliverability adapters may be added only when listed as `approved` in `app/email_verification.py` and documented in this file with licence link and env vars.

## Response semantics (`POST /v1/email/verify`)

- `checkKind`: always `syntax_only` until a deliverability adapter is approved and enabled.
- `syntax.valid`: `true` / `false` for local format rules only.
- `mailboxVerification.performed`: `false` when no deliverability source ran.
- `mailboxVerification.unavailableReason`: `no_approved_deliverability_source` when deliverability was not attempted.
- Do **not** map syntax failure to deliverability verdicts such as “undeliverable mailbox”.

## Error envelope (HTTP layer)

| Code | When |
| --- | --- |
| `invalid_request` | Missing or non-string `email` |
| `email_verification_not_configured` | Reserved for future approved adapters that require operator configuration |

Syntax failures remain HTTP 200 with `syntax.valid: false` so idempotent POST semantics stay stable.
