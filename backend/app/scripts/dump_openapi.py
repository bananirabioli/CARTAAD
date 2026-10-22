"""Write the OpenAPI document used to generate frontend types (make openapi)."""

import json
import sys
from pathlib import Path

from app.main import app

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "openapi.json"
out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1), encoding="utf-8")
print(f"OpenAPI → {out}")
