# Local email delivery observability

n3xusAPI remains draft-first: without `N3XUS_API_SMTP_URL`, `/v1/email/send` stores a draft instead of attempting delivery.

When SMTP is configured and sending succeeds, the API records a `delivery` object alongside the saved message:

- `state`: `accepted` when the relay accepts handoff, or `rejected` when SMTP refuses recipients
- `smtpScheme`, `smtpHost`, `smtpPort`: endpoint metadata without credentials
- `observedAt`: UTC timestamp of the local send attempt
- `limitation`: explicit statement that bounces, opens, and replies are not tracked

`GET /v1/email/messages` returns the same `delivery` block for historical sends. This is not a hosted inbox product; it only surfaces what the local client observed during SMTP submission.
