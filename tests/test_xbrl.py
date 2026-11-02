"""Point-in-time XBRL extraction on synthetic fixtures."""
import copy
import json
from pathlib import Path

import pytest

from maid.xbrl import annual_value, latest_10k, tech_criteria

FIX = Path(__file__).parent / "fixtures/sec"


def load(name):
    return json.loads((FIX / name).read_text())


F = load("companyfacts_example.json")
REV = ["RevenueFromContractWithCustomerExcludingAssessedTax"]


def test_latest_10k_ignores_amendment():
    assert latest_10k(F, "2025-03-31") == ("A-2025", "2025-02-10", "2024-12-31")


def test_latest_10k_respects_filing_date():
    assert latest_10k(F, "2024-12-31")[0] == "A-2024"


def test_restatement_excluded():
    assert tech_criteria(F, "2025-03-31")["values"]["revenue_growth"] == pytest.approx(1000 / 800 - 1)


def test_margins():
    v = tech_criteria(F, "2025-03-31")["values"]
    assert v["operating_margin"] == pytest.approx(0.2)
    assert v["fcf_margin"] == pytest.approx(0.25)
    assert v["rd_intensity"] == pytest.approx(0.15)


def test_quarterly_ignored():
    assert annual_value(F, REV, "A-2025", "2024-12-31")["value"] == 1000


def test_tag_fallback():
    t = tech_criteria(load("companyfacts_revenues_tag.json"), "2025-03-31")["tags"]
    assert t["revenue"] == "Revenues"
    assert t["rd"] == "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"


def test_missing_tag_raises():
    f = copy.deepcopy(F)
    del f["facts"]["us-gaap"]["OperatingIncomeLoss"]
    with pytest.raises(ValueError, match="OperatingIncomeLoss"):
        tech_criteria(f, "2025-03-31")


def test_no_10k_before_date():
    with pytest.raises(ValueError):
        latest_10k(F, "2020-01-01")


def test_latest_10k_custom_tags():
    assert latest_10k(F, "2025-03-31", REV) == ("A-2025", "2025-02-10", "2024-12-31")
    with pytest.raises(ValueError):
        latest_10k(F, "2025-03-31", ["NoSuchTag"])
