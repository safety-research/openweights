-- Function to migrate existing files to default organization
create or replace function migrate_files_to_default_organization()
returns void
language plpgsql
security definer
as $$
declare
    file_record record;
    new_path text;
    default_org_id uuid := '00000000-0000-0000-0000-000000000000';
begin
    -- Loop through all files that are not in an organizations folder
    for file_record in 
        select name, id
        from storage.objects
        where (storage.foldername(name))[1] != 'organizations'
    loop
        -- Generate new path
        new_path := 'organizations/' || default_org_id || '/' || 
                    case 
                        when position('/' in file_record.name) > 0 
                        then substring(file_record.name from position('/' in file_record.name) + 1)
                        else file_record.name
                    end;

        -- Move file to new location
        update storage.objects
        set name = new_path
        where id = file_record.id;

        raise notice 'Moved file % to %', file_record.name, new_path;
    end loop;
end;
$$;

-- Execute the migration function
select migrate_files_to_default_organization();

-- Drop the migration function as it's no longer needed
drop function migrate_files_to_default_organization();