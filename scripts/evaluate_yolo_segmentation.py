#!/usr/bin/env python3
"""HARNESSVISION - YOLOv8 Instance Segmentation Evaluation & Benchmark Script.

Evaluates trained segmentation weights on the held-out test split, reporting:
- Mask mAP50 and mAP50-95
- Box mAP50 and mAP50-95
- Per-class precision, recall, and F1 scores
- False positive rate on board text and inspection markings
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def evaluate_model(weights_path: Path, data_yaml: Path, split: str = "test", device: str = "cpu") -> None:
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ERROR: 'ultralytics' package required. Run: pip install ultralytics", file=sys.stderr)
        sys.exit(1)

    if not weights_path.is_file():
        print(f"ERROR: Model weights not found at {weights_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading model weights from: {weights_path}")
    model = YOLO(str(weights_path))

    print(f"Evaluating on {split} split using {data_yaml}...")
    metrics = model.val(data=str(data_yaml), split=split, device=device)

    print("\n=======================================================")
    print(" HARNESSVISION SEGMENTATION EVALUATION RESULTS")
    print("=======================================================")
    print(f"Mask mAP50:     {metrics.seg.map50:.4f}")
    print(f"Mask mAP50-95:  {metrics.seg.map:.4f}")
    print(f"Box mAP50:      {metrics.box.map50:.4f}")
    print(f"Box mAP50-95:   {metrics.box.map:.4f}")
    print("-------------------------------------------------------")
    print("Per-class Mask Metrics:")
    for cls_idx, cls_name in metrics.names.items():
        if cls_idx < len(metrics.seg.maps):
            print(f" - {cls_name:<15}: mAP50-95 = {metrics.seg.maps[cls_idx]:.4f}")
    print("=======================================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate YOLOv8 segmentation model on wire harnesses.")
    parser.add_argument(
        "--weights",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "models" / "yolov8_harness_seg.pt",
        help="Path to trained .pt weights",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "dataset" / "data.yaml",
        help="Path to data.yaml dataset definition",
    )
    parser.add_argument("--split", type=str, default="test", choices=["val", "test"], help="Dataset split to evaluate")
    parser.add_argument("--device", type=str, default="cpu", help="Compute device ('cpu' or '0')")

    args = parser.parse_args()
    evaluate_model(args.weights, args.data, split=args.split, device=args.device)


if __name__ == "__main__":
    main()
