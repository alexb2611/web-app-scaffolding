"""Dump the FastAPI OpenAPI schema to a JSON file or stdout.

Used to keep the frontend's generated TypeScript types in lock-step with
the backend contract. Run via the Make target:

    make generate-api

Usage:

    python scripts/export_openapi.py                # default path
    python scripts/export_openapi.py path/to/file   # explicit path
    python scripts/export_openapi.py -              # write to stdout

The `-` form is what `make generate-api` uses so the Makefile can pipe
the output to the host's `frontend/openapi.json` from inside Docker —
otherwise `Path(__file__).resolve().parents[2]` resolves to `/` inside
the container and the script silently writes to a file the host never
sees.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import app


def main() -> None:
    schema = app.openapi()
    rendered = json.dumps(schema, indent=2, sort_keys=True) + "\n"

    if len(sys.argv) > 1 and sys.argv[1] == "-":
        # stdout — let the caller redirect to the right host path.
        sys.stdout.write(rendered)
        return

    default_out = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered)
    print(f"wrote {out_path}")  # noqa: T201 — intentional CLI output


if __name__ == "__main__":
    main()
