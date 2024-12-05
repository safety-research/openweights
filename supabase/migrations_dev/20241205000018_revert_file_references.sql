-- Revert any changes to file references
update runs
set log_file = split_part(log_file, '/', 3)
where log_file like 'organizations/%';

-- For jobs.outputs and jobs.params, we need to extract the file ID from the path
create or replace function extract_file_id_from_path(path text)
returns text
language sql
immutable
as $$
    select split_part(path, '/', 3)
    where path like 'organizations/%';
$$;

create or replace function revert_file_refs_in_json(data jsonb)
returns jsonb
language plpgsql
as $$
declare
    result jsonb := data;
    file_path text;
begin
    -- Handle direct 'file' key
    if result ? 'file' and (result->>'file' like 'organizations/%') then
        file_path := result->>'file';
        result := jsonb_set(result, '{file}', to_jsonb(extract_file_id_from_path(file_path)));
    end if;

    -- Handle input_file_id
    if result ? 'input_file_id' and (result->>'input_file_id' like 'organizations/%') then
        file_path := result->>'input_file_id';
        result := jsonb_set(result, '{input_file_id}', to_jsonb(extract_file_id_from_path(file_path)));
    end if;

    -- Handle training_file
    if result ? 'training_file' and (result->>'training_file' like 'organizations/%') then
        file_path := result->>'training_file';
        result := jsonb_set(result, '{training_file}', to_jsonb(extract_file_id_from_path(file_path)));
    end if;

    -- Handle test_file
    if result ? 'test_file' and (result->>'test_file' like 'organizations/%') then
        file_path := result->>'test_file';
        result := jsonb_set(result, '{test_file}', to_jsonb(extract_file_id_from_path(file_path)));
    end if;

    return result;
end;
$$;

-- Revert changes in jobs table
update jobs
set 
    outputs = revert_file_refs_in_json(outputs),
    params = revert_file_refs_in_json(params)
where 
    (outputs::text like '%organizations/%' or params::text like '%organizations/%');

-- Clean up functions
drop function revert_file_refs_in_json(jsonb);
drop function extract_file_id_from_path(text);