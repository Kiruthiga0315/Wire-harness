"""Application services and replaceable processing pipelines."""


def __getattr__(name: str):
    if name in ("ActiveImageRecord", "ActiveImageService", "active_image_service"):
        from app.services import active_image_service

        return getattr(active_image_service, name)
    if name in ("InspectionEngine", "InspectionResult", "inspect_harness"):
        from app.services import inspection_engine

        return getattr(inspection_engine, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ActiveImageRecord",
    "ActiveImageService",
    "active_image_service",
    "InspectionEngine",
    "InspectionResult",
    "inspect_harness",
]
