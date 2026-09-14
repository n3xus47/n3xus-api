# Coding standards

## Scope

- n3xusAPI is local-first, public-web tooling, not a hosted multi-tenant service.
- Preserve SSRF protection and never add credential use, login automation, CAPTCHA bypass, rate-limit evasion, or invented source data.
- Keep source-specific adapters truthful. A generic page fetch is not structured source data.

## Style

- Use Python 3.12, clear type hints and focused modules.
- Prefer the existing FastAPI, Pydantic and async patterns.
- Keep implementation details behind a small module interface when an adapter varies.
- Add comments only for non-obvious safety or design constraints.

## Testing

- Use red-green-refactor for behavior changes.
- Run `npm run typecheck` and `npm run test` before committing.
- Add contract tests for public response changes.
- Provider changes require a reproducible evaluation record; unit tests alone do not establish data quality.

## Git and issues

- Work on exactly one unblocked GitHub issue.
- Do not modify unrelated files or close an issue until tests pass.
- Commit only the issue's change with the required `RALPH:` prefix.
