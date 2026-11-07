"""Point-in-time XBRL extraction on synthetic fixtures."""
import copy
import json
from pathlib import Path

import pytest

from maid.xbrl import annual_value, latest_10k, parse_cover, staples_criteria, tech_criteria

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
    assert v["net_margin"] == pytest.approx(0.2)
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
    del f["facts"]["us-gaap"]["NetIncomeLoss"]
    with pytest.raises(ValueError, match="NetIncomeLoss"):
        tech_criteria(f, "2025-03-31")


def test_no_10k_before_date():
    with pytest.raises(ValueError):
        latest_10k(F, "2020-01-01")


def test_latest_10k_custom_tags():
    assert latest_10k(F, "2025-03-31", REV) == ("A-2025", "2025-02-10", "2024-12-31")
    with pytest.raises(ValueError):
        latest_10k(F, "2025-03-31", ["NoSuchTag"])


def test_revenue_including_tax_fallback():
    f = copy.deepcopy(F)
    u = f["facts"]["us-gaap"]
    u["RevenueFromContractWithCustomerIncludingAssessedTax"] = u.pop("RevenueFromContractWithCustomerExcludingAssessedTax")
    c = tech_criteria(f, "2025-03-31")
    assert c["tags"]["revenue"] == "RevenueFromContractWithCustomerIncludingAssessedTax"
    assert c["values"]["revenue_growth"] == pytest.approx(1000 / 800 - 1)


def test_profit_loss_fallback():
    f = copy.deepcopy(F)
    u = f["facts"]["us-gaap"]
    u["ProfitLoss"] = u.pop("NetIncomeLoss")
    c = tech_criteria(f, "2025-03-31")
    assert c["tags"]["net_income"] == "ProfitLoss"
    assert c["values"]["net_margin"] == pytest.approx(0.2)


def _rename_test(old, new, key):
    f = copy.deepcopy(F)
    u = f["facts"]["us-gaap"]
    u[new] = u.pop(old)
    c = tech_criteria(f, "2025-03-31")
    assert c["tags"][key] == new
    assert c["values"]["fcf_margin"] == pytest.approx(0.25)


def test_capex_other_ppe_fallback():
    _rename_test("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireOtherPropertyPlantAndEquipment", "capex")


def test_capex_other_productive_fallback():
    _rename_test("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireOtherProductiveAssets", "capex")


def test_ocf_continuing_fallback():
    _rename_test("NetCashProvidedByUsedInOperatingActivities",
                 "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations", "operating_cash_flow")


def _with_assets():
    f = copy.deepcopy(F)
    row = {"end": "2024-12-31", "val": 4000, "accn": "A-2025", "form": "10-K", "filed": "2025-02-10"}
    f["facts"]["us-gaap"]["Assets"] = {"units": {"USD": [
        row, {**row, "start": "2024-01-01", "val": 9999}, {**row, "accn": "A-2026", "val": 8888}]}}
    return f


def test_staples_criteria_roa():
    c = staples_criteria(_with_assets(), "2025-03-31")
    assert c["values"] == pytest.approx({"revenue_growth": 0.25, "net_margin": 0.2, "fcf_margin": 0.25, "roa": 0.05})
    assert "rd" not in c["tags"] and c["tags"]["assets"] == "Assets"


def test_staples_criteria_missing_assets_raises():
    with pytest.raises(ValueError, match="Assets"):
        staples_criteria(F, "2025-03-31")


def test_tech_criteria_unchanged():
    assert tech_criteria(F, "2025-03-31") == {
        "accn": "A-2025", "filed": "2025-02-10", "period_end": "2024-12-31",
        "values": {"revenue_growth": 0.25, "net_margin": 0.2, "fcf_margin": 0.25, "rd_intensity": 0.15},
        "tags": {"revenue": "RevenueFromContractWithCustomerExcludingAssessedTax", "net_income": "NetIncomeLoss",
                 "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
                 "capex": "PaymentsToAcquirePropertyPlantAndEquipment", "rd": "ResearchAndDevelopmentExpense"}}


def test_parse_cover():
    c = parse_cover((FIX / "cover_two_classes.xml").read_text())
    assert c["shares"] == 192721011.0
    assert c["symbols"] == [["TAP.A", "NYSE"], ["TAP", "NYSE"], ["TAP 32", "NYSE"]]
    assert parse_cover('<x xmlns:dei="http://xbrl.sec.gov/dei/2024"/>')["shares"] is None
