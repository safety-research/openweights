-- Function to get the organization storage path
create or replace function get_file_path(file_id text)
returns text
language sql
stable
as $$
    select 'organizations/00000000-0000-0000-0000-000000000000/' || file_id;
$$;

-- Function to update file references in a JSON object
create or replace function update_file_refs_in_json(data jsonb)
returns jsonb
language plpgsql
as $$
declare
    result jsonb := data;
    file_id text;
begin
    -- Handle direct 'file' key
    if result ? 'file' and (result->>'file' is not null) then
        file_id := result->>'file';
        result := jsonb_set(result, '{file}', to_jsonb(get_file_path(file_id)));
    end if;

    -- Handle input_file_id
    if result ? 'input_file_id' and (result->>'input_file_id' is not null) then
        file_id := result->>'input_file_id';
        result := jsonb_set(result, '{input_file_id}', to_jsonb(get_file_path(file_id)));
    end if;

    -- Handle training_file
    if result ? 'training_file' and (result->>'training_file' is not null) then
        file_id := result->>'training_file';
        result := jsonb_set(result, '{training_file}', to_jsonb(get_file_path(file_id)));
    end if;

    -- Handle test_file
    if result ? 'test_file' and (result->>'test_file' is not null) then
        file_id := result->>'test_file';
        result := jsonb_set(result, '{test_file}', to_jsonb(get_file_path(file_id)));
    end if;

    return result;
end;
$$;

-- Begin the migration
do $$
declare
    r record;
begin
    -- Update runs.log_file
    update runs
    set log_file = get_file_path(log_file)
    where log_file is not null
    and log_file not like 'organizations/%';

    -- Update jobs.outputs
    update jobs
    set outputs = update_file_refs_in_json(outputs)
    where outputs is not null
    and outputs::text not like '%organizations/%';

    -- Update jobs.params
    update jobs
    set params = update_file_refs_in_json(params)
    where params is not null
    and params::text not like '%organizations/%';

    raise notice 'File references migration completed';
end;
$$;

-- Clean up temporary functions
drop function update_file_refs_in_json(jsonb);
drop function get_file_path(text);