import asyncio
from collections.abc import Generator

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db, seed_demo_data
from app.main import app


def make_demo_database() -> tuple[object, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as session:
        seed_demo_data(session)
    return engine, factory


def test_demo_report_contains_checkpoint_and_length_evidence() -> None:
    engine, factory = make_demo_database()

    def override_get_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async def request_report() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/reports/demo")

    try:
        response = asyncio.run(request_report())
        assert response.status_code == 200
        payload = response.json()
        assert payload["overall_result"] == "NG"
        assert payload["passed"] == 9
        assert payload["failed"] == 3
        assert payload["total_wire_length_pixels"] > 0
        assert payload["extracted_branch_count"] == len(payload["branch_measurements"])
        assert payload["annotated_image"].startswith("data:image/png;base64,")
        assert len(payload["checkpoint_results"]) == 12
    finally:
        app.dependency_overrides.clear()
        engine.dispose()  # type: ignore[attr-defined]


def test_demo_report_csv_contains_summary_checkpoints_and_branches() -> None:
    engine, factory = make_demo_database()

    def override_get_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async def request_csv() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/reports/demo/export.csv")

    try:
        response = asyncio.run(request_csv())
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment; filename=" in response.headers["content-disposition"]
        assert "SUMMARY" in response.text
        assert "CHECKPOINT,CP-004" in response.text
        assert "BRANCH,B001" in response.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()  # type: ignore[attr-defined]
