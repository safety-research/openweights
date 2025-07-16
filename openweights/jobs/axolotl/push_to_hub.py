import argparse
import os
import sys
from huggingface_hub import HfApi, HfFolder
from huggingface_hub.utils import HfHubHTTPError, GatedRepoError, RevisionNotFoundError, RepositoryNotFoundError

def check_repo_non_empty(api: HfApi, repo_id: str, repo_type: str = "model") -> bool:
    """
    Checks if a repository on the Hugging Face Hub exists and is non-empty.
    Considers a repo non-empty if it contains files other than
    potentially auto-generated '.gitattributes' or 'README.md'.
    """
    try:
        files = api.list_repo_files(repo_id=repo_id, repo_type=repo_type)
        # Filter out common auto-generated or empty-repo files
        meaningful_files = [f for f in files if f not in ['.gitattributes', 'README.md']]
        return len(meaningful_files) > 0
    except (RepositoryNotFoundError, RevisionNotFoundError):
        # Repo doesn't exist or has no commit history (effectively empty)
        return False

def push_model_to_hub(local_dir: str, repo_name: str):
    """
    Pushes a local directory to a Hugging Face Hub repository.

    Args:
        local_dir (str): Path to the local directory containing the model.
        repo_name (str): Name of the repository on Hugging Face Hub (e.g., 'username/my-cool-model').
    """
    if not os.path.isdir(local_dir):
        print(f"Error: Local directory '{local_dir}' not found or is not a directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Attempting to push '{local_dir}' to Hugging Face Hub repo '{repo_name}'...")

    # Use HfApi for more control
    api = HfApi()
    repo_id = repo_name # repo_name is expected to be in 'namespace/repo-name' format
    repo_url = f"https://huggingface.co/{repo_id}"
    repo_type = "model" # Assuming it's a model repo

    try:
        # 1. Check if repo exists and is non-empty
        print(f"Checking repository '{repo_id}' on Hugging Face Hub...")
        if check_repo_non_empty(api, repo_id, repo_type):
            print(f"Repository '{repo_id}' already exists and is non-empty. Skipping push.")
            print(f"Repo URL: {repo_url}")
            return # Exit function gracefully

        # 2. If repo exists but was deemed empty, or doesn't exist, proceed.
        # Ensure repo exists (create if needed)
        try:
            # Try getting info again, maybe it exists but was empty or check failed before
            api.repo_info(repo_id=repo_id, repo_type=repo_type)
            print(f"Repository '{repo_id}' exists (or was just checked as empty). Preparing upload.")
        except RepositoryNotFoundError:
            print(f"Repository '{repo_id}' not found. Creating new private repository...")
            try:
                # Create new repo - defaults to private=True
                # Add private=False if you want public repos by default
                api.create_repo(repo_id=repo_id, repo_type=repo_type, private=True)
                print(f"Successfully created repository: {repo_url}")
            except HfHubHTTPError as e:
                print(f"Error: Failed to create repository '{repo_id}': {e}", file=sys.stderr)
                # Check if it's a conflict error (e.g., repo already created by another process)
                if e.response.status_code == 409: # Conflict
                     print("It seems the repository was created concurrently. Will attempt to upload anyway.")
                else:
                    sys.exit(1) # Exit on other creation errors


        # 3. Upload the folder content
        print(f"Uploading contents of '{local_dir}' to '{repo_id}'...")
        # `upload_folder` handles the upload efficiently.
        # It will create commits, handle large files (LFS), and show progress.
        # Setting `allow_patterns` and `ignore_patterns` can be useful
        # e.g., ignore_patterns=["*.safetensors"] if you only want PyTorch bins
        api.upload_folder(
            folder_path=local_dir,
            repo_id=repo_id,
            repo_type=repo_type,
            commit_message=f"Upload model files from {os.path.basename(local_dir)}",
            # Add other args like allow_patterns/ignore_patterns if needed
        )

        print("\nUpload complete!")
        print(f"Model successfully pushed to: {repo_url}")

    except HfHubHTTPError as e:
        print(f"\nError during Hugging Face Hub operation: {e}", file=sys.stderr)
        print(f"HTTP Status Code: {e.response.status_code}")
        print(f"Details: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Push a local model folder to Hugging Face Hub, checking for existence first."
    )
    parser.add_argument(
        "local_folder",
        type=str,
        help="Path to the local directory containing the model files."
    )
    parser.add_argument(
        "hf_repo_name",
        type=str,
        help="Name of the repository on Hugging Face Hub (e.g., 'username/my-model-name')."
    )

    args = parser.parse_args()

    # Basic validation for repo name format
    if '/' not in args.hf_repo_name or len(args.hf_repo_name.split('/')) != 2:
         print(f"Error: Invalid Hugging Face repository name format: '{args.hf_repo_name}'. Expected 'namespace/repository-name'.", file=sys.stderr)
         sys.exit(1)


    push_model_to_hub(args.local_folder, args.hf_repo_name)
    assert os.path.exists('completed'), f"Error: 'completed' file not found. This indicates that axolotl training did not complete successfully. Please check the logs for errors."

if __name__ == "__main__":
    main()

# Usage:
#   python push_to_hub.py /path/to/your/local/model/output your-username/your-model-name