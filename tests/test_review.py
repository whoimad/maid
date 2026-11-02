import pytest
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Command
from pydantic import ValidationError

from maid.graph import build_graph, parse_overrides
from maid.state import CHECKPOINT_TYPES, CriterionScore, ScoreOverride

QUAL = [CriterionScore(company="Company A", criterion="moat", score=4, evidence="q")]


def _payload(**kw):
    o = {"company": "Company A", "criterion": "moat", "score": 7, "reason": "underrated"}
    o.update(kw)
    return {"overrides": [o]}


def test_no_payload_means_no_overrides():
    assert parse_overrides(None, []) == []
    assert parse_overrides({}, []) == []


def test_valid_override_is_parsed():
    result = parse_overrides(_payload(), QUAL)
    assert len(result) == 1 and result[0].score == 7


def test_override_without_reason_is_rejected():
    with pytest.raises(ValidationError):
        parse_overrides(_payload(reason=""), QUAL)


def test_override_score_out_of_range_is_rejected():
    with pytest.raises(ValidationError):
        parse_overrides(_payload(score=10), QUAL)


def test_override_for_unknown_score_is_rejected():
    with pytest.raises(ValueError):
        parse_overrides(_payload(criterion="brand"), QUAL)


def test_non_dict_payload_is_rejected():
    with pytest.raises(ValueError):
        parse_overrides("ok", QUAL)


def test_graph_records_overrides_after_resume():
    graph = build_graph()
    cfg = {"configurable": {"thread_id": "t-review"}}
    graph.invoke({"companies": ["Company A"]}, cfg)
    final = graph.invoke(Command(resume={"overrides": []}), cfg)
    assert final["overrides"] == [] and "report" in final


def test_checkpoint_serde_restores_state_models():
    serde = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)
    state = {
        "qualitative": QUAL,
        "overrides": [ScoreOverride(company="Company A", criterion="moat", score=7, reason="r")],
    }
    back = serde.loads_typed(serde.dumps_typed(state))
    assert isinstance(back["qualitative"][0], CriterionScore) and isinstance(back["overrides"][0], ScoreOverride)
