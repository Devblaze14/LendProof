# Loan Data Verification Copilot — Master Build Plan
### Intain Campus FinTech Challenge 2026 · Full Stack Track

---

## 0. Executive summary (the CEO view)

Judges will spend roughly ten minutes per project: a five-minute demo and a scan of your repo, README, and logs. Every hour of build time should go where it is both **visible** and **weighted**. The rubric tells you exactly where that is:

| Weight | What it really means |
|---|---|
| 50 pts (Full-Stack 20 + Backend 15 + Frontend 15) | Does the whole loop actually run, end to end, without you narrating around a broken part? |
| 30 pts (AI Feature 15 + Agentic Coding 15) | Is there a real, human-controlled AI workflow, and can you prove — with logs — how you built the app with AI? |
| 20 pts (Traceability 10 + Demo 10) | Can a stranger trust this data, and can you show that trust in five minutes? |

**The single biggest risk is not lacking a clever feature. It's a demo that breaks because the walking skeleton (ingest → validate → review → verify → audit) was never finished end-to-end.** Everything below is sequenced so that skeleton exists and works before anything decorative gets built on top of it.

**Thesis for "exceptional" grade:** don't add more surface area — add *coherence*. A judge should be able to trace one loan from a messy CSV row to a hashed, audited, API-exposed verified record, and see exactly where a human made a decision and where AI merely advised. That traceability *is* the product.

---

## 1. Bold decisions beyond the spec (and why each one earns points)

The PDF describes the floor. These are the choices that lift it — each one is scoped to be buildable in a hackathon, not a v2 roadmap item.

