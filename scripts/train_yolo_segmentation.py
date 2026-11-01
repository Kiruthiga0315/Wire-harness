#!/usr/bin/env python3
"""HARNESSVISION - Reproducible YOLOv8 Instance Segmentation Training Pipeline.

Trains an instance segmentation model to separate wire harness trunks, branches,
connectors, and terminals from factory inspection boards, suppressing printed text,
markings, and fixture lines.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def train_harness_segmentation(
    data_yaml: Path,
    epochs: int = 100,
    imgsz: int = 1024,
    batch: int = 8,
    model_variant: str = "yolov8m-seg.pt",
    output_dir: Path | None = None,
    device: str = "0",
) -> Path:
    """Execute YOLOv8-seg training with specialized augmentations for wire harnesses."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print(
            "ERROR: 'ultralytics' package is required for YOLO segmentation training.\n"
            "Please install it with: pip install ultralytics",
            file=sys.stderr,
        )
        sys.exit(1)

    if not data_yaml.is_file():
        raise FileNotFoundError(f"Dataset configuration not found at: {data_yaml}")

    output_dir = output_dir or Path(__file__).resolve().parents[1] / "data" / "models"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading base segmentation weights: {model_variant}")
    model = YOLO(model_variant)

    print(f"Beginning training on dataset: {data_yaml}")
    print(f"Parameters: epochs={epochs}, imgsz={imgsz}, batch={batch}, device={device}")

    # Wire harness specific augmentations:
    # - Flipping & rotation (0 to 180 deg) since harness placement varies
    # - Mild perspective and scaling to emulate different camera distances
    # - HSV jitter to make segmentation robust against lighting & board color changes
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=str(output_dir),
        name="harness_segmentation_run",
        exist_ok=True,
        # Augmentations
        degrees=15.0,
        translate=0.1,
        scale=0.25,
        fliplr=0.5,
        flipud=0.5,
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.4,
        # Mask segmentation loss weights
        box=7.5,
        cls=0.5,
        dfl=1.5,
        plots=True,
        save=True,
    )

    best_weights = output_dir / "harness_segmentation_run" / "weights" / "best.pt"
    target_weights = output_dir / "yolov8_harness_seg.pt"

    if best_weights.is_file():
        import shutil
        shutil.copy2(best_weights, target_weights)
        print(f"\nTraining Complete! Best model exported to: {target_weights}")
        return target_weights
    else:
        print(f"\nTraining finished. Check outputs in: {output_dir / 'harness_segmentation_run'}")
        return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLOv8 wire harness instance segmentation.")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "dataset" / "data.yaml",
        help="Path to data.yaml dataset definition",
    )
    parser.add_argument("--epochs", type=int, default=100, help="Number of training epochs (default: 100)")
    parser.add_argument("--imgsz", type=int, default=1024, help="Input image dimension (default: 1024)")
    parser.add_argument("--batch", type=int, default=8, help="Batch size (default: 8)")
    parser.add_argument("--model", type=str, default="yolov8m-seg.pt", help="Base model weights")
    parser.add_argument("--device", type=str, default="cpu", help="Compute device ('cpu', '0', '0,1')")

    args = parser.parse_args()
    train_harness_segmentation(
        data_yaml=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        model_variant=args.model,
        device=args.device,
    )


if __name__ == "__main__":
    main()
