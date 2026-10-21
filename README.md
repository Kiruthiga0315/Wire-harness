# AI Wire Harness Final Inspection System

Phase 1 application foundation for a production-oriented automotive wire harness inspection HMI.
This project is isolated from the existing PEOS application and can be run locally without Docker.

## Streamlit cloud interface

The repository now also has an additive, cloud-safe Streamlit entry point at `streamlit_app.py`. It accepts
JPG/JPEG/PNG uploads in memory, runs the implemented OpenCV segmentation and harness-graph pipeline on
demand, shows original and annotated evidence, and exports annotated PNG, JSON, and CSV results.

No trained detector weights or validated YOLO/ONNX adapter exist in this repository. Accordingly, the cloud
interface does not call `MockInspectionService`, does not invent detections, and does not issue a production
PASS/FAIL. Component, routing, tape, connector, terminal, and physical-dimension rules remain
`NOT_EVALUATED`; segmentation and topology are marked `REVIEW_REQUIRED` engineering evidence. Pixel
measurements are explicitly uncalibrated.

Run the cloud interface on Windows after installing its root requirements:

```powershell
cd C:\Users\91979\OneDrive\PEOS\wire-harness-ai-inspection
py -3.12 -m venv .venv-cloud
.\.venv-cloud\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv-cloud\Scripts\python.exe -m streamlit run streamlit_app.py
```

After the one-time installation, `run_streamlit.cmd` starts this Streamlit interface with one click.

See [DEPLOYMENT.md](DEPLOYMENT.md) for private GitHub and Streamlit Community Cloud instructions, and
[docs/cloud-readiness-audit.md](docs/cloud-readiness-audit.md) for the pre-change architecture/model audit.
Exact runtime versions, test results, and unverified items are recorded in
[docs/cloud-verification-report.md](docs/cloud-verification-report.md).

## Phase 1 status

Included:

- FastAPI application with automatic OpenAPI documentation.
- Environment-based SQLAlchemy configuration.
- SQLite development fallback and PostgreSQL production support.
- Database-aware `GET /api/health` endpoint.
- File and console application logging.
- React, TypeScript, Vite, and React Router frontend.
- Responsive industrial dashboard, navigation, and system status.
- Live Inspection, Models / Recipes, Cameras, and complete demonstration Reports screens.
- Local test-image upload and backend-served demo-image loading on Live Inspection.
- Experimental OpenCV harness segmentation with binary mask, contours, skeleton, and occupancy metrics.
- Persistent Engineering Checkpoint Editor for model `DEMO-HARNESS-001`.
- Deterministic 12-checkpoint Live Inspection demo using `MockInspectionService`.
- Development `ColorInspectionService` with HSV/LAB diagnostics and optional ROI preview.
- Experimental `HarnessGraphService` for skeleton endpoint and junction feasibility analysis.
- Experimental pixel topology measurements for wire length, junction branch count and orientation,
  node-to-node paths, nearest junction-to-terminal paths, and branch-to-branch distances.
- Complete demonstration Report module with annotated length evidence, checkpoint filtering,
  node-to-node measurement tables, CSV export, and print/save-PDF support.
- Clearly marked placeholders for Checkpoints, Measurements, Calibration, History, and Settings.

Deferred to Phase 2:

- Persistence of completed inspection and report history.
- Production PDF and Excel report generation.
- Calibrated millimetre measurements and production-validated inspection decisions.

## Engineering segmentation feasibility test

Open **Engineering View** in the left navigation. The page runs the configured harness image through:

1. Grayscale conversion and light Gaussian smoothing.
2. Inverted Otsu thresholding for dark-object extraction.
3. Morphological closing to connect small gaps.
4. Connected-component cleanup for small isolated regions.
5. Frame-edge artifact exclusion.
6. External contour generation.
7. Optional skeleton representation using `scikit-image`.

The API endpoint is `POST /api/engineering/segmentation/demo`. It returns PNG data URLs for the
binary mask, contour image, and skeleton, along with occupied-image percentage and diagnostic metrics.
These results are explicitly engineering-only and are not valid for PASS/NG production decisions.

## Engineering Checkpoint Editor

Engineering View contains an interactive editor over the original test image. Click the image to capture
pixel X/Y coordinates, then configure the checkpoint name, extensible category, inspection type, expected
value, tolerance, and ROI dimensions. Saved checkpoints use green markers and blue ROI rectangles.

Checkpoint records are persisted by SQLAlchemy against `DEMO-HARNESS-001` and can be edited or deleted.
The model is seeded automatically when the backend starts. CRUD endpoints are available under:

```text
GET    /api/models/DEMO-HARNESS-001/checkpoints
POST   /api/models/DEMO-HARNESS-001/checkpoints
PUT    /api/models/DEMO-HARNESS-001/checkpoints/{checkpoint_id}
DELETE /api/models/DEMO-HARNESS-001/checkpoints/{checkpoint_id}
```

## Deterministic Live Inspection demo

The seeded model is `DEMO-HARNESS-001` — **Client Wire Harness Sample**. Its demo recipe contains
12 `CP-*` checkpoints. Existing user-created `ENG-*` engineering checkpoints remain preserved but are
not part of the deterministic operator demo.

After loading or uploading an image, **START INSPECTION** enters PROCESSING for two seconds and calls:

```text
POST /api/inspections/demo/process
```

`MockInspectionService` returns a reproducible result of 9 PASS and 3 NG checkpoints. The frontend
draws green PASS boxes and red NG boxes without modifying the image. Selecting a red box displays its
expected value, actual value, tolerance, deviation, confidence, and failure reason in the right panel.

## Colour inspection feasibility test

