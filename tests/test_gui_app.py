"""Smoke test: the Streamlit app runs without exceptions (skipped when the gui extra is missing)."""
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


def test_app_runs():
    at = AppTest.from_file("../app/streamlit_app.py", default_timeout=60).run()
    assert not at.exception
