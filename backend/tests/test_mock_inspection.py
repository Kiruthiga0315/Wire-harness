import asyncio
from collections.abc import Generator

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import inspections as inspection_routes
from app.core.database import Base, get_db, seed_demo_data
from app.main import app
from app.models import Checkpoint, ProductModel
from app.services.mock_inspection_service import MockInspectionService


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


def test_seeded_demo_recipe_returns_nine_pass_and_three_ng() -> None:
    engine, factory = make_demo_database()
    try:
        with factory() as session:
            model = session.scalar(
                select(ProductModel).where(ProductModel.model_id == "DEMO-HARNESS-001")
            )
            assert model is not None
            checkpoints = list(
                session.scalars(
                    select(Checkpoint)
                    .where(
                        Checkpoint.model_id == model.model_id,
                        Checkpoint.checkpoint_id.like("CP-%"),
                    )
                    .order_by(Checkpoint.id)
                )
            )
            response = MockInspectionService().evaluate(model, checkpoints)

        assert model.model_name == "Client Wire Harness Sample"
        assert len(checkpoints) == 12
        assert response.total_checkpoints == 12
        assert response.passed == 9
        assert response.failed == 3
        assert response.state == "NG"
        assert {item.checkpoint_id for item in response.results if item.status == "NG"} == {
            "CP-004",
            "CP-008",
            "CP-011",
        }
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_mock_inspection_api_returns_deterministic_result(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    engine, factory = make_demo_database()

    def override_get_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(inspection_routes, "DEMO_PROCESSING_SECONDS", 0.0)

    async def request_inspection() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/inspections/demo/process",
                json={"model_id": "DEMO-HARNESS-001"},
            )

    try:
        response = asyncio.run(request_inspection())
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_checkpoints"] == 12
        assert payload["passed"] == 9
        assert payload["failed"] == 3
        assert payload["state"] == "NG"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()  # type: ignore[attr-defined]
