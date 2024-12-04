-- Add token_hash column to tokens table
alter table "public"."tokens" 
    add column "token_hash" text;