from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.checkpoint import CheckpointCreate, CheckpointRead, CheckpointUpdate
from app.services.checkpoint_service import (
    CheckpointNotFoundError,
    CheckpointService,
    DuplicateCheckpointError,
    ModelNotFoundError,
)

router = APIRouter(prefix="/models/{model_id}/checkpoints", tags=["Checkpoints"])


@router.get("", response_model=list[CheckpointRead], summary="List model checkpoints")
def list_checkpoints(model_id: str, db: Session = Depends(get_db)) -> list[CheckpointRead]:
    try:
        return CheckpointService(db).list_for_model(model_id)  # type: ignore[return-value]
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Product model not found") from exc


@router.post("", response_model=CheckpointRead, status_code=status.HTTP_201_CREATED)
def create_checkpoint(
    model_id: str,
    payload: CheckpointCreate,
    db: Session = Depends(get_db),
) -> CheckpointRead:
    try:
        return CheckpointService(db).create(model_id, payload)  # type: ignore[return-value]
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Product model not found") from exc
    except DuplicateCheckpointError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/{checkpoint_id}", response_model=CheckpointRead)
def update_checkpoint(
    model_id: str,
    checkpoint_id: str,
    payload: CheckpointUpdate,
    db: Session = Depends(get_db),
) -> CheckpointRead:
    try:
        return CheckpointService(db).update(model_id, checkpoint_id, payload)  # type: ignore[return-value]
    except CheckpointNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Checkpoint not found") from exc


@router.delete("/{checkpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_checkpoint(
    model_id: str,
    checkpoint_id: str,
    db: Session = Depends(get_db),
) -> Response:
    try:
        CheckpointService(db).delete(model_id, checkpoint_id)
    except CheckpointNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Checkpoint not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
