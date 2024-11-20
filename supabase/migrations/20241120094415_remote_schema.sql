
SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;
CREATE EXTENSION IF NOT EXISTS "pgsodium" WITH SCHEMA "pgsodium";
COMMENT ON SCHEMA "public" IS 'standard public schema';
CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";
CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";
CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";
CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";
CREATE TYPE "public"."job_status" AS ENUM (
    'pending',
    'in_progress',
    'completed',
    'failed',
    'canceled'
);
ALTER TYPE "public"."job_status" OWNER TO "postgres";
CREATE TYPE "public"."job_type" AS ENUM (
    'fine-tuning',
    'inference',
    'script'
);
ALTER TYPE "public"."job_type" OWNER TO "postgres";
SET default_tablespace = '';
SET default_table_access_method = "heap";
CREATE TABLE IF NOT EXISTS "public"."events" (
    "id" integer NOT NULL,
    "run_id" integer,
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "data" "jsonb" NOT NULL,
    "file" "text"
);
ALTER TABLE "public"."events" OWNER TO "postgres";
CREATE SEQUENCE IF NOT EXISTS "public"."events_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER TABLE "public"."events_id_seq" OWNER TO "postgres";
ALTER SEQUENCE "public"."events_id_seq" OWNED BY "public"."events"."id";
CREATE TABLE IF NOT EXISTS "public"."files" (
    "id" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "filename" "text" NOT NULL,
    "purpose" "text" NOT NULL,
    "bytes" integer NOT NULL
);
ALTER TABLE "public"."files" OWNER TO "postgres";
CREATE TABLE IF NOT EXISTS "public"."jobs" (
    "id" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "type" "public"."job_type" NOT NULL,
    "model" "text",
    "params" "jsonb",
    "script" "text",
    "outputs" "jsonb",
    "requires_vram_gb" integer DEFAULT 24,
    "status" "public"."job_status" DEFAULT 'pending'::"public"."job_status",
    "worker_id" "text"
);
ALTER TABLE "public"."jobs" OWNER TO "postgres";
CREATE TABLE IF NOT EXISTS "public"."runs" (
    "id" integer NOT NULL,
    "job_id" "text",
    "worker_id" "text",
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "status" "public"."job_status",
    "log_file" "text"
);
ALTER TABLE "public"."runs" OWNER TO "postgres";
CREATE SEQUENCE IF NOT EXISTS "public"."runs_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER TABLE "public"."runs_id_seq" OWNER TO "postgres";
ALTER SEQUENCE "public"."runs_id_seq" OWNED BY "public"."runs"."id";
CREATE TABLE IF NOT EXISTS "public"."worker" (
    "id" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "status" "text",
    "cached_models" "text"[],
    "vram_gb" integer,
    "pod_id" "text",
    "ping" timestamp with time zone
);
ALTER TABLE "public"."worker" OWNER TO "postgres";
ALTER TABLE ONLY "public"."events" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."events_id_seq"'::"regclass");
ALTER TABLE ONLY "public"."runs" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."runs_id_seq"'::"regclass");
ALTER TABLE ONLY "public"."events"
    ADD CONSTRAINT "events_pkey" PRIMARY KEY ("id");
ALTER TABLE ONLY "public"."files"
    ADD CONSTRAINT "files_pkey" PRIMARY KEY ("id");
ALTER TABLE ONLY "public"."jobs"
    ADD CONSTRAINT "jobs_pkey" PRIMARY KEY ("id");
ALTER TABLE ONLY "public"."runs"
    ADD CONSTRAINT "runs_pkey" PRIMARY KEY ("id");
ALTER TABLE ONLY "public"."worker"
    ADD CONSTRAINT "worker_pkey" PRIMARY KEY ("id");
CREATE INDEX "events_run_id_idx" ON "public"."events" USING "btree" ("run_id");
ALTER TABLE ONLY "public"."events"
    ADD CONSTRAINT "events_run_id_fkey" FOREIGN KEY ("run_id") REFERENCES "public"."runs"("id") ON DELETE CASCADE;
ALTER TABLE ONLY "public"."jobs"
    ADD CONSTRAINT "jobs_worker_id_fkey" FOREIGN KEY ("worker_id") REFERENCES "public"."worker"("id");
ALTER TABLE ONLY "public"."runs"
    ADD CONSTRAINT "runs_job_id_fkey" FOREIGN KEY ("job_id") REFERENCES "public"."jobs"("id") ON DELETE CASCADE;
ALTER TABLE ONLY "public"."runs"
    ADD CONSTRAINT "runs_worker_id_fkey" FOREIGN KEY ("worker_id") REFERENCES "public"."worker"("id") ON DELETE SET NULL;
ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";
GRANT ALL ON TABLE "public"."events" TO "anon";
GRANT ALL ON TABLE "public"."events" TO "authenticated";
GRANT ALL ON TABLE "public"."events" TO "service_role";
GRANT ALL ON SEQUENCE "public"."events_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."events_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."events_id_seq" TO "service_role";
GRANT ALL ON TABLE "public"."files" TO "anon";
GRANT ALL ON TABLE "public"."files" TO "authenticated";
GRANT ALL ON TABLE "public"."files" TO "service_role";
GRANT ALL ON TABLE "public"."jobs" TO "anon";
GRANT ALL ON TABLE "public"."jobs" TO "authenticated";
GRANT ALL ON TABLE "public"."jobs" TO "service_role";
GRANT ALL ON TABLE "public"."runs" TO "anon";
GRANT ALL ON TABLE "public"."runs" TO "authenticated";
GRANT ALL ON TABLE "public"."runs" TO "service_role";
GRANT ALL ON SEQUENCE "public"."runs_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."runs_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."runs_id_seq" TO "service_role";
GRANT ALL ON TABLE "public"."worker" TO "anon";
GRANT ALL ON TABLE "public"."worker" TO "authenticated";
GRANT ALL ON TABLE "public"."worker" TO "service_role";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "service_role";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "service_role";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "service_role";
RESET ALL;
