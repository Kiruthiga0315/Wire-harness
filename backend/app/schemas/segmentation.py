from pydantic import BaseModel, Field


class SegmentationImages(BaseModel):
    binary_mask: str
    contour_image: str
    skeleton_image: str
    isolated_harness: str | None = None


class SegmentationMetrics(BaseModel):
    harness_occupied_percentage: float = Field(ge=0, le=100)
    contour_count: int = Field(ge=0)
    otsu_threshold: float = Field(ge=0, le=255)
    removed_component_count: int = Field(ge=0)
    excluded_border_component_count: int = Field(ge=0)
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)


class SegmentationResponse(BaseModel):
    source_image: str
    method: str
    production_ready: bool
    disclaimer: str
    metrics: SegmentationMetrics
    images: SegmentationImages
