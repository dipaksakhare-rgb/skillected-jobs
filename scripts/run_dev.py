"""Run the development server.

Usage: python scripts/run_dev.py [port]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Must be set BEFORE importing the app: settings are read at import time. Keeps
# generated share links (WhatsApp/QR/posters/sitemap) consistent with the actual
# serving port unless APP_BASE_URL was set explicitly.
_port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
os.environ.setdefault("APP_BASE_URL", f"http://127.0.0.1:{_port}")

import uvicorn  # noqa: E402

from app import create_app  # noqa: E402


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    app = create_app()
    print(f"Skillected Jobs running at http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
