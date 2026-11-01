from __future__ import annotations

from datetime import UTC, datetime
from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RuleVerdictRecord(Base):
    """SQLAlchemy model for persistent harness rule verdicts."""

    __tablename__ = "rule_verdicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verdict_id: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)  # ACCEPT, REJECT, HOLD
    variant: Mapped[str] = mapped_column(String(80), nullable=False)
    part_no: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_pack_version: Mapped[str] = mapped_column(String(40), default="1.0.0", nullable=False)
    calibration_provenance: Mapped[str] = mapped_column(String(40), default="uncalibrated", nullable=False)
    image_hash: Mapped[str] = mapped_column(String(128), default="", nullable=False)

    total_rules: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    not_evaluated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    reaction_plan: Mapped[str] = mapped_column(Text, default="", nullable=False)
    results_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reasons_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    operator_input_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
