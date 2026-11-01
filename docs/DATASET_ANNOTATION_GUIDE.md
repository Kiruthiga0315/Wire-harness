# HARNESSVISION – Wire Harness Dataset Annotation & Training Guide

This guide describes the dataset preparation, polygon annotation standards, data splitting protocols, and YOLO instance segmentation training workflow for wire harness inspection.

---

## 1. Directory Structure

The project uses the standard YOLOv8 segmentation format in `data/dataset/`:

```
data/dataset/
├── data.yaml                  # Dataset configuration and class map
├── images/
│   ├── train/                 # 70% of diverse workpieces
│   ├── val/                   # 15% of validation workpieces
│   └── test/                  # 15% of held-out benchmark workpieces
└── labels/
    ├── train/                 # Normalized polygon text files
    ├── val/
    └── test/
```

Each label text file has the same filename as its image (e.g., `harness_001.txt` for `harness_001.jpg`), containing lines in YOLO polygon format:
```
<class_id> <x1> <y1> <x2> <y2> ... <xn> <yn>
```
where all coordinates are normalized floats in the range `[0.0, 1.0]`.

---

## 2. Taxonomy & Annotation Classes

| Class ID | Class Name | Description | Annotation Guideline |
|---|---|---|---|
| `0` | `wire_trunk` | Central thick harness bundle | Polygon tightly tracing the main trunk outer boundary. |
| `1` | `wire_branch` | Individual breakout wire strands | Polygons outlining individual branching wires from trunk to terminals. |
| `2` | `connector` | Multi-pin plastic housing/headers | Polygon around connector body; do not include wires leading in. |
| `3` | `terminal_pin` | Metal crimp contacts, pins, eyelets | Polygons around conductive crimped ends. |
| `4` | `tape_wrap` | Spot tape or spiral wraps | Polygons around insulation tape, vinyl wraps, or conduit sleeves. |

### Critical Negative Annotation Rules:
- **DO NOT** annotate inspection board printed text (e.g. "PA BOARD NO: 2", "J1", "T01").
- **DO NOT** annotate fixture pegs, clamp blocks, or measuring rulers.
- Leaving these unannotated ensures the model penalizes activations on background text and lines.

---

## 3. Recommended Annotation Tools

1. **CVAT (Computer Vision Annotation Tool)** (Self-hosted or cloud):
   - Choose **Polygon** or **AI Mask / Segment Anything (SAM)** mode.
   - Export format: **YOLO 1.1 (Segmentation)**.
2. **Roboflow**:
   - Upload workpiece images, draw polygons, and export with **YOLOv8 Segmentation** format.
3. **Labelme / AnyLabeling**:
   - Desktop GUI for polygon labeling. Convert JSON to YOLO txt format using `labelme2yolo`.

---

## 4. Leakage-Free Splitting Protocol

To prevent near-duplicate leakage:
- **Group Split by Harness Serial Number**: If multiple photos are taken of the same physical harness workpiece (e.g., different camera angles, shifts, or lighting), **all variations of workpiece A must reside in the same split** (e.g., only in `train` or only in `test`).
- **Target Distribution**:
  - `train`: ~70% of physical workpieces.
  - `val`: ~15% for checkpoint selection.
  - `test`: ~15% held out for final model verification.

---

## 5. Training Execution

Once annotated images and label files are placed in `data/dataset/`, train with:

```bash
python scripts/train_yolo_segmentation.py --epochs 100 --imgsz 1024 --batch 8 --device 0
```

The script automatically:
1. Applies wire harness domain augmentations (scale, mild rotation, HSV lighting variation).
2. Optimizes box and polygon mask segmentation losses.
3. Copies the best resulting checkpoint to `data/models/yolov8_harness_seg.pt`.

---

## 6. Evaluation & Benchmarking

Evaluate the trained weights against the held-out test split:

```bash
python scripts/evaluate_yolo_segmentation.py --weights data/models/yolov8_harness_seg.pt --split test
```

The system will report Mask mAP50, Mask mAP50-95, and per-class performance. Once `data/models/yolov8_harness_seg.pt` is saved, the HARNESSVISION backend automatically detects it on startup and switches from the hybrid CV pipeline to neural instance segmentation.