Engineering View includes an ROI Colour Analysis panel. It lists checkpoints whose expected value is
one of `BLACK`, `WHITE`, `BLUE`, `RED`, `GREEN`, `YELLOW`, `ORANGE`, or `GREY`. The service extracts
the saved checkpoint ROI in memory, calculates full-ROI mean HSV and LAB values, estimates a
foreground-aware dominant colour, reports confidence, and compares it with the expected colour.

Enable **Show extracted ROI** before running the analysis to return and display a read-only PNG debug
preview. The endpoint is:

```text
POST /api/engineering/color-inspection
```

This is a development feasibility method, not a production colour-inspection algorithm. Controlled
lighting, camera colour calibration, reference samples, and validated thresholds remain required.

## Harness graph feasibility analysis

Engineering View includes an Experimental Harness Graph panel. It processes the cleaned binary harness
mask by skeletonizing it, counting each skeleton pixel's eight-connected neighbours, treating pixels with
one neighbour as endpoint candidates, and treating pixels with more than two neighbours as junction
candidates. Nearby junction pixels are clustered into candidate junction centres.

The visualization draws the skeleton path in cyan, endpoint candidates as green circles, and clustered
junction candidates as larger red circles. The API endpoint is:

```text
POST /api/engineering/harness-graph/demo
```

These are pixel-neighbour feasibility estimates. Connector geometry, segmentation artifacts, and dense
branches can produce false candidates, so this output is not connected to production PASS/NG logic.

The same graph analysis now reports a weighted centreline length in pixels. Horizontal and vertical
skeleton steps count as `1 px`; diagonal steps count as `sqrt(2) px`. Extracted graph branches include
both along-skeleton path length and straight node-to-node distance. Orientations use image coordinates:
`0°` right, `90°` down, `180°` left, and `270°` up.

For each clustered junction, Engineering View lists its resolved branch count and outward branch
orientations. It also lists the nearest reachable end terminal by graph distance. Branch-to-branch
distance is defined for pairs sharing a junction: the table reports both the path between their
midpoints through the junction and the straight midpoint distance. All values are uncalibrated pixels;
pixel-to-millimetre conversion remains a later calibration step.

## Demonstration inspection report

Open **Reports** to generate a complete report for `DEMO-HARNESS-001`. The annotated evidence image
shows the weighted total wire centreline length and labels the ten longest resolved graph branches.
The original test image remains unchanged; annotation is generated on an in-memory copy.

The report includes traceability fields, the deterministic 9 PASS / 3 NG checkpoint result, all
node-to-node branch measurements, checkpoint search/status filtering, CSV download, and a
print-friendly layout that can be saved as PDF from the browser. The report API endpoints are:

```text
GET /api/reports/demo
GET /api/reports/demo/export.csv
```

## Project structure

```text
wire-harness-ai-inspection/
├── backend/
│   ├── app/
│   │   ├── api/routes/health.py
│   │   ├── core/{database,logging_config,settings}.py
│   │   ├── config.py
│   │   └── main.py
│   ├── tests/test_health.py
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── services/
│   │   └── types/
│   ├── package.json
│   └── vite.config.ts
├── data/
│   ├── calibration/
│   ├── captured_images/
│   ├── inspection_results/
│   ├── models/
│   ├── reference_images/
│   └── reports/
├── tests/
│   ├── test_cloud_io.py
│   ├── test_inspection_engine.py
│   └── test_streamlit_startup.py
├── streamlit_app.py
├── requirements.txt
├── requirements-dev.txt
├── DEPLOYMENT.md
├── docs/architecture.md
├── docs/cloud-readiness-audit.md
├── .env.example
└── docker-compose.yml
```

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer and npm

## Windows development setup

Open PowerShell in this project folder.

### Single-command startup

After the one-time dependency setup below, start the complete application from the project folder with:

```powershell
.\run.cmd
```

This starts both the FastAPI backend and Vite frontend in the same console. Open
http://127.0.0.1:5173 and press `Ctrl+C` in the console to stop both services.

From the parent `PEOS` folder, the equivalent single command is:

```powershell
.\wire-harness-ai-inspection\run.cmd
```

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks activation, the virtual environment can be used directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend URLs:

- Health: http://127.0.0.1:8000/api/health
- OpenAPI: http://127.0.0.1:8000/docs

### 2. Frontend

Open a second PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The dashboard's system readiness indicators call the backend health endpoint.

On Windows systems where PowerShell script execution blocks `npm.ps1`, use `npm.cmd`:

```powershell
npm.cmd install
npm.cmd run dev
```

## Configuration

Development defaults run immediately with SQLite. Copy `.env.example` to `.env` only when values need to change.
For PostgreSQL, set a URL such as:

```text
DATABASE_URL=postgresql+psycopg://inspection_user:password@localhost:5432/wire_harness_inspection
```

Docker is optional. The included Compose file starts PostgreSQL only when its explicit profile is used.

## Verification

For the Streamlit cloud path, from the project root:

```powershell
.\.venv-cloud\Scripts\python.exe -m pytest tests
```

For the original application, from `backend` with the virtual environment active:

```powershell
python -m pytest
```

From `frontend`:

```powershell
npm run build
```

The backend test confirms the API and SQLite connection. The frontend build performs strict TypeScript compilation and a production Vite build.

## Live Inspection test image

The **Load Demo Image** button requests the logical image:

```text
data/test_images/harness_sample_01.jpeg
```

The development image currently present on disk has an additional `.jpeg` suffix. The backend resolves
that filename as a fallback while keeping the original file untouched. **Upload Test Image** creates a
temporary browser preview only; it does not copy, upload, or overwrite the selected local file.
