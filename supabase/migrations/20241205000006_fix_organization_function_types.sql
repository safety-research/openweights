-- Drop existing functions
drop function if exists public.get_organization_members(uuid);
drop function if exists public.get_user_by_email(text);

-- Recreate functions with correct types
create or replace function public.get_organization_members(org_id uuid)
returns table (
    user_id uuid,
    email varchar(255),
    role public.organization_role
) security definer
set search_path = public
language plpgsql
as $$
begin
    return query
    select 
        om.user_id,
        au.email,
        om.role
    from public.organization_members om
    join auth.users au on au.id = om.user_id
    where om.organization_id = org_id
    and exists (
        select 1 
        from public.organization_members viewer 
        where viewer.organization_id = org_id 
        and viewer.user_id = auth.uid()
    );
end;
$$;

-- Function to get user by email
create or replace function public.get_user_by_email(user_email varchar(255))
returns table (
    id uuid,
    email varchar(255)
) security definer
set search_path = public
language plpgsql
as $$
begin
    return query
    select 
        au.id,
        au.email
    from auth.users au
    where au.email = user_email
    limit 1;
end;
$$;

-- Grant execute permissions on the functions
grant execute on function public.get_organization_members(uuid) to authenticated;
grant execute on function public.get_user_by_email(varchar) to authenticated;