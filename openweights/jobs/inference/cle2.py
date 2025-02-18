import json
import time



from validate import InferenceConfig




def main(config_json: str):
    breakpoint()
    cfg = InferenceConfig(**config_json)

if __name__ == "__main__":
    import fire
    fire.Fire(main)