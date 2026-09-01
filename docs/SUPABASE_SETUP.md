# Supabase Setup

LendProof keeps the browser behind the FastAPI API. Use Supabase for Postgres
and Auth, but never place the service-role key in frontend variables.

## Required setup

1. Run `backend/migrations/001_init_supabase.sql` in the Supabase SQL editor.
2. Run `backend/migrations/002_supabase_profiles.sql` in the same editor.
   If it was already run before the storage bucket was added, also run
   `backend/migrations/003_supabase_storage.sql`.
3. In Supabase Auth, create the Operator, Reviewer, and Consumer demo users.
   Put `role` (`operator`, `reviewer`, or `consumer`) and optional `name` in
   each user's raw metadata when creating the user. The trigger creates the
   matching application profile automatically.
4. Copy the values below into `.env`:

```dotenv
DATABASE_MODE=supabase
DATABASE_URL=postgresql+psycopg2://postgres.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=your_publishable_or_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_JWT_SECRET=your_legacy_hs256_jwt_secret
GROQ_MOCK=false
GROQ_API_KEY=your_groq_key
```

`SUPABASE_JWT_SECRET` is used by this backend to verify Supabase access
tokens. Select the legacy HS256 JWT secret in the Supabase API/JWT settings.
Do not put `SUPABASE_SERVICE_ROLE_KEY` in a `VITE_` variable or commit `.env`.

## Start with Supabase

```bash
docker compose -f docker-compose.yml -f docker-compose.supabase.yml up --build backend frontend
```

The Supabase override removes the backend's local database dependency while
retaining the same backend and frontend containers.

## Vercel environment variables

Set the Vercel Application Preset to **Services**, then add the variables from
`.env.supabase.example` for Production and Preview. Do not set
`VITE_API_BASE_URL`; the frontend uses the same deployment's `/api/v1` service
rewrite. Do not add `SUPABASE_SERVICE_ROLE_KEY` as a `VITE_` variable.

The local-only variables `LOCAL_JWT_SECRET`, `LOCAL_STORAGE_DIR`,
`VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY` are not needed for this
deployment. The names `secret_role`, `anon_public`, and `secret_key` are not
read by LendProof and should be removed from your local `.env` and Vercel
environment settings.
