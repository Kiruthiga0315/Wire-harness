from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.settings import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> tuple[bool, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:  # pragma: no cover - depends on external database state
        return False, f"unavailable: {exc.__class__.__name__}"


def initialize_database() -> None:
    from app.models import Checkpoint, ProductModel  # noqa: F401

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        seed_demo_data(session)

    if settings.database_url.startswith("sqlite"):
        with engine.begin() as connection:
            connection.execute(text("PRAGMA optimize"))


def seed_demo_data(session: Session) -> None:
    from app.models import Checkpoint, ProductModel

    model_id = "DEMO-HARNESS-001"
    demo_model = session.query(ProductModel).filter_by(model_id=model_id).one_or_none()
    if demo_model is None:
        demo_model = ProductModel(
            model_id=model_id,
            model_name="Client Wire Harness Sample",
            description="Client wire harness sample for deterministic inspection demonstration.",
            revision="V1.0",
            active=True,
        )
        session.add(demo_model)
    else:
        demo_model.model_name = "Client Wire Harness Sample"
        demo_model.description = "Client wire harness sample for deterministic inspection demonstration."
        demo_model.active = True

    checkpoint_specs = [
        ("CP-001", "Upper End Terminal Presence", "Terminal", "Presence", "Present", None, 1130, 410, 140, 120),
        ("CP-002", "Upper Connector Presence", "Connector", "Presence", "Present", None, 1260, 410, 150, 140),
        ("CP-003", "Main Junction Position", "Junction", "Position", "X 1430 / Y 620", 20.0, 1430, 620, 180, 160),
        ("CP-004", "Branch Connector Orientation", "Orientation", "Orientation", "90 degrees", 5.0, 1535, 545, 140, 140),
        ("CP-005", "Right Connector Presence", "Connector", "Presence", "Present", None, 1635, 555, 150, 140),
        ("CP-006", "Upper Clip Presence", "Clip", "Presence", "Present", None, 1360, 780, 130, 120),
        ("CP-007", "Main Sleeve Presence", "Sleeve", "Presence", "Present", None, 1460, 950, 160, 220),
        ("CP-008", "Tape T1 Colour", "Tape", "Colour", "Blue", None, 1480, 800, 130, 130),
        ("CP-009", "Lower Connector Presence", "Connector", "Presence", "Present", None, 1670, 1180, 150, 150),
        ("CP-010", "Overall Harness Routing", "Routing", "Routing", "Within reference route", 25.0, 1420, 1300, 240, 200),
        ("CP-011", "Branch B2 Length", "Dimension", "Length", "750 mm", 10.0, 1330, 1600, 260, 220),
        ("CP-012", "Lower End Terminal Presence", "Terminal", "Presence", "Present", None, 1650, 1860, 160, 140),
    ]

    existing_checkpoints = {
        checkpoint.checkpoint_id: checkpoint
        for checkpoint in session.query(Checkpoint)
        .filter(Checkpoint.model_id == model_id)
        .all()
    }
    for spec in checkpoint_specs:
        checkpoint_id, name, category, inspection_type, expected, tolerance, x, y, roi_width, roi_height = spec
        existing = existing_checkpoints.get(checkpoint_id)
        if existing is not None:
            existing.checkpoint_name = name
            existing.category = category
            existing.inspection_type = inspection_type
            existing.expected_value = expected
            existing.tolerance = tolerance
            existing.reference_x = x
            existing.reference_y = y
            existing.roi_width = roi_width
            existing.roi_height = roi_height
            existing.enabled = True
            continue
        session.add(
            Checkpoint(
                checkpoint_id=checkpoint_id,
                model_id=model_id,
                checkpoint_name=name,
                category=category,
                inspection_type=inspection_type,
                expected_value=expected,
                tolerance=tolerance,
                reference_x=x,
                reference_y=y,
                roi_width=roi_width,
                roi_height=roi_height,
                enabled=True,
            )
        )
    session.commit()
