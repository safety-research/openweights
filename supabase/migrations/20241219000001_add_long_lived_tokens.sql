-- Create tokens table to keep track of issued tokens
create table if not exists "public"."tokens" (
    "id" uuid not null default gen_random_uuid(),
    "organization_id" uuid not null references organizations(id) on delete cascade,
    "name" text not null,
    "expires_at" timestamp with time zone,
    "created_at" timestamp with time zone default timezone('utc'::text, now()) not null,
    "created_by" uuid not null references auth.users(id) on delete cascade,
    "last_used_at" timestamp with time zone,
    primary key (id)
);

-- Enable RLS
alter table "public"."tokens" enable row level security;

-- Create policy for reading tokens
create policy "Organization members can view their tokens"
    on tokens for select
    using (
        exists (
            select 1 from organization_members
            where organization_id = tokens.organization_id
            and user_id = auth.uid()
        )
    );

-- Create policy for managing tokens (admin only)
create policy "Organization admins can manage tokens"
    on tokens for all
    using (
        exists (
            select 1 from organization_members
            where organization_id = tokens.organization_id
            and user_id = auth.uid()
            and role = 'admin'
        )
    );

-- Grant necessary permissions
grant all on table tokens to postgres, authenticated;