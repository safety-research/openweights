import os
import json
from typing import Dict, Optional, Type, Any
from pydantic import BaseModel, Field

from openweights.client.jobs import BaseJob


class CustomJob(BaseJob):
    """Base class for custom jobs that can be run on OpenWeights."""
    mount: Dict[str, str] = {}  # source path -> target path mapping
    params: Type[BaseModel] = BaseModel  # Pydantic model for parameter validation
    base_image: str = 'nielsrolf/ow-inference'  # Base Docker image to use
    requires_vram_gb: int = 24  # Required VRAM in GB

    def __init__(self, client):
        """Initialize the custom job.
        `client` should be an instance of `openweights.OpenWeights`."""
        self.client = client
    
    @property
    def id_predix(self):
        return self.__class__.__name__.lower()

    @property
    def _supabase(self):
        return self.client._supabase
    
    @property
    def _org_id(self):
        return self.client.organization_id

    def get_entrypoint(self, validated_params: BaseModel) -> str:
        """Get the entrypoint command for the job.
        
        Args:
            validated_params: The validated parameters as a Pydantic model instance
        
        Returns:
            The command to run as a string
        """
        raise NotImplementedError("Subclasses must implement get_entrypoint")

    def _upload_mounted_files(self) -> Dict[str, str]:
        """Upload all mounted files and return mapping of target paths to file IDs."""
        uploaded_files = {}
        
        for source_path, target_path in self.mount.items():
            # Handle both files and directories
            if os.path.isfile(source_path):
                with open(source_path, 'rb') as f:
                    file_response = self.client.files.create(f, purpose='custom_job_file')
                uploaded_files[target_path] = file_response['id']
            elif os.path.isdir(source_path):
                # For directories, upload each file maintaining the structure
                for root, _, files in os.walk(source_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, source_path)
                        target_file_path = os.path.join(target_path, rel_path)
                        
                        with open(full_path, 'rb') as f:
                            file_response = self.client.files.create(f, purpose='custom_job_file')
                        uploaded_files[target_file_path] = file_response['id']
            else:
                raise ValueError(f"Mount source path does not exist: {source_path}")
        
        return uploaded_files

    def create(self, **params) -> Dict[str, Any]:
        """Create and submit a custom job.
        
        Args:
            **params: Parameters for the job, will be validated against self.params

        Returns:
            The created job object
        """
        # Validate parameters
        validated_params = self.params(**params)
        
        # Upload mounted files
        mounted_files = self._upload_mounted_files()
        
        # Get entrypoint command
        entrypoint = self.get_entrypoint(validated_params)
        
        # Create job
        job_data = {
            'type': 'custom',
            'docker_image': self.base_image,
            'requires_vram_gb': params.get('requires_vram_gb', self.requires_vram_gb),
            'script': entrypoint,
            'params': {
                'validated_params': validated_params.model_dump(),
                'mounted_files': mounted_files
            }
        }
        return self.get_or_create_or_reset(job_data)