from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.harness_segmentation_service import ImageArray
from app.services.inspection_engine import InspectionResult

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_IMAGE_DIMENSION = 12_000
MAX_IMAGE_PIXELS = 40_000_000
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png"}
SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png"}
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class UploadedImageValidationError(ValueError):
    pass


def decode_uploaded_image(
    payload: bytes,
    *,
    filename: str,
    content_type: str | None,
    max_bytes: int = MAX_UPLOAD_BYTES,
    max_dimension: int = MAX_IMAGE_DIMENSION,
    max_pixels: int = MAX_IMAGE_PIXELS,
) -> ImageArray:
    """Validate and decode a JPEG/PNG upload into an OpenCV BGR image."""
    if not payload:
        raise UploadedImageValidationError("The uploaded file is empty")
    if len(payload) > max_bytes:
        raise UploadedImageValidationError(
            f"The uploaded file exceeds the {max_bytes // (1024 * 1024)} MB limit"
        )
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise UploadedImageValidationError("Only JPG, JPEG, and PNG files are supported")
    if content_type and content_type.lower() not in SUPPORTED_MIME_TYPES:
        raise UploadedImageValidationError("The uploaded MIME type is not JPEG or PNG")

    try:
        with Image.open(io.BytesIO(payload)) as probe:
            image_format = (probe.format or "").upper()
            width, height = probe.size
            if image_format not in {"JPEG", "PNG"}:
                raise UploadedImageValidationError("The decoded image is not JPEG or PNG")
            expected_format = "PNG" if suffix == ".png" else "JPEG"
            if image_format != expected_format:
                raise UploadedImageValidationError(
                    "The file extension does not match the decoded image format"
                )
            if content_type:
                expected_mime = "image/png" if image_format == "PNG" else "image/jpeg"
                if content_type.lower() != expected_mime:
                    raise UploadedImageValidationError(
                        "The uploaded MIME type does not match the decoded image format"
                    )
            if width < 16 or height < 16:
                raise UploadedImageValidationError("Image dimensions are too small for inspection")
            if width > max_dimension or height > max_dimension:
                raise UploadedImageValidationError(
                    f"Image dimensions exceed the {max_dimension} px per-side limit"
                )
            if width * height > max_pixels:
                raise UploadedImageValidationError(
                    f"Image exceeds the {max_pixels / 1_000_000:.0f} megapixel processing limit"
                )
            probe.verify()

        with Image.open(io.BytesIO(payload)) as decoded:
            decoded = ImageOps.exif_transpose(decoded)
            if decoded.mode in {"RGBA", "LA"} or "transparency" in decoded.info:
                rgba = decoded.convert("RGBA")
                background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                decoded = Image.alpha_composite(background, rgba).convert("RGB")
            else:
                decoded = decoded.convert("RGB")
            rgb = np.asarray(decoded, dtype=np.uint8)
    except UploadedImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise UploadedImageValidationError("The uploaded image is corrupted or cannot be decoded") from exc

    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def encode_annotated_png(result: InspectionResult) -> bytes:
    encoded, png = cv2.imencode(".png", result.annotated_image)
    if not encoded:
        raise RuntimeError("OpenCV could not encode the annotated image")
    return png.tobytes()


def inspection_json_bytes(result: InspectionResult) -> bytes:
    return json.dumps(
        result.to_summary_dict(),
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")


def inspection_csv_bytes(result: InspectionResult) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "record_type",
        "record_id",
        "name",
        "status",
        "value",
        "unit",
        "expected",
        "message",
        "source_node",
        "target_node",
        "straight_distance_px",
        "orientation_deg",
    ])
    writer.writerow([
        "INSPECTION",
        result.inspection_id,
        result.selected_variant,
        result.overall_status,
        "",
        "",
        "",
        result.model_status.message,
        "",
        "",
        "",
        "",
    ])
    for rule in result.rule_results:
        writer.writerow([
            "RULE",
            rule.rule_id,
            rule.rule_name,
            rule.status,
            rule.actual_value or "",
            "",
            rule.expected_value or "",
            rule.message,
            "",
            "",
            "",
            "",
        ])
    for measurement in result.measurements:
        writer.writerow([
            "MEASUREMENT",
            measurement.measurement_id,
            measurement.name,
            "MEASURED",
            f"{measurement.value:.4f}",
            measurement.unit,
            "",
            measurement.method,
            "",
            "",
            "",
            "",
        ])
    for branch in result.branches:
        writer.writerow([
            "BRANCH",
            branch.branch_id,
            "Node-to-node centreline",
            "MEASURED",
            f"{branch.path_length_pixels:.4f}",
            "px",
            "",
            "Experimental skeleton graph",
            branch.source_node_id,
            branch.target_node_id,
            f"{branch.straight_distance_pixels:.4f}",
            f"{branch.orientation_degrees:.4f}",
        ])
    for junction in result.junctions:
        orientations = "; ".join(
            f"{branch_id}:{angle:.2f}deg"
            for branch_id, angle in junction.branch_orientations
        )
        writer.writerow([
            "JUNCTION",
            junction.node_id,
            "Incident branch count",
            "MEASURED",
            junction.branch_count,
            "count",
            "",
            f"Pixel ({junction.x}, {junction.y}); {orientations}",
            "",
            "",
            "",
            "",
        ])
    for distance in result.junction_terminal_distances:
        writer.writerow([
            "JUNCTION_TERMINAL",
            f"{distance.junction_node_id}-{distance.terminal_node_id}",
            "Junction-to-end-terminal path",
            "MEASURED",
            f"{distance.path_distance_pixels:.4f}",
            "px",
            "",
            "Experimental skeleton graph",
            distance.junction_node_id,
            distance.terminal_node_id,
            f"{distance.straight_distance_pixels:.4f}",
            "",
        ])
    for pair in result.branch_pair_distances:
        writer.writerow([
            "BRANCH_PAIR",
            f"{pair.first_branch_id}-{pair.second_branch_id}",
            "Branch-to-branch via junction",
            "MEASURED",
            f"{pair.via_junction_distance_pixels:.4f}",
            "px",
            "",
            f"Junction {pair.junction_node_id}; angular separation {pair.angular_separation_degrees:.4f} deg",
            pair.first_branch_id,
            pair.second_branch_id,
            f"{pair.midpoint_straight_distance_pixels:.4f}",
            f"{pair.angular_separation_degrees:.4f}",
        ])
    return output.getvalue().encode("utf-8-sig")
