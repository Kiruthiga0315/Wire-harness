"""Root application entrypoint forwarding to the FastAPI application.

Ensures compatibility across cloud platforms (Render, Railway, VPS, Docker)
regardless of whether the start command uses `main:app` or `backend.app.main:app`.
"""
import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from app.main import app  # noqa: E402

__all__ = ["app"]
