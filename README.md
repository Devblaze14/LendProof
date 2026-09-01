# LendProof

Loan Data Verification Copilot for the Intain Campus FinTech Challenge 2026.

LendProof is an AI-assisted full-stack application for turning messy loan files into reviewable,
auditable data. It ingests CSV files, normalizes and validates loan records with configurable rules,
routes exceptions to a human reviewer, adds optional Groq-powered decision support, and creates a
hash-chained verified record after approval.

Built for the Intain Campus FinTech Challenge 2026 - Full Stack Track.

## Demo highlights

- Deterministic synthetic dataset with 1,500 loan rows and intentional data-quality issues.
- Config-driven validation engine with severity, field, and message metadata.
- Role-based workflows for operator, reviewer, and consumer users.
- Human-in-the-loop exception decisions with optional AI recommendations.
- Immutable-style audit events and hash-chain integrity verification.
- Supabase-backed deployment with Auth, Postgres, private source-file storage, and role profiles.
- Groq-powered exception explanations and batch triage, with an offline mock mode for local demos.
- Searchable, severity-filtered review queue with reviewer notes, correction requests, and audit history.
- CI checks for backend tests and frontend production builds.

## Architecture

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS | Login, operations, exception review, verified records |
| API | FastAPI, Pydantic | Authentication, uploads, validation, review, audit APIs |
| Persistence | PostgreSQL, SQLAlchemy | Users, loan records, exceptions, AI decisions, audit events |
| AI | Groq API with mock mode | Review recommendations with timeout/retry/fallback behavior |
| Delivery | Vercel, Supabase, Docker Compose | Serverless deployment, durable data, and local development |

## Production Deployment

LendProof deploys as Vercel Services: a Vite frontend and a FastAPI backend
sharing one domain. Supabase provides Auth, Postgres, and private storage for
source-file lineage.

1. In the Supabase SQL Editor, run these migrations in order:

```text
backend/migrations/001_init_supabase.sql
backend/migrations/002_supabase_profiles.sql
backend/migrations/003_supabase_storage.sql
```

2. Create Operator, Reviewer, and Consumer users in Supabase Auth. Give each
user raw metadata such as `{"role":"reviewer","name":"Reviewer Demo"}`.
The profile trigger assigns their in-app role.
3. In Vercel, import this repository from its root directory. Add every value
from [`.env.supabase.example`](.env.supabase.example) to both Production and
Preview environments. Do not set `VITE_API_BASE_URL` in Vercel.
4. Set the Vercel Application Preset to **Services**, then deploy.
[`vercel.json`](vercel.json) routes `/api/v1/*` to FastAPI and all other
paths to the Vite frontend.

Never commit a populated `.env` file or expose `SUPABASE_SERVICE_ROLE_KEY`
through a `VITE_` variable. Full setup details are in
[`docs/SUPABASE_SETUP.md`](docs/SUPABASE_SETUP.md).

## Quick start with Docker

Requirements: Docker Desktop with Compose support.

```bash
cp .env.example .env
docker compose up --build
```

The backend waits for Postgres, then seeds the demo users and validation rules automatically. Open:

- Frontend: http://localhost:5173/
- API health: http://localhost:8000/health
- Interactive API docs: http://localhost:8000/docs

To stop the stack:

```bash
docker compose down
```

To reset the local database and remove demo data:

```bash
docker compose down -v
```

## Demo flow

1. Sign in as the Operator and upload `data/loan_tape.csv`.
2. Show the normalization and validation summary, then switch to the Reviewer.
3. Search or filter exceptions, request a Groq explanation, add a note, and request a correction or approve a clean record.
4. Open AI Insights to generate a batch triage briefing. AI recommendations remain separate from human decisions.
5. Sign in as the Consumer, select a verified record, verify its hash chain, inspect its audit timeline, and export verified data.

Demo credentials are listed in [`TEST_CREDENTIALS.md`](TEST_CREDENTIALS.md). They are intended only
for local development and evaluation. Guest access creates/reuses a local consumer session and does
not expose upload, review, or approval controls.

## Run without Docker

Requirements: Python 3.12+, Node.js 20+, and PostgreSQL 16.

```bash
cp .env.example .env
createdb loan_copilot
psql loan_copilot -f backend/migrations/001_init_local.sql

cd backend
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python -m app.seed.seed_db
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

For a non-Docker backend, set `DATABASE_URL` in `.env` to your PostgreSQL connection string.
For Vercel deployment, leave `VITE_API_BASE_URL` unset so the frontend calls the same-origin API.

## Configuration

Copy `.env.example` to `.env` and keep `.env` out of version control.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_MODE` | `local` | Local JWT/Postgres mode; `supabase` is the production integration path |
| `DATABASE_URL` | local Postgres URL | PostgreSQL connection string |
| `GROQ_MOCK` | `true` | Uses deterministic local fixtures when true |
| `GROQ_API_KEY` | empty | Required only when `GROQ_MOCK=false` |
| `LOCAL_JWT_SECRET` | development value | Change this outside local demos |
| `VITE_API_BASE_URL` | `http://localhost:8000` | API URL used by the frontend |

For Supabase, use the production-only template [`.env.supabase.example`](.env.supabase.example).
It contains the required database, Auth, Storage, and Groq variables without secrets.

## Testing and build checks

Backend unit tests:

```bash
cd backend
python -m pytest tests/ -v
```

Frontend production build:

```bash
cd frontend
npm ci
npm run build
```

GitHub Actions runs both checks on pushes and pull requests. Frontend output in `frontend/dist/` is
intentionally ignored by Git.

## Repository structure

```text
backend/       FastAPI application, validation engine, services, migrations, tests
frontend/      React + TypeScript application
data/          Reproducible synthetic CSV data and validation rules
docs/          Requirements, architecture, build plan, and production-readiness notes
.github/       CI workflow
```

## Scope and limitations

This repository is a working challenge/demo implementation, not a production lending system. It
uses Supabase Auth and Postgres, private Supabase Storage for source-file lineage, and a
human-controlled Groq workflow. Review decisions remain explicit; AI does not silently edit data.

The current UI demonstrates ingestion → validation → searchable exception triage → AI assistance →
human review → verification → audit/export. Synthetic data only is included.

Synthetic data only is included. Do not upload real borrower or financial information to an
unreviewed development deployment.

## Further documentation

- [`docs/Loan_Data_Verification_Copilot_Master_Plan.md`](docs/Loan_Data_Verification_Copilot_Master_Plan.md)
- [`docs/Requirements_SRS_and_AI_Build_Prompt.md`](docs/Requirements_SRS_and_AI_Build_Prompt.md)
- [`docs/Production_Readiness_Engineering_Playbook.md`](docs/Production_Readiness_Engineering_Playbook.md)
- [`docs/Antigravity_Build_Package.md`](docs/Antigravity_Build_Package.md)
- [`AI_DEVELOPMENT_LOG.md`](AI_DEVELOPMENT_LOG.md)

## License

MIT 
