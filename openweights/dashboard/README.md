# OpenWeights Dashboard

A web dashboard for monitoring OpenWeights jobs, runs, and workers.

## Setup

### Backend

1. Install dependencies:
```bash
pip install fastapi uvicorn
```

2. Set environment variables:
```bash
export SUPABASE_URL=your_supabase_url
export SUPABASE_KEY=your_supabase_key
```

3. Run the backend:
```bash
cd backend
uvicorn main:app --reload --port 8123
```

The backend will be available at http://localhost:8123

### Frontend

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Run the development server:
```bash
npm run dev
```

The frontend will be available at http://localhost:5173

## Features

### Jobs View
- Shows jobs in three columns: pending, in progress, and completed/failed
- Each job card shows basic information and a link to detailed view
- Detailed view shows:
  - Job parameters
  - Script (if applicable)
  - List of associated runs

### Runs View
- Shows runs in three columns: pending, in progress, and completed/failed
- Each run card shows:
  - Associated job (with link)
  - Associated worker (with link)
  - Status and timestamps
- Detailed view shows:
  - Full run information
  - Log file (if available)
  - Links to associated job and worker

### Workers View
- Shows workers in three columns: starting, active, and terminated
- Each worker card shows:
  - GPU information
  - Docker image
  - Status
- Detailed view shows:
  - Full worker information
  - History of runs executed by this worker