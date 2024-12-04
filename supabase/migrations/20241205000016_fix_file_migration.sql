-- Function to ensure folder exists and migrate files
create or replace function migrate_files_to_default_organization_v2()
returns void
language plpgsql
security definer
as $$
declare
    file_record record;
    new_path text;
    default_org_id uuid := '00000000-0000-0000-0000-000000000000';
begin
    -- Create the organizations folder if it doesn't exist
    insert into storage.objects (bucket_id, name, owner, created_at, updated_at, version)
    values ('files', 'organizations/.keep', auth.uid(), now(), now(), '1')
    on conflict do nothing;

    -- Create the default organization folder if it doesn't exist
    insert into storage.objects (bucket_id, name, owner, created_at, updated_at, version)
    values ('files', 'organizations/' || default_org_id || '/.keep', auth.uid(), now(), now(), '1')
    on conflict do nothing;

    -- Loop through all files that are not in an organizations folder
    for file_record in 
        select name, id, owner, created_at, updated_at, version, metadata
        from storage.objects
        where bucket_id = 'files' 
        and name not like 'organizations/%'
        and name not like '%.keep'
    loop
        -- Generate new path
        new_path := 'organizations/' || default_org_id || '/' || file_record.name;

        -- Insert file with new path
        insert into storage.objects (
            bucket_id, 
            name, 
            owner, 
            created_at, 
            updated_at, 
            version, 
            metadata
        )
        values (
            'files',
            new_path,
            file_record.owner,
            file_record.created_at,
            file_record.updated_at,
            file_record.version,
            file_record.metadata
        );

        -- Delete old file entry
        delete from storage.objects 
        where id = file_record.id;

        raise notice 'Moved file % to %', file_record.name, new_path;
    end loop;
end;
$$;

-- Execute the migration function
select migrate_files_to_default_organization_v2();

-- Drop the migration functions as they're no longer needed
drop function if exists migrate_files_to_default_organization();
drop function migrate_files_to_default_organization_v2();