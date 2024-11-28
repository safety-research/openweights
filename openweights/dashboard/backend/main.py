from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from typing import List, Optional

from database import Database
from models import Job, Run, Worker, JobWithRuns, RunWithJobAndWorker, WorkerWithRuns

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db = Database()

@app.get("/jobs/", response_model=List[Job])
async def get_jobs(status: Optional[str] = None):
    return db.get_jobs(status)

@app.get("/jobs/{job_id}", response_model=JobWithRuns)
async def get_job(job_id: str):
    try:
        return db.get_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/runs/", response_model=List[Run])
async def get_runs(status: Optional[str] = None):
    return db.get_runs(status)

@app.get("/runs/{run_id}", response_model=RunWithJobAndWorker)
async def get_run(run_id: str):
    try:
        return db.get_run(run_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/runs/{run_id}/logs", response_class=PlainTextResponse)
async def get_run_logs(run_id: str):
    try:
        return db.get_log_file_content(run_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/workers/", response_model=List[Worker])
async def get_workers(status: Optional[str] = None):
    return db.get_workers(status)

@app.get("/workers/{worker_id}", response_model=WorkerWithRuns)
async def get_worker(worker_id: str):
    try:
        return db.get_worker(worker_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/files/{file_id}/content", response_class=PlainTextResponse)
async def get_file_content(file_id: str):
    try:
        # Print debug info
        print(f"Fetching content for file: {file_id}")
        content = db.get_file_content(file_id)
        print(f"Content length: {len(content) if content else 0}")
        return content
    except Exception as e:
        print(f"Error fetching file content: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))