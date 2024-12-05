-- First, drop all existing policies that might cause recursion
drop policy if exists "Members can view their organizations" on organizations;
drop policy if exists "Admins can update their organizations" on organizations;
drop policy if exists "Enable read access for organization members" on organization_members;
drop policy if exists "Enable write access for organization admins" on organization_members;
drop policy if exists "Members can manage jobs in their organizations" on jobs;
drop policy if exists "Members can manage runs in their organizations" on runs;
drop policy if exists "Members can manage workers in their organizations" on worker;
drop policy if exists "Members can manage events in their organizations" on events;
drop policy if exists "Members can view their organization's API keys" on third_party_api_keys;
drop policy if exists "Admins can manage their organization's API keys" on third_party_api_keys;

-- Create a function to check organization membership
create or replace function is_organization_member(org_id uuid)
returns boolean as $$
begin
  return exists (
    select 1
    from organization_members
    where organization_id = org_id
    and user_id = auth.uid()
  );
end;
$$ language plpgsql security definer;

-- Create a function to check organization admin status
create or replace function is_organization_admin(org_id uuid)
returns boolean as $$
begin
  return exists (
    select 1
    from organization_members
    where organization_id = org_id
    and user_id = auth.uid()
    and role = 'admin'
  );
end;
$$ language plpgsql security definer;

-- Organizations policies
create policy "Enable read access for organization members"
    on organizations for select
    using (is_organization_member(id));

create policy "Enable write access for organization admins"
    on organizations for all
    using (is_organization_admin(id));

-- Organization members policies
create policy "Enable read access for members"
    on organization_members for select
    using (is_organization_member(organization_id));

create policy "Enable write access for admins"
    on organization_members for all
    using (is_organization_admin(organization_id));

-- Jobs policies
create policy "Enable access for organization members"
    on jobs for all
    using (is_organization_member(organization_id));

-- Runs policies (through jobs)
create policy "Enable access for organization members"
    on runs for all
    using (
        exists (
            select 1
            from jobs
            where jobs.id = runs.job_id
            and is_organization_member(jobs.organization_id)
        )
    );

-- Workers policies
create policy "Enable access for organization members"
    on worker for all
    using (is_organization_member(organization_id));

-- Events policies (through runs and jobs)
create policy "Enable access for organization members"
    on events for all
    using (
        exists (
            select 1
            from runs
            join jobs on jobs.id = runs.job_id
            where runs.id = events.run_id
            and is_organization_member(jobs.organization_id)
        )
    );

-- Third-party API keys policies
create policy "Enable read for members"
    on third_party_api_keys for select
    using (is_organization_member(organization_id));

create policy "Enable write for admins"
    on third_party_api_keys for all
    using (is_organization_admin(organization_id));