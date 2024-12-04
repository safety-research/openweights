-- Drop existing storage policies
drop policy if exists "Organization members can read their files" on storage.objects;
drop policy if exists "Organization members can upload files" on storage.objects;
drop policy if exists "Organization members can delete their files" on storage.objects;

-- Enable RLS on storage.objects
alter table storage.objects enable row level security;

-- Function to extract organization ID from storage path
create or replace function storage.get_path_organization_id(path text)
returns uuid
language plpgsql
as $$
declare
    parts text[];
    org_id uuid;
begin
    -- Split path into parts
    parts := string_to_array(path, '/');
    
    -- Check if path starts with 'organizations'
    if parts[1] != 'organizations' then
        return null;
    end if;
    
    -- Try to convert second part to UUID
    begin
        org_id := parts[2]::uuid;
        return org_id;
    exception when others then
        return null;
    end;
end;
$$;

-- Policy for reading files:
create policy "Organization members can read their files"
on storage.objects for select
using (
    bucket_id = 'files' 
    and (
        -- Allow access to .keep files
        name like '%.keep'
        or (
            -- Check if file is in an organization folder and user is a member
            name like 'organizations/%'
            and exists (
                select 1
                from public.organization_members
                where organization_id = storage.get_path_organization_id(name)
                and user_id = auth.uid()
            )
        )
    )
);

-- Policy for inserting files:
create policy "Organization members can upload files"
on storage.objects for insert
with check (
    bucket_id = 'files'
    and (
        -- Allow .keep files
        name like '%.keep'
        or (
            -- Check if file is in an organization folder and user is a member
            name like 'organizations/%'
            and exists (
                select 1
                from public.organization_members
                where organization_id = storage.get_path_organization_id(name)
                and user_id = auth.uid()
            )
        )
    )
);

-- Policy for updating files:
create policy "Organization members can update their files"
on storage.objects for update
using (
    bucket_id = 'files'
    and (
        -- Allow .keep files
        name like '%.keep'
        or (
            -- Check if file is in an organization folder and user is a member
            name like 'organizations/%'
            and exists (
                select 1
                from public.organization_members
                where organization_id = storage.get_path_organization_id(name)
                and user_id = auth.uid()
            )
        )
    )
);

-- Policy for deleting files:
create policy "Organization members can delete their files"
on storage.objects for delete
using (
    bucket_id = 'files'
    and (
        -- Allow .keep files
        name like '%.keep'
        or (
            -- Check if file is in an organization folder and user is an admin
            name like 'organizations/%'
            and exists (
                select 1
                from public.organization_members
                where organization_id = storage.get_path_organization_id(name)
                and user_id = auth.uid()
                and role = 'admin'
            )
        )
    )
);