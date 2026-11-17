create table if not exists public.job_postings (
  id uuid primary key default gen_random_uuid(),
  job_role_id uuid null references public.job_roles (id) on delete set null,
  role_key text not null,
  provider text not null,
  external_id text not null,
  title text not null,
  company text null,
  description text null,
  location text null,
  posted_at timestamp with time zone null,
  apply_url text null,
  publisher text null,
  country text null,
  raw_data jsonb not null default '{}'::jsonb,
  fetched_at timestamp with time zone not null default now(),
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint job_postings_provider_external_id_key unique (provider, external_id)
);

create index if not exists job_postings_role_posted_at_idx
  on public.job_postings (job_role_id, posted_at desc);

create index if not exists job_postings_role_key_posted_at_idx
  on public.job_postings (role_key, posted_at desc);

alter table public.job_postings enable row level security;

drop policy if exists "Anyone can read job postings" on public.job_postings;
create policy "Anyone can read job postings"
  on public.job_postings
  for select
  to anon, authenticated
  using (true);

grant select on public.job_postings to anon, authenticated;
