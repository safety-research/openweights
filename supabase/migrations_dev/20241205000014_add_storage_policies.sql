-- Create storage policies for the files bucket
-- Note: The bucket itself needs to be created manually in the dashboard

-- Drop any existing policies to avoid conflicts
begin;
  drop policy if exists "Organization members can read their files" on storage.objects;
  drop policy if exists "Organization members can upload files" on storage.objects;
  drop policy if exists "Organization members can delete their files" on storage.objects;

  -- Policy for reading files:
  -- Allow if user is member of the organization that owns the file
  create policy "Organization members can read their files"
    on storage.objects for select
    using (
      -- Check if file is in an organization folder
      (storage.foldername(name))[1] = 'organizations'
      and (
        -- User is member of the organization specified in the path
        exists (
          select 1
          from public.organization_members
          where organization_id = uuid((storage.foldername(name))[2])
          and user_id = auth.uid()
        )
      )
    );

  -- Policy for inserting files:
  -- Allow if user is member of the organization and file path matches organization
  create policy "Organization members can upload files"
    on storage.objects for insert
    with check (
      -- Ensure file is being uploaded to an organization folder
      (storage.foldername(name))[1] = 'organizations'
      and (
        -- User is member of the organization specified in the path
        exists (
          select 1
          from public.organization_members
          where organization_id = uuid((storage.foldername(name))[2])
          and user_id = auth.uid()
        )
      )
    );

  -- Policy for deleting files:
  -- Allow if user is admin of the organization that owns the file
  create policy "Organization members can delete their files"
    on storage.objects for delete
    using (
      -- Check if file is in an organization folder
      (storage.foldername(name))[1] = 'organizations'
      and (
        -- User is admin of the organization specified in the path
        exists (
          select 1
          from public.organization_members
          where organization_id = uuid((storage.foldername(name))[2])
          and user_id = auth.uid()
          and role = 'admin'
        )
      )
    );

  -- Create a function to get the correct organization path for file storage
  create or replace function public.get_organization_storage_path(
    org_id uuid,
    filename text
  ) returns text
  language sql
  stable
  as $$
    select 'organizations/' || org_id || '/' || filename;
  $$;

  -- Grant execute permissions
  grant execute on function public.get_organization_storage_path(uuid, text) to authenticated;

commit;