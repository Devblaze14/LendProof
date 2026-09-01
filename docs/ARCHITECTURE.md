# LendProof Architecture Note

## System Design

LendProof is a full-stack loan data verification system with a clean separation of concerns across four layers:

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Layer                            │
│              React + TypeScript + Vite                       │
│  Role-gated dashboards (Operator/Reviewer/Consumer)         │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────────┐
│                    API Layer                                  │
│                  FastAPI + Pydantic                           │
│  Auth, uploads, validation, review, audit endpoints         │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│               Data & Service Layer                           │
│         PostgreSQL + Supabase + Groq AI                     │
│  Validation engine, AI service, audit writer, hash chain    │
└─────────────────────────────────────────────────────────────┘
```

**Technology Stack:**
- **Frontend**: React, TypeScript, Vite, TanStack Query, Tailwind CSS
- **Backend**: FastAPI, SQLAlchemy, Pydantic, Python 3.12+
- **Database**: PostgreSQL via Supabase (managed) with local dev support
- **AI**: Groq API (`openai/gpt-oss-120b` for reasoning, `openai/gpt-oss-20b` for summaries)
- **Storage**: Supabase Storage for source file lineage
- **Deployment**: Vercel (frontend + backend as Services), Docker Compose for local

**Data Flow:**
1. CSV upload → file hash check → Supabase Storage
2. Background ingestion → parse → normalize → store as `loan_records`
3. Validation engine applies config-driven rules → creates `exceptions`
4. Reviewer workflow → optional AI assistance → human decision
5. Approval creates hash-chained `verified_loan_records`
6. Every step writes to append-only `audit_log`

## Data Model

The schema is relational with JSONB columns for flexible data. Core tables:

| Table | Purpose | Key Design |
|-------|---------|------------|
| `profiles` | User roles (operator/reviewer/consumer) | Maps to Supabase Auth users |
| `upload_batches` | File metadata and processing status | Unique `file_hash` for idempotency |
| `raw_loan_rows` | Original CSV rows for lineage | Stores `raw_json` and `parse_error` |
| `loan_records` | Normalized loan data | Indexed by `loan_id`, `borrower_id` |
| `validation_rules` | Config-driven validation rules | `active` flag enables/disables without code changes |
| `exceptions` | Validation failures | Status workflow: open → in_review → resolved |
| `ai_recommendations` | AI suggestions | Never writes directly to loan data |
| `reviewer_actions` | Human decisions | Links to AI recommendations when used |
| `verified_loan_records` | Approved records with hash chain | `record_hash = SHA256(canonical_data + prev_hash)` |
| `audit_log` | Append-only event history | No UPDATE/DELETE paths exist |

**Hash Chain Design:**
Each loan's verified history forms a chain: `record_hash = SHA256(canonical_json(fields) + prev_hash)`. First record uses genesis string. Recomputing from audit log provides tamper evidence without blockchain complexity.

**Key Indexes:**
- `loan_records(loan_id)` - business key lookups
- `loan_records(borrower_id, original_principal, origination_date)` - duplicate detection
- `exceptions(status, severity)` - review queue filtering
- `audit_log(loan_record_id, created_at)` - timeline queries

## API Design

RESTful API under `/api/v1/` with role-based access control:

| Module | Key Endpoints | Access |
|--------|---------------|--------|
| `auth` | `/login`, `/guest` | Public |
| `uploads` | `POST /uploads`, `GET /uploads/:id` | Operator |
| `loans` | `GET /loans`, `GET /loans/:id` | All (scoped) |
| `exceptions` | `GET /exceptions`, `POST /exceptions/:id/decision` | Reviewer |
| `ai` | `POST /ai/summarize-batch`, `POST /ai/generate-rule` | Reviewer/Operator |
| `verified` | `GET /verified-loans`, `GET /verified-loans/:id/verify-integrity` | Consumer |
| `audit` | `GET /audit/:loanId`, `GET /summary` | All (scoped) |
| `export` | `GET /export/verified-dataset` | Consumer |

**Authentication:**
- Local mode: JWT issued by backend, verified server-side
- Supabase mode: Supabase Auth JWT verified via JWKS or secret
- Role checks enforced on every route via `require_role()` dependency

**Error Handling:**
Standardized envelope: `{error: {code, message, field?, request_id?}}`. Structured logging includes request IDs for traceability.

## Validation Engine

Config-driven rule interpreter - rules are data, not hardcoded logic:

**Rule Types:**
- `required` - Field presence check
- `regex` - Pattern matching (email, state codes, etc.)
- `range` - Numeric bounds (interest rates, balances)
- `date_order` - Temporal consistency (maturity > origination)
- `cross_field` - Multi-field logic (status vs days past due)
- `duplicate` - Key combination uniqueness
- `staleness` - Data freshness (last_updated_at thresholds)
- `cross_file` - loan_tape vs servicer_update conflicts

**Execution Flow:**
1. Load active `validation_rules` from database
2. Apply per-row rules via dispatch table
3. Run batch-level duplicate detection
4. Compare against servicer_update rows if present
5. Return structured `Exception_` objects for storage

Adding a new rule requires only a database insert (if using existing rule_type) or code addition (for new rule_type). This enables AI-generated rules to function immediately.

## AI Feature

Groq integration with human-in-the-loop controls and resilience patterns:

**Design Rules:**
- AI writes only to `ai_recommendations` table, never to loan data
- Every call logged with prompt, model, response, confidence, latency
- Human decision required for any data mutation
- AI unavailable state explicitly handled, never blocks workflow

**Resilience:**
- 10s hard timeout on all Groq calls
- Exponential backoff, max 2 retries (5xx/timeout only)
- Fallback to "AI unavailable, continue manually" UI state
- Per-user rate limiting on `/ai/*` endpoints

**Capabilities:**
- Exception explanation with confidence scoring
- Suggested corrections with reasoning
- Batch summarization for review triage
- Natural-language to validation rule generation

**Mock Mode:**
`GROQ_MOCK=true` uses deterministic fixtures for offline demos, identical interface to real API calls.

## Audit Trail

Append-only audit log with hash-chained integrity verification:

**Event Types:**
- `file.uploaded`, `loan_record.imported`, `validation.executed`
- `exception.created`, `ai.recommendation_generated`
- `reviewer.comment_added`, `field.edited`
- `loan.approved`, `loan.rejected`, `loan.correction_requested`
- `verified_record.created`

**Integrity Verification:**
- `audit_log` is append-only at application layer
- Verified records include hash chain linking each to previous
- `GET /verified-loans/:id/verify-integrity` recomputes chain
- Any tampering breaks the chain and is detectable

**Access Control:**
- Server-side role checks on every endpoint
- Service-role key never exposed to frontend
- All actions attributed to `actor_id` in audit log

## Trade-offs

**Performance vs Simplicity:**
- Chose FastAPI `BackgroundTasks` over Celery/Redis for ingestion
- Rationale: 5,000-row dataset doesn't need message broker overhead
- Impact: Serverless deployments may complete ingestion synchronously

**Security Scope:**
- Implemented: JWT auth, RBAC, parameterized queries, input validation
- Explicitly out of scope (per brief): Penetration testing, encryption at rest, SOC2, WAF
- Rationale: Bounded by hackathon scope and synthetic data
- Documented as conscious decision, not gap

**Scalability Limits:**
- Current design handles: thousands of loans, handful of concurrent reviewers
- Would need rework at 10-100x: Real queue system, Supabase Pro tier, AI call batching
- Free-tier constraints: 500MB DB, 1GB storage, 7-day auto-pause

**AI Control:**
- Strict separation: AI advises, humans decide
- No silent data mutation by AI
- Confidence scores and full metadata on every suggestion
- Rejected AI suggestions logged alongside accepted ones

**Data Storage:**
- Supabase Storage for source files (lineage)
- PostgreSQL for structured data
- JSONB for flexible fields (raw rows, AI responses)
- No automated backups on free tier (mitigated by pre-submission export)

For detailed implementation specifications, see:
- `docs/Loan_Data_Verification_Copilot_Master_Plan.md` - Build strategy and data flow
- `docs/Requirements_SRS_and_AI_Build_Prompt.md` - Functional requirements and database schema
- `docs/Production_Readiness_Engineering_Playbook.md` - Engineering standards and testing strategy