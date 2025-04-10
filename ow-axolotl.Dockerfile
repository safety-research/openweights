FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# Install SSH
RUN apt-get update && \
    apt-get install -y openssh-server && \
    mkdir /var/run/sshd

# Create a directory for SSH keys
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh

RUN python3 -m pip install "huggingface_hub[cli]" supabase python-dotenv fire httpx>=0.24.0
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install "unsloth[cu124-ampere-torch240] @ git+https://github.com/unslothai/unsloth.git"
RUN python3 -m pip install --upgrade --no-cache-dir "git+https://github.com/unslothai/unsloth-zoo.git"
RUN python3 -m pip install inspect_ai git+https://github.com/UKGovernmentBEIS/inspect_evals
RUN python3 -m pip install transformers
RUN python3 -m pip install -U packaging==23.2 setuptools==75.8.0 wheel ninja
RUN python3 -m pip install --no-build-isolation axolotl[flash-attn,deepspeed]

COPY README.md .
COPY pyproject.toml .
COPY openweights openweights
COPY entrypoint.sh .
RUN python3 -m pip install -e .


EXPOSE 22
EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
