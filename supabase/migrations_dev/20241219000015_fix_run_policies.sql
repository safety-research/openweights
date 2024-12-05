-- Drop existing run policy
drop policy if exists "Enable access for organization members" on runs;

-- Create separate policies for read and write operations
create policy "Organization members can read runs"
    on runs for select
    using (
        exists (
            select 1
            from jobs j
            where j.id = runs.job_id
            and (
                is_organization_member(j.organization_id)
                or
                (
                    auth.jwt() ? 'is_service_account' 
                    and (auth.jwt()->>'organization_id')::uuid = j.organization_id
                )
            )
        )
    );

create policy "Organization members can insert runs"
    on runs for insert
    with check (
        exists (
            select 1
            from jobs j
            where j.id = job_id
            and (
                is_organization_member(j.organization_id)
                or
                (
                    auth.jwt() ? 'is_service_account' 
                    and (auth.jwt()->>'organization_id')::uuid = j.organization_id
                )
            )
        )
    );

create policy "Organization members can update runs"
    on runs for update
    using (
        exists (
            select 1
            from jobs j
            where j.id = runs.job_id
            and (
                is_organization_member(j.organization_id)
                or
                (
                    auth.jwt() ? 'is_service_account' 
                    and (auth.jwt()->>'organization_id')::uuid = j.organization_id
                )
            )
        )
    );

create policy "Organization members can delete runs"
    on runs for delete
    using (
        exists (
            select 1
            from jobs j
            where j.id = runs.job_id
            and (
                is_organization_member(j.organization_id)
                or
                (
                    auth.jwt() ? 'is_service_account' 
                    and (auth.jwt()->>'organization_id')::uuid = j.organization_id
                )
            )
        )
    );