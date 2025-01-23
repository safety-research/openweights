FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# Install SSH
RUN apt-get update && \
    apt-get install -y openssh-server && \
    mkdir /var/run/sshd

# Create a directory for SSH keys
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh

RUN python3 -m pip install huggingface_hub supabase python-dotenv fire httpx>=0.24.0
RUN python3 -m pip install "unsloth[cu124-ampere-torch240] @ git+https://github.com/unslothai/unsloth.git"

COPY README.md .
COPY pyproject.toml .
COPY openweights openweights
COPY entrypoint.sh .
RUN python3 -m pip install -e .


EXPOSE 22
EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]