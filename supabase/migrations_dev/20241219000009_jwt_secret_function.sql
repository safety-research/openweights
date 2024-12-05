-- Create a function to get the JWT secret
create or replace function get_jwt_secret()
returns text
language plpgsql
security definer
as $$
begin
    -- This is a placeholder - in production, you'd want to store this more securely
    return 'AsQjcwl78lW6ND4aXiFXGg5bEuEfw7fcnte8opUfUrTR65Mz83YuksM+kRCcneAdp+yW/5NNDCZ6Gb2mZ+VJrw==';
end;
$$;

-- Update the token creation function to use the new get_jwt_secret function
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
    -- Get JWT secret
    v_jwt_secret := get_jwt_secret();
    
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