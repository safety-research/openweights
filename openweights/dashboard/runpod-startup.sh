#!/bin/bash

# Install system dependencies
apt-get update
apt-get install -y nodejs npm python3-pip git cron

# Install Python dependencies
pip3 install fastapi uvicorn python-dotenv supabase pyjwt

# Clone repo
git clone https://github.com/StampyAI/openweights /app/openweights
cd /app/openweights

# Set up deployment script
cp dashboard/deploy.sh /usr/local/bin/
chmod +x /usr/local/bin/deploy.sh

# Set up cron job
(crontab -l 2>/dev/null; echo "*/30 * * * * /usr/local/bin/deploy.sh") | crontab -

# Start cron daemon
service cron start

# Initial deployment
/usr/local/bin/deploy.sh