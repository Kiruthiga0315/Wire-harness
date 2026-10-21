# Streamlit deployment guide

This guide deploys the additive Streamlit interface. The existing FastAPI/React application remains
available through `run.cmd` and is not required by the Streamlit process.

## Current capability boundary

The repository contains real OpenCV segmentation, skeleton, topology, orientation, and pixel-distance
algorithms. It does **not** contain trained YOLO/ONNX weights, an object-detector loader, a class map,
validated component rules, reference routing data, or pixel-to-physical calibration. The Streamlit app
therefore runs the implemented engineering pipeline and truthfully reports production rules as
`NOT_EVALUATED`. It never substitutes the deterministic mock service for inference.

The acceptance criterion requiring real trained-model detections cannot be completed until the owner
supplies an authorized model and its matching validated preprocessing, loader, post-processing, class map,
thresholds, and inspection-rule configuration.

## Supported runtime

- Python 3.12 (deployment target)
- CPU execution
- Linux-compatible `opencv-python-headless`
- No camera, database, Node.js, CUDA, or writable persistent storage required for upload mode

## Local execution on Windows

Open PowerShell in the project folder:

```powershell
cd C:\Users\91979\OneDrive\PEOS\wire-harness-ai-inspection
py -3.12 -m venv .venv-cloud
.\.venv-cloud\Scripts\python.exe -m pip install --upgrade pip
.\.venv-cloud\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv-cloud\Scripts\python.exe -m pytest tests
.\.venv-cloud\Scripts\python.exe -m streamlit run streamlit_app.py
```

Open the local URL printed by Streamlit, normally `http://localhost:8501`.

After setup, the single-command launcher is:

```powershell
.\run_streamlit.cmd
```

The machine-specific shortcut **AI Wire Harness Inspection** is generated beside the launcher and can be
copied to the Windows Desktop. It is intentionally excluded from Git because it contains a local path.

The original local application still starts separately with:

```powershell
.\run.cmd
```

## Create a private GitHub repository

Before committing, verify that `git status` does not list customer images, model weights, databases,
credentials, `.env`, Streamlit secrets, or generated reports. The repository `.gitignore` excludes those
categories by default, including `data/test_images/` and `data/models/`.

Using GitHub CLI:

```powershell
git init
git add .
git status
git commit -m "Add cloud-safe Streamlit inspection interface"
gh auth login
gh repo create wire-harness-ai-inspection --private --source . --remote origin --push
```

Alternatively, create a **private** empty repository in GitHub, then follow GitHub's displayed commands to
add the remote and push. Do not override the ignore rules to commit confidential data or unauthorized
weights.

## Deploy on Streamlit Community Cloud

1. Sign in to Streamlit Community Cloud using the GitHub account that can access the private repository.
2. Choose **Create app** and select the private repository and branch.
3. Set the main file path to `streamlit_app.py`.
4. In advanced settings, select Python 3.12.
5. No secrets are required for the current OpenCV-only app.
6. Deploy, open the app URL, upload a non-confidential JPEG/PNG test image, and verify the downloadable
   PNG, JSON, and CSV outputs.

Community Cloud installs root `requirements.txt` automatically. `.streamlit/config.toml` provides the
headless server configuration and a 15 MB upload limit.

## Configuration and secrets

Current deployment requires no environment variable, API key, database URL, or secret.

`MODEL_WEIGHTS_PATH` is reserved for future integration. Setting it today only reports that the file is
unsupported; inference remains disabled until a validated adapter exists. Never place private URLs or
credentials in source code. If future model storage needs credentials, configure them through Streamlit
secrets and load them at runtime without logging their values.

For a future large authorized model, use private object storage or a private model registry with:

- short-lived or least-privilege read credentials;
- a pinned object version and cryptographic checksum;
- download size/time limits and a cache scoped to the Streamlit worker;
- an explicit failure state when the download or checksum validation fails.

## CPU hosting limitations

Community Cloud is CPU-oriented. OpenCV segmentation and skeletonization scale with image size, so the app
limits uploads to 15 MB, 12,000 pixels per side, and 40 megapixels. Large images may still process slowly or
hit platform memory/time limits. A future detector must use bounded input size, batch size, confidence/NMS
settings, and CPU-safe device selection supported by its real API.

Streamlit sessions share cached read-only engine resources, while uploads and results stay in each user's
session memory. No upload or temporary file is written by the Streamlit path.

## Post-deployment verification

- App opens without a model or camera.
- JPEG/JPG/PNG validation rejects mismatched, corrupt, oversized, or over-dimensioned uploads.
- Inspection runs only after the user presses **Run AI Inspection**.
- Original input pixels are not modified.
- Engineering measurements remain in pixels.
- Unavailable component and dimensional rules show `NOT_EVALUATED`.
- Annotated PNG, JSON, and CSV downloads open correctly.
- Repeated runs receive unique inspection IDs and do not accumulate temporary files.

See `docs/cloud-readiness-audit.md` for the full architecture and capability audit.
