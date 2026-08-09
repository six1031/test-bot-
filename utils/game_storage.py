import json
import os

COUNT_FILE = "data/counting.json"
WORD_FILE = "data/wordchain.json"

def load_json(path):
    if not os.path.exists(path):
        return {"channels": {}}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

# Counting
def load_counting():
    return load_json(COUNT_FILE)

def save_counting(data):
    save_json(COUNT_FILE, data)

# Word Chain
def load_wordchain():
    return load_json(WORD_FILE)

def save_wordchain(data):
    save_json(WORD_FILE, data)
