"""10-K text extraction and anonymization (no network)."""
import urllib.request
from pathlib import Path

import pytest

from maid.tenk import anonymize_text, approx_tokens, extract_sections, heading, html_to_text, name_variants

HTML = (Path(__file__).parent / "fixtures/tenk/mini_10k.htm").read_text()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network in tests")

    monkeypatch.setattr(urllib.request, "urlopen", boom)


def test_html_to_text_drops_hidden_header():
    assert "SECRET-HIDDEN-FACT" not in html_to_text(HTML)


def test_extract_skips_toc_and_cross_references():
    s = extract_sections(HTML)
    assert s["1"].startswith("Item 1. Business")
    assert "raised prices 5%" in s["1"]
    assert "Input costs" not in s["1"]
    assert s["1a"].startswith("Item 1A. Risk Factors")
    assert "We returned cash through dividends." in s["7"]
    assert "Rates." not in s["7"]
    assert "\n" not in s["7"]


def test_item1_does_not_match_1a():
    assert heading("1").search("Item 1A. Risk Factors") is None


def test_item7_does_not_match_7a():
    assert heading("7").search("Item 7A. Quantitative") is None


def test_name_variants():
    assert name_variants(["PROCTER & GAMBLE Co"]) == ["PROCTER & GAMBLE"]
    assert name_variants(["ALTRIA GROUP, INC."]) == ["ALTRIA GROUP"]
    assert name_variants(["The Hershey Company"]) == ["Hershey"]


def test_anonymize_text():
    s = extract_sections(HTML)
    out, n = anonymize_text(s["1"], ["ACME FOODS, Inc."], "ACME", "Company 007")
    assert "Company 007 sells cereal" in out
    assert "ACME" not in out and "Acme" not in out
    assert n == 2
    assert anonymize_text("ACMEX and acme", ["ACME FOODS"], "ACME", "L")[1] == 0


def test_anonymize_hyphen_and_space_variants():
    out, n = anonymize_text("The Coca-Cola Company and Coca Cola and COCA-COLA.", ["COCA COLA CO"], "KO", "Company 030")
    assert n == 3 and "Coca" not in out and "COCA" not in out


def test_approx_tokens():
    assert approx_tokens("abcd") == 1
    assert approx_tokens("") == 0
