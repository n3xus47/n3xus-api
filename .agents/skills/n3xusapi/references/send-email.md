# Local email workflow

Use email routes only when the user explicitly asks for contact discovery, drafting, or sending.

## Draft first

`POST /v1/email/send` with `to`, `subject`, and `text` creates a local draft unless `send: true` is supplied:

```json
{
  "to": "person@example.com",
  "subject": "Question",
  "text": "Hello ..."
}
```

Sending requires a configured local SMTP URL and a default identity. Do not send automatically based on a research result. Present the recipient, subject, and body to the user before an irreversible send when the user has not already supplied that exact message and asked to send it.

Use `/v1/email/drafts`, `/v1/email/drafts/{draftId}/send`, `/v1/email/identities`, and `/v1/email/messages` to manage local state. Domain verification uses `/v1/email/domains` and DNS token checks; it does not prove mailbox deliverability.

## Contact data

`POST /v1/email/find` returns only explicitly published addresses found on the company's public pages. It does not guess address patterns or use a people-data broker. `POST /v1/email/verify` performs syntax validation only and returns `checkKind: "syntax_only"`. `/v1/email/enrich` is intentionally unavailable for person-data enrichment.
