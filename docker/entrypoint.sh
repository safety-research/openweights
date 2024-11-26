#!/bin/bash

# Add public keys to authorized_keys
if [ -n "$PUBLIC_KEYS" ]; then
    echo "$PUBLIC_KEYS" > /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
fi

# Start SSH service
service ssh start

# Execute the main application
exec python openweights/openweights/worker/main.py