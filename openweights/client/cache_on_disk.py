import hashlib
import json
import os
from functools import wraps

import diskcache as dc

cache_dir = os.path.join(os.path.dirname(__file__), ".llm-cache")


cache = dc.Cache(cache_dir)
def cache_on_disk(required_kwargs=[]):
    def decorator(function):
        @wraps(function)
        async def wrapper(*args, **kwargs):
            if not all(k in kwargs for k in required_kwargs):
                return await function(*args, **kwargs)
            
            serialized = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
            # Hash the JSON string to create a shorter key
            key = hashlib.sha256(serialized.encode()).hexdigest()
            if key in cache:
                return cache[key]
            
            result = await function(*args, **kwargs)
            cache[key] = result
            return result
        return wrapper
    return decorator