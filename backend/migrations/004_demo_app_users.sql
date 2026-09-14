-- Run after the Supabase migrations when using LendProof-managed demo login.
-- This deliberately does not create or contact Supabase Auth users.

create table if not exists app_users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  password_hash text not null,
  created_at timestamptz default now()
);

-- Supabase's original profile migration links profiles to auth.users. The
-- application now owns these fixed demo identities, so remove that optional
-- Auth-only dependency while preserving existing profile and application data.
alter table profiles drop constraint if exists profiles_id_fkey;

insert into app_users (id, email, password_hash)
values
  ('00000000-0000-0000-0000-000000000001', 'operator@testmail.dev', encode(hmac('DemoPass123!', 'loan-copilot-static-dev-salt', 'sha256'), 'hex')),
  ('00000000-0000-0000-0000-000000000002', 'reviewer@testmail.dev', encode(hmac('DemoPass123!', 'loan-copilot-static-dev-salt', 'sha256'), 'hex')),
  ('00000000-0000-0000-0000-000000000003', 'consumer@testmail.dev', encode(hmac('DemoPass123!', 'loan-copilot-static-dev-salt', 'sha256'), 'hex'))
on conflict (email) do update
set password_hash = excluded.password_hash;

insert into profiles (id, role, name)
values
  ('00000000-0000-0000-0000-000000000001', 'operator', 'Dana Operator'),
  ('00000000-0000-0000-0000-000000000002', 'reviewer', 'Rae Reviewer'),
  ('00000000-0000-0000-0000-000000000003', 'consumer', 'Cam Consumer')
on conflict (id) do update
set role = excluded.role, name = excluded.name;
