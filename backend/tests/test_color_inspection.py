import asyncio
from collections.abc import Generator

import cv2
import httpx
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db, seed_demo_data
from app.main import app
from app.services.color_inspection_service import ColorInspectionService


@pytest.mark.parametrize(
    ("expected", "bgr"),
    [
        ("BLACK", (10, 10, 10)),
        ("WHITE", (245, 245, 245)),
        ("BLUE", (220, 60, 25)),
        ("RED", (25, 40, 220)),
        ("GREEN", (40, 190, 40)),
        ("YELLOW", (30, 220, 220)),
        ("ORANGE", (25, 120, 230)),
        ("GREY", (135, 135, 135)),
    ],
)
def test_supported_colour_classification(expected: str, bgr: tuple[int, int, int]) -> None:
    image = np.full((120, 120, 3), bgr, dtype=np.uint8)
    result = ColorInspectionService().inspect(
        image,
        expected_colour=expected,
        center_x=60,
        center_y=60,
        roi_width=80,
        roi_height=80,
    )

    assert result.detected_colour == expected
    assert result.status == "PASS"
    assert result.confidence >= 0.99
    assert len(result.mean_hsv) == 3
    assert len(result.mean_lab) == 3


def test_foreground_colour_is_not_overwhelmed_by_board_background() -> None:
    image = np.full((100, 100, 3), (180, 180, 180), dtype=np.uint8)
    cv2.rectangle(image, (44, 5), (55, 94), (220, 60, 25), -1)

    result = ColorInspectionService().inspect(
        image,
        expected_colour="BLUE",
        center_x=50,
        center_y=50,
        roi_width=100,
        roi_height=100,
    )

    assert result.detected_colour == "BLUE"
    assert result.status == "PASS"
    assert 0.5 <= result.confidence <= 1


def test_colour_api_uses_configured_checkpoint_roi_and_optional_debug_image() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as session:
        seed_demo_data(session)

    def override_get_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async def request_colour() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/engineering/color-inspection",
                json={
                    "model_id": "DEMO-HARNESS-001",
                    "checkpoint_id": "CP-008",
                    "debug": True,
                },
            )

    try:
        response = asyncio.run(request_colour())
        assert response.status_code == 200
        payload = response.json()
        assert payload["expected_colour"] == "BLUE"
        assert payload["detected_colour"] in {
            "BLACK", "WHITE", "BLUE", "RED", "GREEN", "YELLOW", "ORANGE", "GREY"
        }
        assert payload["status"] in {"PASS", "NG"}
        assert len(payload["mean_hsv"]) == 3
        assert len(payload["mean_lab"]) == 3
        assert 0 <= payload["confidence"] <= 1
        assert payload["roi"] == {"x": 315, "y": 390, "width": 100, "height": 100}
        assert payload["debug_roi_image"].startswith("data:image/png;base64,")
        assert payload["production_ready"] is False
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
