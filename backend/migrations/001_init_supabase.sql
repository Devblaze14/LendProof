-- Authoritative schema for Supabase deployment.
-- Apply via the Supabase SQL editor or CLI migrations.
-- profiles.id references Supabase's managed auth.users — do not create a
-- separate users table when deploying to Supabase.

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

-- Enable RLS, default-deny for anon. Backend uses the service-role key and
-- is the only writer for this version of the app (see Production Readiness
-- Playbook, Hat 3: "if you later let the frontend query Supabase directly
-- for reads, add explicit per-role SELECT policies keyed off profiles.role").
alter table profiles enable row level security;
alter table upload_batches enable row level security;
alter table raw_loan_rows enable row level security;
alter table loan_records enable row level security;
alter table servicer_updates enable row level security;
alter table document_manifest enable row level security;
alter table validation_rules enable row level security;
alter table exceptions enable row level security;
alter table exception_comments enable row level security;
alter table ai_recommendations enable row level security;
alter table reviewer_actions enable row level security;
alter table verified_loan_records enable row level security;
alter table audit_log enable row level security;
