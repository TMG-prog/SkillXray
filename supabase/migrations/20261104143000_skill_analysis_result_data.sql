alter table public.skill_analyses
  add column if not exists result_data jsonb;

create index if not exists skill_analyses_user_created_at_idx
  on public.skill_analyses (user_id, created_at desc);

alter table public.skill_analyses enable row level security;

drop policy if exists "Users can read their own skill analyses" on public.skill_analyses;
create policy "Users can read their own skill analyses"
  on public.skill_analyses
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "Users can create their own skill analyses" on public.skill_analyses;
create policy "Users can create their own skill analyses"
  on public.skill_analyses
  for insert
  to authenticated
  with check (
    auth.uid() = user_id
    and exists (
      select 1
      from public.resumes
      where resumes.id = resume_id
        and resumes.user_id = auth.uid()
    )
  );

grant select, insert on public.skill_analyses to authenticated;

notify pgrst, 'reload schema';
