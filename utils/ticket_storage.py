import json
import os

FILE_PATH = "data/tickets.json"

def load_panels():
    if not os.path.exists(FILE_PATH):
        return {"panels": []}

    with open(FILE_PATH, "r") as f:
        return json.load(f)

def save_panels(data):
    with open(FILE_PATH, "w") as f:
        json.dump(data, f, indent=4)
