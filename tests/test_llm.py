import dataclasses
import json
from types import SimpleNamespace as NS

import pytest

from maid.cache import DiskCache
from maid.config import get_settings
from maid.llm import ContextTruncated, LLMScorer, ScoringError, make_client, parse_reply, quote_in_text
from maid.rubrics import RUBRICS, SYSTEM, build_messages

TEXT = "We raised prices 5% while volume grew 2%. Costs were passed through to customers."
OK = json.dumps({"score": 8, "evidence": "We raised prices 5% while volume grew 2%.", "reasoning": "r"})


class FakeClient:
    """Returns queued reply contents; records every create() call."""

    def __init__(self, contents, prompt_tokens=None, model="fake-1"):
        self.contents, self.calls, self.pt, self.model = list(contents), [], prompt_tokens, model
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        sent = sum(len(m["content"]) for m in kw["messages"]) // 4
        return NS(choices=[NS(message=NS(content=self.contents.pop(0)))], model=self.model,
                  usage=NS(prompt_tokens=self.pt if self.pt is not None else sent, completion_tokens=20))


def scorer(client, tmp_path, **kw):
    return LLMScorer(client, "m", DiskCache(tmp_path), **kw)


@pytest.mark.parametrize("crit", sorted(RUBRICS))
def test_build_messages(crit):
    m = build_messages(crit, "Company 007", "Some text.")
    assert len(m) == 2
    assert "json" in m[0]["content"] and "Company 007" in m[0]["content"] and RUBRICS[crit] in m[0]["content"]
    assert m[1]["content"].endswith("Some text.")


def test_build_messages_unknown_criterion():
    with pytest.raises(ValueError):
        build_messages("nope", "Company 001", "x")


def test_k_valid_samples(tmp_path):
    fc = FakeClient([OK] * 3)
    s = scorer(fc, tmp_path)
    out = s.score("Company 001", "pricing_power", TEXT, 3)
    assert [x.score for x in out] == [8, 8, 8]
    assert [c["seed"] for c in fc.calls] == [0, 1000, 2000]
    assert all(c["response_format"] == {"type": "json_object"} for c in fc.calls)
    assert len(s.log) == 3 and all(r["ok"] and r["model"] == "fake-1" for r in s.log)


def test_retry_after_invalid_reply(tmp_path):
    fc = FakeClient(["not json", OK])
    s = scorer(fc, tmp_path)
    assert len(s.score("Company 001", "pricing_power", TEXT, 1)) == 1
    assert [c["seed"] for c in fc.calls] == [0, 1]
    assert s.log[0]["ok"] is False


@pytest.mark.parametrize("bad", [
    {"score": 8, "evidence": "not in the text at all"},
    {"score": 10, "evidence": "We raised prices 5%"},
    {"score": True, "evidence": "We raised prices 5%"},
    {"score": 8, "evidence": ""},
])
def test_parse_reply_rejects(bad):
    with pytest.raises(ValueError):
        parse_reply(json.dumps(bad), TEXT)


def test_parse_reply_accepts_integral_float_and_fence():
    assert parse_reply(json.dumps({"score": 7.0, "evidence": "We raised prices 5%"}), TEXT)[0] == 7
    assert parse_reply("```json\n" + OK + "\n```", TEXT)[0] == 8


def test_quote_normalization():
    assert quote_in_text("We ’raised’  prices", "We 'raised' prices now")


def test_too_few_valid_samples(tmp_path):
    bad = "not json"
    with pytest.raises(ScoringError):
        scorer(FakeClient([OK, bad, bad, bad]), tmp_path, max_attempts=1).score("C", "pricing_power", TEXT, 4)
    out = scorer(FakeClient([OK, bad, OK, bad]), tmp_path / "b", max_attempts=1).score("C", "pricing_power", TEXT, 4)
    assert len(out) == 2


def test_truncation_guard_does_not_cache(tmp_path):
    with pytest.raises(ContextTruncated):
        scorer(FakeClient([OK], prompt_tokens=5), tmp_path).score("C", "pricing_power", TEXT * 200, 1)
    assert not list(tmp_path.glob("*.json"))


def test_cache_reuse_and_temperature_key(tmp_path):
    first = scorer(FakeClient([OK]), tmp_path).score("C", "pricing_power", TEXT, 1)
    fc = FakeClient([])
    assert scorer(fc, tmp_path).score("C", "pricing_power", TEXT, 1) == first
    assert fc.calls == []
    fc2 = FakeClient([OK])
    scorer(fc2, tmp_path, temperature=0.2).score("C", "pricing_power", TEXT, 1)
    assert len(fc2.calls) == 1


def test_make_client(tmp_path):
    s = get_settings()
    with pytest.raises(ValueError):
        make_client(dataclasses.replace(s, base_url="https://api.example.com"))
    assert make_client(dataclasses.replace(s, base_url="http://localhost:11434/v1")) is not None
    assert make_client(dataclasses.replace(s, base_url="http://127.0.0.1:11434/v1")) is not None


def test_quote_length_limit():
    long = "Costs rose. " * 40
    for n, ok in ((350, True), (401, False)):
        q = long[:n].strip()
        while len(q) < n:
            q += "x"
        text = "Intro. " + q + " End."
        reply = json.dumps({"score": 5, "evidence": q})
        if ok:
            assert parse_reply(reply, text)[0] == 5
        else:
            with pytest.raises(ValueError):
                parse_reply(reply, text)
    assert "400 characters" in SYSTEM
