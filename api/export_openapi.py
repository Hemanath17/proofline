"""Dev-only: writes the FastAPI app's OpenAPI schema to api/openapi.json,
the source `openapi-typescript` reads to generate web/lib/api-types.ts
(CLAUDE.md: "API types are generated from FastAPI's OpenAPI schema, never
written by hand"). Run this, then `npm --prefix web run gen-api-types`,
whenever a route changes.

    python3 export_openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path

from proofline.app import app

if __name__ == "__main__":
    schema = app.openapi()
    out_path = Path(__file__).resolve().parent / "openapi.json"
    out_path.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {out_path}")
