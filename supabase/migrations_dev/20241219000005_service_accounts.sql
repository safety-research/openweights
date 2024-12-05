-- Add service account metadata to auth.users
create or replace function auth.check_if_service_account()
returns boolean as $$
  select coalesce(
    current_setting('request.jwt.claims', true)::json->>'is_service_account',
    'false'
  )::boolean;
$$ language sql security definer;

-- Update RLS functions to handle service accounts
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
        
        -- Update last_used_at in tokens table
        update tokens
        set last_used_at = now()
        where id = (current_setting('request.jwt.claims', true)::json->>'token_id')::uuid;
        
        return org_id;
    end if;
    
    -- Otherwise, get organization from membership
    select organization_id into org_id
    from organization_members
    where user_id = auth.uid()
    limit 1;
    
    return org_id;
end;
$$;

-- Update is_organization_admin to give service accounts admin access
create or replace function is_organization_admin(org_id uuid)
returns boolean
language plpgsql
security definer
as $$
begin
    -- Service accounts have admin access to their organization
    if auth.check_if_service_account() then
        return get_organization_from_token() = org_id;
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

-- Add function to create service account
create or replace function create_service_account_token(
    org_id uuid,
    token_name text,
    expires_at timestamp with time zone default null
)
returns table (
    token_id uuid,
    jwt_token text
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_token_id uuid;
    v_user_id uuid;
    v_jwt_secret text;
    v_jwt_token text;
begin
    -- Get JWT secret from vault
    select decrypted_secret into v_jwt_secret 
    from vault.decrypted_secrets 
    where name = 'jwt_secret' 
    limit 1;

    if v_jwt_secret is null then
        raise exception 'JWT secret not found in vault';
    end if;

    -- Create token record
    insert into tokens (organization_id, name, expires_at, created_by)
    values (org_id, token_name, expires_at, auth.uid())
    returning id into v_token_id;

    -- Create JWT token with service account claims
    v_jwt_token := extensions.sign(
        json_build_object(
            'role', 'authenticated',
            'iss', 'supabase',
            'iat', extract(epoch from now())::integer,
            'exp', case 
                when expires_at is null then extract(epoch from now() + interval '10 years')::integer
                else extract(epoch from expires_at)::integer
            end,
            'is_service_account', true,
            'organization_id', org_id,
            'token_id', v_token_id
        )::json,
        v_jwt_secret
    );

    return query select v_token_id, v_jwt_token;
end;
$$;

-- Grant execute permissions
grant execute on function create_service_account_token(uuid, text, timestamp with time zone) to authenticated;