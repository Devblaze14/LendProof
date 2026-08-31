# Requirements Specification & AI Build Prompt
### Companion to `Loan_Data_Verification_Copilot_Master_Plan.md`

This document has three parts:
- **Part A** — the actual functional/non-functional requirements (what the strategy doc didn't have)
- **Part B** — a self-contained prompt you paste directly into your AI coding tool (Claude Code, Cursor, etc.)
- **Part C** — the honest list of what stays on you, and why some of it should

---

## Part A — Software Requirements Specification

### A.1 Scope

Build a full-stack application that ingests messy loan CSVs, validates them against a configurable rule engine, routes failures to a human reviewer with AI-assisted explanations, and produces a hash-chained, auditable "verified loan record" exposed via API — matching the Intain Campus FinTech Challenge 2026 Full Stack Track brief.

### A.2 Locked technology stack

| Layer | Choice | Why |
|---|---|---|
| Database | **Supabase (managed Postgres)** | Relational integrity for loan↔exception↔decision links, built-in Auth, Storage, RLS |
| Auth | **Supabase Auth** | Don't hand-roll JWT/bcrypt — three roles map cleanly onto Supabase Auth + a `profiles.role` column |
| File storage | **Supabase Storage** | Raw CSV uploads live here, referenced by hash, not on local disk |
| Backend | **Python — FastAPI** | Async by default, typed, matches the brief's suggested stack, integrates cleanly with Supabase's Python client |
| Async ingestion | **FastAPI `BackgroundTasks`** (not Celery/Redis) | 1,000–5,000 rows doesn't need a message broker; adding Redis is infra you'd be maintaining for no real benefit at this scale. Revisit only if you have spare time (see cut list) |
| AI | **Groq — `openai/gpt-oss-120b`** (chat completions, `response_format: json_object`) | `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` are being retired by Groq — don't build on either. `gpt-oss-120b` supports JSON mode, function calling, 131k context. Use `openai/gpt-oss-20b` as a faster/cheaper fallback for high-volume calls (e.g. batch summarization) |
| Frontend | **React + TypeScript (Vite)** | As in the master plan |

### A.3 Functional requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-ING-1 | Operator can upload `loan_tape.csv`, `servicer_update.csv`, `document_manifest.csv` | File stored in Supabase Storage; row referencing it created in `upload_batches` |
| FR-ING-2 | System parses and normalizes rows into the internal schema without blocking the HTTP response | Upload endpoint returns immediately with a `batch_id`; processing happens in a background task; status is pollable |
| FR-ING-3 | Rows that fail to parse are captured, not silently dropped | Each unparseable row visible in `raw_loan_rows.parse_error`, counted in the upload summary |
| FR-ING-4 | Re-uploading an identical file does not create duplicate records | `upload_batches.file_hash` is unique; duplicate upload is rejected or flagged, not silently reprocessed |
| FR-VAL-1 | Every rule in brief §7 ("Intentional Data Issues") has a corresponding entry in `validation_rules` and is enforced | Feeding the sample dataset produces the expected exception set (spot-checked against `expected_exception_sample.csv`) |
| FR-VAL-2 | Validation rules are data, not hardcoded logic | Disabling a rule row stops it from firing, without a code change |
| FR-VAL-3 | Conflicts between `loan_tape.csv` and `servicer_update.csv` are surfaced per field, not just as one generic exception | `servicer_updates` row exists per conflicting field with both source values visible |
| FR-EXC-1 | Reviewer can filter the exception queue by type, severity, status; search by loan/borrower ID | Query params on `GET /exceptions` support all four |
| FR-EXC-2 | Reviewer can comment, and approve / reject / edit / request-correction on an exception | Each action recorded in `reviewer_actions` with old/new value where applicable |
| FR-EXC-3 | Every reviewer action is attributed and timestamped | No action row without `reviewer_id` and `created_at` |
| FR-AI-1 | Reviewer can request an AI explanation + suggested correction for any open exception | `ai_recommendations` row created with prompt, model, response, confidence |
| FR-AI-2 | AI recommendation is shown separately from the human decision, and the reviewer must explicitly accept/edit/reject it | No exception can move to `resolved` status from an AI call alone — only via `POST /exceptions/:id/decision` |
| FR-AI-3 | Reviewer can request an AI summary of a batch of exceptions | `POST /ai/summarize-batch` returns a structured summary, logged the same way as single-exception calls |
| FR-AI-4 | Reviewer/operator can propose a new validation rule in natural language | AI returns a structured `validation_rules` row with `active = false`; a human must explicitly activate it |
| FR-VER-1 | Approving an exception (or a clean record) produces a `verified_loan_records` row | Contains canonical data, validation result, reviewer decision, AI recommendation (if used), hash, verifier, timestamp |
| FR-VER-2 | Each verified record's hash incorporates the previous record's hash for that loan | Recomputing the chain from `audit_log` matches the stored `record_hash` |
| FR-AUD-1 | Every event in brief §8 Module F is written to `audit_log` | File-upload, import, validation-run, exception-created, AI-recommendation, comment, field-edit, approve/reject, verified-record-created/exported all present as distinct `event_type` values |
| FR-AUD-2 | Audit trail for a single loan is viewable as an ordered timeline | `GET /audit/:loanId` returns events in chronological order |
| FR-DASH-1 | Operator dashboard shows upload/import history, validation summary, records needing correction | — |
| FR-DASH-2 | Reviewer dashboard shows the exception queue, AI panel, pending and recent decisions | — |
| FR-DASH-3 | Consumer dashboard shows verified records, a data-quality score, verification history, export | Data-quality score = resolved-clean / total records in a batch, or equivalent documented formula |
| FR-API-1 | All endpoints listed in brief §8 Module H exist and return the documented shape | `GET /loans`, `GET /loans/:id`, `GET /exceptions`, `GET /verified-loans`, `GET /verified-loans/:id`, `GET /audit/:loanId`, `GET /summary` |
| FR-AUTH-1 | Three roles (operator, reviewer, consumer) are enforced on every relevant endpoint | A reviewer-only endpoint rejects a consumer-role token with 403 |

### A.4 Non-functional requirements

| Category | Requirement |
|---|---|
| Performance | A 5,000-row upload must not block the API thread; UI must show progress, not hang |
| Reliability | A failed/partial ingestion must not leave the DB in an inconsistent state — wrap batch processing in a transaction per chunk, and make re-running a failed batch safe |
| Idempotency | Re-processing the same file or the same AI call twice must not create duplicate exceptions or duplicate audit entries |
| Usability | Every empty state explains *why* it's empty; every async action (upload, AI call) shows a loading state, not a frozen UI |
| Auditability | `audit_log` is append-only at the application layer — no update/delete path exists for it |
| Maintainability | Validation logic lives in data (`validation_rules`), not scattered `if` statements, so a new rule doesn't require a deploy |
| Security (bounded) | Role-based access enforced server-side on every route (never trust a frontend role check alone); Supabase service-role key never exposed to the frontend; **production-grade security (pen-testing, encryption at rest, SOC2) is explicitly out of scope per the brief** — state this in the architecture note, don't silently skip it |
| Cost control | Cache AI responses per `(exception_id, rule_key, record_hash)`; rate-limit AI endpoints server-side; both Groq and Supabase have free-tier ceilings that a demo-day traffic spike could hit |
| Portability | `docker compose up` brings up the full local stack (backend + frontend) using a `.env` pointing at your Supabase project and Groq key — no other setup |
| Observability | Structured logging on ingestion and AI calls (batch ID, row counts, latency) — doesn't need to be fancy, needs to exist |

### A.5 Constraints

- Supabase free tier: 500MB database, 1GB storage (50MB per file), 50,000 MAU, 5GB egress — the synthetic dataset (a few thousand rows, tens of columns) is well within this, but **the project pauses automatically after 7 days with no traffic** — resume it before judging if there's a gap after submission.
- No automatic backups on Supabase free tier — not a concern for a synthetic dataset, but don't treat this as production storage.
- Groq: don't build on `llama-3.3-70b-versatile` or `llama-3.1-8b-instant` (being retired) — use `openai/gpt-oss-120b` / `openai/gpt-oss-20b`.
- Hackathon timeline is fixed and unknown to this document — Part B's phases are ordered by dependency, not by day, so compress or stretch them to your actual clock.

### A.6 Out of scope (per brief §16, unchanged)

Real structured-finance analytics, securitization logic, borrowing-base calculations, real OCR, real blockchain, real underwriting/credit-scoring, payment workflows, production-grade security, regulatory compliance engine.

---

## Part B — AI Build Prompt

**Copy everything between the two banners below into your AI coding tool as the first message of a fresh session.** It's self-contained — the AI doesn't need Part A in context, though pasting both is better if your tool allows it.

---
### ▼▼▼ COPY EVERYTHING BELOW THIS LINE ▼▼▼

You are building a full-stack hackathon project: a **Loan Data Verification Copilot**. It ingests messy loan CSVs, validates them, routes failures to a human reviewer with AI-assisted suggestions, and produces a hash-chained, auditable "verified loan record" exposed via API.

**Locked stack — do not substitute:**
- Database/Auth/Storage: Supabase (managed Postgres + Supabase Auth + Supabase Storage)
- Backend: Python, FastAPI, async, `BackgroundTasks` for ingestion (no Celery/Redis)
- AI: Groq API, model `openai/gpt-oss-120b` for reasoning calls, `openai/gpt-oss-20b` for high-volume/summary calls, `response_format={"type": "json_object"}` for all structured outputs
- Frontend: React + TypeScript (Vite), TanStack Query, TanStack Table
- Local run: Docker Compose (frontend + backend containers; DB/Auth/Storage are the hosted Supabase project, referenced via env vars, not containerized)

**Non-negotiable design rules — do not deviate from these even if it seems more convenient:**
1. The AI service may only ever write to an `ai_recommendations` table. No code path may let an AI response mutate `loan_records` or `verified_loan_records` directly. Only a human action through the decision endpoint may do that.
2. Every AI call must be logged with: prompt, model, full response, confidence, latency, timestamp — before the response is shown to the user, not after.
3. Validation logic must be data-driven from a `validation_rules` table, dispatched by a single rule interpreter — never hardcoded per-field `if` statements.
4. `audit_log` is append-only. Never write an UPDATE or DELETE against it.
5. Role checks happen server-side on every route. Never rely on the frontend hiding a button as the access control.

**Database schema — create this as a Supabase migration. Use this exact shape, extend only where noted:**

```sql
-- profiles extends Supabase's built-in auth.users with app-specific role
create table profiles (
  id uuid primary key references auth.users(id),
  role text not null check (role in ('operator','reviewer','consumer')),
  name text,
  created_at timestamptz default now()
);

create table upload_batches (
  id uuid primary key default gen_random_uuid(),
  filename text not null,
  file_hash text not null unique,
  source_type text not null check (source_type in ('loan_tape','servicer_update','document_manifest')),
  storage_path text not null,
  uploaded_by uuid references profiles(id),
  row_count int,
  status text not null default 'processing',
  created_at timestamptz default now()
);

create table raw_loan_rows (
  id uuid primary key default gen_random_uuid(),
  batch_id uuid references upload_batches(id),
  row_number int not null,
  raw_json jsonb not null,
  parse_error text
);

create table loan_records (
  id uuid primary key default gen_random_uuid(),
  loan_id text not null,
  borrower_id text,
  loan_type text, origination_date date, maturity_date date,
  original_principal numeric, current_balance numeric, interest_rate numeric,
  term_months int, borrower_state text, loan_purpose text, credit_grade text,
  employment_length text, income_band text, payment_status text,
  days_past_due int, servicer_name text, last_payment_date date,
  last_updated_at timestamptz, document_status text, source_system text,
  source_batch_id uuid references upload_batches(id),
  version int not null default 1,
  created_at timestamptz default now(), updated_at timestamptz default now()
);
create index on loan_records (loan_id);
create index on loan_records (borrower_id, original_principal, origination_date);

create table servicer_updates (
  id uuid primary key default gen_random_uuid(),
  loan_id text not null, field_name text not null,
  batch_value text, servicer_value text, resolved_value text,
  resolved_by uuid references profiles(id),
  batch_id uuid references upload_batches(id)
);

create table document_manifest (
  id uuid primary key default gen_random_uuid(),
  loan_id text not null, document_status text,
  batch_id uuid references upload_batches(id)
);

create table validation_rules (
  id uuid primary key default gen_random_uuid(),
  rule_key text not null unique, field text,
  rule_type text not null check (rule_type in
    ('required','range','regex','date_order','cross_field','duplicate','staleness','cross_file')),
  params jsonb not null default '{}',
  severity text not null check (severity in ('critical','high','medium','low')),
  message_template text not null,
  source text not null default 'seed' check (source in ('seed','ai_generated')),
  active boolean not null default true,
  created_at timestamptz default now()
);

create table exceptions (
  id uuid primary key default gen_random_uuid(),
  loan_record_id uuid references loan_records(id),
  rule_key text not null,
  severity text not null,
  status text not null default 'open' check (status in ('open','in_review','resolved')),
  field text, detail jsonb,
  created_at timestamptz default now()
);
create index on exceptions (status, severity);

create table exception_comments (
  id uuid primary key default gen_random_uuid(),
  exception_id uuid references exceptions(id),
  author_id uuid references profiles(id), body text, created_at timestamptz default now()
);

create table ai_recommendations (
  id uuid primary key default gen_random_uuid(),
  exception_id uuid references exceptions(id),
  prompt text not null, model text not null,
  response_json jsonb not null, confidence numeric,
  latency_ms int, accepted boolean, reviewed_by uuid references profiles(id),
  created_at timestamptz default now()
);

create table reviewer_actions (
  id uuid primary key default gen_random_uuid(),
  exception_id uuid references exceptions(id),
  reviewer_id uuid references profiles(id) not null,
  action text not null check (action in ('approve','reject','edit','request_correction')),
  field_changed text, old_value text, new_value text,
  ai_recommendation_id uuid references ai_recommendations(id),
  created_at timestamptz default now()
);

create table verified_loan_records (
  id uuid primary key default gen_random_uuid(),
  loan_record_id uuid references loan_records(id),
  canonical_data jsonb not null, validation_result jsonb not null,
  reviewer_decision jsonb, ai_recommendation_id uuid references ai_recommendations(id),
  record_hash text not null, prev_hash text,
  verified_by uuid references profiles(id), verified_at timestamptz default now()
);

create table audit_log (
  id uuid primary key default gen_random_uuid(),
  event_type text not null, loan_record_id uuid references loan_records(id),
  actor_id uuid references profiles(id), detail jsonb,
  record_hash text, created_at timestamptz default now()
);
create index on audit_log (loan_record_id, created_at);

-- Enable RLS on every table above. Default-deny for anon; the FastAPI backend
-- talks to Supabase using the service-role key (bypasses RLS) and is the ONLY
-- writer. If you later let the frontend query Supabase directly for reads,
-- add explicit per-role SELECT policies keyed off profiles.role — do this
-- deliberately, not as a shortcut, and confirm with the team lead first.
```

**Build order — do not start a phase until the previous one's exit criterion is met:**

1. **Contracts**: Supabase project created, migration above applied, `.env.example` with `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `GROQ_API_KEY`. FastAPI skeleton with a `/health` route. Seed script creating one user per role via Supabase Auth admin API + a `profiles` row each.
   *Exit: `docker compose up` serves a working health check.*
2. **Ingestion**: `POST /uploads`, background task parses CSV → `raw_loan_rows` → normalizes into `loan_records`, writes `upload_batches.status`. Idempotent on `file_hash`.
   *Exit: uploading the sample `loan_tape.csv` produces the expected row count and no duplicate on re-upload.*
3. **Validation engine**: rule interpreter reading `validation_rules`, one function per `rule_type`, produces `exceptions` rows. Seed `validation_rules` from `validation_rules.json`.
   *Exit: running validation on the sample dataset matches `expected_exception_sample.csv`.*
4. **Exception workflow**: `GET /exceptions` (filterable/searchable), `POST /exceptions/:id/comments`, `POST /exceptions/:id/decision`. Reviewer-role frontend queue + detail view with the two-source diff.
   *Exit: a human can resolve a real exception end-to-end through the UI.*
5. **AI Review Assistant**: Groq integration service, `POST /exceptions/:id/ai-review`, `POST /ai/summarize-batch`, `POST /ai/generate-rule`. Every call writes `ai_recommendations` before returning. Frontend AI panel with accept/edit/reject controls, confidence badge, model+timestamp shown.
   *Exit: a reviewer can see an AI suggestion and independently accept one and reject another, and both are visible in the log.*
6. **Verified records + audit + hash chain**: on approval, write `verified_loan_records` with `record_hash = sha256(canonical_json(fields) + prev_hash)`. Write every event type to `audit_log`. `GET /verified-loans`, `GET /verified-loans/:id`, `GET /audit/:loanId`. Audit timeline component.
   *Exit: opening one loan shows its full history from raw row to hash, and recomputing the chain matches the stored hash.*
7. **Dashboards + summary API + export**: `GET /summary`, data-quality score, three role dashboards, `GET /export/verified-dataset`.
   *Exit: all three role logins show a coherent, non-empty dashboard against the seeded dataset.*
8. **Polish**: README, `docker-compose.yml` finalized, OpenAPI docs exposed, error/loading/empty states pass on every screen.

**Where you must stop and ask the human instead of assuming:**
- Exact numeric thresholds not stated in the brief (interest rate valid range, staleness cutoff in days, what counts as "suspiciously repeated" borrower records) — propose a value, flag it clearly, don't silently pick one and move on.
- Whether the frontend ever queries Supabase directly (bypassing FastAPI) for reads — default is *no*, all access goes through FastAPI; only change this if explicitly told to.
- Visual/branding decisions (colors beyond severity-coding, logo, copy tone) — propose, don't finalize unilaterally.
- Deployment target (local-only vs. also hosting on Render/Vercel) — ask before spending time on hosting config.
- Anything where a "clever" shortcut would violate one of the five non-negotiable design rules above — stop and flag it instead of taking the shortcut.

**Logging requirement:** append one entry to `AI_DEVELOPMENT_LOG.md` for every meaningful step (new module, non-trivial bug fix, any rejected/reworked suggestion) in this format:

```
Tool: <name>
Use case: <what you were building>
Prompt: <verbatim>
Output summary: <what was generated>
Human review: <what was reviewed and changed>
Verdict: accepted | accepted with modification | rejected — why
```

Tag commits `[ai-assisted]` or `[human]` so the AI-generated-code percentage can be computed from git history at the end.

### ▲▲▲ COPY EVERYTHING ABOVE THIS LINE ▲▲▲

---

## Part C — What only you can do

Being honest about this is part of doing it well — and per the brief, it's literally graded.

**Before the AI can start:**
- Create the Supabase project yourself; get the URL, anon key, and service-role key. The AI can write the migration, but you're the one clicking "New Project."
- Create your Groq API key.
- Decide team role split (§2 of the master plan) and actual timeline — the AI can't know your deadline or headcount.

**While it's building — non-delegable by design:**
- **Actually review the AI's output.** Not skim — run it, click through it, try to break it. The rubric requires two genuine examples of rejected AI output with reasoning. If you never push back, you have nothing honest to write there, and it's 15 points.
- **Make the threshold calls** the prompt is instructed to flag rather than guess (interest rate range, staleness window, duplicate-detection sensitivity) — these are judgment calls about what "reasonable" looks like for this domain, not facts the AI can look up.
- **Resolve genuine ambiguity** in the brief the same way — e.g. exactly what the data-quality score formula should reward.

**Near the end — inherently yours:**
- Write the architecture note and the "lessons learned" section in your own voice — it's meant to be your reflection, not the AI's.
- Rehearse and record the five-minute demo. Software doesn't demo itself, and a rehearsed script is the difference between "found a bug live" and "confidently walked through the app."
- Resume the Supabase project (it pauses after 7 days idle) before judging if there's a gap after submission.
- Final QA pass logged in as all three roles, right before submission — the one check that catches "works on my machine" failures.
