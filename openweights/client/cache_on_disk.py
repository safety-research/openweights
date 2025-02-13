import asyncio
import hashlib
import json
import os
from functools import wraps

import diskcache as dc

class CacheOnDisk:
    def __init__(self, n_semaphore=100, cache_dir=None):
        """
        Create a CacheOnDisk instance.

        Parameters:
            n_semaphore (int): Maximum number of parallel cache accesses.
            cache_dir (str): Path to the cache directory. Defaults to a ".llm-cache"
                             directory alongside this file.
        """
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), ".llm-cache")
        os.makedirs(cache_dir, exist_ok=True)
        self.cache = dc.FanoutCache(cache_dir, shards=64, timeout=10)
        self.semaphore = asyncio.Semaphore(n_semaphore)

    def __call__(self, possible_func=None, *, required_kwargs=None):
        """
        When used as a decorator, CacheOnDisk works in two ways:

          1. As a no-argument decorator:
                @cache_on_disk
                async def my_func(...): ...

          2. As a parameterized decorator:
                @cache_on_disk(required_kwargs=["foo"])
                async def my_func(...): ...

        The `required_kwargs` parameter (a list) determines which keyword
        arguments are needed for caching. If they are not present, the function
        is simply executed.
        """
        if possible_func is not None and callable(possible_func):
            # Used as "@cache_on_disk" without explicit parameters.
            return self._make_decorator(required_kwargs or [])(possible_func)
        else:
            # Used as "@cache_on_disk(required_kwargs=[...])". Return a decorator.
            required_kwargs = required_kwargs or []
            def decorator(func):
                return self._make_decorator(required_kwargs)(func)
            return decorator

    def _make_decorator(self, required_kwargs):
        def decorator(function):
            @wraps(function)
            async def wrapper(*args, **kwargs):
                # Only attempt caching if all required keyword arguments are present.
                if not all(k in kwargs for k in required_kwargs):
                    return await function(*args, **kwargs)

                # Serialize args/kwargs and compute the cache key.
                serialized = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
                key = hashlib.sha256(serialized.encode()).hexdigest()

                # Limit the number of concurrent cache accesses.
                async with self.semaphore:
                    cached_result = await asyncio.to_thread(self.cache.get, key, None)
                if cached_result is not None:
                    return cached_result

                result = await function(*args, **kwargs)

                async with self.semaphore:
                    await asyncio.to_thread(self.cache.set, key, result)
                return result
            return wrapper
        return decorator

# Create a default object for easy importing.
cache_on_disk = CacheOnDisk()