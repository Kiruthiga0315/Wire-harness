from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.checkpoint import Checkpoint


class ProductModel(Base):
    __tablename__ = "product_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[str] = mapped_column(String(40), default="V1.0", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    checkpoints: Mapped[list[Checkpoint]] = relationship(
        back_populates="product_model",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
