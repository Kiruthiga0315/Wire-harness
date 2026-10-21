from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_application_starts_without_exception() -> None:
    app = AppTest.from_file(str(PROJECT_ROOT / "streamlit_app.py")).run(timeout=30)
    assert not app.exception
    assert any("AI Wire Harness Inspection System" in item.value for item in app.markdown)
    assert app.file_uploader
    assert any("Choose an image to preview it" in item.value for item in app.markdown)


def test_mobile_responsive_style_is_present() -> None:
    source = (PROJECT_ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    assert "@media (max-width: 700px)" in source
    assert 'data-testid="column"' in source
