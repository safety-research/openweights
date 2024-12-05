-- First drop all policies that use these functions
drop policy if exists "Enable read access for organization members" on organizations;
drop policy if exists "Enable write access for organization admins" on organizations;
drop policy if exists "Enable read access for members" on organization_members;
drop policy if exists "Enable write access for admins" on organization_members;
drop policy if exists "Enable access for organization members" on jobs;
drop policy if exists "Enable access for organization members" on runs;
drop policy if exists "Enable access for organization members" on worker;
drop policy if exists "Enable access for organization members" on events;
drop policy if exists "Enable read for members" on third_party_api_keys;
drop policy if exists "Enable write for admins" on third_party_api_keys;

-- Now we can safely drop the functions
drop function if exists public.is_organization_member(uuid);
drop function if exists public.is_organization_admin(uuid);

-- Recreate is_organization_member function with explicit column references
create or replace function is_organization_member(org_id uuid)
returns boolean as $$
begin
  return exists (
    select 1
    from organization_members om
    where om.organization_id = org_id
    and om.user_id = auth.uid()
  );
end;
$$ language plpgsql security definer;

-- Recreate is_organization_admin function with explicit column references
create or replace function is_organization_admin(org_id uuid)
returns boolean as $$
begin
  return exists (
    select 1
    from organization_members om
    where om.organization_id = org_id
    and om.user_id = auth.uid()
    and om.role = 'admin'
  );
end;
$$ language plpgsql security definer;

-- Recreate policies with explicit table references
create policy "Enable read access for organization members"
    on organizations for select
    using (is_organization_member(id));

create policy "Enable write access for organization admins"
    on organizations for all
    using (is_organization_admin(id));

create policy "Enable read access for members"
    on organization_members for select
    using (is_organization_member(organization_id));

create policy "Enable write access for admins"
    on organization_members for all
    using (is_organization_admin(organization_id));

create policy "Enable access for organization members"
    on jobs for all
    using (is_organization_member(organization_id));

create policy "Enable access for organization members"
    on runs for all
    using (
        exists (
            select 1
            from jobs j
            where j.id = runs.job_id
            and is_organization_member(j.organization_id)
        )
    );

create policy "Enable access for organization members"
    on worker for all
    using (is_organization_member(organization_id));

create policy "Enable access for organization members"
    on events for all
    using (
        exists (
            select 1
            from runs r
            join jobs j on j.id = r.job_id
            where r.id = events.run_id
            and is_organization_member(j.organization_id)
        )
    );

create policy "Enable read for members"
    on third_party_api_keys for select
    using (is_organization_member(organization_id));

create policy "Enable write for admins"
    on third_party_api_keys for all
    using (is_organization_admin(organization_id));

-- Grant execute permissions
grant execute on function public.is_organization_member(uuid) to authenticated;
grant execute on function public.is_organization_admin(uuid) to authenticated;