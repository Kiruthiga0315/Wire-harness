from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Checkpoint, ProductModel
from app.schemas.checkpoint import CheckpointCreate, CheckpointUpdate


class ModelNotFoundError(LookupError):
    pass


class CheckpointNotFoundError(LookupError):
    pass


class DuplicateCheckpointError(ValueError):
    pass


class CheckpointService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_model(self, model_id: str) -> list[Checkpoint]:
        self._require_model(model_id)
        statement = (
            select(Checkpoint)
            .where(Checkpoint.model_id == model_id)
            .order_by(Checkpoint.id)
        )
        return list(self.session.scalars(statement))

    def create(self, model_id: str, payload: CheckpointCreate) -> Checkpoint:
        self._require_model(model_id)
        data = payload.model_dump(exclude={"checkpoint_id"})
        checkpoint = Checkpoint(
            **data,
            model_id=model_id,
            checkpoint_id=payload.checkpoint_id or self._next_checkpoint_id(model_id),
        )
        self.session.add(checkpoint)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise DuplicateCheckpointError("Checkpoint ID already exists for this model") from exc
        self.session.refresh(checkpoint)
        return checkpoint

    def update(self, model_id: str, checkpoint_id: str, payload: CheckpointUpdate) -> Checkpoint:
        checkpoint = self._require_checkpoint(model_id, checkpoint_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(checkpoint, field, value)
        self.session.commit()
        self.session.refresh(checkpoint)
        return checkpoint

    def delete(self, model_id: str, checkpoint_id: str) -> None:
        checkpoint = self._require_checkpoint(model_id, checkpoint_id)
        self.session.delete(checkpoint)
        self.session.commit()

    def _require_model(self, model_id: str) -> ProductModel:
        model = self.session.scalar(select(ProductModel).where(ProductModel.model_id == model_id))
        if model is None:
            raise ModelNotFoundError(model_id)
        return model

    def _require_checkpoint(self, model_id: str, checkpoint_id: str) -> Checkpoint:
        statement = select(Checkpoint).where(
            Checkpoint.model_id == model_id,
            Checkpoint.checkpoint_id == checkpoint_id,
        )
        checkpoint = self.session.scalar(statement)
        if checkpoint is None:
            raise CheckpointNotFoundError(checkpoint_id)
        return checkpoint

    def _next_checkpoint_id(self, model_id: str) -> str:
        statement = select(Checkpoint.checkpoint_id).where(Checkpoint.model_id == model_id)
        highest = 0
        for checkpoint_id in self.session.scalars(statement):
            if checkpoint_id.startswith("ENG-") and checkpoint_id[4:].isdigit():
                highest = max(highest, int(checkpoint_id[4:]))
        return f"ENG-{highest + 1:03d}"
