-- Drop existing job policy
drop policy if exists "Enable access for organization members" on jobs;

-- Create separate policies for read and write operations
create policy "Organization members can read jobs"
    on jobs for select
    using (is_organization_member(organization_id));

create policy "Organization members can insert jobs"
    on jobs for insert
    with check (
        -- For new jobs, organization_id must match the user's organization
        organization_id = get_organization_from_token()
    );

create policy "Organization members can update their jobs"
    on jobs for update
    using (is_organization_member(organization_id));

create policy "Organization members can delete their jobs"
    on jobs for delete
    using (is_organization_member(organization_id));