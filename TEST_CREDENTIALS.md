# Test Credentials

Seeded automatically by `backend/app/seed/seed_db.py`.

| Role | Email | Password |
|---|---|---|
| Operator | operator@testmail.dev | DemoPass123! |
| Reviewer | reviewer@testmail.dev | DemoPass123! |
| Consumer | consumer@testmail.dev | DemoPass123! |

These are local-mode credentials only (see `app/security.py`). If you switch
`DATABASE_MODE=supabase`, create these three users in Supabase Auth instead
(Antigravity Build Package Task 1 does this via the Supabase Admin API using
your service-role key) and this file's passwords no longer apply.
