alter table public.learning_resources
  add column if not exists trust_signals text[] not null default '{}',
  add column if not exists trust_evidence_url text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'learning_resources_trust_signals_allowed'
      and conrelid = 'public.learning_resources'::regclass
  ) then
    alter table public.learning_resources
      add constraint learning_resources_trust_signals_allowed
      check (trust_signals <@ array[
        'nita_accredited',
        'university_backed',
        'free_open_access',
        'industry_certification'
      ]::text[]);
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'learning_resources_trust_evidence_url_valid'
      and conrelid = 'public.learning_resources'::regclass
  ) then
    alter table public.learning_resources
      add constraint learning_resources_trust_evidence_url_valid
      check (
        (cardinality(trust_signals) = 0 or trust_evidence_url is not null)
        and (trust_evidence_url is null or trust_evidence_url ~* '^https?://[^[:space:]]+$')
      );
  end if;
end $$;

update public.learning_resources
set trust_signals = array['university_backed'],
    trust_evidence_url = url
where url in (
  'https://www.coursera.org/specializations/python',
  'https://www.coursera.org/learn/sql-for-data-science',
  'https://www.coursera.org/specializations/machine-learning-introduction'
);

update public.learning_resources
set trust_signals = array['industry_certification'],
    trust_evidence_url = url
where url in (
  'https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/',
  'https://developer.hashicorp.com/terraform/tutorials/certification-003'
);

update public.learning_resources
set trust_signals = array['free_open_access'],
    trust_evidence_url = url
where url = 'https://learn.microsoft.com/training/paths/azure-fundamentals-describe-cloud-concepts/';
