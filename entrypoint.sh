#!/bin/bash

echo "[$(date)] Starting entrypoint script"

# Add public keys to authorized_keys
echo "[$(date)] Checking for PUBLIC_KEY environment variable"
if [ -n "$PUBLIC_KEY" ]; then
    echo "[$(date)] Setting up SSH public key"
    mkdir -p /root/.ssh
    echo "$PUBLIC_KEY" > /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
    echo "[$(date)] SSH public key setup completed"
else
    echo "[$(date)] No PUBLIC_KEY provided, skipping SSH key setup"
fi

# if OW_COMMIT is set, checkout the commit
echo "[$(date)] Checking for OW_COMMIT environment variable"
if [ -n "$OW_COMMIT" ]; then
    echo "[$(date)] Starting repository checkout for commit: $OW_COMMIT"
    rm -rf openweights
    git clone https://github.com/longtermrisk/openweights.git openweights_dev
    cd openweights_dev
    git checkout $OW_COMMIT
    mv openweights ../openweights
    cd ..
    rm -rf openweights_dev
    echo "[$(date)] Repository checkout completed"
else
    echo "[$(date)] No OW_COMMIT specified, skipping repository checkout"
fi

# Login to huggingface
echo "[$(date)] Attempting to login to Hugging Face"
python3 -c "from huggingface_hub.hf_api import HfFolder; import os; HfFolder.save_token(os.environ['HF_TOKEN'])"
echo "[$(date)] Hugging Face login completed"

# Generate SSH host keys
echo "[$(date)] Generating SSH host keys"
ssh-keygen -A
echo "[$(date)] SSH host keys generated"

# Start SSH service
echo "[$(date)] Starting SSH service"
service ssh start
echo "[$(date)] SSH service started"

# Print sshd logs to stdout
tail -f /var/log/auth.log &

mkdir -p logs

# Start a simple Python HTTP server to serve files from logs/
echo "[$(date)] Starting HTTP log server on port 10101"
python3 -c '
import http.server
import socketserver
import os

class LogHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # If path is /logs, serve logs/main
        if self.path == "/logs":
            file_path = "logs/main"
        else:
            # Remove leading slash and ensure path is within logs directory
            path = self.path.lstrip("/")
            file_path = os.path.join("logs", path)
        
        # Check if file exists and is within logs directory
        if os.path.exists(file_path) and os.path.commonprefix([os.path.abspath(file_path), os.path.abspath("logs")]) == os.path.abspath("logs"):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "File not found")

with socketserver.TCPServer(("", 10101), LogHandler) as httpd:
    httpd.serve_forever()
' &

echo "[$(date)] HTTP log server started"

# Execute the main application or run in dev mode
if [ "$OW_DEV" = "true" ]; then
    echo "[$(date)] Starting in development mode"
    exec tail -f /dev/null
else
    echo "[$(date)] Starting main application"
    exec python3 openweights/worker/main.py
fi
