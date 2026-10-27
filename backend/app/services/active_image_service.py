from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.api.routes.images import DEMO_IMAGE_LOGICAL_NAME, resolve_demo_image
from app.services.cloud_io import decode_uploaded_image
from app.services.harness_segmentation_service import ImageArray

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ActiveImageRecord:
    filename: str
    content_type: str
    data: bytes
    bgr_image: ImageArray
    width: int
    height: int
    source: str  # "demo" or "upload"


class ActiveImageService:
    """Manages the in-memory active inspection image across operations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current_image: ActiveImageRecord | None = None

    def _load_demo_image(self) -> ActiveImageRecord:
        image_path = resolve_demo_image()
        if image_path is None or not image_path.is_file():
            raise RuntimeError(
                f"Demo image is missing from data/test_images/{DEMO_IMAGE_LOGICAL_NAME}"
            )
        data = image_path.read_bytes()
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Unable to decode demo image at {image_path}")
        height, width = image.shape[:2]
        return ActiveImageRecord(
            filename=DEMO_IMAGE_LOGICAL_NAME,
            content_type="image/jpeg",
            data=data,
            bgr_image=image,
            width=width,
            height=height,
            source="demo",
        )

    def get_active_image(self) -> ActiveImageRecord:
        with self._lock:
            if self._current_image is None:
                self._current_image = self._load_demo_image()
            return self._current_image

    def set_uploaded_image(
        self,
        payload: bytes,
        *,
        filename: str,
        content_type: str | None = None,
    ) -> ActiveImageRecord:
        bgr_image = decode_uploaded_image(
            payload,
            filename=filename,
            content_type=content_type,
        )
        height, width = bgr_image.shape[:2]
        suffix = Path(filename).suffix.lower()
        if not content_type:
            if suffix == ".png":
                content_type = "image/png"
            elif suffix == ".bmp":
                content_type = "image/bmp"
            else:
                content_type = "image/jpeg"

        record = ActiveImageRecord(
            filename=filename,
            content_type=content_type,
            data=payload,
            bgr_image=bgr_image,
            width=width,
            height=height,
            source="upload",
        )
        with self._lock:
            self._current_image = record
        logger.info(
            "Active inspection image updated | file=%s | size=%d | %dx%d",
            filename,
            len(payload),
            width,
            height,
        )
        return record

    def reset_to_demo(self) -> ActiveImageRecord:
        with self._lock:
            self._current_image = self._load_demo_image()
        logger.info("Active inspection image reset to demo")
        return self._current_image


# Global singleton instance
active_image_service = ActiveImageService()
