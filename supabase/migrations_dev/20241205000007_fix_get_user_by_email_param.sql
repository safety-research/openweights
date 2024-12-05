-- Drop existing function
drop function if exists public.get_user_by_email(varchar);

-- Recreate function with parameter named 'email'
create or replace function public.get_user_by_email(email varchar(255))
returns table (
    user_id uuid,
    user_email varchar(255)
) security definer
set search_path = public
language plpgsql
as $$
begin
    return query
    select 
        au.id as user_id,
        au.email as user_email
    from auth.users au
    where au.email = get_user_by_email.email
    limit 1;
end;
$$;

-- Grant execute permissions on the function
grant execute on function public.get_user_by_email(varchar) to authenticated;