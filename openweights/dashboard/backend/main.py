from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from database import Database
from models import (Job, JobWithRuns, Run, RunWithJobAndWorker, Worker,
                   WorkerWithRuns, TokenCreate, Token)
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_db(authorization: str = Header(None)) -> Database:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is required")
    
    try:
        # Extract the token from the Authorization header
        # Format should be "Bearer <token>"
        if not authorization.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        
        token = authorization.split(" ")[1]
        return Database(auth_token=token)
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/jobs/", response_model=List[Job])
async def get_jobs(status: Optional[str] = None, db: Database = Depends(get_db)):
    return db.get_jobs(status)

@app.get("/jobs/{job_id}", response_model=JobWithRuns)
async def get_job(job_id: str, db: Database = Depends(get_db)):
    try:
        return db.get_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/runs/", response_model=List[Run])
async def get_runs(status: Optional[str] = None, db: Database = Depends(get_db)):
    return db.get_runs(status)

@app.get("/runs/{run_id}", response_model=RunWithJobAndWorker)
async def get_run(run_id: str, db: Database = Depends(get_db)):
    try:
        return db.get_run(run_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/runs/{run_id}/logs", response_class=PlainTextResponse)
async def get_run_logs(run_id: str, db: Database = Depends(get_db)):
    try:
        return db.get_log_file_content(run_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/workers/", response_model=List[Worker])
async def get_workers(status: Optional[str] = None, db: Database = Depends(get_db)):
    return db.get_workers(status)

@app.get("/workers/{worker_id}", response_model=WorkerWithRuns)
async def get_worker(worker_id: str, db: Database = Depends(get_db)):
    try:
        return db.get_worker(worker_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/files/{file_id}/content", response_class=PlainTextResponse)
async def get_file_content(file_id: str, db: Database = Depends(get_db)):
    try:
        # Print debug info
        print(f"Fetching content for file: {file_id}")
        content = db.get_file_content(file_id)
        print(f"Content length: {len(content) if content else 0}")
        return content
    except Exception as e:
        print(f"Error fetching file content: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/organizations/{organization_id}/tokens", response_model=Token)
async def create_token(
    organization_id: str,
    token_data: TokenCreate,
    db: Database = Depends(get_db)
):
    try:
        return await db.create_token(organization_id, token_data)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.get("/organizations/{organization_id}/tokens", response_model=List[Token])
async def list_tokens(
    organization_id: str,
    db: Database = Depends(get_db)
):
    try:
        return await db.list_tokens(organization_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/organizations/{organization_id}/tokens/{token_id}")
async def delete_token(
    organization_id: str,
    token_id: str,
    db: Database = Depends(get_db)
):
    try:
        await db.delete_token(token_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files after all API routes
app.mount("/", StaticFiles(directory="static", html=True), name="static")