DROP FUNCTION IF EXISTS update_job_status_if_in_progress(text, text, text, jsonb, text) CASCADE;

CREATE OR REPLACE FUNCTION update_job_status_if_in_progress(
    _job_id text,
    _new_status text,        -- We allow text to come in from Supabase
    _worker_id text,
    _job_outputs jsonb DEFAULT null,
    _job_script text DEFAULT null
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE jobs
     SET status = _new_status::job_status,   -- <--- cast to job_status
         outputs = _job_outputs,
         script = COALESCE(_job_script, script)
   WHERE id = _job_id
     AND status = 'in_progress'   -- Assuming 'in_progress' also exists in your enum
     AND worker_id = _worker_id;
END;
$$;

GRANT EXECUTE ON FUNCTION update_job_status_if_in_progress(text, text, text, jsonb, text) TO authenticated;
