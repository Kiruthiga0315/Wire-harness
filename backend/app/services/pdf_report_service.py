from __future__ import annotations

import base64
import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.report import InspectionReportResponse


class PdfReportService:
    """Generates focused, single-page Specification Sticker Inspection PDF reports."""

    def generate_pdf(self, report: InspectionReportResponse) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        normal = styles["Normal"]

        eyebrow_style = ParagraphStyle(
            "Eyebrow",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0284c7"),
            textTransform="uppercase",
        )
        title_style = ParagraphStyle(
            "DocTitle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0f172a"),
        )
        meta_label = ParagraphStyle(
            "MetaLabel",
            parent=normal,
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#64748b"),
        )
        meta_val = ParagraphStyle(
            "MetaVal",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1e293b"),
        )

        field_label = ParagraphStyle(
            "FieldLabel",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#475569"),
            textTransform="uppercase",
        )
        code_val = ParagraphStyle(
            "CodeVal",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=16,
            textColor=colors.HexColor("#0284c7"),
        )
        pn_val = ParagraphStyle(
            "PnVal",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=colors.HexColor("#0f172a"),
        )
        text_val = ParagraphStyle(
            "TextVal",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1e293b"),
        )
        barcode_val = ParagraphStyle(
            "BarcodeVal",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0369a1"),
        )

        story = []

        # 1. Company & System Top Header
        top_meta = [
            [
                Paragraph("<b>AI WIRE HARNESS INSPECTION SYSTEM</b>", ParagraphStyle("SysName", fontName="Helvetica-Bold", fontSize=11, leading=13, textColor=colors.HexColor("#0b2947"))),
                Paragraph(f"<b>Report ID:</b> {report.report_id}", meta_val),
                Paragraph(f"<b>Date:</b> {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}", meta_val),
            ],
            [
                Paragraph("Automated Traceability & Specification Sticker Quality Certificate", meta_label),
                Paragraph(f"<b>Work Order:</b> {report.work_order}", meta_label),
                Paragraph(f"<b>Model:</b> {report.model_id} (Rev {report.revision})", meta_label),
            ],
        ]
        top_table = Table(top_meta, colWidths=[240, 140, 143])
        top_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(top_table)
        story.append(Spacer(1, 4))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceBefore=2, spaceAfter=8))

        # 2. Main Title Row with Status Pill
        sticker = report.sticker_inspection
        stk_is_present = sticker.present

        pill_text = "STICKER PRESENT" if stk_is_present else "NO STICKER PRESENT"
        pill_bg = colors.HexColor("#ddf4e7") if stk_is_present else colors.HexColor("#fce5e7")
        pill_border = colors.HexColor("#a9dec0") if stk_is_present else colors.HexColor("#f1b9bd")
        pill_color = colors.HexColor("#09663a") if stk_is_present else colors.HexColor("#a91f27")

        pill_p = Paragraph(f"<font color='{pill_color.hexval()}'><b>{pill_text}</b></font>", ParagraphStyle("Pill", fontName="Helvetica-Bold", fontSize=9, leading=11, alignment=1))
        pill_table = Table([[pill_p]], colWidths=[120])
        pill_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), pill_bg),
            ("BOX", (0, 0), (-1, -1), 1, pill_border),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))

        title_data = [
            [
                Paragraph("TRACEABILITY & LABELLING", eyebrow_style),
                "",
            ],
            [
                Paragraph("<b>Specification Sticker Inspection</b>", title_style),
                pill_table,
            ],
        ]
        title_table = Table(title_data, colWidths=[400, 123])
        title_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 1), (1, 1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))
        story.append(title_table)
        story.append(Spacer(1, 8))

        # 3. Notification Message Box
        if stk_is_present:
            notif_text = f"<b>✔ {sticker.notification}</b>"
            notif_bg = colors.HexColor("#f0fdf4")
            notif_border = colors.HexColor("#86efac")
            notif_color = colors.HexColor("#166534")
        else:
            notif_text = "<b>✖ NO STICKER IS PRESENT ON THIS WIRE HARNESS</b><br/><font size='7' color='#991b1b'>Inspection notification: The automated visual inspection did not detect a specification label or 2D barcode on the workpiece. Verify label placement on the assembly line.</font>"
            notif_bg = colors.HexColor("#fef2f2")
            notif_border = colors.HexColor("#fca5a5")
            notif_color = colors.HexColor("#991b1b")

        notif_p = Paragraph(f"<font color='{notif_color.hexval()}'>{notif_text}</font>", ParagraphStyle("Notif", fontName="Helvetica", fontSize=8.5, leading=12))
        notif_table = Table([[notif_p]], colWidths=[523])
        notif_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), notif_bg),
            ("BOX", (0, 0), (-1, -1), 1, notif_border),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(notif_table)
        story.append(Spacer(1, 10))

        # 4. Specification Details & Sticker Crop Layout (The exact view from the 2nd picture)
        fields = sticker.fields

        # Individual field boxes
        def make_field_box(label: str, val_p: Paragraph) -> Table:
            t = Table(
                [[Paragraph(label, field_label)], [val_p]],
                colWidths=[185],
                style=[
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ],
            )
            return t

        box_code = make_field_box("HARNESS CODE", Paragraph(fields.harness_code or "—", code_val))
        box_pn = make_field_box("PART NUMBER", Paragraph(fields.part_number or "—", pn_val))
        box_desc = make_field_box("DESCRIPTION", Paragraph(fields.description or "—", text_val))
        box_dwg = make_field_box("DRAWING NUMBER", Paragraph(fields.drawing_number or "—", text_val))
        box_barcode = make_field_box("2D BARCODE (DATA MATRIX)", Paragraph(fields.barcode_payload or "—", barcode_val))
        box_serial = make_field_box("SERIAL / LOT NO", Paragraph(fields.serial_number or "—", text_val))
        box_supplier = make_field_box("SUPPLIER / VENDOR", Paragraph(fields.supplier or "—", pn_val))
        box_batch = make_field_box("BATCH CODE", Paragraph(fields.batch_code or "—", pn_val))

        # 2-column grid for fields (2 x 4 = 8 fields)
        grid_data = [
            [box_code, box_pn],
            [box_desc, box_dwg],
            [box_barcode, box_serial],
            [box_supplier, box_batch],
        ]
        fields_grid = Table(grid_data, colWidths=[190, 190])
        fields_grid.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))

        # Thumbnail Crop Box (Right Side)
        rl_thumb = None
        if sticker.thumbnail and sticker.thumbnail.startswith("data:image"):
            try:
                raw_b64 = sticker.thumbnail.split(",", 1)[1]
                thumb_bytes = io.BytesIO(base64.b64decode(raw_b64))
                rl_thumb = RLImage(thumb_bytes, width=1.45 * inch, height=0.9 * inch)
            except Exception:
                rl_thumb = None

        caption_p = Paragraph(f"<font color='#475569'><b>Sticker Crop ({int(sticker.confidence * 100)}% conf)</b></font>", ParagraphStyle("Cap", fontName="Helvetica", fontSize=7, leading=9, alignment=1))

        if rl_thumb:
            thumb_cell = [
                Spacer(1, 10),
                rl_thumb,
                Spacer(1, 8),
                caption_p,
                Spacer(1, 10),
            ]
        else:
            thumb_cell = [
                Spacer(1, 30),
                Paragraph("<font color='#94a3b8'><i>No sticker crop detected</i></font>", ParagraphStyle("NoCrp", fontName="Helvetica", fontSize=8, alignment=1)),
                Spacer(1, 30),
            ]

        thumb_table = Table([[thumb_cell]], colWidths=[135])
        thumb_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        main_section = Table([[fields_grid, thumb_table]], colWidths=[384, 139])
        main_section.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(main_section)
        story.append(Spacer(1, 14))

        # 5. Inspection Context & Overall Summary Strip
        summary_strip = [
            [
                Paragraph("<b>OVERALL RESULT</b>", field_label),
                Paragraph("<b>SOURCE FILE</b>", field_label),
                Paragraph("<b>CYCLE TIME</b>", field_label),
                Paragraph("<b>OPERATOR</b>", field_label),
            ],
            [
                Paragraph(
                    f"<font color='{'#16a34a' if report.overall_result == 'PASS' else '#dc2626'}'><b>{report.overall_result} ({report.passed} PASS · {report.failed} NG)</b></font>",
                    ParagraphStyle("OvRes", fontName="Helvetica-Bold", fontSize=9, leading=11),
                ),
                Paragraph(f"<b>{report.source_image}</b>", meta_val),
                Paragraph(f"<b>{report.cycle_time_seconds:.1f} s</b>", meta_val),
                Paragraph(f"<b>{report.operator}</b>", meta_val),
            ],
        ]
        strip_table = Table(summary_strip, colWidths=[140, 163, 110, 110])
        strip_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(strip_table)
        story.append(Spacer(1, 18))

        # 6. Quality Assurance Sign-Off Block
        signoff_data = [
            [
                Paragraph("<b>OPERATOR VERIFICATION</b>", field_label),
                Paragraph("<b>QUALITY ASSURANCE APPROVAL</b>", field_label),
            ],
            [
                Paragraph(
                    f"Operator Station: <b>Final Visual Line</b><br/>"
                    f"Inspected by: <b>{report.operator}</b><br/>"
                    f"Date: <b>{report.generated_at.strftime('%Y-%m-%d')}</b><br/>"
                    f"Signature: ___________________________",
                    ParagraphStyle("SigText", parent=normal, fontName="Helvetica", fontSize=8, leading=12),
                ),
                Paragraph(
                    f"Quality Disposition: <b>{'ACCEPTED' if report.overall_result == 'PASS' else 'REWORK / REVIEW'}</b><br/>"
                    f"Batch Traceability: <b>{fields.batch_code or 'VERIFIED'}</b><br/>"
                    f"Approved by: ___________________________<br/>"
                    f"Signature: ___________________________",
                    ParagraphStyle("SigText", parent=normal, fontName="Helvetica", fontSize=8, leading=12),
                ),
            ],
        ]
        signoff_table = Table(signoff_data, colWidths=[261, 262])
        signoff_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(signoff_table)
        story.append(Spacer(1, 12))

        # 7. Document Footer Note
        story.append(
            Paragraph(
                f"<font color='#94a3b8'><i>Official Wire Harness Specification & Traceability Certificate. Generated automatically by AI Final Inspection Station. Document ID: {report.report_id}.</i></font>",
                ParagraphStyle("FootNote", parent=normal, fontName="Helvetica", fontSize=7, leading=9, alignment=1),
            )
        )

        doc.build(story)
        return buffer.getvalue()


pdf_report_service = PdfReportService()
