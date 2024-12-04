-- Drop existing policies that might cause recursion
drop policy if exists "Members can manage members in their organizations" on organization_members;
drop policy if exists "Admins can manage members in their organizations" on organization_members;

-- Create new, more specific policies for organization members
create policy "Members can view organization members"
    on organization_members for select
    using (
        exists (
            select 1 from organization_members as om
            where om.organization_id = organization_members.organization_id
            and om.user_id = auth.uid()
        )
    );

create policy "Admins can insert organization members"
    on organization_members for insert
    with check (
        exists (
            select 1 from organization_members as om
            where om.organization_id = organization_members.organization_id
            and om.user_id = auth.uid()
            and om.role = 'admin'
        )
    );

create policy "Admins can update organization members"
    on organization_members for update
    using (
        exists (
            select 1 from organization_members as om
            where om.organization_id = organization_members.organization_id
            and om.user_id = auth.uid()
            and om.role = 'admin'
        )
    );

create policy "Admins can delete organization members"
    on organization_members for delete
    using (
        exists (
            select 1 from organization_members as om
            where om.organization_id = organization_members.organization_id
            and om.user_id = auth.uid()
            and om.role = 'admin'
        )
    );