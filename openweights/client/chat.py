import openai
import asyncio
import functools
from openweights.client.cache_on_disk import cache_on_disk
import backoff

APIS = {}
DEPLOYMENT_QUEUE = []
STARTING = []


class AsyncChatCompletions:
    def __init__(self, ow, deploy_kwargs={}):
        self.ow = ow
        self.completions = self
        self.deploy_kwargs = deploy_kwargs
    
    async def create(self, model: str, **kwargs):
        @cache_on_disk(required_kwargs=['seed'])
        async def cached_create(model, **kwargs):
            return await self._create(model, **kwargs)
        return await cached_create(model, **kwargs)
    
    async def _create(self, model, **kwargs):
        api = await self._get_api(model)
        async with api.sem:
            return await self._create_with_backoff(api, model, **kwargs)

    @backoff.on_exception(
        wait_gen=backoff.expo,
        exception=(
            openai.RateLimitError,
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.InternalServerError
        ),
        max_value=60,
        factor=1.5,
        max_tries=10
    )   
    async def _create_with_backoff(self, api, model, **kwargs):
        return await api.async_client.chat.completions.create(model=model, **kwargs)
    
    async def _get_api(self, model):
        """If the model is not yet deployed, we add it to a queue of to-be-deployed models and wait for 5 seconds
        to group them at once, which is more efficient if the multiple lora finetunes of the same model are deployed."""
        if model in APIS:
            return APIS[model]
        if model not in DEPLOYMENT_QUEUE and model not in STARTING:
            print(f"Adding {model} to deployment queue")
            DEPLOYMENT_QUEUE.append(model)
            # Create a task to deploy the model in 5 seconds
            asyncio.create_task(self._wait_and_deploy_queue())
        # Poll until model is deployed
        while model not in APIS:
            await asyncio.sleep(1)
        return APIS[model]
    
    async def _wait_and_deploy_queue(self, seconds_to_wait=5):
        for _ in range(seconds_to_wait):
            await asyncio.sleep(1)
            if len(DEPLOYMENT_QUEUE) == 0:
                return
        # Move all models from the queue to a list of models to be deployed, such that DEPLOYMENT_QUEUE is empty after this
        models_to_deploy = DEPLOYMENT_QUEUE.copy()
        DEPLOYMENT_QUEUE.clear()
        STARTING.extend(models_to_deploy)
        print(f"Deploying {models_to_deploy}")
        # Deploy the models
        apis = self.ow.multi_deploy(models_to_deploy, **self.deploy_kwargs)
        # Wait for apis to be up
        print(f"Waiting for {models_to_deploy} to be up")
        set_of_apis = set(apis.values())
        await asyncio.gather(*[api.async_up() for api in set_of_apis])
        APIS.update(apis)
        for model in models_to_deploy:
            STARTING.remove(model)
        


class ChatCompletions(AsyncChatCompletions):
    def create(self, *args, **kwargs):
        return asyncio.run(super().create(*args, **kwargs))