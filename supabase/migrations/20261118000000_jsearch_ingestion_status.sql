-- Monthly JSearch quota counter used by Backend/app/ingest_postings.py.
create table if not exists public.jsearch_usage (
  month text primary key,
  requests integer not null default 0
);
alter table public.jsearch_usage enable row level security;
revoke all on public.jsearch_usage from anon, authenticated;
grant select, insert, update on public.jsearch_usage to service_role;

create or replace function public.bump_jsearch_usage(p_month text)
returns void language sql set search_path = '' as $$
  insert into public.jsearch_usage (month, requests) values (p_month, 1)
  on conflict (month) do update set requests = public.jsearch_usage.requests + 1;
$$;
revoke all on function public.bump_jsearch_usage(text) from public, anon, authenticated;
grant execute on function public.bump_jsearch_usage(text) to service_role;

-- One row per scheduled or manual ingestion run, shown read-only in the admin console.
create table if not exists public.ingestion_runs (
  id uuid primary key default gen_random_uuid(),
  started_at timestamptz not null default now(),
  finished_at timestamptz null,
  trigger text not null default 'manual',
  status text not null default 'running' check (status in ('running', 'success', 'partial', 'failed')),
  requests_used integer not null default 0,
  postings_stored integer not null default 0,
  roles jsonb not null default '[]'::jsonb,
  error text null
);
create index if not exists ingestion_runs_started_at_idx on public.ingestion_runs (started_at desc);
alter table public.ingestion_runs enable row level security;
revoke all on public.ingestion_runs from anon, authenticated;
grant select, insert, update on public.ingestion_runs to service_role;
