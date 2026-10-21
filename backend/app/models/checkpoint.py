from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product_model import ProductModel


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    __table_args__ = (
        UniqueConstraint("model_id", "checkpoint_id", name="uq_checkpoints_model_checkpoint"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    checkpoint_id: Mapped[str] = mapped_column(String(80), nullable=False)
    model_id: Mapped[str] = mapped_column(
        ForeignKey("product_models.model_id", ondelete="CASCADE"),
        nullable=False,
    )
    checkpoint_name: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    inspection_type: Mapped[str] = mapped_column(String(80), nullable=False)
    expected_value: Mapped[str | None] = mapped_column(String(180))
    tolerance: Mapped[float | None] = mapped_column(Float)
    reference_x: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_y: Mapped[int] = mapped_column(Integer, nullable=False)
    roi_width: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    roi_height: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    product_model: Mapped[ProductModel] = relationship(back_populates="checkpoints")
