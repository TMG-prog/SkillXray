-- Membership is managed by a project owner, never by the browser.
create table if not exists public.admin_members (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);
alter table public.admin_members enable row level security;
revoke all on public.admin_members from anon, authenticated;
grant select on public.admin_members to service_role;

-- ESCO changes are staged until an operator rebuilds the model artifacts.
create table if not exists public.admin_taxonomy_changes (
  id uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('skill', 'occupation', 'skill_relation', 'broader_relation')),
  operation text not null check (operation in ('upsert', 'delete')),
  record_key text not null,
  record jsonb not null default '{}'::jsonb,
  updated_by uuid not null references auth.users(id),
  updated_at timestamptz not null default now(),
  unique (kind, record_key)
);
alter table public.admin_taxonomy_changes enable row level security;
revoke all on public.admin_taxonomy_changes from anon, authenticated;
grant all on public.admin_taxonomy_changes to service_role;

create table if not exists public.learning_resources (
  id uuid primary key default gen_random_uuid(),
  title text not null check (length(trim(title)) > 0),
  provider text not null check (length(trim(provider)) > 0),
  url text not null check (url ~* '^https?://'),
  keywords text[] not null check (cardinality(keywords) > 0),
  priority integer not null default 100,
  published boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.learning_resources enable row level security;
drop policy if exists "Read published learning resources" on public.learning_resources;
create policy "Read published learning resources" on public.learning_resources
  for select to anon, authenticated using (published);
grant select on public.learning_resources to anon, authenticated;
grant all on public.learning_resources to service_role;

create or replace function public.admin_set_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
drop trigger if exists admin_taxonomy_updated_at on public.admin_taxonomy_changes;
create trigger admin_taxonomy_updated_at before update on public.admin_taxonomy_changes
  for each row execute function public.admin_set_updated_at();
drop trigger if exists learning_resources_updated_at on public.learning_resources;
create trigger learning_resources_updated_at before update on public.learning_resources
  for each row execute function public.admin_set_updated_at();

grant select, insert, update, delete on public.job_roles, public.profiles, public.job_postings to service_role;

insert into public.learning_resources (title, provider, url, keywords, priority, published)
select seed.title, seed.provider, seed.url, seed.keywords, seed.priority, true
from (values
  ('Python for Everybody Specialization', 'Coursera · University of Michigan', 'https://www.coursera.org/specializations/python', array['python'], 10),
  ('SQL for Data Science', 'Coursera · University of California, Davis', 'https://www.coursera.org/learn/sql-for-data-science', array['sql','database'], 20),
  ('Docker for the Absolute Beginner', 'KodeKloud', 'https://kodekloud.com/courses/docker-for-the-absolute-beginner-course/', array['docker'], 30),
  ('Certified Kubernetes Application Developer (CKAD)', 'Linux Foundation', 'https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/', array['kubernetes'], 40),
  ('Terraform Associate learning path', 'HashiCorp', 'https://developer.hashicorp.com/terraform/tutorials/certification-003', array['terraform'], 50),
  ('AWS Cloud Practitioner Essentials', 'AWS Skill Builder', 'https://skillbuilder.aws/learn', array['aws','amazon web services'], 60),
  ('Azure Fundamentals learning path', 'Microsoft Learn', 'https://learn.microsoft.com/training/paths/azure-fundamentals-describe-cloud-concepts/', array['azure'], 70),
  ('Google Cloud learning paths', 'Google Cloud Skills Boost', 'https://www.cloudskillsboost.google/paths', array['google cloud','gcp'], 80),
  ('Google Project Management Professional Certificate', 'Coursera · Google', 'https://www.coursera.org/professional-certificates/google-project-management', array['project management'], 90),
  ('Google Data Analytics Professional Certificate', 'Coursera · Google', 'https://www.coursera.org/professional-certificates/google-data-analytics', array['data analytics','data analysis'], 100),
  ('Machine Learning Specialization', 'Coursera · DeepLearning.AI and Stanford', 'https://www.coursera.org/specializations/machine-learning-introduction', array['machine learning','artificial intelligence','deep learning'], 110)
) as seed(title, provider, url, keywords, priority)
where not exists (select 1 from public.learning_resources r where r.url = seed.url);

insert into storage.buckets (id, name, public)
values ('admin-datasets', 'admin-datasets', false)
on conflict (id) do update set public = false;
