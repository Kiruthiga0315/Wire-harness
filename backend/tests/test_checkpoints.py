import asyncio
from collections.abc import Generator

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import ProductModel


def test_checkpoint_crud_is_scoped_to_demo_model() -> None:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    test_session_factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    with test_session_factory() as session:
        session.add(
            ProductModel(
                model_id="DEMO-HARNESS-001",
                model_name="Checkpoint API Test Model",
                revision="V1.0",
            )
        )
        session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async def exercise_crud() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            create_response = await client.post(
                "/api/models/DEMO-HARNESS-001/checkpoints",
                json={
                    "checkpoint_name": "Main connector presence",
                    "category": "Connector",
                    "inspection_type": "Presence",
                    "expected_value": "Present",
                    "tolerance": 5,
                    "reference_x": 210,
                    "reference_y": 340,
                    "roi_width": 120,
                    "roi_height": 90,
                    "enabled": True,
                },
            )
            assert create_response.status_code == 201
            created = create_response.json()
            assert created["checkpoint_id"] == "ENG-001"
            assert created["model_id"] == "DEMO-HARNESS-001"

            list_response = await client.get("/api/models/DEMO-HARNESS-001/checkpoints")
            assert list_response.status_code == 200
            assert len(list_response.json()) == 1

            update_response = await client.put(
                "/api/models/DEMO-HARNESS-001/checkpoints/ENG-001",
                json={**created, "checkpoint_name": "Updated connector", "reference_x": 225},
            )
            assert update_response.status_code == 200
            assert update_response.json()["checkpoint_name"] == "Updated connector"
            assert update_response.json()["reference_x"] == 225

            delete_response = await client.delete(
                "/api/models/DEMO-HARNESS-001/checkpoints/ENG-001"
            )
            assert delete_response.status_code == 204

            empty_response = await client.get("/api/models/DEMO-HARNESS-001/checkpoints")
            assert empty_response.json() == []

    try:
        asyncio.run(exercise_crud())
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()


def test_sync_checkpoints_from_golden_reference() -> None:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    test_session_factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    with test_session_factory() as session:
        session.add(
            ProductModel(
                model_id="DEMO-HARNESS-001",
                model_name="Client Wire Harness Sample",
                revision="V1.0",
            )
        )
        session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async def exercise_sync() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            sync_res = await client.post(
                "/api/models/DEMO-HARNESS-001/checkpoints/sync-from-golden?replace=true"
            )
            assert sync_res.status_code == 200
            checkpoints = sync_res.json()
            assert len(checkpoints) >= 34
            # Verify CP-T01 exists and has scaled coordinates
            cpt01 = next((c for c in checkpoints if c["checkpoint_id"] == "CP-T01"), None)
            assert cpt01 is not None
            assert cpt01["category"] == "Terminal"
            assert cpt01["inspection_type"] == "Length"
            assert "cm" in (cpt01["expected_value"] or "")
            assert cpt01["reference_x"] > 0
            assert cpt01["reference_y"] > 0

            # Verify CP-008 is present for colour inspection
            cp008 = next((c for c in checkpoints if c["checkpoint_id"] == "CP-008"), None)
            assert cp008 is not None
            assert cp008["category"] == "Tape"
            assert cp008["inspection_type"] == "Colour"
            assert cp008["expected_value"] == "Blue"

            # Check engineering endpoint alias
            eng_sync_res = await client.post(
                "/api/engineering/checkpoints/sync-golden?model_id=DEMO-HARNESS-001"
            )
            assert eng_sync_res.status_code == 200
            assert len(eng_sync_res.json()) == len(checkpoints)

    try:
        asyncio.run(exercise_sync())
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()
