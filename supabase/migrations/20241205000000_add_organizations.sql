-- Create role enum type
create type "public"."organization_role" as enum ('admin', 'user');

-- Create organizations table
create table if not exists "public"."organizations" (
    "id" uuid not null default gen_random_uuid(),
    "created_at" timestamp with time zone default timezone('utc'::text, now()) not null,
    "updated_at" timestamp with time zone default timezone('utc'::text, now()) not null,
    "name" text not null,
    primary key (id)
);

-- Create organization_members junction table with role
create table if not exists "public"."organization_members" (
    "organization_id" uuid not null references organizations(id) on delete cascade,
    "user_id" uuid not null references auth.users(id) on delete cascade,
    "role" organization_role not null default 'user',
    "created_at" timestamp with time zone default timezone('utc'::text, now()) not null,
    primary key (organization_id, user_id)
);

-- Create third_party_api_keys table for RunPod, HuggingFace, etc.
create table if not exists "public"."third_party_api_keys" (
    "organization_id" uuid not null references organizations(id) on delete cascade,
    "service" text not null, -- 'runpod', 'huggingface'
    "api_key" text not null,
    "created_at" timestamp with time zone default timezone('utc'::text, now()) not null,
    "updated_at" timestamp with time zone default timezone('utc'::text, now()) not null,
    primary key (organization_id, service)
);

-- Create a default organization for existing data
insert into "public"."organizations" (id, name)
values ('00000000-0000-0000-0000-000000000000', 'Default Organization');

-- Add organization ownership to jobs
alter table "public"."jobs" 
    add column "organization_id" uuid references organizations(id) on delete cascade;

-- Add organization ownership to workers
alter table "public"."worker"
    add column "organization_id" uuid references organizations(id) on delete cascade;

-- Migrate existing jobs and workers to default organization
update "public"."jobs"
set "organization_id" = '00000000-0000-0000-0000-000000000000'
where "organization_id" is null;

update "public"."worker"
set "organization_id" = '00000000-0000-0000-0000-000000000000'
where "organization_id" is null;

-- Make organization_id not null after migration
alter table "public"."jobs"
    alter column "organization_id" set not null;

alter table "public"."worker"
    alter column "organization_id" set not null;

-- Enable RLS on all tables
alter table "public"."organizations" enable row level security;
alter table "public"."organization_members" enable row level security;
alter table "public"."third_party_api_keys" enable row level security;
alter table "public"."jobs" enable row level security;
alter table "public"."runs" enable row level security;
alter table "public"."worker" enable row level security;
alter table "public"."events" enable row level security;

-- Organizations: members can read, admins can update
create policy "Members can view their organizations"
    on organizations for select
    using (
        exists (
            select 1 from organization_members
            where organization_id = organizations.id
            and user_id = auth.uid()
        )
    );

create policy "Admins can update their organizations"
    on organizations for update
    using (
        exists (
            select 1 from organization_members
            where organization_id = organizations.id
            and user_id = auth.uid()
            and role = 'admin'
        )
    );

-- Organization members: members can view, admins can manage
create policy "Members can view other members in their organizations"
    on organization_members for select
    using (
        exists (
            select 1 from organization_members as om
            where om.organization_id = organization_members.organization_id
            and om.user_id = auth.uid()
        )
    );

create policy "Admins can manage members in their organizations"
    on organization_members for all
    using (
        exists (
            select 1 from organization_members
            where organization_id = organization_members.organization_id
            and user_id = auth.uid()
            and role = 'admin'
        )
    );

-- Jobs: members can CRUD jobs in their organizations
create policy "Members can manage jobs in their organizations"
    on jobs for all
    using (
        exists (
            select 1 from organization_members
            where organization_id = jobs.organization_id
            and user_id = auth.uid()
        )
    );

-- Runs: members can manage runs of jobs in their organizations
create policy "Members can manage runs in their organizations"
    on runs for all
    using (
        exists (
            select 1 from organization_members om
            join jobs j on j.organization_id = om.organization_id
            where j.id = runs.job_id
            and om.user_id = auth.uid()
        )
    );

-- Workers: members can manage workers in their organizations
create policy "Members can manage workers in their organizations"
    on worker for all
    using (
        exists (
            select 1 from organization_members
            where organization_id = worker.organization_id
            and user_id = auth.uid()
        )
    );

-- Events: members can manage events of runs in their organizations
create policy "Members can manage events in their organizations"
    on events for all
    using (
        exists (
            select 1 from organization_members om
            join jobs j on j.organization_id = om.organization_id
            join runs r on r.job_id = j.id
            where r.id = events.run_id
            and om.user_id = auth.uid()
        )
    );

-- Third-party API Keys: members can view, admins can manage
create policy "Members can view their organization's API keys"
    on third_party_api_keys for select
    using (
        exists (
            select 1 from organization_members
            where organization_id = third_party_api_keys.organization_id
            and user_id = auth.uid()
        )
    );

create policy "Admins can manage their organization's API keys"
    on third_party_api_keys for all
    using (
        exists (
            select 1 from organization_members
            where organization_id = third_party_api_keys.organization_id
            and user_id = auth.uid()
            and role = 'admin'
        )
    );

-- Grant permissions
grant usage on schema public to postgres, anon, authenticated, service_role;

grant all privileges on all tables in schema public to postgres, service_role;
grant all privileges on all sequences in schema public to postgres, service_role;

grant select, insert, update, delete on public.organizations to anon, authenticated;
grant select, insert, update, delete on public.organization_members to anon, authenticated;
grant select, insert, update, delete on public.third_party_api_keys to anon, authenticated;
grant select, insert, update, delete on public.jobs to anon, authenticated;
grant select, insert, update, delete on public.runs to anon, authenticated;
grant select, insert, update, delete on public.worker to anon, authenticated;
grant select, insert, update, delete on public.events to anon, authenticated;

-- Add updated_at trigger for organizations
create trigger set_updated_at_organizations
    before update on public.organizations
    for each row
    execute function public.handle_updated_at();

-- Add updated_at trigger for third_party_api_keys
create trigger set_updated_at_third_party_api_keys
    before update on public.third_party_api_keys
    for each row
    execute function public.handle_updated_at();