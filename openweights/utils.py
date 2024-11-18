import json


def validate_message(message):
    try:
        assert message['role'] in ['system', 'user', 'assistant']
        assert isinstance(message['content'], str)
        return True
    except (KeyError, AssertionError):
        return False

def validate_messages(content):
    try:
        lines = content.strip().split("\n")
        for line in lines:
            row = json.loads(line)
            for message in row['messages']:
                if not validate_message(message):
                    return False
        return True
    except (json.JSONDecodeError, KeyError, ValueError, AssertionError):
        return False

def validate_preference_dataset(content):
    try:
        lines = content.strip().split("\n")
        for line in lines:
            row = json.loads(line)
            for message in row['prompt'] + row['rejected'] + row['chosen']:
                if not validate_message(message):
                    return False
        return True
    except (json.JSONDecodeError, KeyError, ValueError, AssertionError):
        return False

