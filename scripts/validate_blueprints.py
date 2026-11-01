"""Structural validation only; does not create or modify Render resources."""

import json
import urllib.request
from pathlib import Path
import jsonschema
import yaml

with urllib.request.urlopen(
    "https://render.com/schema/render.yaml.json", timeout=30
) as response:
    schema = json.load(response)
for path in ["render.yaml", "deploy/render.staging.yaml"]:
    jsonschema.validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")), schema)
    print(f"{path}: schema valid")
