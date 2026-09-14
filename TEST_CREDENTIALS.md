# Test Credentials

Seeded automatically by `backend/app/seed/seed_db.py`.

| Role | Email | Password |
|---|---|---|
| Operator | operator@testmail.dev | DemoPass123! |
| Reviewer | reviewer@testmail.dev | DemoPass123! |
| Consumer | consumer@testmail.dev | DemoPass123! |

These are application-managed credentials in both local and Supabase database
modes. For an online deployment, run
`backend/migrations/004_demo_app_users.sql` in the Supabase SQL editor. The
login flow does not use Supabase Auth.
