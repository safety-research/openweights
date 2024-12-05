-- Drop all existing policies on organization_members to start fresh
drop policy if exists "Members can view organization members" on organization_members;
drop policy if exists "Admins can insert organization members" on organization_members;
drop policy if exists "Admins can update organization members" on organization_members;
drop policy if exists "Admins can delete organization members" on organization_members;
drop policy if exists "Members can view other members in their organizations" on organization_members;
drop policy if exists "Admins can manage members in their organizations" on organization_members;

-- Create new simplified policies that avoid recursion
create policy "Enable read access for organization members"
    on organization_members for select
    using (auth.uid() = user_id);

create policy "Enable write access for organization admins"
    on organization_members for all
    using (
        auth.uid() in (
            select user_id 
            from organization_members
            where organization_id = organization_members.organization_id
            and role = 'admin'
            and user_id = auth.uid()
        )
    );