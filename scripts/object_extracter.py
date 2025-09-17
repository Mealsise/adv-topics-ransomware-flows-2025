import json
from pathlib import Path
from pprint import pprint

# File path
file_path = Path("flows/Change Healthcare - BlackCat (ALPHV).afb")

# IDs to ignore
skip_ids = {"horizontal_anchor", "vertical_anchor", "dynamic_line", "generic_latch", "generic_handle"}

# Skip individual keys within each object
skip_elements = {"instance", "anchors", "objects"}

def main():
    # Load the JSON
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    objects = data.get("objects", [])

    filtered = []
    for obj in objects:
        if obj.get("id") in skip_ids:
            continue

        # Remove unwanted keys from a copy of the object
        cleaned = {k: v for k, v in obj.items() if k not in skip_elements}
        filtered.append(cleaned)

    # Pretty print result
    pprint(filtered)

if __name__ == "__main__":
    main()
