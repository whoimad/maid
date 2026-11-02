"""Point-in-time XBRL extraction: only facts filed on or before the decision date (see docs/architecture/data.md)."""
from datetime import date

REVENUE = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"]
TAGS = {
    "revenue": REVENUE,
    "net_income": ["NetIncomeLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "rd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
           "ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost"],
}
TECH_CRITERIA = ["revenue_growth", "net_margin", "fcf_margin", "rd_intensity"]  # same names as demo_data.QUANT_CRITERIA


def _usd(facts, tag) -> list[dict]:
    """USD facts for a us-gaap tag (empty if absent)."""
    return facts["facts"].get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])


def _days(start, end) -> int:
    """Days from start to end (ISO dates)."""
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _annual(f) -> bool:
    """True for a duration fact of about one year."""
    return "start" in f and 350 <= _days(f["start"], f["end"]) <= 380


def latest_10k(facts, decision_date, tags=REVENUE) -> tuple[str, str, str]:
    """(accn, filed, period_end) of the latest 10-K filed on or before decision_date."""
    cands = [f for tag in tags for f in _usd(facts, tag)
             if f.get("form") == "10-K" and f["filed"] <= decision_date and _annual(f)]
    if not cands:
        raise ValueError(f"no 10-K revenue filed on or before {decision_date}: {facts.get('entityName')}")
    filed = max(f["filed"] for f in cands)
    top = [f for f in cands if f["filed"] == filed]
    accn = top[0]["accn"]
    return accn, filed, max(f["end"] for f in top if f["accn"] == accn)


def annual_value(facts, tags, accn, period_end) -> dict:
    """Annual 10-K value for the first matching tag in this accession and period."""
    for tag in tags:
        hits = [f for f in _usd(facts, tag) if f.get("accn") == accn and f.get("form") == "10-K"
                and f["end"] == period_end and _annual(f)]
        if hits:
            if len({f["val"] for f in hits}) > 1:
                raise ValueError(f"conflicting annual values for {tag} in {accn} ending {period_end}")
            return {"value": float(hits[0]["val"]), "tag": tag}
    raise ValueError(f"no annual fact for {tags} in {accn} ending {period_end}")


def prior_period_end(facts, tags, accn, period_end) -> str:
    """End of the annual period one year before period_end, in the same accession."""
    for tag in tags:
        for f in _usd(facts, tag):
            if (f.get("accn") == accn and f.get("form") == "10-K" and _annual(f)
                    and 350 <= _days(f["end"], period_end) <= 380):
                return f["end"]
    raise ValueError(f"no prior annual period for {tags} in {accn} before {period_end}")


def tech_criteria(facts, decision_date) -> dict:
    """Four tech criteria from the latest 10-K filed on or before decision_date."""
    accn, filed, end = latest_10k(facts, decision_date)
    got = {k: annual_value(facts, t, accn, end) for k, t in TAGS.items()}
    rt = [got["revenue"]["tag"]]
    prev = annual_value(facts, rt, accn, prior_period_end(facts, rt, accn, end))
    rev, rev0 = got["revenue"]["value"], prev["value"]
    if rev <= 0 or rev0 <= 0:
        raise ValueError(f"non-positive revenue in {accn}: {facts.get('entityName')}")
    v = {k: x["value"] for k, x in got.items()}
    return {"accn": accn, "filed": filed, "period_end": end,
            "values": {"revenue_growth": rev / rev0 - 1, "net_margin": v["net_income"] / rev,
                       "fcf_margin": (v["operating_cash_flow"] - v["capex"]) / rev, "rd_intensity": v["rd"] / rev},
            "tags": {k: x["tag"] for k, x in got.items()}}
