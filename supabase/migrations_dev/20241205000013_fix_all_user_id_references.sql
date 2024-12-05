-- Drop and recreate get_user_by_email function with explicit references
drop function if exists public.get_user_by_email(varchar);

create or replace function public.get_user_by_email(email varchar(255))
returns table (
    user_id uuid,
    user_email varchar(255)
) security definer
set search_path = public
language plpgsql
as $$
begin
    if email is null then
        raise exception 'Email parameter cannot be null';
    end if;

    return query
    select 
        au.id as user_id,
        au.email as user_email
    from auth.users au
    where lower(au.email) = lower(get_user_by_email.email)
    limit 1;

    if not found then
        raise exception 'User with email % not found', email;
    end if;
end;
$$;

-- Drop and recreate invite_organization_member function with explicit references
drop function if exists public.invite_organization_member(uuid, varchar, public.organization_role);

create or replace function public.invite_organization_member(
    org_id uuid,
    member_email varchar(255),
    member_role public.organization_role
)
returns table (
    user_id uuid,
    email varchar(255),
    role public.organization_role
) security definer
set search_path = public
language plpgsql
as $$
declare
    v_user_id uuid;
    v_email varchar(255);
begin
    -- Check if the inviter is an admin of the organization
    if not exists (
        select 1
        from organization_members om
        where om.organization_id = org_id
        and om.user_id = auth.uid()
        and om.role = 'admin'
    ) then
        raise exception 'Only organization admins can invite members';
    end if;

    -- Get the user ID for the email
    select au.id, au.email
    into v_user_id, v_email
    from auth.users au
    where lower(au.email) = lower(member_email);

    if v_user_id is null then
        raise exception 'User with email % not found', member_email;
    end if;

    -- Check if user is already a member
    if exists (
        select 1
        from organization_members om
        where om.organization_id = org_id
        and om.user_id = v_user_id
    ) then
        raise exception 'User is already a member of this organization';
    end if;

    -- Insert the new member
    insert into organization_members (organization_id, user_id, role)
    values (org_id, v_user_id, member_role);

    -- Return the result explicitly
    user_id := v_user_id;
    email := v_email;
    role := member_role;
    return next;
end;
$$;

-- Grant execute permissions
grant execute on function public.get_user_by_email(varchar) to authenticated;
grant execute on function public.invite_organization_member(uuid, varchar, public.organization_role) to authenticated;