-- Run this if 002_supabase_profiles.sql was applied before the storage-bucket
-- section was added.
insert into storage.buckets (id, name, public)
values ('loan-uploads', 'loan-uploads', false)
on conflict (id) do nothing;
