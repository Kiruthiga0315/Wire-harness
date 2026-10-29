from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.core.settings import get_settings
from app.services.cloud_io import decode_uploaded_image
from app.services.harness_segmentation_service import ImageArray

logger = logging.getLogger(__name__)

DEMO_IMAGE_LOGICAL_NAME = "harness_sample_01.jpeg"
DEMO_IMAGE_CANDIDATES = (
    DEMO_IMAGE_LOGICAL_NAME,
    f"{DEMO_IMAGE_LOGICAL_NAME}.jpeg",
)

CACHE_DATA_FILENAME = ".active_image_cache.dat"
CACHE_META_FILENAME = ".active_image_cache.json"


def _cache_dir() -> Path:
    directory = get_settings().project_root / "data" / "test_images"
    directory.mkdir(parents=True, exist_ok=True)
    return directory



def resolve_demo_image() -> Path | None:
    test_image_directory = get_settings().project_root / "data" / "test_images"
    for filename in DEMO_IMAGE_CANDIDATES:
        candidate = test_image_directory / filename
        if candidate.is_file():
            return candidate
    return None


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

    def _load_cached_image(self) -> ActiveImageRecord | None:
        try:
            cache_dir = _cache_dir()
            data_file = cache_dir / CACHE_DATA_FILENAME
            meta_file = cache_dir / CACHE_META_FILENAME
            if not data_file.is_file() or not meta_file.is_file():
                return None
            demo_path = resolve_demo_image()
            if demo_path and demo_path.is_file():
                if demo_path.stat().st_mtime > data_file.stat().st_mtime:
                    logger.info("Demo image updated; invalidating stale active image cache")
                    self._clear_cache()
                    return None
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            data = data_file.read_bytes()
            bgr_image = decode_uploaded_image(
                data,
                filename=meta.get("filename", "cached_image.png"),
                content_type=meta.get("content_type"),
            )
            height, width = bgr_image.shape[:2]
            return ActiveImageRecord(
                filename=meta.get("filename", "cached_image.png"),
                content_type=meta.get("content_type", "image/png"),
                data=data,
                bgr_image=bgr_image,
                width=width,
                height=height,
                source=meta.get("source", "upload"),
            )
        except Exception as exc:
            logger.warning("Failed to restore cached active image: %s", exc)
            return None

    def _persist_cache(self, record: ActiveImageRecord) -> None:
        try:
            cache_dir = _cache_dir()
            data_file = cache_dir / CACHE_DATA_FILENAME
            meta_file = cache_dir / CACHE_META_FILENAME
            data_file.write_bytes(record.data)
            meta = {
                "filename": record.filename,
                "content_type": record.content_type,
                "width": record.width,
                "height": record.height,
                "size": len(record.data),
                "source": record.source,
            }
            meta_file.write_text(json.dumps(meta), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to persist active image cache: %s", exc)

    def _clear_cache(self) -> None:
        try:
            cache_dir = _cache_dir()
            data_file = cache_dir / CACHE_DATA_FILENAME
            meta_file = cache_dir / CACHE_META_FILENAME
            if data_file.is_file():
                data_file.unlink(missing_ok=True)
            if meta_file.is_file():
                meta_file.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Failed to clear active image cache: %s", exc)

    def get_active_image(self) -> ActiveImageRecord:
        with self._lock:
            if self._current_image is None:
                self._current_image = self._load_cached_image() or self._load_demo_image()
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
            self._persist_cache(record)
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
            self._clear_cache()
            self._current_image = self._load_demo_image()
        logger.info("Active inspection image reset to demo")
        return self._current_image


# Global singleton instance
active_image_service = ActiveImageService()
