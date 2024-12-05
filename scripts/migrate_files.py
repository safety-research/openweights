import os
import sys
from pathlib import Path
import tempfile
from typing import Optional
from supabase import create_client, Client

from dotenv import load_dotenv
load_dotenv()

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000000"

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set")
        sys.exit(1)
    return create_client(url, key)

def download_file(supabase: Client, path: str, temp_dir: str) -> Optional[str]:
    """Download a file to a temporary directory."""
    try:
        print(f"Downloading {path}...")
        response = supabase.storage.from_("files").download(path)
        if not response:
            print(f"Warning: Could not download {path}")
            return None
        
        # Save to temp file
        temp_path = os.path.join(temp_dir, os.path.basename(path))
        with open(temp_path, "wb") as f:
            f.write(response)
        return temp_path
    except Exception as e:
        print(f"Error downloading {path}: {e}")
        return None

def upload_file(supabase: Client, local_path: str, original_path: str) -> bool:
    """Upload a file to the new organization structure."""
    try:
        # New path will be organizations/DEFAULT_ORG_ID/original_filename
        new_path = f"organizations/{DEFAULT_ORG_ID}/{os.path.basename(original_path)}"
        print(f"Uploading to {new_path}...")
        
        with open(local_path, "rb") as f:
            response = supabase.storage.from_("files").upload(
                new_path,
                f
                # file_options={"upsert": True}
            )
        return True
    except Exception as e:
        print(f"Error uploading {original_path}: {e}")
        return False

def migrate_files():
    supabase = get_supabase()
    
    # List all files in the bucket with pagination
    files = []
    offset = 0
    limit = 1000  # Supabase maximum limit per request
    
    while True:
        try:
            response = supabase.storage.from_("files").list(
                path="",
                options={
                    "limit": limit,
                    "offset": offset,
                }
            )
            batch = [f["name"] for f in response if not f["name"].startswith("organizations/")]
            files.extend(batch)
            
            if len(batch) < limit:  # No more files to fetch
                break
                
            offset += limit
        except Exception as e:
            print(f"Error listing files at offset {offset}: {e}")
            return

    print(f"Found {len(files)} files to migrate")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        for file_path in files:
            # Skip .keep files
            if file_path.endswith(".keep"):
                continue
                
            # Download file
            local_path = download_file(supabase, file_path, temp_dir)
            if not local_path:
                continue
            # Upload to new location
            success = upload_file(supabase, local_path, file_path)
            if success:
                print(f"Successfully migrated {file_path}")
            else:
                print(f"Failed to migrate {file_path}")

if __name__ == "__main__":
    migrate_files()