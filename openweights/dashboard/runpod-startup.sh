#!/bin/bash

# Configuration
WORK_DIR="/workspace/openweights"
DASHBOARD_DIR="$WORK_DIR/openweights/dashboard"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Setup Node.js
log "Setting up Node.js..."
if ! command -v nvm &> /dev/null; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
fi

# Install and use Node.js 20
log "Installing Node.js 20..."
nvm install 20
nvm use 20

# Verify versions
log "Node.js version: $(node --version)"
log "npm version: $(npm --version)"

# Build frontend
log "Building frontend..."
cd $DASHBOARD_DIR/frontend
log "Cleaning npm cache and node_modules..."
npm cache clean --force
rm -rf node_modules package-lock.json
log "Installing dependencies..."
npm install

# Run TypeScript fixes
log "Applying TypeScript fixes..."
cd $DASHBOARD_DIR
bash fix-typescript.sh

# Return to frontend directory and build
cd frontend
log "Building..."
npm run build

# Create static directory in backend
log "Moving frontend build to backend..."
mkdir -p ../backend/static
cp -r dist/* ../backend/static/

# Restart backend service
log "Restarting backend service..."
cd ../backend
if [ -f "backend.pid" ]; then
    kill $(cat backend.pid) || true
fi
nohup python main.py > backend.log 2>&1 & echo $! > backend.pid

log "Deployment completed!"