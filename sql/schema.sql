-- Create custom types for USER-DEFINED fields
CREATE TYPE job_type AS ENUM ('type1', 'type2');
CREATE TYPE job_status AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'canceled');
CREATE TYPE run_status AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'canceled');

-- Create events table
CREATE TABLE public.events (
    id integer PRIMARY KEY,
    run_id integer,
    created_at timestamp with time zone,
    data jsonb NOT NULL,
    file text
);

-- Create files table
CREATE TABLE public.files (
    id text PRIMARY KEY,
    created_at timestamp with time zone,
    filename text NOT NULL,
    purpose text NOT NULL,
    bytes integer NOT NULL
);

-- Create jobs table
CREATE TABLE public.jobs (
    id text PRIMARY KEY,
    created_at timestamp with time zone,
    type job_type NOT NULL,
    model text,
    params jsonb,
    script text,
    outputs jsonb,
    requires_vram_gb integer,
    status job_status,
    worker_id text
);

-- Create runs table
CREATE TABLE public.runs (
    id integer PRIMARY KEY,
    job_id text,
    worker_id text,
    created_at timestamp with time zone,
    status run_status,
    log_file text
);

-- Create worker table
CREATE TABLE public.worker (
    id text PRIMARY KEY,
    created_at timestamp with time zone,
    status text,
    cached_models text[],
    vram_gb integer,
    pod_id text
);

-- Add foreign key constraints
ALTER TABLE public.events
    ADD CONSTRAINT fk_run_id FOREIGN KEY (run_id) REFERENCES public.runs(id);

ALTER TABLE public.events
    ADD CONSTRAINT fk_file FOREIGN KEY (file) REFERENCES public.files(id);

ALTER TABLE public.runs
    ADD CONSTRAINT fk_job_id FOREIGN KEY (job_id) REFERENCES public.jobs(id);

ALTER TABLE public.runs
    ADD CONSTRAINT fk_worker_id FOREIGN KEY (worker_id) REFERENCES public.worker(id);

ALTER TABLE public.jobs
    ADD CONSTRAINT fk_worker_id FOREIGN KEY (worker_id) REFERENCES public.worker(id);