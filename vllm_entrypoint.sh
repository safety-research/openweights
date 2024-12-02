#!/bin/bash

# Add public keys to authorized_keys
if [ -n "$PUBLIC_KEY" ]; then
    mkdir -p /root/.ssh
    echo "$PUBLIC_KEY" > /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
fi

# Login to huggingface
python3 -c "from huggingface_hub.hf_api import HfFolder; import os; HfFolder.save_token(os.environ['HF_TOKEN'])"

# Generate SSH host keys
ssh-keygen -A
# Start SSH service
service ssh start

# Print sshd logs to stdout
tail -f /var/log/auth.log &

# Execute the main application or run in dev mode
exec vllm serve $VLLM_MODEL --dtype auto --api-key $VLLM_API_KEY
