"""Configurable colour detection thresholds for wire harness inspection.

All HSV ranges use OpenCV convention: H ∈ [0,180), S ∈ [0,255], V ∈ [0,255].
LAB ranges use OpenCV convention: L ∈ [0,255], A ∈ [0,255], B ∈ [0,255].

Thresholds are intentionally broad for the initial engineering release.
Production deployments should calibrate against reference samples under
controlled illumination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HSVRange:
    """Inclusive HSV range for colour segmentation."""
    h_min: int
    h_max: int
    s_min: int = 0
    s_max: int = 255
    v_min: int = 0
    v_max: int = 255


@dataclass
class LABRange:
    """Inclusive LAB range for colour refinement."""
    l_min: int = 0
    l_max: int = 255
    a_min: int = 0
    a_max: int = 255
    b_min: int = 0
    b_max: int = 255


@dataclass
class ColourThreshold:
    """Complete threshold specification for a single colour."""
    colour_id: str
    display_name: str
    hsv_ranges: list[HSVRange]
    lab_range: LABRange | None = None
    # Minimum contiguous region area in pixels to accept a detection
    min_area: int = 80
    # Morphological kernel size for opening/closing
    morph_kernel_size: int = 5
    # Overlay colour for visualisation (BGR)
    overlay_bgr: tuple[int, int, int] = (0, 255, 0)
    overlay_hex: str = "#00FF00"


@dataclass
class TapeThresholds:
    """Thresholds specific to coloured tape detection."""
    # Minimum aspect ratio (width/height or height/width) to qualify as tape-like
    min_aspect_ratio: float = 1.35
    # Maximum circularity to exclude round blobs (tape is elongated)
    max_circularity: float = 0.75
    # Minimum area in pixels
    min_area: int = 150
    # Maximum area to avoid massive false positives (board labels, etc.)
    max_area: int = 25000
    # Minimum solidity (filled area / convex hull area)
    min_solidity: float = 0.30


@dataclass
class WireThresholds:
    """Thresholds specific to wire insulation colour detection."""
    # Minimum area in pixels
    min_area: int = 60
    # Maximum width of a wire cross-section in pixels (used with distance transform)
    max_wire_radius: float = 14.0
    # Minimum distance-transform value to accept (avoids edge pixels)
    min_dist_from_edge: float = 0.5
    # Minimum aspect ratio (max_dim / min_dim) for elongated wire runs
    min_aspect_ratio: float = 1.30
    # Rejection of square/compact connector housings and mounting blocks
    connector_min_dim: int = 24
    connector_max_aspect: float = 1.30
    # Display confidence tiers
    high_confidence_min: float = 0.80
    medium_confidence_min: float = 0.60


# ---------------------------------------------------------------------------
# Default threshold sets
# ---------------------------------------------------------------------------

def default_tape_colour_thresholds() -> list[ColourThreshold]:
    """Return default HSV/LAB thresholds for the three required tape colours."""
    return [
        ColourThreshold(
            colour_id="green_tape",
            display_name="Green Tape",
            hsv_ranges=[
                HSVRange(h_min=35, h_max=85, s_min=40, s_max=255, v_min=40, v_max=255),
            ],
            lab_range=LABRange(a_min=0, a_max=120),  # a < 128 = green
            min_area=150,
            morph_kernel_size=5,
            overlay_bgr=(0, 220, 0),
            overlay_hex="#00DC00",
        ),
        ColourThreshold(
            colour_id="dark_blue_tape",
            display_name="Dark Blue Tape",
            hsv_ranges=[
                HSVRange(h_min=90, h_max=135, s_min=40, s_max=255, v_min=25, v_max=180),
            ],
            lab_range=LABRange(b_min=0, b_max=115),  # b < 128 = blue
            min_area=150,
            morph_kernel_size=5,
            overlay_bgr=(220, 120, 0),
            overlay_hex="#0078DC",
        ),
        ColourThreshold(
            colour_id="gray_tape",
            display_name="Gray Tape",
            hsv_ranges=[
                HSVRange(h_min=0, h_max=180, s_min=0, s_max=30, v_min=80, v_max=165),
            ],
            lab_range=LABRange(l_min=80, l_max=165, a_min=122, a_max=134, b_min=122, b_max=134),
            min_area=200,
            morph_kernel_size=5,
            overlay_bgr=(180, 180, 180),
            overlay_hex="#B4B4B4",
        ),
    ]


def default_wire_colour_thresholds() -> list[ColourThreshold]:
    """Return default HSV/LAB thresholds for wire insulation colours."""
    return [
        ColourThreshold(
            colour_id="red",
            display_name="Red",
            hsv_ranges=[
                HSVRange(h_min=0, h_max=8, s_min=60, s_max=255, v_min=50, v_max=255),
                HSVRange(h_min=170, h_max=180, s_min=60, s_max=255, v_min=50, v_max=255),
            ],
            min_area=50,
            overlay_bgr=(0, 0, 220),
            overlay_hex="#DC0000",
        ),
        ColourThreshold(
            colour_id="green",
            display_name="Green",
            hsv_ranges=[
                HSVRange(h_min=40, h_max=82, s_min=48, s_max=255, v_min=55, v_max=225),
            ],
            lab_range=LABRange(a_min=0, a_max=121, b_min=126, b_max=255),
            min_area=40,
            overlay_bgr=(0, 200, 0),
            overlay_hex="#00C800",
        ),
        ColourThreshold(
            colour_id="blue",
            display_name="Blue",
            hsv_ranges=[
                HSVRange(h_min=85, h_max=135, s_min=40, s_max=255, v_min=30, v_max=255),
            ],
            lab_range=LABRange(b_min=0, b_max=118),
            min_area=40,
            overlay_bgr=(220, 100, 0),
            overlay_hex="#0064DC",
        ),
        ColourThreshold(
            colour_id="yellow",
            display_name="Yellow",
            hsv_ranges=[
                HSVRange(h_min=20, h_max=38, s_min=60, s_max=255, v_min=100, v_max=255),
            ],
            min_area=50,
            overlay_bgr=(0, 220, 220),
            overlay_hex="#DCDC00",
        ),
        ColourThreshold(
            colour_id="black",
            display_name="Black",
            hsv_ranges=[
                HSVRange(h_min=0, h_max=180, s_min=0, s_max=50, v_min=0, v_max=55),
            ],
            min_area=60,
            overlay_bgr=(0, 140, 255),
            overlay_hex="#FF8C00",
        ),
        ColourThreshold(
            colour_id="white",
            display_name="White",
            hsv_ranges=[
                HSVRange(h_min=0, h_max=180, s_min=0, s_max=35, v_min=200, v_max=255),
            ],
            min_area=60,
            overlay_bgr=(255, 255, 200),
            overlay_hex="#C8FFFF",
        ),
        ColourThreshold(
            colour_id="gray",
            display_name="Gray",
            hsv_ranges=[
                HSVRange(h_min=0, h_max=180, s_min=0, s_max=30, v_min=65, v_max=165),
            ],
            lab_range=LABRange(l_min=65, l_max=165, a_min=120, a_max=136, b_min=120, b_max=136),
            min_area=60,
            overlay_bgr=(190, 190, 190),
            overlay_hex="#BEBEBE",
        ),
        ColourThreshold(
            colour_id="brown",
            display_name="Brown",
            hsv_ranges=[
                HSVRange(h_min=8, h_max=22, s_min=60, s_max=255, v_min=30, v_max=160),
            ],
            min_area=50,
            overlay_bgr=(30, 70, 160),
            overlay_hex="#A04620",
        ),
        ColourThreshold(
            colour_id="orange",
            display_name="Orange",
            hsv_ranges=[
                HSVRange(h_min=10, h_max=22, s_min=100, s_max=255, v_min=120, v_max=255),
            ],
            min_area=50,
            overlay_bgr=(0, 140, 255),
            overlay_hex="#FF8C00",
        ),
        ColourThreshold(
            colour_id="purple",
            display_name="Purple",
            hsv_ranges=[
                HSVRange(h_min=135, h_max=170, s_min=45, s_max=255, v_min=30, v_max=255),
            ],
            lab_range=LABRange(a_min=132),
            min_area=50,
            overlay_bgr=(200, 50, 180),
            overlay_hex="#B432C8",
        ),
    ]


def default_tape_thresholds() -> TapeThresholds:
    return TapeThresholds()


def default_wire_thresholds() -> WireThresholds:
    return WireThresholds()
