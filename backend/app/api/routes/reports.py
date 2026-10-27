from __future__ import annotations

import base64
import csv
import io

import cv2
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Checkpoint, ProductModel
from app.schemas.report import InspectionReportResponse, ReportBranchMeasurement
from app.services.active_image_service import (
    DEMO_IMAGE_LOGICAL_NAME,
    active_image_service,
    resolve_demo_image,
)
from app.services.harness_segmentation_service import ImageArray
from app.services.reporting_service import InspectionReportResult, ReportingService

router = APIRouter(prefix="/reports", tags=["Reports"])
reporting_service = ReportingService()
DEMO_MODEL_ID = "DEMO-HARNESS-001"


def _png_data_url(image: ImageArray) -> str:
    encoded, png = cv2.imencode(".png", image)
    if not encoded:
        raise RuntimeError("OpenCV could not encode the annotated report image")
    payload = base64.b64encode(png.tobytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def _generate_demo_report(db: Session) -> tuple[ProductModel, InspectionReportResult]:
    model = db.scalar(select(ProductModel).where(ProductModel.model_id == DEMO_MODEL_ID))
    if model is None:
        raise HTTPException(status_code=404, detail="Demo product model not found")
    checkpoints = list(db.scalars(
        select(Checkpoint)
        .where(
            Checkpoint.model_id == DEMO_MODEL_ID,
            Checkpoint.enabled.is_(True),
            Checkpoint.checkpoint_id.like("CP-%"),
        )
        .order_by(Checkpoint.id)
    ))
    if not checkpoints:
        raise HTTPException(status_code=422, detail="No enabled demo checkpoints are configured")

    active = active_image_service.get_active_image()
    image = active.bgr_image
    try:
        return model, reporting_service.generate(model, checkpoints, image)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=f"Report generation failed: {exc}") from exc


@router.get(
    "/demo",
    response_model=InspectionReportResponse,
    summary="Generate the complete demonstration inspection report",
)
def get_demo_report(db: Session = Depends(get_db)) -> InspectionReportResponse:
    model, report = _generate_demo_report(db)
    active = active_image_service.get_active_image()
    graph = report.graph
    inspection = report.inspection
    return InspectionReportResponse(
        report_id=report.report_id,
        inspection_id=inspection.inspection_id,
        generated_at=report.generated_at,
        model_id=model.model_id,
        model_name=model.model_name,
        revision=model.revision,
        work_order="WO-DEMO-001",
        barcode="DEMO-WH-001",
        operator="Development",
        source_image=active.filename,
        overall_result=inspection.state,
        total_checkpoints=inspection.total_checkpoints,
        passed=inspection.passed,
        failed=inspection.failed,
        warnings=inspection.warnings,
        cycle_time_seconds=inspection.cycle_time_seconds,
        total_wire_length_pixels=graph.total_wire_length_pixels,
        extracted_branch_count=len(graph.branches),
        clustered_junction_count=len(graph.junctions),
        terminal_count=sum(node.node_type == "END_TERMINAL" for node in graph.nodes),
        unresolved_segment_count=graph.unresolved_segment_count,
        annotated_image=_png_data_url(report.annotated_image),
        checkpoint_results=inspection.results,
        branch_measurements=[ReportBranchMeasurement(
            branch_id=branch.branch_id,
            source_node_id=branch.source_node_id,
            target_node_id=branch.target_node_id,
            path_length_pixels=branch.path_length_pixels,
            straight_distance_pixels=branch.straight_distance_pixels,
            orientation_degrees=branch.orientation_degrees,
        ) for branch in graph.branches],
        disclaimer=(
            "Development report generated from deterministic checkpoint results and experimental "
            "OpenCV topology. Lengths are uncalibrated pixels and are not valid for production PASS/NG."
        ),
    )


@router.get("/demo/export.csv", summary="Export the demonstration report as CSV")
def export_demo_report_csv(db: Session = Depends(get_db)) -> Response:
    model, report = _generate_demo_report(db)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "record_type", "record_id", "description", "status", "expected", "actual",
        "tolerance", "confidence", "source_node", "target_node", "path_length_px",
        "straight_distance_px", "orientation_deg",
    ])
    writer.writerow([
        "SUMMARY", report.report_id, model.model_name, report.inspection.state, "", "", "", "",
        "", "", f"{report.graph.total_wire_length_pixels:.3f}", "", "",
    ])
    for result in report.inspection.results:
        writer.writerow([
            "CHECKPOINT", result.checkpoint_id, result.checkpoint_name, result.status,
            result.expected_value or "", result.actual_value or "", result.tolerance or "",
            f"{result.confidence:.3f}", "", "", "", "", "",
        ])
    for branch in report.graph.branches:
        writer.writerow([
            "BRANCH", branch.branch_id, "Node-to-node centreline", "MEASURED", "", "", "", "",
            branch.source_node_id, branch.target_node_id, f"{branch.path_length_pixels:.3f}",
            f"{branch.straight_distance_pixels:.3f}", f"{branch.orientation_degrees:.3f}",
        ])
    filename = f"{report.report_id}.csv"
    return Response(
        content=output.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
