#!/bin/bash

# Configuration
REPO_URL="https://github.com/StampyAI/openweights"
REPO_BRANCH="main"
WORK_DIR="/app/openweights"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Update code
log "Pulling latest code..."
if [ -d "$WORK_DIR" ]; then
    cd "$WORK_DIR"
    git pull origin $REPO_BRANCH
else
    git clone -b $REPO_BRANCH $REPO_URL "$WORK_DIR"
    cd "$WORK_DIR"
fi

# Build frontend
log "Building frontend..."
cd dashboard/frontend
npm install
npm run build

# Create static directory in backend
log "Moving frontend build to backend..."
mkdir -p ../backend/static
cp -r dist/* ../backend/static/

# Restart backend service
log "Restarting backend service..."
cd ../backend
if [ -f "backend.pid" ]; then
    kill $(cat backend.pid)
fi
nohup python main.py > backend.log 2>&1 & echo $! > backend.pid

log "Deployment completed!"