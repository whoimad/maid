"""10-K text extraction and anonymization (no network)."""
import urllib.request
from pathlib import Path

import pytest

from maid.tenk import (
    anonymize_text,
    approx_tokens,
    clip,
    criterion_text,
    extract_sections,
    heading,
    html_to_text,
    name_variants,
    split_mdna,
)

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
    assert name_variants(["ALTRIA GROUP, INC."]) == ["ALTRIA GROUP", "ALTRIA"]
    assert name_variants(["The Hershey Company"]) == ["Hershey"]


def test_anonymize_text():
    s = extract_sections(HTML)
    out, n = anonymize_text(s["1"], ["ACME FOODS, Inc."], "ACME", "Company 007")
    assert "Company 007 sells cereal" in out
    assert "ACME" not in out and "Acme" not in out
    assert n == 2
    assert anonymize_text("ACMEX and acme", ["ACME FOODS"], "ACME", "L") == ("ACMEX and L", 1)


def test_anonymize_hyphen_and_space_variants():
    out, n = anonymize_text("The Coca-Cola Company and Coca Cola and COCA-COLA.", ["COCA COLA CO"], "KO", "Company 030")
    assert n == 3 and "Coca" not in out and "COCA" not in out


def test_approx_tokens():
    assert approx_tokens("abcd") == 1
    assert approx_tokens("") == 0


def test_heading_dotted_subitems():
    assert heading("1a").search("Item 1.A. Risk Factors")
    assert heading("1a").search("ITEM 1. A RISK FACTORS")
    assert heading("7a").search("Item 7.A. Quantitative and Qualitative")
    assert heading("1").search("Item 1.A. Risk Factors") is None
    assert heading("1").search("Item 1A. Risk Factors") is None


def test_find_mdna_longest_span():
    from maid.tenk import find_mdna

    body = "<p>Net sales rose.</p>" * 50
    html = ("<p>Management’s Discussion and Analysis of Financial Condition</p><p>Report of Independent Registered</p>"
            "<p>Management’s Discussion and Analysis of Financial Condition and Results</p>" + body
            + "<p>Consolidated Statements of Earnings</p><p>Later.</p>")
    got = find_mdna(html)
    assert "Net sales rose." in got and "Later" not in got and got.count("Net sales rose.") == 50


def test_name_variants_v2():
    v = name_variants
    assert "CLOROX" in v(["CLOROX CO /DE/"])
    assert v(["MCCORMICK & CO INC"]) == ["MCCORMICK"]
    assert v(["CHURCH & DWIGHT CO INC /DE/"]) == ["CHURCH & DWIGHT"]
    assert v(["HORMEL FOODS CORP /DE/"]) == ["HORMEL FOODS", "HORMEL"]
    assert v(["Celsius Holdings, Inc."]) == ["Celsius Holdings", "Celsius"]
    assert "Albertsons" in v(["Albertsons Companies, Inc."])
    assert v(["J&J SNACK FOODS CORP"]) == ["J&J SNACK FOODS", "J&J SNACK"]
    assert "P&G" in v(["PROCTER & GAMBLE Co"], aliases=["P&G"])


def test_common_core_stoplist_and_dotless_suffix():
    v = name_variants
    assert v(["Post Holdings, Inc."]) == ["Post Holdings"]
    assert v(["CORN PRODUCTS INTERNATIONAL INC"]) == ["CORN PRODUCTS INTERNATIONAL"]
    assert v(["NATIONAL BEVERAGE CORP"]) == ["NATIONAL BEVERAGE"]
    assert v(["Bunge Global SA"]) == ["Bunge Global", "Bunge"]
    assert anonymize_text("Post Holdings funds post-retirement plans.", ["Post Holdings, Inc."], "POST", "Company 045")[0] == "Company 045 funds post-retirement plans."
    assert anonymize_text("Bunge sells grain.", ["Bunge Global SA"], "BG", "Company 004")[0] == "Company 004 sells grain."
    assert anonymize_text("Pilgrim’s chicken", ["PILGRIMS PRIDE CORP"], "PPC", "Company 046", aliases=["Pilgrims"])[0] == "Company 046 chicken"


