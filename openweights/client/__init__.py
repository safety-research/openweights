import asyncio
import atexit
import json
from typing import Optional, BinaryIO, Dict, Any, List, Union
import os
import sys
from postgrest.exceptions import APIError
import hashlib
from datetime import datetime
from openai import OpenAI, AsyncOpenAI
import backoff
import time
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

from openweights.validate import validate_messages, validate_preference_dataset, TrainingConfig, InferenceConfig, ApiConfig
from openweights.client.files import Files
from openweights.client.jobs import FineTuningJobs, InferenceJobs, Deployments, Jobs
from openweights.client.run import Run, Runs
from openweights.client.events import Events
from openweights.client.temporary_api import TemporaryApi, group_models_or_adapters_by_model, get_lora_rank


def create_authenticated_client(supabase_url: str, supabase_anon_key: str, auth_token: Optional[str] = None):
    """Create a Supabase client with authentication.
    
    Args:
        supabase_url: Supabase project URL
        supabase_anon_key: Supabase anon key
        auth_token: Session token from Supabase auth (optional)
        api_key: OpenWeights API key starting with 'ow_' (optional)
    """
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    else:
        raise ValueError("No auth_token provided")
    
    options = ClientOptions(
        schema="public",
        headers=headers,
        auto_refresh_token=False,
        persist_session=False
    )
    
    return create_client(supabase_url, supabase_anon_key, options)


class OpenWeights:
    def __init__(self, 
                 supabase_url: Optional[str] = None, 
                 supabase_key: Optional[str] = None, 
                 auth_token: Optional[str] = None,
                 organization_id: Optional[str] = None):
        """Initialize OpenWeights client
        
        Args:
            supabase_url: Supabase project URL (or SUPABASE_URL env var)
            supabase_key: Supabase anon key (or SUPABASE_ANON_KEY env var)
            auth_token: Authentication token (or OPENWEIGHTS_API_KEY env var)
                       Can be either a session token or a service account JWT token
        """
        self.supabase_url = supabase_url or os.environ.get('SUPABASE_URL', 'https://taofkfabrhpgtohaikst.supabase.co')
        self.supabase_key = supabase_key or os.environ.get('SUPABASE_ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRhb2ZrZmFicmhwZ3RvaGFpa3N0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzE5MjkyMjcsImV4cCI6MjA0NzUwNTIyN30.KRufleTgprt16mfm0_91YjKIFZAne1-IW8buMxWVMeE')
        self.auth_token = auth_token or os.getenv('OPENWEIGHTS_API_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Supabase URL and key must be provided either as arguments or environment variables")
        
        if not self.auth_token:
            raise ValueError("Authentication token must be provided either as argument or OPENWEIGHTS_API_KEY environment variable")
        
        self._supabase = create_authenticated_client(
            self.supabase_url, 
            self.supabase_key, 
            self.auth_token
        )
        
        # Get organization ID from token
        self.organization_id = organization_id or self.get_organization_id()
        self.set_hf_org_env()
        
        # Initialize components with organization ID
        self.files = Files(self._supabase, self.organization_id)
        self.fine_tuning = FineTuningJobs(self._supabase, self.organization_id)
        self.inference = InferenceJobs(self._supabase, self.organization_id)
        self.jobs = Jobs(self._supabase, self.organization_id)
        self.deployments = Deployments(self._supabase, self.organization_id)
        self.runs = Runs(self._supabase)
        self.events = Events(self._supabase)

        self._current_run = None
    
    def get_organization_id(self) -> str:
        """Get the organization ID associated with the current token"""
        result = self._supabase.rpc('get_organization_from_token').execute()
        if not result.data:
            raise ValueError("Could not determine organization ID from token")
        return result.data
    
    def set_hf_org_env(self):
        """Get organization secrets from the database."""
        if os.environ.get('HF_ORG'):
            return
        result = self._supabase.table('organization_secrets')\
            .select('value')\
            .eq('organization_id', self.organization_id)\
            .eq('name', 'HF_ORG')\
            .single().execute()
        if not result.data:
            raise ValueError("Could not determine organization ID from token")
        os.environ['HF_ORG'] = result.data['value']
        print(f"Set HF_ORG to {os.environ['HF_ORG']}")
        
    @property
    def run(self):
        if not self._current_run:
            self._current_run = Run(self._supabase, organization_id=self.organization_id)
        return self._current_run
    
    def deploy(self, model, lora_adapters=[], max_lora_rank='guess', max_model_len=2048, client_type=OpenAI, api_key=os.environ.get('OW_DEFAULT_API_KEY'), requires_vram_gb='guess') -> TemporaryApi:
        """Deploy a model on OpenWeights"""
        if api_key is None:
            api_key = self.auth_token
        if lora_adapters and max_lora_rank == 'guess':
            max_lora_rank = max(get_lora_rank(a) for a in lora_adapters)
        else:
            max_lora_rank = 16
        job = self.deployments.create(
            model=model, max_model_len=max_model_len, api_key=api_key, requires_vram_gb=requires_vram_gb,
            lora_adapters=lora_adapters, max_lora_rank=max_lora_rank)
        return TemporaryApi(self, job['id'], client_type=client_type)
    
    def multi_deploy(self, models, max_model_len=2048, client_type=OpenAI, api_key=os.environ.get('OW_DEFAULT_API_KEY'), requires_vram_gb='guess') -> Dict[str, TemporaryApi]:
        """Deploy multiple models - creates on server for each base model, and deploys all lora adapters on of the same base model together"""
        lora_groups = group_models_or_adapters_by_model(models)
        apis = {}
        for model, lora_adapters in lora_groups.items():
            api = self.deploy(model, lora_adapters=lora_adapters, max_model_len=max_model_len, client_type=client_type, api_key=api_key, requires_vram_gb=requires_vram_gb)
            for model_id in [model] + lora_adapters:
                apis[model_id] = api
        return apis
