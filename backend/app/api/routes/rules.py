from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

import cv2
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
import numpy as np
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.settings import get_settings
from app.models.rule_verdict import RuleVerdictRecord
from app.services.active_image_service import active_image_service
from app.services.cloud_io import decode_uploaded_image
from app.services.rules.engine import rule_engine
from app.services.rules.loader import rule_pack_loader
from app.services.rules.schemas import (
    HarnessVerdict,
    InspectionContext,
    OperatorInput,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rules", tags=["rules"])


def _results_dir() -> Path:
    res_dir = get_settings().project_root / "data" / "inspection_results"
    res_dir.mkdir(parents=True, exist_ok=True)
    return res_dir


def _persist_verdict(verdict: HarnessVerdict, operator_input: OperatorInput | None, db: Session) -> None:
    """Persists verdict to both SQLite database and filesystem JSON snapshot."""
    # 1. Save JSON snapshot
    try:
        results_path = _results_dir() / f"{verdict.verdict_id}.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(verdict.model_dump(), f, indent=2)
    except Exception as exc:
        logger.warning("Failed to save inspection verdict JSON snapshot: %s", exc)

    # 2. Persist to DB table rule_verdicts
    try:
        record = RuleVerdictRecord(
            verdict_id=verdict.verdict_id,
            verdict=verdict.verdict,
            variant=verdict.variant,
            part_no=verdict.part_no,
            rule_pack_version=verdict.rule_pack_version,
            calibration_provenance=verdict.calibration_provenance,
            image_hash=verdict.image_hash,
            total_rules=verdict.summary.get("TOTAL", len(verdict.rule_results)),
            passed_count=verdict.summary.get("PASS", 0),
            failed_count=verdict.summary.get("FAIL", 0),
            review_count=verdict.summary.get("REVIEW", 0),
            not_evaluated_count=verdict.summary.get("NOT_EVALUATED", 0),
            reaction_plan=verdict.reaction_plan,
            results_json=[r.model_dump() for r in verdict.rule_results],
            summary_json=verdict.summary,
            reasons_json=verdict.reasons,
            operator_input_json=operator_input.model_dump() if operator_input else {},
        )
        db.add(record)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to persist RuleVerdictRecord to database: %s", exc)


class RuleEvaluationRequest(BaseModel):
    variant: str = "YH200502"
    part_no: str = "YH200502"
    use_active_image: bool = True
    image_base64: str | None = None
    operator_input: OperatorInput | None = None


@router.post("/evaluate", response_model=HarnessVerdict)
def evaluate_rules(
    request: RuleEvaluationRequest,
    db: Session = Depends(get_db),
) -> HarnessVerdict:
    """Deterministic evaluation of harness quality rules against vision evidence and operator inputs."""
    # 1. Acquire Image
    if request.image_base64:
        try:
            raw_bytes = base64.b64decode(request.image_base64)
            bgr_image = decode_uploaded_image(raw_bytes, filename="uploaded_inspection.png")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to decode base64 image: {exc}",
            ) from exc
    elif request.use_active_image:
        try:
            active_rec = active_image_service.get_active_image()
            bgr_image = active_rec.bgr_image
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to load active inspection image: {exc}",
            ) from exc
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must either provide image_base64 or set use_active_image=True",
        )

    # 2. Run Deterministic Rule Engine
    verdict = rule_engine.evaluate_image(
        image=bgr_image,
        operator_input=request.operator_input,
        variant=request.variant,
        part_no=request.part_no,
    )

    # 3. Persist Verdict
    _persist_verdict(verdict, request.operator_input, db)

    return verdict


@router.post("/evaluate/upload", response_model=HarnessVerdict)
def evaluate_uploaded_image(
    file: UploadFile = File(...),
    variant: str = Form("YH200502"),
    part_no: str = Form("YH200502"),
    operator_inputs_json: str | None = Form(None),
    db: Session = Depends(get_db),
) -> HarnessVerdict:
    """Evaluate an uploaded image file with optional JSON-encoded operator inputs."""
    try:
        content = file.file.read()
        bgr_image = decode_uploaded_image(content, filename=file.filename or "upload.png")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image file upload: {exc}",
        ) from exc

    op_input = None
    if operator_inputs_json:
        try:
            data = json.loads(operator_inputs_json)
            op_input = OperatorInput.model_validate(data)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Malformed operator_inputs_json: {exc}",
            ) from exc

    verdict = rule_engine.evaluate_image(
        image=bgr_image,
        operator_input=op_input,
        variant=variant,
        part_no=part_no,
    )

    _persist_verdict(verdict, op_input, db)
    return verdict


@router.get("/pack")
def get_rule_packs(
    pack_id: str | None = Query(None, description="Specific rule pack ID, or all if omitted"),
) -> dict[str, Any]:
    """Retrieve versioned rule pack configurations."""
    if pack_id:
        try:
            return rule_pack_loader.get_pack(pack_id)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rule pack '{pack_id}' not found",
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return rule_pack_loader.load_all_packs()


@router.get("/verdicts/{verdict_id}", response_model=dict[str, Any])
def get_verdict_by_id(
    verdict_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve historical rule inspection verdict by ID."""
    # Check DB first
    record = db.query(RuleVerdictRecord).filter_by(verdict_id=verdict_id).first()
    if record:
        return {
            "verdict_id": record.verdict_id,
            "timestamp": record.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "verdict": record.verdict,
            "variant": record.variant,
            "part_no": record.part_no,
            "rule_pack_version": record.rule_pack_version,
            "calibration_provenance": record.calibration_provenance,
            "image_hash": record.image_hash,
            "summary": record.summary_json,
            "reaction_plan": record.reaction_plan,
            "reasons": record.reasons_json,
            "rule_results": record.results_json,
            "operator_input": record.operator_input_json,
        }

    # Check filesystem snapshot
    json_path = _results_dir() / f"{verdict_id}.json"
    if json_path.is_file():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Error reading verdict JSON file %s: %s", json_path, exc)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Verdict '{verdict_id}' not found",
    )


@router.get("/verdicts", response_model=list[dict[str, Any]])
def list_verdicts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List recent inspection verdicts with summary metrics."""
    records = (
        db.query(RuleVerdictRecord)
        .order_by(RuleVerdictRecord.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "verdict_id": r.verdict_id,
            "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "verdict": r.verdict,
            "variant": r.variant,
            "part_no": r.part_no,
            "rule_pack_version": r.rule_pack_version,
            "calibration_provenance": r.calibration_provenance,
            "total_rules": r.total_rules,
            "passed_count": r.passed_count,
            "failed_count": r.failed_count,
            "review_count": r.review_count,
            "not_evaluated_count": r.not_evaluated_count,
            "reaction_plan": r.reaction_plan,
        }
        for r in records
    ]
