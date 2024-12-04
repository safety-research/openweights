-- Function to validate an API token
create or replace function validate_api_token(token_text text)
returns table (
    organization_id uuid
)
language plpgsql
security definer
as $$
begin
    -- Update last_used_at timestamp
    update api_tokens
    set last_used_at = now()
    where token = token_text;

    -- Return the organization_id if token is valid
    return query
    select t.organization_id
    from api_tokens t
    where t.token = token_text;

    if not found then
        raise exception 'Invalid API token';
    end if;
end;
$$;

-- Grant execute permission
grant execute on function validate_api_token(text) to authenticated, anon;