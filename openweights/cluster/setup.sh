

pip install --upgrade pip
pip install huggingface_hub
python -c "from huggingface_hub.hf_api import HfFolder; import os; HfFolder.save_token(os.environ['HF_TOKEN'])"

# Unsloth
pip install --upgrade --force-reinstall --no-cache-dir torch==2.4.0 triton \
  --index-url https://download.pytorch.org/whl/cu121
pip install "unsloth[cu121-torch240] @ git+https://github.com/unslothai/unsloth.git"
pip install vllm


# Main repo
cd /workspace
git clone https://github.com/nielsrolf/openweights.git
cd openweights
pip install -e .

# Start experisana worker in a screen session
screen -dmS worker bash -c "python /workspace/openweights/openweights/worker.py"
