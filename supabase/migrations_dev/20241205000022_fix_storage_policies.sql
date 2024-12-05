-- Drop existing policies to avoid conflicts
drop policy if exists "Organization members can read their files" on storage.objects;
drop policy if exists "Organization members can upload files" on storage.objects;
drop policy if exists "Organization members can delete their files" on storage.objects;

-- Enable RLS on storage.objects
alter table storage.objects enable row level security;

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
                where organization_id = uuid(split_part(name, '/', 2))
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
                where organization_id = uuid(split_part(name, '/', 2))
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
                where organization_id = uuid(split_part(name, '/', 2))
                and user_id = auth.uid()
                and role = 'admin'
            )
        )
    )
);