@pytest.mark.parametrize("text,name", [
    ("The Clorox Company", "CLOROX CO /DE/"), ("Pilgrim’s Pride", "PILGRIMS PRIDE CORP"),
    ("Pilgrim's Pride", "PILGRIMS PRIDE CORP"), ("The J.M. Smucker Company", "J M SMUCKER CO"),
    ("Estée Lauder", "ESTEE LAUDER COMPANIES INC"), ("McCormick & Company", "MCCORMICK & CO INC"),
    ("Church and Dwight", "CHURCH & DWIGHT CO INC /DE/"), ("Celsius", "Celsius Holdings, Inc."),
    ("Albertsons", "Albertsons Companies, Inc."), ("Hormel Foods", "HORMEL FOODS CORP /DE/")])
def test_anonymize_tolerant(text, name):
    from maid.tenk import residual_mentions

    out, n = anonymize_text(f"We, {text}, sell goods.", [name], "ZZZZ", "Company 001")
    assert n >= 1 and "Company 001" in out
    assert residual_mentions(out, [name]) == 0


def test_anonymize_aliases_and_residual():
    from maid.tenk import residual_mentions

    out, n = anonymize_text("P&G and Procter & Gamble sell Tide.", ["PROCTER & GAMBLE Co"], "PG", "Company 001",
                            aliases=["P&G"])
    assert out == "Company 001 and Company 001 sell Tide." and n == 2
    names = ["HORMEL FOODS CORP /DE/"]
    text = "Hormel Foods sells Hormel chili"
    assert residual_mentions(text, names) > 0
    assert residual_mentions(anonymize_text(text, names, "HRL", "Company 001")[0], names) == 0


def _mdna(head_at: float, n: int = 1000) -> str:
    sents = [f"Sentence {i} about sales." for i in range(n)]
    sents.insert(int(n * head_at), "Liquidity and Capital Resources We have cash.")
    return " ".join(sents)


def test_split_mdna_at_midpoint():
    ops, liq, found = split_mdna(_mdna(0.5))
    assert found and liq.startswith("Liquidity and Capital Resources") and "Liquidity" not in ops


def test_split_mdna_ignores_early_heading():
    ops, liq, found = split_mdna(_mdna(0.1))
    assert not found and ops == liq


def test_clip_long_and_short():
    text = " ".join(f"Sentence number {i} here." for i in range(6000))
    assert approx_tokens(text) > 24000
    out, cut = clip(text)
    assert cut and approx_tokens(out) <= 24000 and out.endswith(".") and text.startswith(out)
    assert clip("Short one. Two.") == ("Short one. Two.", False)


def test_clip_tail_keeps_last_sentence():
    text = " ".join(f"Sentence number {i} here." for i in range(6000))
    out, cut = clip(text, tail=True)
    assert cut and out.endswith("Sentence number 5999 here.") and approx_tokens(out) <= 24000
    assert out.startswith("Sentence")


def test_criterion_text_sources():
    secs = {"1": "Business. " * 10, "1a": "r", "7": _mdna(0.5)}
    assert criterion_text(secs, "strategy_clarity")["source"] == "1"
    p = criterion_text(secs, "pricing_power")
    c = criterion_text(secs, "capital_allocation")
    assert p["source"] == "7_ops" and c["source"] == "7_liq" and c["text"].startswith("Liquidity")
    assert c["split_found"] and not c["truncated"] and c["tokens"] == approx_tokens(c["text"])
    secs["7"] = _mdna(0.1)
    c2 = criterion_text(secs, "capital_allocation")
    assert c2["source"] == "7_tail" and not c2["split_found"]
    with pytest.raises(ValueError):
        criterion_text(secs, "other")


def test_extractor_version_2():
    from maid.tenk import EXTRACTOR_VERSION

    assert EXTRACTOR_VERSION == "2"
