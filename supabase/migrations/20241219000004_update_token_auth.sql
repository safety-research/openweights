-- Drop existing functions that we're replacing
drop function if exists get_organization_from_token();
drop function if exists has_organization_access(uuid);

-- Function to get organization ID from token
create or replace function get_organization_from_token()
returns uuid
language plpgsql
security definer
as $$
declare
    auth_token text;
    custom_token text;
    org_id uuid;
begin
    -- First try custom token header
    custom_token := coalesce(
        current_setting('request.headers', true)::json->>'x-openweights-token',
        ''
    );
    
    if custom_token != '' and custom_token like 'ow_%' then
        -- Look up organization ID from tokens table
        select organization_id into org_id
        from tokens
        where token_hash = custom_token
        and (expires_at is null or expires_at > now());
        
        if found then
            -- Update last_used_at
            update tokens
            set last_used_at = now()
            where token_hash = custom_token;
            
            return org_id;
        end if;
    end if;
    
    -- If no custom token, try normal auth
    auth_token := coalesce(
        current_setting('request.headers', true)::json->>'authorization',
        ''
    );
    
    -- Extract token from "Bearer <token>"
    auth_token := replace(auth_token, 'Bearer ', '');
    
    -- If it's a valid JWT, auth.uid() will work
    if auth_token != '' then
        -- Return organization ID from membership
        select organization_id into org_id
        from organization_members
        where user_id = auth.uid()
        limit 1;
        
        return org_id;
    end if;
    
    -- No valid token found
    return null;
end;
$$;

-- Function to check if current token has access to an organization
create or replace function has_organization_access(org_id uuid)
returns boolean
language plpgsql
security definer
as $$
declare
    token_org_id uuid;
begin
    -- First check custom tokens
    token_org_id := get_organization_from_token();
    if token_org_id is not null then
        return token_org_id = org_id;
    end if;
    
    -- Fall back to checking organization membership
    return exists (
        select 1
        from organization_members
        where organization_id = org_id
        and user_id = auth.uid()
    );
end;
$$;

-- Update existing functions to use the new logic
create or replace function is_organization_member(org_id uuid)
returns boolean
language plpgsql
security definer
as $$
begin
    return has_organization_access(org_id);
end;
$$;

create or replace function is_organization_admin(org_id uuid)
returns boolean
language plpgsql
security definer
as $$
declare
    custom_token text;
begin
    -- First try custom token header
    custom_token := coalesce(
        current_setting('request.headers', true)::json->>'x-openweights-token',
        ''
    );
    
    -- API tokens have admin access
    if custom_token != '' and custom_token like 'ow_%' then
        return has_organization_access(org_id);
    end if;
    
    -- Otherwise check normal admin membership
    return exists (
        select 1
        from organization_members
        where organization_id = org_id
        and user_id = auth.uid()
        and role = 'admin'
    );
end;
$$;