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
uvicorn main:app --reload --port 8124
```

The backend will be available at http://localhost:8124

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
