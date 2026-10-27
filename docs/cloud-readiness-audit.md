# Cloud readiness audit

> **Status Note (2026-10-27)**: The Streamlit prototype has been retired from this codebase. The stack is solely React 19 (frontend) + FastAPI (backend) + Swagger OpenAPI docs. This document is retained for historical capability reference.

Audit date: 2026-10-16  
Project: AI Wire Harness Final Inspection System

## Scope inspected

The audit covered every Python source and test file outside the virtual environment, the React/TypeScript
entry points, pages, reusable UI components, API client and types, dependency manifests, runtime launcher,
environment example, Docker configuration, Git exclusions, architecture notes, model/data directories,
and searches for trained-weight formats and platform-specific integrations.

## Existing architecture

- `run.py` / `run.cmd` start a local two-process application.
- `frontend/` is a React 19 + TypeScript + Vite industrial HMI.
- `backend/` is a FastAPI application with SQLAlchemy, SQLite by default, optional PostgreSQL, and REST
  routes for checkpoints, engineering analysis, mock inspections, and reports.
- `backend/app/services/` contains the reusable image-processing implementations.
- The browser upload in the existing React Live Inspection page remains in browser memory. The uploaded
  image is not posted to the backend; the current Start Inspection action calls the deterministic mock
  evaluator without image pixels.

## Model and inference inventory

- No `.pt`, `.onnx`, `.engine`, `.weights`, `.pth`, `.pb`, `.tflite`, or `.mlmodel` file exists.
- No active `torch`, `ultralytics`, ONNX Runtime, CUDA, or YOLO import exists.
- `ultralytics` appears only as a commented future dependency.
- There is no trained-model loader, class map, confidence/NMS configuration, or validated object-detection
  post-processing implementation to preserve or deploy.
- `MockInspectionService` intentionally ignores image pixels and returns a fixed 9 PASS / 3 NG scenario.
  It is suitable only for the existing UI demonstration and must not be presented as uploaded-image AI
  inference.

## Functional inspection matrix

| Capability | Current state | Cloud-safe interpretation |
| --- | --- | --- |
| Dark-object segmentation | Implemented, experimental | Run and display; never make production PASS/FAIL |
| Contours and skeleton | Implemented, experimental | Run and expose engineering evidence |
| Endpoint/junction candidates | Implemented, experimental | Report as candidates requiring review |
| Pixel centreline/branch distances | Implemented, uncalibrated | Report in pixels only |
| Branch orientations | Implemented from graph chords | Report as experimental image-coordinate angles |
| ROI colour classification | Implemented for configured ROI | Available only when a valid ROI and expected colour are supplied |
| Connector/terminal detection | Not implemented | `NOT_EVALUATED` |
| Tape/component detection | Not implemented | `NOT_EVALUATED` |
| Missing/wrong/extra components | Not implemented | `NOT_EVALUATED` |
| Calibrated physical dimensions | Not implemented; no scale/reference calibration | `NOT_EVALUATED`; never claim millimetres |
| Routing validation against reference | Not implemented | `NOT_EVALUATED` |
| Deterministic checkpoint demo | Implemented mock workflow | Keep local demo, exclude from real cloud inference evidence |
| Report annotation/CSV | Implemented for fixed demo image | Reuse export patterns for uploaded-image engineering results |

## Portability and cloud findings

- Application code already uses `pathlib.Path` and project-relative storage. No hardcoded application
  Windows path was found.
- `run.py` contains expected Windows launcher handling for the existing local React/FastAPI version; it is
  not needed by Streamlit Community Cloud.
- No `cv2.VideoCapture` or industrial camera SDK is used. Upload-only execution can be camera-independent.
- No unconditional CUDA call exists. Because no model runtime exists, the safe current device is CPU.
- FastAPI startup writes logs and initializes SQLite/runtime directories. A stateless Streamlit upload path
  should avoid that lifecycle and operate entirely in memory.
- PostgreSQL is optional and not required for the uploaded-image engineering pipeline.
- The physical demo image has the filename `harness_sample_01.jpeg.jpeg`, while APIs expose the logical
  name `harness_sample_01.jpeg`.

## Dependency findings

The validated computer-vision stack is NumPy, `opencv-python-headless`, and scikit-image. FastAPI,
SQLAlchemy, psycopg, React, and Node are required only for the existing two-process application. A new
root Streamlit requirement set can be smaller and independent while leaving backend requirements intact.

## Required cloud architecture

1. Add a reusable `inspect_harness(image, variant=None, config=None)` engine around the existing OpenCV
   segmentation and graph services.
2. Return actual engineering measurements and annotations, empty object detections, explicit model
   availability, warnings, and rule statuses.
3. Set production rules and overall inspection to `NOT_EVALUATED` while trained weights, validated
   detection adapters, model-specific references, and calibration are unavailable.
4. Add a Streamlit upload UI that decodes and validates images in memory and invokes the engine only after
   the user presses Run AI Inspection.
5. Add in-memory PNG, JSON, and CSV exports; do not persist client uploads by default.
6. Add Streamlit deployment configuration, root cloud requirements, security-focused Git exclusions,
   deployment documentation, and tests for decoding, limits, engine behavior, exports, missing weights,
   repeatability, and CPU execution.

## Deployment blockers and unverified items

- The acceptance criterion requiring real trained-model inference cannot be satisfied from this repository
  because no validated detector implementation or weights are present.
- Object counts, boxes, component PASS/FAIL, and accuracy figures cannot be truthfully produced.
- Physical-unit measurements require camera calibration and a validated pixel-to-unit mapping.
- Streamlit Community Cloud compatibility must be validated with the new dependency set; GPU/CUDA should
  not be assumed.

This audit is the baseline for the additive Streamlit implementation. The existing FastAPI/React local
application and its algorithms will remain available and unchanged except for deployment documentation and
safe repository exclusions.
