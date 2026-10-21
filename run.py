from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


def resolve_backend_python() -> Path:
    if os.name == "nt":
        windows_venv = BACKEND_ROOT / ".venv" / "Scripts" / "python.exe"
        if windows_venv.is_file():
            return windows_venv
    else:
        unix_venv = BACKEND_ROOT / ".venv" / "bin" / "python"
        if unix_venv.is_file() and os.access(unix_venv, os.X_OK):
            return unix_venv
    return Path(sys.executable)


def resolve_npm() -> str:
    npm = shutil.which("npm.cmd") if os.name == "nt" else shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm was not found. Install Node.js 20 or newer and try again.")
    return npm


def validate_setup(backend_python: Path, npm: str) -> None:
    required_paths = [
        BACKEND_ROOT / "app" / "main.py",
        FRONTEND_ROOT / "package.json",
    ]
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in required_paths if not path.exists()]
    if missing:
        raise RuntimeError(f"Required project file is missing: {', '.join(missing)}")
    test_image_directory = PROJECT_ROOT / "data" / "test_images"
    if not any(
        (test_image_directory / filename).is_file()
        for filename in ("harness_sample_01.jpeg", "harness_sample_01.jpeg.jpeg")
    ):
        raise RuntimeError("The configured harness test image is missing from data/test_images.")
    if not backend_python.exists():
        raise RuntimeError("Python was not found. Install Python 3.11 or newer and try again.")
    if not (FRONTEND_ROOT / "node_modules").is_dir():
        raise RuntimeError("Frontend dependencies are missing. Run 'npm install' in frontend once.")

    backend_check = subprocess.run(
        [str(backend_python), "-c", "import fastapi, uvicorn"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if backend_check.returncode != 0:
        raise RuntimeError(
            "Backend dependencies are missing. Install backend/requirements-dev.txt once."
        )
    npm_check = subprocess.run(
        [npm, "--version"],
        cwd=FRONTEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if npm_check.returncode != 0:
        raise RuntimeError("npm could not start. Check the Node.js installation.")


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
        process.wait(timeout=5)


def run_application() -> int:
    backend_python = resolve_backend_python()
    npm = resolve_npm()
    validate_setup(backend_python, npm)

    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"

    print("Starting AI Wire Harness Final Inspection System...")
    print("Frontend: http://127.0.0.1:5173")
    print("Backend:  http://127.0.0.1:8000")
    print("OpenAPI:  http://127.0.0.1:8000/docs")
    print("Press Ctrl+C to stop both services.\n")

    backend = subprocess.Popen(
        [
            str(backend_python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=BACKEND_ROOT,
        env=environment,
        creationflags=creation_flags,
    )
    frontend = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=FRONTEND_ROOT,
        env=environment,
        creationflags=creation_flags,
    )

    try:
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(0.4)
        if backend.poll() is not None:
            print(f"Backend stopped unexpectedly with exit code {backend.returncode}.")
            return backend.returncode or 1
        print(f"Frontend stopped unexpectedly with exit code {frontend.returncode}.")
        return frontend.returncode or 1
    except KeyboardInterrupt:
        print("\nStopping application...")
        return 0
    finally:
        stop_process(frontend)
        stop_process(backend)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the backend and frontend together.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the local runtime without starting the services.",
    )
    args = parser.parse_args()
    try:
        backend_python = resolve_backend_python()
        npm = resolve_npm()
        validate_setup(backend_python, npm)
        if args.check:
            print("Launcher check passed: Python, backend packages, npm, and frontend packages are ready.")
            return 0
        return run_application()
    except RuntimeError as error:
        print(f"Cannot start application: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
