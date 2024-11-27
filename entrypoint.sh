#!/bin/bash

# Add public keys to authorized_keys
if [ -n "$PUBLIC_KEY" ]; then
    echo "$PUBLIC_KEY" > /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
fi

# Start SSH service
service ssh start

# Execute the main application
exec python3 openweights/worker/main.py