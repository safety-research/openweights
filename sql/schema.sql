-- Existing schemas
-- Create enum for job types
CREATE TYPE job_type AS ENUM ('fine-tuning', 'inference', 'script');

-- Create jobs table
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    type job_type NOT NULL,
    model TEXT,
    params JSONB,
    script TEXT,
    outputs JSONB,
    status TEXT DEFAULT 'pending'
);

-- Add new column 'requires_vram_gb' with a default value
ALTER TABLE jobs ADD COLUMN requires_vram_gb INTEGER DEFAULT 24;

-- Create a new enum type for job status
CREATE TYPE job_status AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'canceled');

-- Add the 'status' column with a default value using the newly created enum
ALTER TABLE jobs ADD COLUMN status job_status DEFAULT 'pending';

-- Drop the old 'status' column of type TEXT, if exists
ALTER TABLE jobs DROP COLUMN status;

-- Re-add the 'status' column using the created ENUM type
ALTER TABLE jobs ADD COLUMN status job_status DEFAULT 'pending';

-- Create files table
CREATE TABLE files (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    filename TEXT NOT NULL,
    purpose TEXT NOT NULL,
    bytes INTEGER NOT NULL
);

-- Create worker table
CREATE TABLE worker (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status TEXT,
    cached_models TEXT[],
    vram_gb INTEGER
);

-- Add worker column as a foreign key to the jobs table
ALTER TABLE jobs ADD COLUMN worker TEXT REFERENCES worker(id);

-- New schema for runs table
CREATE TABLE runs (
    id SERIAL PRIMARY KEY,
    job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    worker_id TEXT REFERENCES worker(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status job_status,
    log_file TEXT
);

-- Create events table
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES runs(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data JSONB NOT NULL
);

ALTER TABLE events ADD COLUMN file TEXT;