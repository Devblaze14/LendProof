# Antigravity Build Package — Loan Data Verification Copilot
### Everything below is written to be handed to Antigravity. You supply the env vars in Section 0. Everything else is instructions for the agent.

---

## Section 0 — What you must do before starting (nothing else)

1. Create a Supabase project. From Project Settings → API, copy:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_JWT_SECRET` (if your project shows a legacy JWT secret; if it only shows a JWKS endpoint, note that instead — Task 1 tells the agent to detect which and wire it up)
2. Create a Groq API key → `GROQ_API_KEY`.
3. Put all four in a `.env` file at the project root (gitignored). Nothing else needs to exist yet — the agent creates the repo structure, the schema, the seed data, and the test users itself.
4. Start Antigravity in this project folder, and paste **Section 1** as your very first message, before Task 1. Explicitly tell it: *"Persist these as project rules in your memory so every task you or future agents run in this project loads them automatically."* Antigravity is built to carry learned rules/decisions across tasks once told to — this is what makes the rest of this package hold together across 8 separate task runs instead of being re-explained each time.
5. Run Tasks 1 through 8 **as separate Manager-surface tasks, in order**, not as one giant prompt. Each task ends with an exit criterion and an Artifact (screenshot/recording) for you to glance at before starting the next one. That's roughly 8 check-ins for the entire build.

That's it — everything past this point is the agent's job.

---

## Section 1 — Persistent project rules (paste first, ask Antigravity to remember these)

**Stack — do not substitute anything here:**
- DB/Auth/Storage: Supabase (Postgres + Supabase Auth + Supabase Storage)
- Backend: Python, FastAPI, async, `BackgroundTasks` for ingestion (no Celery/Redis)
- AI: Groq API, model `openai/gpt-oss-120b` for reasoning calls, `openai/gpt-oss-20b` for high-volume/summary calls, `response_format={"type":"json_object"}` for all structured output
- Frontend: React + TypeScript (Vite), TanStack Query, TanStack Table
- All API routes under `/api/v1/...`

**Five non-negotiable design rules — violating any of these is a bug, even if it seems like a convenient shortcut:**
1. The AI service may only ever write to `ai_recommendations`. No code path may let an AI response mutate `loan_records` or `verified_loan_records` directly — only a human action through `POST /api/v1/exceptions/:id/decision` may do that.
2. Every AI call is logged (prompt, model, full response, confidence, latency, timestamp) *before* the response is shown to the user.
3. Validation logic is data-driven from a `validation_rules` table via one rule interpreter — never hardcoded per-field `if` statements.
4. `audit_log` is append-only. Never write an UPDATE or DELETE against it.
5. Role checks happen server-side on every route. Never rely on a frontend check alone.

**Standard error envelope — every error response, no exceptions:**
```json
{"error": {"code": "VALIDATION_FAILED", "message": "Human-readable summary", "field": "interest_rate", "request_id": "a1b2c3"}}
```

**Structured logging — one JSON object per line:**
```json
{"timestamp":"...", "level":"info", "request_id":"a1b2c3", "event":"ingestion.batch_complete", "batch_id":"...", "row_count":5000, "duration_ms":4200}
```

**Groq call resilience:** 10s hard timeout; exponential backoff, max 2 retries, only on 5xx/timeout, never on 4xx; on exhausted retries, the UI shows a clear "AI unavailable, continue manually" state — the human review/approve workflow must never be blocked by the AI being down. Rate-limit `/api/v1/ai/*` per user (~20 calls/min) to protect the Groq free tier.

**Coding standards:** Python via `black` + `ruff` + type hints (Pydantic models for every request/response). Frontend via ESLint + Prettier, TypeScript strict mode. Both enforced in CI, not just locally.

**Commit convention:** prefix every commit `[ai-assisted]` or `[human]` so % AI-generated code can be computed from git history later.

**Handling ambiguity — this is the rule that matters most for an unattended run:** if you hit a numeric threshold, business-rule value, or visual/branding decision that isn't explicitly specified anywhere in this package (e.g. exact interest-rate valid range, exact staleness cutoff in days, what counts as a "suspiciously repeated" borrower, color palette beyond severity-coding), **do not silently pick one and move on.** Pick a reasonable default, implement it, clearly mark it in code with a `# DECISION:` comment explaining what you chose and why, log it in `AI_DEVELOPMENT_LOG.md`, and continue — don't halt the whole task waiting for a synchronous answer, but make every such decision trivially easy for a human to find and override later. This is what keeps the build honest without turning it back into a supervised session.

**On every task's exit:** use the browser subagent to actually walk through the relevant flow and save a screenshot/recording Artifact — don't report a task complete on code-compiles-and-unit-tests-pass alone.

---

## Section 2 — Database schema (apply as a Supabase migration in Task 1)

```sql
create table profiles (
  id uuid primary key references auth.users(id),
  role text not null check (role in ('operator','reviewer','consumer')),
  name text, created_at timestamptz default now()
);
create table upload_batches (
  id uuid primary key default gen_random_uuid(), filename text not null,
  file_hash text not null unique,
  source_type text not null check (source_type in ('loan_tape','servicer_update','document_manifest')),
  storage_path text not null, uploaded_by uuid references profiles(id),
  row_count int, status text not null default 'processing', created_at timestamptz default now()
);
create table raw_loan_rows (
  id uuid primary key default gen_random_uuid(), batch_id uuid references upload_batches(id),
  row_number int not null, raw_json jsonb not null, parse_error text
);
create table loan_records (
  id uuid primary key default gen_random_uuid(), loan_id text not null, borrower_id text,
  loan_type text, origination_date date, maturity_date date, original_principal numeric,
  current_balance numeric, interest_rate numeric, term_months int, borrower_state text,
  loan_purpose text, credit_grade text, employment_length text, income_band text,
  payment_status text, days_past_due int, servicer_name text, last_payment_date date,
  last_updated_at timestamptz, document_status text, source_system text,
  source_batch_id uuid references upload_batches(id), version int not null default 1,
  created_at timestamptz default now(), updated_at timestamptz default now()
);
create index on loan_records (loan_id);
create index on loan_records (borrower_id, original_principal, origination_date);
create table servicer_updates (
  id uuid primary key default gen_random_uuid(), loan_id text not null, field_name text not null,
  batch_value text, servicer_value text, resolved_value text, resolved_by uuid references profiles(id),
  batch_id uuid references upload_batches(id)
);
create table document_manifest (
  id uuid primary key default gen_random_uuid(), loan_id text not null, document_status text,
  batch_id uuid references upload_batches(id)
);
create table validation_rules (
  id uuid primary key default gen_random_uuid(), rule_key text not null unique, field text,
  rule_type text not null check (rule_type in
    ('required','range','regex','date_order','cross_field','duplicate','staleness','cross_file')),
  params jsonb not null default '{}', severity text not null check (severity in ('critical','high','medium','low')),
  message_template text not null, source text not null default 'seed' check (source in ('seed','ai_generated')),
  active boolean not null default true, created_at timestamptz default now()
);
create table exceptions (
  id uuid primary key default gen_random_uuid(), loan_record_id uuid references loan_records(id),
  rule_key text not null, severity text not null,
  status text not null default 'open' check (status in ('open','in_review','resolved')),
  field text, detail jsonb, created_at timestamptz default now()
);
create index on exceptions (status, severity);
create table exception_comments (
  id uuid primary key default gen_random_uuid(), exception_id uuid references exceptions(id),
  author_id uuid references profiles(id), body text, created_at timestamptz default now()
);
create table ai_recommendations (
  id uuid primary key default gen_random_uuid(), exception_id uuid references exceptions(id),
  prompt text not null, model text not null, response_json jsonb not null, confidence numeric,
  latency_ms int, accepted boolean, reviewed_by uuid references profiles(id), created_at timestamptz default now()
);
create table reviewer_actions (
  id uuid primary key default gen_random_uuid(), exception_id uuid references exceptions(id),
  reviewer_id uuid references profiles(id) not null,
  action text not null check (action in ('approve','reject','edit','request_correction')),
  field_changed text, old_value text, new_value text,
  ai_recommendation_id uuid references ai_recommendations(id), created_at timestamptz default now()
);
create table verified_loan_records (
  id uuid primary key default gen_random_uuid(), loan_record_id uuid references loan_records(id),
  canonical_data jsonb not null, validation_result jsonb not null, reviewer_decision jsonb,
  ai_recommendation_id uuid references ai_recommendations(id), record_hash text not null, prev_hash text,
  verified_by uuid references profiles(id), verified_at timestamptz default now()
);
create table audit_log (
  id uuid primary key default gen_random_uuid(), event_type text not null,
  loan_record_id uuid references loan_records(id), actor_id uuid references profiles(id),
  detail jsonb, record_hash text, created_at timestamptz default now()
);
create index on audit_log (loan_record_id, created_at);
-- Enable RLS on every table, default-deny for anon. The FastAPI backend uses the
-- service-role key (bypasses RLS) and is the only writer for now.
```

---

## Section 3 — API contract (implement across Tasks 2–7)

`POST /api/v1/auth/login` · `POST /api/v1/uploads` · `GET /api/v1/uploads/:id` · `GET /api/v1/loans` · `GET /api/v1/loans/:id` · `GET /api/v1/exceptions` · `GET /api/v1/exceptions/:id` · `POST /api/v1/exceptions/:id/comments` · `POST /api/v1/exceptions/:id/decision` · `POST /api/v1/exceptions/:id/ai-review` · `POST /api/v1/ai/summarize-batch` · `POST /api/v1/ai/generate-rule` · `GET /api/v1/validation-rules` · `GET /api/v1/verified-loans` · `GET /api/v1/verified-loans/:id` · `GET /api/v1/audit/:loanId` · `GET /api/v1/summary` · `GET /api/v1/export/verified-dataset`

Expose auto-generated OpenAPI docs at `/docs`.

---

## Section 4 — Tasks (run each as its own Antigravity Manager task, in order)

### Task 1 — Foundation & contracts
Scaffold: FastAPI backend + React/TS (Vite) frontend + `docker-compose.yml` (backend + frontend containers; Supabase/Groq stay external, referenced by env vars). Apply the Section 2 schema as a Supabase migration. Detect whether the Supabase project uses a JWT secret or JWKS for auth verification and wire up server-side token verification accordingly. Seed one test user per role (operator/reviewer/consumer) via the Supabase Admin API using the service-role key, and write their credentials to `TEST_CREDENTIALS.md`. Set up `black`/`ruff`/ESLint/Prettier configs and a GitHub Actions workflow running lint + tests on every push/PR. Create `AI_DEVELOPMENT_LOG.md` and start logging from this task onward.
**Exit criterion:** `docker compose up` from a clean state serves a working `/health` endpoint; browser subagent confirms the frontend loads and can log in as each seeded role; `TEST_CREDENTIALS.md` exists.

### Task 2 — Synthetic dataset + ingestion pipeline
No organizer-provided dataset is assumed to exist — generate one. Write a data-generation script producing `loan_tape.csv` (1,000–5,000 rows), `servicer_update.csv`, `document_manifest.csv`, and `validation_rules.json`, deliberately including every issue type listed in the challenge brief's "Intentional Data Issues" section (missing/duplicate loan IDs, invalid dates, maturity-before-origination, negative balances, current balance exceeding original principal, out-of-range interest rates, payment-status/days-past-due mismatches, missing document status, cross-file conflicts, stale records, invalid state codes, suspicious repeats, closed-but-positive-balance loans). Save an `expected_exception_sample.csv` documenting which rows should trigger which exception. Implement `POST /api/v1/uploads` (stores file in Supabase Storage, idempotent on file hash) and a background task that parses, normalizes into `loan_records`, and captures unparseable rows in `raw_loan_rows`.
**Exit criterion:** uploading the generated `loan_tape.csv` produces the expected row count with no duplicates on re-upload; browser subagent walks the operator upload flow and screenshots the import summary.

### Task 3 — Validation engine
Implement the rule interpreter, dispatching on `rule_type`, seeded from the generated `validation_rules.json`. Rules must be enforced from the DB table, not hardcoded per-field logic.
**Exit criterion:** running validation against the Task 2 dataset produces exceptions matching `expected_exception_sample.csv`; unit tests cover the interpreter at roughly 90%.

### Task 4 — Exception workflow & reviewer UI
Implement `GET/POST /api/v1/exceptions*` and the reviewer-role frontend: filterable/searchable queue, loan detail view with a clear side-by-side diff for `loan_tape` vs `servicer_update` conflicts, comments, and approve/reject/edit/request-correction actions.
**Exit criterion:** browser subagent logs in as reviewer and resolves one real exception end-to-end; screenshots of the queue, the diff view, and the resolved state are saved as Artifacts.

### Task 5 — AI Review Assistant (Groq)
Build the Groq integration service per Section 1's resilience rules. Implement explain/suggest, batch summarize, and natural-language rule generation (inserted into `validation_rules` with `active=false` until a human approves it). Build the reviewer's AI panel: recommendation, confidence badge, model/timestamp metadata, and explicit accept/edit/reject controls.
**Exit criterion:** browser subagent triggers an AI review on one exception, **accepts one suggestion and rejects a different one**, and both outcomes are visible in the UI and present as rows in `ai_recommendations`.

### Task 6 — Verified records, hash chain, audit trail
Implement `record_hash = sha256(canonical_json(fields) + prev_hash)` per loan. Write every event type (upload, import, validation run, exception created, AI recommendation, comment, field edit, approve/reject, verified-record created/exported) to `audit_log`. Build the audit timeline UI and `GET /api/v1/verified-loans*`, `GET /api/v1/audit/:loanId`. Add a "verify integrity" action that recomputes the chain and compares it to the stored hash.
**Exit criterion:** one loan walked fully through its lifecycle shows a complete, correctly ordered timeline, and the integrity check passes; screenshot Artifact of the timeline saved.

### Task 7 — Dashboards, summary, export
Build the Operator, Reviewer, and Consumer dashboards per the brief. Implement `GET /api/v1/summary` including a data-quality score (state the formula used in a code comment and in the architecture note draft) and `GET /api/v1/export/verified-dataset`.
**Exit criterion:** browser subagent logs into all three roles and screenshots each non-empty dashboard.

### Task 8 — Polish & submission readiness
Write the README (setup, env vars, run commands), finalize `AI_DEVELOPMENT_LOG.md` (real dated entries, at least two genuine rejected/reworked AI outputs, an AI-generated-code % computed from `git log` commit prefixes), draft the 1–2 page architecture note (system design, data model, API, validation engine, AI feature, audit trail, and the explicit security/scope trade-offs — production-grade security, real OCR, real blockchain, and real credit-scoring are out of scope per the brief; state that plainly rather than leaving it implicit). Write one Playwright/Cypress e2e test mirroring the five-minute demo path. Fix every error/loading/empty state gap found along the way.
**Exit criterion:** a fresh clone, `docker compose up`, and a full run through the demo path succeeds twice in a row; every `# DECISION:` comment from earlier tasks is compiled into one visible list for human review before submission.

---

## Section 5 — After Task 8 (yours, not the agent's)

- Read every `# DECISION:` comment the agent left — these are the judgment calls it made without you. Overrule any that don't sit right.
- Read the AI Development Log for real — this is the artifact judges will actually read, and it should sound like your team, not like boilerplate.
- Rehearse the demo yourself at least twice.
- Ping the Supabase project awake shortly before judging if time has passed since submission (free tier pauses after 7 days idle).
