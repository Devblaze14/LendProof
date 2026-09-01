-- Run after 001_init_supabase.sql. Creates exactly one application profile
-- per Supabase Auth user and keeps the service-role key out of user flows.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, role, name)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'role', 'consumer'),
    nullif(new.raw_user_meta_data ->> 'name', '')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Existing Auth users created before this migration receive a consumer profile.
insert into public.profiles (id, role, name)
select id, 'consumer', coalesce(raw_user_meta_data ->> 'name', email)
from auth.users
on conflict (id) do nothing;

-- Private storage for raw CSV lineage. Writes are made only by the backend
-- service role; no browser policy is added.
insert into storage.buckets (id, name, public)
values ('loan-uploads', 'loan-uploads', false)
on conflict (id) do nothing;
