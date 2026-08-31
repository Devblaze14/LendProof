# Production Readiness & Engineering Standards Playbook
### The "all hats" layer — companion to `Loan_Data_Verification_Copilot_Master_Plan.md` and `Requirements_SRS_and_AI_Build_Prompt.md`

The first two documents answer *what to build* and *how to hand it to an AI safely*. This one answers the question a VP of Engineering would ask before letting anything ship: what standards, gates, and runbooks turn "it works on my laptop" into "I'd stand behind this in a review." Everything here is bounded by the brief's own out-of-scope list (§16) — this is engineering discipline appropriate to a hackathon deliverable, not gold-plating a system that explicitly doesn't need SOC2 or pen-testing.

**How to use this with the AI build prompt:** paste this alongside Part B of the SRS document in your build session. Where the two overlap (error handling, logging), this document is the authoritative spec.

---

## Hat 1 — CEO: vision, scope discipline, risk appetite

**Vision, one paragraph:** loan data is only useful once someone can trust it. This product doesn't analyze loans — it builds the trust layer underneath analysis: a record that says, provably, *this data was checked, here's what failed, here's who decided what, here's the AI's role in that decision, and here's the unbroken chain from raw file to verified fact.*

**What "production grade" means here — scoped, not unlimited:**

| In scope for production discipline | Explicitly not (per brief §16 — don't build it anyway) |
|---|---|
| Consistent error handling, structured logging, CI gates, code review discipline, a real threat model for what's actually exposed | Penetration testing, SOC2, encryption at rest, WAF, HA/multi-region failover |
| Idempotent, auditable, hash-verifiable data pipeline | Real securitization/waterfall logic, real credit scoring, real OCR |
| A demo-day runbook for the failure modes that can actually happen (Groq down, Supabase paused) | 24/7 on-call, paging, SRE error budgets |

**Risk appetite — say this out loud to the team before you build:**
- **Unacceptable, ever:** silent data mutation by AI, an audit trail with gaps, a reviewer decision that isn't attributable to a person.
- **Acceptable, and worth stating plainly in the architecture note:** no automated backups (free-tier reality), no horizontal scaling, no formal pen-test. Naming these as conscious trade-offs reads as maturity; hiding them reads as an oversight if a judge finds them.

**If this were a real product**, the metric that would matter is *reviewer time per loan* and *escape rate* (bad data that made it to "verified" anyway). You don't need to build a dashboard for this, but framing one slide of your demo around "this is the workflow that would move that number" is a stronger pitch than a feature list.

---

## Hat 2 — VP Engineering: governance and definition of done

**RACI** (adapt names to your actual team size — even solo, filling this in forces you to notice gaps):

| Function | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| DB schema & migrations | Backend | Backend lead | Frontend (for API shape) | Whole team |
| Validation rule content | Backend | Product/PM hat | Domain brief (§7) | Whole team |
| AI prompt design & controls | AI integration | Backend lead | — | Whole team |
| Dashboards/UX | Frontend | Frontend lead | Backend (data shape) | Whole team |
| CI/CD, deployment | Whoever owns DevOps hat | Backend lead | — | Whole team |
| Demo script & rehearsal | PM/rotating | Whole team | — | — |
| AI Development Log | Whoever pairs with the AI that session | Whole team | — | Judges (it's a deliverable) |

**Definition of Done — project level, not per-feature:**
- [ ] CI green on `main` (lint + type-check + tests)
- [ ] No Blocker or Major bug open (see Hat 7 severity scale)
- [ ] Every endpoint in the API contract implemented and documented in the auto-generated OpenAPI spec
- [ ] Every event type in Module F is actually being written to `audit_log` — verified by walking one loan through the full lifecycle and reading its timeline back
- [ ] `AI_DEVELOPMENT_LOG.md` has real entries dated throughout the build, not backfilled the night before
- [ ] `docker compose up` works from a clean clone, on a machine that isn't yours

**Branching & commits:** trunk-based, short-lived branches (`feat/ingestion`, `feat/ai-review`), PRs merge into `main` only when CI is green. Commit prefix convention `[ai-assisted]` / `[human]` (already established in the build prompt) is what makes your "% AI-generated" estimate a git command instead of a guess:
```
git log --oneline | grep -c '\[ai-assisted\]'
git log --oneline | grep -c '\[human\]'
```

---

## Hat 3 — Principal Architect: capacity, topology, scalability envelope

**Environment topology:**

| Environment | What runs there | Talks to |
|---|---|---|
| Local dev | `docker compose up` — FastAPI + React dev server | Your hosted Supabase project + Groq (both external even in local dev — there's no local Postgres to keep dev/prod parity simple) |
| CI (GitHub Actions) | Lint, type-check, unit + integration tests | A disposable/test Supabase project or fully mocked Supabase client — **never point CI at the same project you'll demo from** |
| Hosted demo (optional) | Vercel (frontend) + Render/Railway (backend) | Same Supabase project as local dev, same Groq key |

**Capacity & performance budget** — set numbers now so you know what "done" performance-wise looks like, instead of discovering it live:

| Metric | Target | Why this number |
|---|---|---|
| Ingestion throughput | 5,000-row CSV fully processed in < 60s | Brief's stated max dataset size; keeps a live demo upload watchable, not awkward |
| API p95 latency (non-AI endpoints) | < 400ms | Standard "feels instant" threshold for a CRUD-ish call |
| Groq call latency budget | < 5s, with a 10s hard timeout | Groq is fast by design; a 10s timeout with a visible fallback message beats a frozen AI panel |
| Concurrent demo users | 3 (one per role, live) | Matches the actual demo, not a hypothetical |
| DB size headroom | Stay under ~50MB of the 500MB free-tier ceiling | Leaves 10x headroom for re-imports and mistakes during dev |

**Scalability envelope — say what this design handles today, and what it wouldn't, without building for the second case:**
- Handles today: thousands of loans, a handful of concurrent reviewers, synchronous-feeling AI review.
- Would need rework at 10–100x: `BackgroundTasks` would need to become a real queue (Celery/Redis or Supabase Edge Functions + a queue table); Supabase free tier would need to become Pro; Groq calls would need batching/queuing to respect rate limits.
- Naming this explicitly in the architecture note is a stronger signal of engineering judgment than pretending the hackathon build is infinitely scalable.

**API versioning:** every route lives under `/api/v1/...` from the first commit — costs nothing now, and "we clearly haven't thought about API evolution" is a cheap thing for a judge to dock you for.

---

## Hat 4 — Backend Engineer: contracts and standards

**Standard error envelope — every error response, no exceptions:**
```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Human-readable summary",
    "field": "interest_rate",
    "request_id": "a1b2c3"
  }
}
```

**Structured logging — one JSON object per line:**
```json
{"timestamp": "...", "level": "info", "request_id": "a1b2c3", "event": "ingestion.batch_complete", "batch_id": "...", "row_count": 5000, "duration_ms": 4200}
```

**Groq call resilience — this is what protects your live demo:**
- Timeout: 10s hard cap.
- Retry: exponential backoff, max 2 retries, only on 5xx/timeout — never retry on a 4xx (that's a bug in your prompt/payload, not a transient failure).
- Fallback on exhausted retries: return a clear "AI unavailable, continue manually" state in the UI — **never let an AI outage block the reviewer from approving/rejecting a record.** The human workflow must survive the AI being down.

**Rate limiting:** a simple per-user token bucket on `/ai/*` endpoints (e.g. 20 calls/minute) — protects your Groq free-tier budget from a demo-day accident (someone double-clicking "explain" ten times) more than it protects against abuse.

**Validation:** every request/response is a typed Pydantic model. Malformed input returns `422` with the error envelope above, field-level.

---

## Hat 5 — Frontend Engineer: standards

- TypeScript strict mode on; ESLint + Prettier enforced (add to the CI pipeline in Hat 6, not just a local habit).
- **Accessibility, concretely:** severity is never color-only — pair every severity badge with a text label or icon (critical/high/medium/low), and make sure the exception queue is keyboard-navigable. This is a cheap, visible signal of craft.
- **Performance budget:** virtualize any table over ~200 rows (TanStack Table), lazy-load each role's dashboard route so an operator never downloads the reviewer bundle.
- **Error boundaries:** one per dashboard, so a failure in the AI panel shows a contained error card, not a blank white screen for the whole reviewer view.

---

## Hat 6 — DevOps/SRE: CI/CD, observability, incident readiness

**Minimal CI (GitHub Actions) — real, not aspirational:**
```yaml
name: ci
on: [pull_request, push]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: ruff check . && black --check .
      - run: pytest
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci && npm run lint && npm run build
```

**Secrets:** never commit `.env`. Local dev uses `.env` (gitignored) from `.env.example`. CI uses GitHub Actions secrets. Hosted demo uses Vercel/Render's environment variable dashboards. The Supabase **service-role key** lives only in the backend's environment — it must never reach frontend code or a client-visible bundle.

**Observability, right-sized:** structured JSON logs (Hat 4) are your primary tool. `GET /summary` doubles as your metrics surface for this scope — no need for a separate monitoring stack. If you have spare time, a free-tier Sentry project for error tracking is a cheap, visible upgrade.

**Demo-day runbook — write this down before you need it:**

| Failure | Response |
|---|---|
| Groq API is slow/down mid-demo | AI panel shows the fallback state (Hat 4); narrate "here's what happens when the AI is unavailable — the reviewer isn't blocked" as a *feature*, not an excuse |
| Supabase project is paused (7-day idle) | Ping any endpoint 10 minutes before judging to wake it; know this *before* you're live |
| A live upload fails | Have a known-good pre-uploaded batch ready as a fallback path in the script |
| Free-tier rate limit hit | Keep a cached/recorded fallback of the AI response for the exact demo record, shown only if the live call fails |

**Backup stance:** free tier has no automated backups. Mitigate by exporting a known-good seed dump (`pg_dump` or Supabase's export) the night before submission, and keep `main` tagged at your last-known-good commit.

---

## Hat 7 — QA / Test Engineering: pyramid and exit criteria

| Layer | Scope | Target |
|---|---|---|
| Unit | Validation rule interpreter, hash-chain function | ~90% coverage — this logic is pure, deterministic, and cheap to test thoroughly |
| Integration | Ingestion pipeline (upload → parse → normalize → validate) | One test per intentional-issue type from brief §7, asserting the right exception fires |
| E2E | One Playwright/Cypress script mirroring the 5-minute demo exactly | Must pass twice in a row before submission |
| AI golden-set | Fixed sample exceptions, assert response *shape* (severity bucket present, suggested value present) not exact wording | Manual spot-check, not automated assertion on free text |

**Bug severity triage:**
- **Blocker** — breaks the demo path (upload fails, login fails, AI panel crashes the page). Zero tolerated at submission.
- **Major** — a required feature is broken but the demo path avoids it. Zero tolerated at submission.
- **Minor** — cosmetic, edge-case. Fine to ship with a note in "honest limitations."

---

## Hat 8 — Security: a bounded threat model

Scoped to what's actually exposed by this design — not a general pen-test:

| Threat | Where it applies | Mitigation already in the design |
|---|---|---|
| Spoofing | Forged/stolen auth token | Supabase Auth JWT verified server-side on every request; never trust a client-asserted role |
| Tampering | Direct DB write bypassing the API | RLS default-deny on every table; only the backend's service-role key can write; frontend never holds that key |
| Repudiation | "I didn't do that" on a reviewer decision | `audit_log` is append-only, tied to `actor_id`, and hash-chained |
| Information disclosure | Service-role key or Groq key leaking to the client bundle | Keys live only in backend env vars; never referenced in frontend code, never in a public repo |
| Denial of service | AI endpoint hammered, burning free-tier quota | Per-user rate limiting on `/ai/*` |
| Elevation of privilege | Consumer-role token hitting a reviewer-only route | Server-side RBAC check on every route, tested explicitly (a 403 test case per role boundary) |

**Restated, deliberately: penetration testing, encryption at rest, and compliance frameworks are out of scope per the brief.** This table exists so that statement is a documented decision, not a silent gap.

---

## Hat 9 — Data / Compliance: governance statement

- All loan and borrower data is **synthetic** — state this explicitly in the UI (a small footer note) and in the architecture note. No real PII is processed.
- No retention policy is needed for ephemeral hackathon data, but stating what one *would* look like in a real deployment (e.g., "verified records retained per regulatory schedule, raw uploads purged after N days") is a cheap line in the architecture note that signals you understand the domain beyond the hackathon's bounds.

---

## Hat 10 — Program Management: go/no-go checklist

Run this the night before submission, not the morning of:

- [ ] Fresh clone, `docker compose up`, works with zero manual fixes
- [ ] All three test-role logins work and show non-empty dashboards
- [ ] Full loan lifecycle walked end-to-end: upload → exception → AI review (one accepted, one rejected) → approval → verified record → audit timeline → API response
- [ ] Hash-chain integrity check passes on at least one loan
- [ ] `AI_DEVELOPMENT_LOG.md` has dated entries and at least 2 genuine rejected-suggestion writeups
- [ ] CI is green on `main`
- [ ] Zero open Blocker/Major bugs (Hat 7)
- [ ] Demo rehearsed twice, on time, by whoever is presenting
- [ ] Supabase project confirmed awake (pinged) within the hour before judging
- [ ] README, architecture note, and test credentials are current with whatever changed in the last 24 hours — this is where late-stage divergence usually hides
