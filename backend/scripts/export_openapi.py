"""Dump the FastAPI OpenAPI schema to a JSON file.

Used to keep the frontend's generated TypeScript types in lock-step with
the backend contract. Run via the Make target:

    make generate-api

The output path defaults to ../frontend/openapi.json relative to this
file but can be overridden with the first positional argument.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import app


def main() -> None:
    default_out = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    schema = app.openapi()
    out_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out_path}")  # noqa: T201 — intentional CLI output


if __name__ == "__main__":
    main()
