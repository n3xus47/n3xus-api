# Social source selection (issue #6)

Public probe target: `@nasa` profile pages fetched without credentials (2026-09-14).

| Source | HTTP | Structured profile fields from public HTML | Post grid without login |
| --- | --- | --- | --- |
| Instagram | 200 | username, display name, follower/following/post counts, avatar, profile URL via Open Graph | No |
| Threads | 200 | username, display name, follower/thread counts, bio snippet, avatar via Open Graph | No |
| X | 200 | username, display name, bio via Open Graph; no follower/post counts | No |
| TikTok | 200 | page returned; sparse Open Graph compared with Instagram | No |

Decision: implement the first structured adapter for **Instagram** because it exposes the richest lawful public profile metadata without login. Post records are collected only when callers supply explicit public post URLs; profile responses remain `partial` when no post URLs are returned.

Re-run: `npm run eval -- --fixtures evals/social-source-selection.json --output docs/evals/social-source-selection-latest.md`
