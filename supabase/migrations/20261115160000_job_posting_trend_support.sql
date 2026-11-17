alter table public.job_postings
  add column if not exists dedupe_key text;

create index if not exists job_postings_posted_at_idx
  on public.job_postings (posted_at desc);

create index if not exists job_postings_country_posted_at_idx
  on public.job_postings (country, posted_at desc);

create index if not exists job_postings_role_dedupe_key_idx
  on public.job_postings (role_key, dedupe_key)
  where dedupe_key is not null;