| Decision | Rationale | Rubric line it serves |
|---|---|---|
| **Hash-chained record history** — `record_hash = SHA256(canonical_fields + prev_hash)`, one chain per loan | Gives you real tamper-evidence (the PDF's "record hash" requirement) without the out-of-scope burden of "real blockchain deployment" | Traceability (10) |
| **Two-source reconciliation diff view** — side-by-side `loan_tape.csv` vs `servicer_update.csv` per loan, with a clear "which value wins and why" | The PDF explicitly lists "conflicting values between files" as an intentional issue but doesn't specify a resolution UI — this is where most teams will improvise badly under time pressure | Frontend UX (15), Backend (15) |
| **Async ingestion via a job queue**, not a blocking upload request | 5,000-row files must not freeze the UI or the API thread; shows real backend maturity | Backend Architecture (15) |
| **Data-quality score (0–100)** per batch and trended across uploads | Gives the Data Consumer dashboard a single number judges remember, and it's a natural demo "wow" moment | Demo Quality (10), Full-Stack (20) |
| **AI-generated validation rules from natural language**, wired into the same rule engine the CSV pipeline uses (not a toy side feature) | The PDF lists this as one Module D bullet — most teams will skip it because it looks hard. Doing it for real, with the rule actually taking effect, is a genuine differentiator | AI Feature Quality (15) |
| **Confidence score + full metadata (model, prompt, latency, timestamp) on every AI suggestion**, stored and rendered | Directly satisfies "Required AI Controls" (§9 of the brief) rather than bolting it on afterward | AI Feature Quality (15) |
| **Idempotent uploads** via file-hash dedup | Prevents "oops I imported it twice" during a live demo — a small thing that prevents a real failure mode | Backend, Demo Quality |
| **`AI_DEVELOPMENT_LOG.md` written from day one**, not reconstructed at the end | Judges can tell a retrofitted log from a real one. Commit-tagging (`[ai-assisted]` vs `[human]`) makes the "% AI-generated" number defensible | Agentic Coding (15) |
| **One deliberately-documented rejected AI suggestion**, captured live rather than invented | The brief requires 2+ examples of rejected AI output — staging one honestly (e.g. asking the AI to "just auto-fix it" and rejecting that shortcut) is more credible than fabricating one after the fact | Agentic Coding (15) |
| **Docker Compose one-command local run** | Directly satisfies "local runnable setup" and removes the single most common demo-day failure: "it doesn't run on my laptop" | Full-Stack Completeness (20) |

Everything else — WebSocket live updates, a no-code rule builder UI, fuzzy/embedding duplicate detection — is real but explicitly a **stretch tier**. See §17 for the cut list.

---

## 2. Team structure

Assume a team of 3–4, mapped onto the PDF's own role split plus one addition:

| Role | Owns | Suggested count |
|---|---|---|
| **Backend / Data / API** | Schema, ingestion pipeline, validation engine, audit trail, hashing, `/verified-loans` API | 1 |
| **AI Integration** | Claude API layer, prompt templates, `ai_recommendations` service, AI Development Log | 1 (can double with backend on a 3-person team) |
| **Frontend / Workflow / UX** | Upload flow, three dashboards, exception queue, AI panel, audit viewer | 1–2 |
| **PM / Demo / Docs** (rotating, not full-time) | Architecture note, README, demo script rehearsal, judging-rubric self-check | shared |

Contract-first collaboration: agree on the DB schema and API shapes (§5–6 below) in the first hour, so frontend can build against mocked responses while backend builds the real thing in parallel.

---

## 3. Build sequence (phase-based, not calendar-locked — compress or stretch to fit your actual clock)

| Phase | Goal | Exit criterion |
|---|---|---|
| **P0 — Contracts** | Finalize DB schema, API contract, seed synthetic dataset, auth/roles | Can `docker compose up` and hit a health-check endpoint |
| **P1 — Walking skeleton** | Upload → parse → normalize → validate → list records (no AI, no auth UI polish) | One CSV goes in, exceptions come out, visible in a raw table |
| **P2 — Exception workflow** | Reviewer login, exception queue, approve/reject/edit, comments, reviewer history | A flagged record can be resolved by a human end-to-end |
| **P3 — AI Review Assistant** | Wire Claude API for explain / suggest / classify / summarize; log every call | Reviewer sees an AI suggestion next to (never instead of) their own decision |
| **P4 — Verified record + audit + Consumer view** | Hash chain, `/verified-loans` API, audit trail viewer, data-quality score | A judge can open one loan and see its full history from raw row to hash |
| **P5 — Polish & demo readiness** | Dashboards, deployment, README, architecture note, AI dev log, rehearsed 5-min script | Fresh clone → `docker compose up` → full demo works, twice in a row |

**Rule of thumb:** don't start P3 until P1 and P2 are demoable. A working non-AI loop beats a broken AI-first build every time — the rubric literally puts full-stack completeness (20) above AI (15).

---

## 4. System architecture

The pipeline diagram above is the spine. Concretely:

- **Frontend**: React + TypeScript (Vite), talking to the backend only over the documented REST API — no shared code, so frontend can be built against mocks from hour one.
- **Backend**: Node.js/Express (or FastAPI if the team is stronger in Python) exposing the REST API, doing auth/RBAC, orchestrating ingestion, validation, AI calls, and audit writes.
- **Job queue**: Redis + BullMQ (or a simple in-process async queue if Redis is one dependency too many) — decouples the upload request from the actual parse/validate work so large files don't block.
- **Database**: PostgreSQL. Relational integrity (foreign keys between loans, exceptions, reviewer actions, verified records) matters more here than schema flexibility, and Postgres's `JSONB` columns give you the flexibility of Mongo where you actually need it (raw row storage, AI response payloads) without giving up constraints everywhere else.
- **AI layer**: a thin service wrapping the Anthropic API, called only by the backend — never directly from the frontend, so every AI call is logged and rate-limited server-side.
- **File storage**: local disk (or S3-compatible bucket if deploying) for raw uploaded files, referenced by hash for lineage and idempotency.
- **Deployment**: Docker Compose for local judging; optionally Render/Railway (backend + Postgres) and Vercel (frontend) for a hosted demo link.

**Why Postgres over Mongo here, explicitly:** the domain is full of relationships that need to stay consistent — a loan has many exceptions, an exception has many reviewer actions, a verified record references exactly one loan and one validation result. That's a foreign-key problem, not a document problem. Keep the messy, semi-structured bits (raw CSV row, AI response) in `JSONB` columns instead of separate tables.

---

## 5. Data model

Core tables (columns abbreviated to what matters — fill in types/nullability as you build):

```
users               id, name, email, password_hash, role (operator|reviewer|consumer), created_at
upload_batches      id, filename, file_hash (unique), source_type (loan_tape|servicer_update|document_manifest),
                    uploaded_by, row_count, status, created_at
raw_loan_rows       id, batch_id (FK), row_number, raw_json (JSONB), parse_error (nullable)
loan_records        id, loan_id (business key), borrower_id, loan_type, origination_date, maturity_date,
                    original_principal, current_balance, interest_rate, term_months, borrower_state,
                    loan_purpose, credit_grade, employment_length, income_band, payment_status,
                    days_past_due, servicer_name, last_payment_date, last_updated_at, document_status,
                    source_system, source_batch_id (FK), version, created_at, updated_at
servicer_updates    id, loan_id, field_name, batch_value, servicer_value, resolved_value, resolved_by,
                    batch_id (FK)
document_manifest   id, loan_id, document_status, batch_id (FK)
validation_rules    id, rule_key, field, rule_type (required|range|regex|date_order|cross_field|
                    duplicate|staleness|cross_file), params (JSONB), severity, message_template,
                    source (seed|ai_generated), active, created_at
exceptions          id, loan_id (FK), rule_key, severity, status (open|in_review|resolved), field,
                    detail (JSONB), created_at
exception_comments  id, exception_id (FK), author_id (FK), body, created_at
reviewer_actions     id, exception_id (FK), reviewer_id (FK), action (approve|reject|edit|request_correction),
                    field_changed, old_value, new_value, ai_recommendation_id (nullable FK), created_at
ai_recommendations  id, exception_id (FK), prompt, model, response_json (JSONB), confidence,
                    latency_ms, accepted (nullable bool), reviewed_by, created_at
verified_loan_records id, loan_id (FK), canonical_data (JSONB), validation_result (JSONB),
                    reviewer_decision (JSONB), ai_recommendation_id (nullable FK), record_hash,
                    prev_hash, verified_by, verified_at
audit_log           id, event_type, loan_id (nullable FK), actor_id (nullable FK), detail (JSONB),
                    record_hash (nullable), created_at
```

Indices worth adding explicitly (small dataset, but shows you thought about it): `loan_records(loan_id)`, `loan_records(borrower_id, original_principal, origination_date)` for the duplicate-combination check, `exceptions(status, severity)` for the queue filter, `audit_log(loan_id, created_at)` for the timeline view.

**Hash chain detail:** for each loan, `record_hash = SHA256(canonical_json(verified_fields) + prev_hash)`. The first record in a loan's history uses a fixed genesis string as `prev_hash`. Recomputing the chain from `audit_log` and comparing to the stored hash is your tamper-evidence check — worth exposing as a "verify integrity" button in the Consumer dashboard, it's cheap and looks great in a demo.

---

## 6. Backend API

All endpoints required by the brief, plus the additions needed to make the product actually work:

| Method & path | Purpose | Role |
|---|---|---|
| `POST /auth/login` | Issue JWT | public |
| `POST /uploads` | Upload a CSV (loan_tape / servicer_update / document_manifest), enqueue processing | operator |
| `GET /uploads/:id` | Batch status, row counts, failed rows | operator |
| `GET /loans` | List normalized loan records, filterable | all (scoped) |
| `GET /loans/:id` | Single loan, current + version history | all (scoped) |
| `GET /exceptions` | Filter by type/severity/status, search by loan/borrower ID | reviewer |
| `GET /exceptions/:id` | Full detail incl. conflicting-source diff | reviewer |
| `POST /exceptions/:id/comments` | Add reviewer comment | reviewer |
| `POST /exceptions/:id/decision` | Approve / reject / edit / request correction | reviewer |
| `POST /exceptions/:id/ai-review` | Trigger AI explain/suggest for this exception | reviewer |
| `POST /ai/summarize-batch` | Summarize a batch of exceptions | reviewer |
| `POST /ai/generate-rule` | Natural-language → validation rule (goes to `validation_rules`, inactive until approved) | reviewer/operator |
| `GET /validation-rules` | List active rules | operator |
| `GET /verified-loans` | List verified records | consumer |
| `GET /verified-loans/:id` | Single verified record incl. hash chain | consumer |
| `GET /audit/:loanId` | Full audit timeline for a loan | all (scoped) |
| `GET /summary` | Dashboard aggregates (counts, data-quality score, trend) | all (scoped) |
| `GET /export/verified-dataset` | CSV/JSON bundle of verified records + audit trail | consumer |

Publish this as OpenAPI/Swagger (auto-generated from route definitions) — it's low effort and directly demonstrates "good APIs" under the Backend Architecture rubric line.

**Validation engine, concretely:** don't hardcode the checks in application code. Read `validation_rules.json` (seeded) into the `validation_rules` table at startup, and write one interpreter that dispatches on `rule_type`. This is what makes "generate validation rules from natural language" (Module D) a real feature instead of a demo trick — the AI-generated rule is just another row the same interpreter already knows how to run.

**AI control enforcement, concretely:** the AI service must only ever write to `ai_recommendations`. No code path lets an AI response touch `loan_records` or `verified_loan_records` directly — only `POST /exceptions/:id/decision`, driven by a human, is allowed to mutate a loan. This single design rule is what makes "AI output must not silently change data" true by construction rather than by promise.

---

## 7. AI Review Assistant — mapped to concrete calls

| Module D requirement | Implementation |
|---|---|
| Explain why a record failed | Prompt with the failed rule + the record's relevant fields → structured JSON `{explanation, likely_cause}` |
| Suggest likely corrections | Same call, extended with `{suggested_value, confidence}` |
| Compare conflicting records | Feed both source values (loan_tape vs servicer_update) → `{recommended_value, reasoning}` |
| Generate reviewer notes | Summarize the exception + reviewer's stated decision into a note draft the reviewer can edit before saving |
| Classify exception severity | Structured output constrained to `critical|high|medium|low` with a one-line justification |
| Summarize a batch | Aggregate N exceptions → executive summary card for the Reviewer dashboard |
| Generate rules from natural language | Prompt → structured `validation_rules` row, inserted as `active=false` until an operator approves it |

Every call is logged to `ai_recommendations` with `prompt`, `model`, `response_json`, `confidence`, `latency_ms`, and later `accepted`/`reviewed_by` once a human acts on it. Ask the model for **structured JSON output** (not free text) so the frontend can render confidence badges and diffs reliably instead of parsing prose.

Cache AI responses per `(exception_id, rule_key, record_hash)` so re-opening the same exception doesn't re-spend a call — cheap to build, protects your API budget during a live demo.

---

## 8. Frontend architecture & UX

- **Stack**: React + TypeScript + Vite, TanStack Query for data fetching/caching, TanStack Table (virtualized) so a 5,000-row exception queue stays smooth, Tailwind for styling with a small custom design-token layer rather than default component library looks.
- **Three role-gated dashboards**, matching the brief exactly:
  - **Data Operator**: upload widget with progress, import history, validation summary, "records needing correction" shortcut.
  - **Reviewer**: exception queue (filter by type/severity, search by loan/borrower ID), loan detail view with the two-source diff, AI panel showing recommendation + confidence + accept/reject/edit controls, pending vs recent decisions.
  - **Data Consumer**: verified records table, data-quality score with trend, verification history, export button, audit trail viewer.
- **Design language**: severity color-coding (critical/high/medium/low) used consistently across queue, detail view, and dashboard cards; skeleton loaders for the async ingestion state; empty states that explain *why* a table is empty (e.g. "no exceptions — every record in this batch passed validation") rather than a blank table.
- **Audit trail viewer**: a vertical timeline per loan (upload → validate → exception → AI recommendation → reviewer decision → verified) — this single component is your best "traceability" demo asset, build it early enough to be reliable, not last-minute.

---

## 9. Security posture (deliberately bounded)

The brief explicitly puts "production-grade security" out of scope — treat that as permission to *not* over-invest, not permission to skip basics that also happen to be required for role-based dashboards to work at all:

**In scope, baseline hygiene:** JWT auth, bcrypt password hashing, RBAC middleware on every route, parameterized queries via the ORM, input validation on upload and API bodies, CORS configuration, secrets via environment variables.

**Explicitly out of scope, and say so in the architecture note:** penetration testing, encryption at rest, SOC2-style controls, a WAF, rate-limiting beyond a basic per-IP guard on the AI endpoints (which you want anyway for cost control, not security theater). Naming this trade-off explicitly reads as engineering maturity to judges, not as a gap.

---

## 10. Testing strategy (time-boxed, high-value only)

- **Validation engine unit tests** — highest value per minute spent. The rule interpreter is pure, deterministic logic; a dozen small tests covering each `rule_type` against known-good and known-bad rows is cheap insurance and directly demonstrable ("here's our test suite passing on the intentional-issues list from the brief").
- **One ingestion integration test** — upload a small CSV fixture, assert the right exceptions get created.
- **One end-to-end happy-path test** (Playwright/Cypress) that mirrors your five-minute demo script exactly — this doubles as your demo rehearsal safety net.
- **AI golden-set spot-check** — a handful of fixed exceptions with an expected *shape* of response (severity bucket, presence of a suggested value), checked manually rather than asserted exactly, since AI text output shouldn't be pinned word-for-word.

Skip broad frontend unit-test coverage unless time allows — the e2e test covers more real risk per minute spent.

---

## 11. Deployment & DevOps

- **`docker-compose.yml`** bringing up frontend, backend, Postgres, and Redis (if used) with one command, plus a seed script that loads the synthetic dataset and creates one test user per role. This is worth doing early — "the judge can run it themselves" is not optional, it's the first bullet on the deliverables list.
- **Optional hosted deployment** for a live demo link: Render or Railway for backend + Postgres, Vercel for the frontend.
- **A minimal GitHub Actions workflow** running lint + the unit/integration tests on every PR — cheap to set up, and it's tangible evidence of engineering discipline that supports both the Backend Architecture and Agentic Coding rubric lines.

---

## 12. Agentic coding log — built as you go, not reconstructed

Start `AI_DEVELOPMENT_LOG.md` on day one with one entry per meaningful AI-assisted step:

```
Tool: Claude Code
Use case: validation engine scaffold
Prompt: "..." (verbatim)
Output summary: generated rule interpreter with 6 rule types
Human review: reviewed, fixed off-by-one in date_order check, added missing null check
Verdict: accepted with modification
```

Adopt a commit-message convention (`[ai-assisted]` vs `[human]`) so the "estimated % AI-generated code" figure in your deliverables can be computed from git history instead of guessed. Deliberately capture at least two genuine rejections — for example, asking the AI to auto-apply a correction without review, and rejecting that because it violates the "AI must not silently change data" control — and write down *why* it was wrong, not just that it was. That's a much stronger answer to "lessons learned" than a generic one.

---

## 13. Judging rubric → feature traceability

| Category | Pts | Primary features earning it |
|---|---|---|
| Full-Stack Product Completeness | 20 | Working Docker Compose run, full upload→verify loop, persistence |
| Backend Architecture & Data Modeling | 15 | Schema in §5, rule-engine design, API in §6, error handling |
| Frontend Workflow & UX | 15 | Three dashboards, exception queue, diff view, audit timeline |
| AI Feature Quality | 15 | §7 AI calls, confidence + metadata logging, human accept/reject controls |
| Agentic Coding Demonstration | 15 | `AI_DEVELOPMENT_LOG.md`, commit tagging, 2+ documented rejections |
| Traceability & Auditability | 10 | Hash chain, `audit_log`, timeline viewer, integrity-check button |
| Demo Quality | 10 | Rehearsed 5-min script (§16), honest limitations slide |

---

## 14. Deliverables checklist (mapped 1:1 to brief §12)

- [ ] GitHub repo, complete source
- [ ] Working app — Docker Compose local run + optional hosted link
- [ ] README — setup, env vars, run commands
- [ ] Demo video, ≤5 minutes
- [ ] Architecture note, 1–2 pages (system design, data model, API, validation engine, AI feature, audit trail, trade-offs — including the explicit security-scope trade-off from §9)
- [ ] `AI_DEVELOPMENT_LOG.md`
- [ ] Test credentials for Operator, Reviewer, Consumer
- [ ] Sample output: verified dataset export + audit trail export

---

## 15. Five-minute demo script

| Time | Beat |
|---|---|
| 0:00–0:30 | Log in as Data Operator, upload a messy loan tape |
| 0:30–1:00 | Show import + validation summary — call out a couple of the intentional issue types by name |
| 1:00–1:30 | Open one failed record; show the two-source conflict diff |
| 1:30–2:30 | Switch to Reviewer, open the exception queue, trigger AI explain/suggest, show confidence + metadata, **accept one suggestion and reject another** (this is your differentiation moment) |
| 2:30–3:00 | Approve the record; show it becoming a verified record with a hash |
| 3:00–3:30 | Switch to Data Consumer, show the verified-records dashboard and data-quality score |
| 3:30–4:00 | Open the audit trail timeline for that same loan, click "verify integrity" on the hash chain |
| 4:00–4:30 | Show one live API response (`GET /verified-loans/:id`) in a terminal or Swagger UI |
| 4:30–5:00 | Thirty seconds on the AI Development Log — show a real rejected-suggestion entry, state your AI-generated-code estimate, name one honest limitation |

Rehearse this exact path as your Playwright e2e test (§10) so the demo and your test suite are the same script.

---

## 16. Risk register / cut list (if time runs short)

**Non-negotiable (cut nothing here):** ingestion, validation engine, exception workflow, one real AI feature (explain + suggest is the minimum), hash-chained verified record, audit trail, three basic dashboards, Docker Compose run.

**Cut in this order if squeezed:**
1. WebSocket live queue updates
2. Natural-language rule generation (keep the seeded rules only)
3. Fuzzy/embedding-based duplicate detection (keep exact-match duplicate rules)
4. Hosted deployment (local Docker run still satisfies the requirement)
5. Batch-summarization AI feature
6. Export bundle polish (keep raw CSV/JSON export, skip the zip packaging)

Never cut: the audit trail, the hash chain, or the human-accept/reject control on AI suggestions — these three are what separate this submission from a generic CRUD-plus-chatbot entry.
