-- Local development variant — used only when DATABASE_MODE=local (see app/config.py).
-- Identical to 001_init_supabase.sql except profiles.id is a standalone
-- primary key backed by app_users, instead of referencing Supabase's
-- managed auth.users. This lets the whole ingestion/validation/audit
-- pipeline be built and tested against a real Postgres without requiring
-- live Supabase credentials. Swapping to Supabase in production means
-- applying 001_init_supabase.sql instead and pointing the backend's
-- SUPABASE_* env vars at your project — no application code changes.

create table app_users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  password_hash text not null,
  created_at timestamptz default now()
);

create table profiles (
  id uuid primary key references app_users(id),
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
  loan_type text,
  origination_date date,
  maturity_date date,
  original_principal numeric,
  current_balance numeric,
  interest_rate numeric,
  term_months int,
  borrower_state text,
  loan_purpose text,
  credit_grade text,
  employment_length text,
  income_band text,
  payment_status text,
  days_past_due int,
  servicer_name text,
  last_payment_date date,
  last_updated_at timestamptz,
  document_status text,
  source_system text,
  source_batch_id uuid references upload_batches(id),
  version int not null default 1,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index idx_loan_records_loan_id on loan_records (loan_id);
create index idx_loan_records_dup_combo on loan_records (borrower_id, original_principal, origination_date);

create table servicer_updates (
  id uuid primary key default gen_random_uuid(),
  loan_id text not null,
  field_name text not null,
  batch_value text,
  servicer_value text,
  resolved_value text,
  resolved_by uuid references profiles(id),
  batch_id uuid references upload_batches(id)
);

create table document_manifest (
  id uuid primary key default gen_random_uuid(),
  loan_id text not null,
  document_status text,
  batch_id uuid references upload_batches(id)
);

create table validation_rules (
  id uuid primary key default gen_random_uuid(),
  rule_key text not null unique,
  field text,
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
  field text,
  detail jsonb,
  created_at timestamptz default now()
);
create index idx_exceptions_status_severity on exceptions (status, severity);

create table exception_comments (
  id uuid primary key default gen_random_uuid(),
  exception_id uuid references exceptions(id),
  author_id uuid references profiles(id),
  body text,
  created_at timestamptz default now()
);

create table ai_recommendations (
  id uuid primary key default gen_random_uuid(),
  exception_id uuid references exceptions(id),
  prompt text not null,
  model text not null,
  response_json jsonb not null,
  confidence numeric,
  latency_ms int,
  accepted boolean,
  reviewed_by uuid references profiles(id),
  created_at timestamptz default now()
);

create table reviewer_actions (
  id uuid primary key default gen_random_uuid(),
  exception_id uuid references exceptions(id),
  reviewer_id uuid references profiles(id) not null,
  action text not null check (action in ('approve','reject','edit','request_correction')),
  field_changed text,
  old_value text,
  new_value text,
  ai_recommendation_id uuid references ai_recommendations(id),
  created_at timestamptz default now()
);

create table verified_loan_records (
  id uuid primary key default gen_random_uuid(),
  loan_record_id uuid references loan_records(id),
  canonical_data jsonb not null,
  validation_result jsonb not null,
  reviewer_decision jsonb,
  ai_recommendation_id uuid references ai_recommendations(id),
  record_hash text not null,
  prev_hash text,
  verified_by uuid references profiles(id),
  verified_at timestamptz default now()
);

create table audit_log (
  id uuid primary key default gen_random_uuid(),
  event_type text not null,
  loan_record_id uuid references loan_records(id),
  actor_id uuid references profiles(id),
  detail jsonb,
  record_hash text,
  created_at timestamptz default now()
);
create index idx_audit_log_loan_time on audit_log (loan_record_id, created_at);
