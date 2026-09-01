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
- Offline-first local mode: Postgres, JWT authentication, and mocked AI require no external accounts.
- CI checks for backend tests and frontend production builds.

## Architecture

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS | Login, operations, exception review, verified records |
| API | FastAPI, Pydantic | Authentication, uploads, validation, review, audit APIs |
| Persistence | PostgreSQL, SQLAlchemy | Users, loan records, exceptions, AI decisions, audit events |
| AI | Groq API with mock mode | Review recommendations with timeout/retry/fallback behavior |
| Delivery | Docker Compose, GitHub Actions | Reproducible local stack and automated checks |

## Quick start with Docker

Requirements: Docker Desktop with Compose support.

```bash
cp .env.example .env
docker compose up --build
```

The backend waits for Postgres, then seeds the demo users and validation rules automatically. Open:

- Frontend: 
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

1. Use **Continue as guest** for the read-only consumer view, or sign in as the operator to upload `data/loan_tape.csv`.
2. Open the reviewer dashboard and inspect the generated exception queue.
3. Request AI review for an exception. In the default mock mode this is fully offline.
4. Approve or reject the exception as the reviewer.
5. Sign in as the consumer to inspect verified records and the data-quality summary.
6. Use the API docs to inspect audit events and verify the hash chain.

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

For a non-Docker backend, set `DATABASE_URL` in `.env` to your PostgreSQL connection string. The
frontend reads `VITE_API_BASE_URL` and defaults to `http://localhost:8000`.

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

Supabase settings and the production migration are documented in
[`docs/Antigravity_Build_Package.md`](docs/Antigravity_Build_Package.md).

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

This repository is a working challenge/demo implementation, not a production lending system. Local
mode and mocked AI are the verified, reproducible path. Live Groq and Supabase integrations are
extension points that require external credentials and deployment-specific security review.

The current UI focuses on the ingestion → validation → exception → review → verification spine.
Cross-file conflict visualization, a dedicated audit timeline page, and frontend batch summarization
remain planned follow-up work; related backend/API foundations are present where noted in the planning
documents.

Synthetic data only is included. Do not upload real borrower or financial information to an
unreviewed development deployment.

## Further documentation

- [`docs/Loan_Data_Verification_Copilot_Master_Plan.md`](docs/Loan_Data_Verification_Copilot_Master_Plan.md)
- [`docs/Requirements_SRS_and_AI_Build_Prompt.md`](docs/Requirements_SRS_and_AI_Build_Prompt.md)
- [`docs/Production_Readiness_Engineering_Playbook.md`](docs/Production_Readiness_Engineering_Playbook.md)
- [`docs/Antigravity_Build_Package.md`](docs/Antigravity_Build_Package.md)
- [`AI_DEVELOPMENT_LOG.md`](AI_DEVELOPMENT_LOG.md)

## License

No license has been selected yet. Until a license is added, the repository should be treated as
all-rights-reserved and not reused, redistributed, or deployed commercially without permission.
