-- Create API tokens table
create table if not exists "public"."api_tokens" (
    "id" uuid not null default gen_random_uuid(),
    "organization_id" uuid not null references organizations(id) on delete cascade,
    "name" text not null,
    "token" text not null,
    "created_at" timestamp with time zone default timezone('utc'::text, now()) not null,
    "created_by" uuid not null references auth.users(id) on delete cascade,
    "last_used_at" timestamp with time zone,
    primary key (id)
);

-- Enable RLS
alter table "public"."api_tokens" enable row level security;

-- Create policy for reading tokens
create policy "Organization members can view their tokens"
    on api_tokens for select
    using (
        exists (
            select 1 from organization_members
            where organization_id = api_tokens.organization_id
            and user_id = auth.uid()
        )
    );

-- Create policy for managing tokens (admin only)
create policy "Organization admins can manage tokens"
    on api_tokens for all
    using (
        exists (
            select 1 from organization_members
            where organization_id = api_tokens.organization_id
            and user_id = auth.uid()
            and role = 'admin'
        )
    );

-- Function to generate a secure random token
create or replace function generate_api_token()
returns text
language plpgsql
as $$
declare
    token text;
begin
    -- Generate a random UUID and encode it to base64
    token := encode(digest(gen_random_uuid()::text || now()::text, 'sha256'), 'base64');
    -- Remove any non-alphanumeric characters and trim to 32 characters
    token := regexp_replace(token, '[^a-zA-Z0-9]', '', 'g');
    return substring(token, 1, 32);
end;
$$;

-- Function to create a new API token
create or replace function create_api_token(
    org_id uuid,
    token_name text
)
returns table (
    id uuid,
    name text,
    token text,
    created_at timestamptz
)
language plpgsql
security definer
as $$
declare
    new_token text;
    result record;
begin
    -- Check if user is an admin of the organization
    if not exists (
        select 1 from organization_members
        where organization_id = org_id
        and user_id = auth.uid()
        and role = 'admin'
    ) then
        raise exception 'Only organization admins can create API tokens';
    end if;

    -- Generate new token
    new_token := generate_api_token();

    -- Insert new token
    insert into api_tokens (organization_id, name, token, created_by)
    values (org_id, token_name, new_token, auth.uid())
    returning id, name, token, created_at into result;

    return query select result.id, result.name, result.token, result.created_at;
end;
$$;

-- Function to delete an API token
create or replace function delete_api_token(token_id uuid)
returns void
language plpgsql
security definer
as $$
begin
    -- Check if user is an admin of the organization that owns the token
    if not exists (
        select 1 from api_tokens t
        join organization_members m on m.organization_id = t.organization_id
        where t.id = token_id
        and m.user_id = auth.uid()
        and m.role = 'admin'
    ) then
        raise exception 'Only organization admins can delete API tokens';
    end if;

    -- Delete the token
    delete from api_tokens where id = token_id;
end;
$$;

-- Grant necessary permissions
grant all on table api_tokens to postgres, authenticated;
grant execute on function generate_api_token() to postgres, authenticated;
grant execute on function create_api_token(uuid, text) to postgres, authenticated;
grant execute on function delete_api_token(uuid) to postgres, authenticated;