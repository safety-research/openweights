-- Function to get organization ID from token
create or replace function get_organization_from_token()
returns uuid
language plpgsql
security definer
as $$
declare
    org_id uuid;
begin
    -- If this is a service account token, get org from claims
    if auth.check_if_service_account() then
        org_id := (current_setting('request.jwt.claims', true)::json->>'organization_id')::uuid;
        return org_id;
    end if;
    
    -- Otherwise, get organization from membership
    select organization_id into org_id
    from organization_members
    where user_id = auth.uid()
    limit 1;
    
    if org_id is null then
        raise exception 'No organization found for current user/token';
    end if;
    
    return org_id;
end;
$$;

-- Grant execute permissions
grant execute on function get_organization_from_token() to authenticated, anon;