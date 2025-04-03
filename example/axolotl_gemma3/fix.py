import json


def clean(path):
    with open(path, "r") as f:
        rows = [json.loads(line) for line in f.readlines()]
        rows = [i for i in rows if i['messages'][-1]['content'] != '']

    with open(path, 'w') as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

clean("test.jsonl")
clean("test_ood.jsonl")