# Load environment variables
export $(grep -v '^#' /workspace/.env | xargs)
echo "export $(grep -v '^#' /workspace/.env | xargs)" >> ~/.bashrc
# Github & Huggingface tokens
git config --global credential.helper store
echo "https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com" > ~/.git-credentials
echo "https://${HF_USER}:${HF_TOKEN}@huggingface.co" >> ~/.git-credentials

# Main repo
cd /workspace
git clone https://github.com/nielsrolf/openweights.git
cd openweights
pip install -e .

# Huggingface setup
pip install --upgrade pip
pip install huggingface_hub
python -c "from huggingface_hub.hf_api import HfFolder; import os; HfFolder.save_token(os.environ['HF_TOKEN'])"

# Unsloth + VLLM setup
# pip install "unsloth[cu124-ampere-torch240] @ git+https://github.com/unslothai/unsloth.git"
# pip install vllm

# Unsloth
python install_unsloth.py

apt-get update
apt-get install -y screen
# Start experisana worker in a screen session
screen -dmS worker bash -c "python /workspace/openweights/openweights/worker.py"
