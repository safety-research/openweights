-- First drop all policies that use these functions
drop policy if exists "Enable read access for organization members" on organizations;
drop policy if exists "Enable write access for organization admins" on organizations;
drop policy if exists "Enable read access for members" on organization_members;
drop policy if exists "Enable write access for admins" on organization_members;
drop policy if exists "Enable access for organization members" on jobs;
drop policy if exists "Enable access for organization members" on runs;
drop policy if exists "Enable access for organization members" on worker;
drop policy if exists "Enable access for organization members" on events;
drop policy if exists "Enable read for members" on third_party_api_keys;
drop policy if exists "Enable write for admins" on third_party_api_keys;

-- Now we can safely drop the functions
drop function if exists get_organization_from_token();
drop function if exists has_organization_access(uuid);
drop function if exists is_organization_member(uuid);
drop function if exists is_organization_admin(uuid);

-- Function to update token last used timestamp
create or replace function update_token_last_used(token_id uuid)
returns void
language plpgsql
security definer
as $$
begin
    -- Update last_used_at in a separate transaction
    update tokens
    set last_used_at = now()
    where id = token_id;
exception 
    when others then
        -- Ignore any errors during update
        null;
end;
$$;

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
    token_id uuid;
begin
    -- First try custom token header
    custom_token := coalesce(
        current_setting('request.headers', true)::json->>'x-openweights-token',
        ''
    );
    
    if custom_token != '' and custom_token like 'ow_%' then
        -- Look up organization ID from tokens table
        select t.organization_id, t.id into org_id, token_id
        from tokens t
        where t.token_hash = custom_token
        and (t.expires_at is null or t.expires_at > now());
        
        if found then
            -- Try to update last_used_at in background
            perform update_token_last_used(token_id);
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

-- Recreate policies with explicit table references
create policy "Enable read access for organization members"
    on organizations for select
    using (is_organization_member(id));

create policy "Enable write access for organization admins"
    on organizations for all
    using (is_organization_admin(id));

create policy "Enable read access for members"
    on organization_members for select
    using (is_organization_member(organization_id));

create policy "Enable write access for admins"
    on organization_members for all
    using (is_organization_admin(organization_id));

create policy "Enable access for organization members"
    on jobs for all
    using (is_organization_member(organization_id));

create policy "Enable access for organization members"
    on runs for all
    using (
        exists (
            select 1
            from jobs j
            where j.id = runs.job_id
            and is_organization_member(j.organization_id)
        )
    );

create policy "Enable access for organization members"
    on worker for all
    using (is_organization_member(organization_id));

create policy "Enable access for organization members"
    on events for all
    using (
        exists (
            select 1
            from runs r
            join jobs j on j.id = r.job_id
            where r.id = events.run_id
            and is_organization_member(j.organization_id)
        )
    );

create policy "Enable read for members"
    on third_party_api_keys for select
    using (is_organization_member(organization_id));

create policy "Enable write for admins"
    on third_party_api_keys for all
    using (is_organization_admin(organization_id));

-- Grant execute permissions
grant execute on function update_token_last_used(uuid) to postgres, authenticated, anon;
grant execute on function get_organization_from_token() to postgres, authenticated, anon;
grant execute on function has_organization_access(uuid) to postgres, authenticated, anon;
grant execute on function is_organization_member(uuid) to postgres, authenticated, anon;
grant execute on function is_organization_admin(uuid) to postgres, authenticated, anon;