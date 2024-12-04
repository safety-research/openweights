-- Drop existing function
drop function if exists create_service_account_token(uuid, text, timestamp with time zone);

-- Recreate with user_id parameter
create or replace function create_service_account_token(
    org_id uuid,
    token_name text,
    created_by uuid,
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
    v_jwt_secret text;
    v_jwt_token text;
begin
    -- Get JWT secret from env var for now (we'll move this to vault later)
    v_jwt_secret := current_setting('app.jwt_secret', true);
    
    if v_jwt_secret is null then
        raise exception 'JWT secret not configured';
    end if;

    -- Create token record
    insert into tokens (organization_id, name, expires_at, created_by)
    values (org_id, token_name, expires_at, created_by)
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

    -- Update token hash
    update tokens 
    set token_hash = v_jwt_token
    where id = v_token_id;

    return query select v_token_id, v_jwt_token;
end;
$$;