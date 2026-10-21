# Cloud implementation verification report

Verification date: 2026-10-16  
Target runtime: Python 3.12 / Streamlit Community Cloud / CPU

## Files added

- `streamlit_app.py` — cloud web entry point and responsive industrial dashboard.
- `requirements.txt` — minimal Streamlit/OpenCV runtime dependencies.
- `requirements-dev.txt` — test dependency overlay.
- `.streamlit/config.toml` — headless server, upload bound, XSRF, and theme settings.
- `DEPLOYMENT.md` — Windows, private GitHub, and Streamlit Community Cloud instructions.
- `run_streamlit.cmd` — one-click local Streamlit launcher used by the Desktop shortcut.
- `docs/cloud-readiness-audit.md` — pre-change architecture, model, feature, and portability audit.
- `backend/app/services/inspection_engine.py` — reusable uploaded-image inspection interface.
- `backend/app/services/cloud_io.py` — bounded in-memory upload decoding and result exports.
- `tests/conftest.py`, `tests/test_cloud_io.py`, `tests/test_inspection_engine.py`, and
  `tests/test_streamlit_startup.py` — cloud functional tests.

## Files updated

- `.gitignore` — excludes private images/reference data, outputs, credentials, secrets, and model weights.
- `.env.example` — documents the reserved `MODEL_WEIGHTS_PATH` without a credential or real path.
- `README.md` — adds Streamlit usage and truthful capability limits.
- `backend/app/services/__init__.py` — exports the reusable engine interface.

The existing React/FastAPI routes, mock operator demo, segmentation algorithm, graph algorithm, report
module, database layer, launchers, and the original harness test image were not replaced or overwritten.

## Runtime versions exercised

- Python 3.12.14
- Streamlit 1.66.0
- NumPy 2.5.2
- OpenCV headless 4.14.0.94
- scikit-image 0.26.0
- Pillow 12.3.0
- pytest 8.4.2

These versions satisfy the bounded ranges in root `requirements.txt` and `requirements-dev.txt`.
`pip check` reported no broken requirements.

## Test results

| Check | Result |
| --- | --- |
| New upload/engine/export/Streamlit suite | 14 passed |
| Existing FastAPI/backend suite | 21 passed |
| Real Streamlit CLI headless startup on port 8502 | Passed |
| Python compile check for entry point, backend services, and tests | Passed |
| Valid JPEG/JPG/PNG decoding | Passed |
| Extension, MIME, corruption, byte, dimension, and pixel bounds | Passed |
| Missing and unsupported model handling | Passed |
| CPU-only device status | Passed |
| Implemented evidence rules and unavailable production-rule statuses | Passed |
| PNG, JSON, and CSV exports | Passed |
| Repeated inspections and unique IDs | Passed |
| Responsive mobile CSS presence | Passed |
| Existing private harness fixture processed by real OpenCV pipeline | Passed |
| Original private fixture SHA-256 unchanged | Passed |

The fixture SHA-256 remained
`93EAC1E49018344EF9D7E808DA3F8DACFC95695E7FE49D4AAAADE58E38326536`.

## Unverified or blocked items

- No external Streamlit Community Cloud deployment was made, so the application URL and real Linux-host
  behavior remain to be verified after the private GitHub repository is connected.
- Windows denied automated writes to both the user and Public Desktop. The verified launcher and generated
  shortcut remain in the project folder; the shortcut can be copied to the Desktop manually.
- No trained model, model loader, class map, or validated detector fixtures exist. Real component detection,
  confidence boxes, and model-derived PASS/FAIL cannot be tested or enabled.
- No calibration artifact exists. Physical dimensions remain unverified and are reported only in pixels.
- Browser behavior was exercised through Streamlit's application test framework and responsive CSS checks;
  physical mobile-device visual QA remains a deployment smoke-test item.
- Sustained multi-user load and platform memory ceilings require testing in the selected hosting tier.
