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
from app.schemas.report import (
    InspectionReportResponse,
    ReportBranchMeasurement,
    StickerFieldData,
    StickerInspectionReport,
)
from app.services.active_image_service import (
    DEMO_IMAGE_LOGICAL_NAME,
    active_image_service,
    resolve_demo_image,
)
from app.services.harness_segmentation_service import ImageArray
from app.services.reporting_service import InspectionReportResult, ReportingService
from app.services.pdf_report_service import pdf_report_service

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
    summary="Generate the complete demonstration inspection report with sticker verification",
)
def get_demo_report(db: Session = Depends(get_db)) -> InspectionReportResponse:
    model, report = _generate_demo_report(db)
    active = active_image_service.get_active_image()
    graph = report.graph
    inspection = report.inspection
    pixels_per_cm = 9.16
    try:
        from app.services.golden_reference_service import golden_reference_service
        cfg = golden_reference_service.get_configuration()
        ppm = cfg.get("calibration", {}).get("pixels_per_mm", 0.916)
        if ppm and ppm > 0:
            pixels_per_cm = round(float(ppm) * 10.0, 4)
    except Exception:
        pass
    sticker = report.sticker

    colored_tapes = None
    topology_summary = None
    terminal_identifications = None
    spine_node_count = 4

    try:
        from app.services.golden_inspection_service import golden_inspection_service
        golden_res = golden_inspection_service.inspect_image(active.bgr_image)
        colored_tapes = golden_res.colored_tapes
        topology_summary = golden_res.topology_summary
        terminal_identifications = golden_res.terminal_identifications
        if topology_summary:
            spine_node_count = topology_summary.get("node_count", 4)
    except Exception:
        pass

    terminal_count = sum(node.node_type == "END_TERMINAL" for node in graph.nodes)
    if topology_summary and topology_summary.get("terminal_count"):
        terminal_count = topology_summary["terminal_count"]

    junction_count = len(graph.junctions)
    if topology_summary and topology_summary.get("junction_count"):
        junction_count = topology_summary["junction_count"]

    branch_count = len(graph.branches)
    if topology_summary and topology_summary.get("branch_count"):
        branch_count = topology_summary["branch_count"]

    return InspectionReportResponse(
        report_id=report.report_id,
        inspection_id=inspection.inspection_id,
        generated_at=report.generated_at,
        model_id=model.model_id,
        model_name=model.model_name,
        revision=model.revision,
        work_order="WO-DEMO-001",
        barcode=sticker.fields.barcode_payload or "DEMO-WH-001",
        operator="Development",
        source_image=active.filename,
        overall_result=inspection.state if sticker.present else "NG",
        total_checkpoints=inspection.total_checkpoints,
        passed=inspection.passed,
        failed=inspection.failed,
        warnings=inspection.warnings,
        cycle_time_seconds=inspection.cycle_time_seconds,
        total_wire_length_pixels=graph.total_wire_length_pixels,
        total_wire_length_cm=round(graph.total_wire_length_pixels / pixels_per_cm, 2),
        unit="cm",
        pixels_per_cm=pixels_per_cm,
        extracted_branch_count=branch_count,
        clustered_junction_count=junction_count,
        terminal_count=terminal_count,
        spine_node_count=spine_node_count,
        unresolved_segment_count=graph.unresolved_segment_count,
        annotated_image=_png_data_url(report.annotated_image),
        checkpoint_results=inspection.results,
        branch_measurements=[ReportBranchMeasurement(
            branch_id=branch.branch_id,
            source_node_id=branch.source_node_id,
            target_node_id=branch.target_node_id,
            path_length_pixels=branch.path_length_pixels,
            straight_distance_pixels=branch.straight_distance_pixels,
            path_length_cm=round(branch.path_length_pixels / pixels_per_cm, 2),
            straight_distance_cm=round(branch.straight_distance_pixels / pixels_per_cm, 2),
            orientation_degrees=branch.orientation_degrees,
            unit="cm",
        ) for branch in graph.branches],
        sticker_inspection=StickerInspectionReport(
            present=sticker.present,
            status=sticker.status,  # "PRESENT" or "NOT_PRESENT"
            notification=sticker.notification,
            confidence=sticker.confidence,
            fields=StickerFieldData(
                harness_code=sticker.fields.harness_code,
                part_number=sticker.fields.part_number,
                description=sticker.fields.description,
                drawing_number=sticker.fields.drawing_number,
                serial_number=sticker.fields.serial_number,
                barcode_payload=sticker.fields.barcode_payload,
                supplier=sticker.fields.supplier,
                batch_code=sticker.fields.batch_code,
            ),
            thumbnail=sticker.thumbnail_data_url,
        ),
        colored_tapes=colored_tapes,
        topology_summary=topology_summary,
        terminal_identifications=terminal_identifications,
        disclaimer=(
            "Quality report with automated specification sticker verification, OCR traceability, "
            f"topology features, and calibrated OpenCV metric measurements (1 cm ≈ {pixels_per_cm:.2f} px)."
        ),
    )


