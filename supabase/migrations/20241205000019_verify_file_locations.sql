-- Create a function to list all files in storage
create or replace function list_storage_files()
returns table (
    id bigint,
    name text,
    bucket_id text,
    owner uuid,
    created_at timestamptz,
    updated_at timestamptz,
    last_accessed_at timestamptz,
    metadata jsonb,
    version text,
    size bigint
) 
security definer
language plpgsql
as $$
begin
    return query
    select *
    from storage.objects
    where bucket_id = 'files'
    order by name;
end;
$$;

-- Grant execute permission
grant execute on function list_storage_files() to postgres;

-- Create a function to check and fix file locations
create or replace function verify_and_fix_file_locations()
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

    for file_record in 
        select * from storage.objects 
        where bucket_id = 'files'
        and name not like 'organizations/%'
        and name not like '%.keep'
    loop
        new_path := 'organizations/' || default_org_id || '/' || file_record.name;
        
        begin
            -- Copy the file to new location
            insert into storage.objects (
                bucket_id,
                name,
                owner,
                created_at,
                updated_at,
                version,
                size,
                metadata
            )
            select
                bucket_id,
                new_path,
                owner,
                created_at,
                updated_at,
                version,
                size,
                metadata
            from storage.objects
            where id = file_record.id;

            -- Log successful copy
            insert into migration_log values (
                file_record.name,
                file_record.name,
                new_path,
                'copied'
            );

        exception when others then
            -- Log failed copy
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

-- Execute the verification and get results
select * from verify_and_fix_file_locations();

-- Clean up
drop function verify_and_fix_file_locations();
drop function list_storage_files();