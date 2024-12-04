-- Drop the older api_tokens table and related functions
drop function if exists public.generate_api_token();
drop function if exists public.create_api_token(uuid, text);
drop function if exists public.delete_api_token(uuid);
drop table if exists public.api_tokens;

-- Keep the newer tokens table and its functions
-- But add an index on token_hash for faster lookups
create index if not exists idx_tokens_token_hash on public.tokens(token_hash);