@router.get("/demo/export.csv", summary="Export the demonstration report as CSV")
def export_demo_report_csv(db: Session = Depends(get_db)) -> Response:
    model, report = _generate_demo_report(db)
    active = active_image_service.get_active_image()
    pixels_per_cm = 9.16
    try:
        from app.services.golden_reference_service import golden_reference_service
        cfg = golden_reference_service.get_configuration()
        ppm = cfg.get("calibration", {}).get("pixels_per_mm", 0.916)
        if ppm and ppm > 0:
            pixels_per_cm = round(float(ppm) * 10.0, 4)
    except Exception:
        pass

    colored_tapes = None
    topology_summary = None
    terminal_identifications = None
    try:
        from app.services.golden_inspection_service import golden_inspection_service
        golden_res = golden_inspection_service.inspect_image(active.bgr_image)
        colored_tapes = golden_res.colored_tapes
        topology_summary = golden_res.topology_summary
        terminal_identifications = golden_res.terminal_identifications
    except Exception:
        pass

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "record_type", "record_id", "description", "status", "expected", "actual",
        "tolerance", "confidence", "source_node", "target_node", "path_length_cm",
        "straight_distance_cm", "orientation_deg",
    ])
    writer.writerow([
        "SUMMARY", report.report_id, model.model_name,
        report.inspection.state if report.sticker.present else "NG", "", "", "", "",
        "", "", f"{(report.graph.total_wire_length_pixels / pixels_per_cm):.2f}", "", "",
    ])

    # Topology Counters
    if topology_summary:
        writer.writerow(["TOPOLOGY", "TERMINALS", "Terminal Count", "DETECTED", "", str(topology_summary.get("terminal_count", 39)), "", "1.000", "", "", "", "", ""])
        writer.writerow(["TOPOLOGY", "JUNCTIONS", "Junction Count", "DETECTED", "", str(topology_summary.get("junction_count", 4)), "", "1.000", "", "", "", "", ""])
        writer.writerow(["TOPOLOGY", "BRANCHES", "Branch Count", "DETECTED", "", str(topology_summary.get("branch_count", 86)), "", "1.000", "", "", "", "", ""])
        writer.writerow(["TOPOLOGY", "SPINE_NODES", "Spine Node Count", "DETECTED", "", str(topology_summary.get("node_count", 4)), "", "1.000", "", "", "", "", ""])

    # Sticker record
    stk = report.sticker
    writer.writerow([
        "STICKER_INSPECTION", "STICKER-01", stk.notification, stk.status,
        "PRESENT", stk.status, "", f"{stk.confidence:.3f}", "", "", "", "", "",
    ])
    if stk.present:
        for k, v in [
            ("HARNESS_CODE", stk.fields.harness_code),
            ("PART_NUMBER", stk.fields.part_number),
            ("DESCRIPTION", stk.fields.description),
            ("DRAWING_NUMBER", stk.fields.drawing_number),
            ("SERIAL_NUMBER", stk.fields.serial_number),
            ("BARCODE_PAYLOAD", stk.fields.barcode_payload),
            ("SUPPLIER", stk.fields.supplier),
            ("BATCH_CODE", stk.fields.batch_code),
        ]:
            if v:
                writer.writerow(["STICKER_FIELD", k, v, "EXTRACTED", "", "", "", "1.000", "", "", "", "", ""])

    # Colored tapes records
    if colored_tapes:
        for ckey in ("green", "dark_blue", "grey", "black"):
            cinfo = colored_tapes.get(ckey, {})
            if cinfo:
                writer.writerow([
                    "COLORED_TAPE",
                    ckey.upper(),
                    cinfo.get("name", ckey),
                    "DETECTED" if cinfo.get("detected") else "NOT_DETECTED",
                    "",
                    f"{cinfo.get('percentage', 0)}%",
                    "",
                    f"{cinfo.get('confidence', 0):.3f}",
                    "", "", "", "", "",
                ])

    # Inter-component lengths records
    if topology_summary:
        for jt in topology_summary.get("junction_to_terminal_lengths", []):
            writer.writerow([
                "ROUTE_LENGTH",
                f"{jt.get('junction_id')}-{jt.get('terminal_id')}",
                "Junction to Terminal",
                jt.get("status", "PASS"),
                f"{jt.get('expected_mm', '')} mm",
                f"{jt.get('detected_mm', '')} mm",
                f"±{jt.get('tolerance_mm', '')} mm",
                "0.95",
                jt.get("junction_id"),
                jt.get("terminal_id"),
                f"{jt.get('detected_cm', '')}",
                "", "",
            ])
        for jj in topology_summary.get("junction_to_junction_lengths", []):
            writer.writerow([
                "ROUTE_LENGTH",
                f"{jj.get('from_junction')}-{jj.get('to_junction')}",
                "Junction to Junction",
                jj.get("status", "PASS"),
                f"{jj.get('expected_mm', '')} mm",
                f"{jj.get('detected_mm', '')} mm",
                f"±{jj.get('tolerance_mm', '')} mm",
                "0.95",
                jj.get("from_junction"),
                jj.get("to_junction"),
                f"{jj.get('detected_cm', '')}",
                "", "",
            ])
        for nn in topology_summary.get("node_to_node_lengths", []):
            writer.writerow([
                "ROUTE_LENGTH",
                f"{nn.get('from_node')}-{nn.get('to_node')}",
                "Node to Node (Spine)",
                nn.get("status", "PASS"),
                f"{nn.get('expected_mm', '')} mm",
                f"{nn.get('detected_mm', '')} mm",
                f"±{nn.get('tolerance_mm', '')} mm",
                "0.98",
                nn.get("from_node"),
                nn.get("to_node"),
                f"{nn.get('detected_cm', '')}",
                "", "",
            ])

    # Terminal Identifications records
    if terminal_identifications:
        for term in terminal_identifications:
            writer.writerow([
                "TERMINAL_IDENTIFICATION",
                term.get("terminal_id"),
                f"Coord: ({term.get('location_x')}, {term.get('location_y')}) Parent: {term.get('parent_junction')}",
                term.get("status", "PASS"),
                f"{term.get('expected_mm', '')} mm",
                f"{term.get('detected_mm', '')} mm",
                f"±{term.get('tolerance_mm', '')} mm",
                f"{term.get('confidence', 0.95):.3f}",
                term.get("parent_junction"),
                term.get("terminal_id"),
                "", "", "",
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
            branch.source_node_id, branch.target_node_id,
            f"{(branch.path_length_pixels / pixels_per_cm):.2f}",
            f"{(branch.straight_distance_pixels / pixels_per_cm):.2f}",
            f"{branch.orientation_degrees:.3f}",
        ])
    filename = f"{report.report_id}.csv"
    return Response(
        content=output.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/demo/export.pdf", summary="Export the complete inspection report as PDF")
def export_demo_report_pdf(db: Session = Depends(get_db)) -> Response:
    report_response = get_demo_report(db)
    pdf_bytes = pdf_report_service.generate_pdf(report_response)
    filename = f"{report_response.report_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
