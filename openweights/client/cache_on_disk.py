import hashlib
import json
import os
from functools import wraps

import diskcache as dc

# Ensure the cache directory exists
cache_dir = os.path.join(os.path.dirname(__file__), ".llm-cache")
os.makedirs(cache_dir, exist_ok=True)

# Use FanoutCache with multiple shards and a short timeout
cache = dc.FanoutCache(cache_dir, shards=64, timeout=1)

def cache_on_disk(required_kwargs=[]):
    def decorator(function):
        @wraps(function)
        async def wrapper(*args, **kwargs):
            # Only cache if all required kwargs are present
            if not all(k in kwargs for k in required_kwargs):
                return await function(*args, **kwargs)
            
            # Serialize args/kwargs into a JSON string and hash it
            serialized = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
            key = hashlib.sha256(serialized.encode()).hexdigest()
            
            if key in cache:
                return cache[key]
            
            result = await function(*args, **kwargs)
            cache[key] = result
            return result
        return wrapper
    return decorator
