alter table public.skill_analyses enable row level security;

drop policy if exists "Users can read their own skill analyses" on public.skill_analyses;
create policy "Users can read their own skill analyses"
  on public.skill_analyses
  for select
  to authenticated
  using (user_id = (select auth.uid()));

drop policy if exists "Users can create their own skill analyses" on public.skill_analyses;
create policy "Users can create their own skill analyses"
  on public.skill_analyses
  for insert
  to authenticated
  with check (
    user_id = (select auth.uid())
    and exists (
      select 1
      from public.resumes as owned_resume
      where owned_resume.id = skill_analyses.resume_id
        and owned_resume.user_id = (select auth.uid())
    )
  );

grant select, insert on public.skill_analyses to authenticated;

notify pgrst, 'reload schema';
