"""Deep-merge a JSON fragment (stdin) into an i18n catalog file. Usage: python scripts/i18n_merge.py <catalog.json> < fragment.json"""

import json
import sys


def merge(dst: dict, src: dict) -> dict:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            merge(dst[key], value)
        else:
            dst[key] = value
    return dst


path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    catalog = json.load(fh)
merge(catalog, json.load(sys.stdin))
with open(path, "w", encoding="utf-8") as fh:
    json.dump(catalog, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
