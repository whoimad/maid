"""Smoke test: the Streamlit app runs without exceptions (skipped when the gui extra is missing)."""
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


def test_app_runs():
    at = AppTest.from_file("../app/streamlit_app.py", default_timeout=60).run()
    assert not at.exception


def test_override_through_form():
    at = AppTest.from_file("../app/streamlit_app.py", default_timeout=60).run()
    at.text_input[0].set_value("manager disagrees")
    at.button[0].click().run()  # form submit button "Add override"
    assert not at.exception
    assert at.session_state["overrides"][0]["reason"] == "manager disagrees"
    assert any("manager disagrees" in m.value for m in at.markdown)
