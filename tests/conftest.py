from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest


@pytest.fixture(autouse=True)
def _clean_active_image_environment() -> None:
    try:
        from app.services.active_image_service import active_image_service
        active_image_service.reset_to_demo()
    except Exception:
        pass

