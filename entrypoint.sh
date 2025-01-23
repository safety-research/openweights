#!/bin/bash

# Add public keys to authorized_keys
if [ -n "$PUBLIC_KEY" ]; then
    mkdir -p /root/.ssh
    echo "$PUBLIC_KEY" > /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
fi

# if OW_COMMIT is set, checkout the commit
if [ -n "$OW_COMMIT" ]; then
    rm -rf openweights
    git clone https://github.com/longtermrisk/openweights.git openweights_dev
    cd openweights_dev
    git checkout $OW_COMMIT
    mv openweights ../openweights
    cd ..
    rm -rf openweights_dev
fi

# Login to huggingface
python3 -c "from huggingface_hub.hf_api import HfFolder; import os; HfFolder.save_token(os.environ['HF_TOKEN'])"

# Generate SSH host keys
ssh-keygen -A
# Start SSH service
service ssh start

# Print sshd logs to stdout
tail -f /var/log/auth.log &

# Start a simple server that serves the content of main.log on port 10101
# Create main.log if it doesn't exist
touch main.log

# Start a simple Python HTTP server to serve main.log
python3 -c '
import http.server
import socketserver

class LogHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        with open("main.log", "rb") as f:
            self.wfile.write(f.read())

with socketserver.TCPServer(("", 10101), LogHandler) as httpd:
    httpd.serve_forever()
' &



# Execute the main application or run in dev mode
if [ "$OW_DEV" = "true" ]; then
    exec tail -f /dev/null
else
    exec python3 openweights/worker/main.py > main.log 2>&1
fi
