-- Create a function to move files in storage
create or replace function move_files_in_storage()
returns table (
    file_name text,
    old_path text,
    new_path text,
    status text
)
language plpgsql
security definer
as $$
declare
    file_record record;
    new_path text;
    default_org_id uuid := '00000000-0000-0000-0000-000000000000';
begin
    create temp table if not exists migration_log (
        file_name text,
        old_path text,
        new_path text,
        status text
    );

    -- First ensure the organization folders exist
    insert into storage.objects (
        bucket_id,
        name,
        owner,
        created_at,
        updated_at,
        version,
        metadata
    ) values 
    ('files', 'organizations/.keep', auth.uid(), now(), now(), '1', '{}'),
    ('files', 'organizations/' || default_org_id || '/.keep', auth.uid(), now(), now(), '1', '{}')
    on conflict (bucket_id, name) do nothing;

    -- Move each file
    for file_record in 
        select * from storage.objects 
        where bucket_id = 'files'
        and name not like 'organizations/%'
        and name not like '%.keep'
    loop
        new_path := 'organizations/' || default_org_id || '/' || file_record.name;
        
        begin
            -- Move the file using storage.copy_object
            insert into storage.objects (
                bucket_id,
                name,
                owner,
                created_at,
                updated_at,
                version,
                metadata
            )
            select
                bucket_id,
                new_path,
                owner,
                created_at,
                updated_at,
                version,
                metadata
            from storage.objects
            where id = file_record.id
            returning name into new_path;

            -- If copy successful, delete the old object
            delete from storage.objects where id = file_record.id;

            -- Log successful move
            insert into migration_log values (
                file_record.name,
                file_record.name,
                new_path,
                'moved'
            );

        exception when others then
            -- Log failed move
            insert into migration_log values (
                file_record.name,
                file_record.name,
                new_path,
                'failed: ' || SQLERRM
            );
        end;
    end loop;

    return query select * from migration_log;
    
    drop table migration_log;
end;
$$;

-- Execute the move operation and get results
select * from move_files_in_storage();

-- Clean up
drop function move_files_in_storage();