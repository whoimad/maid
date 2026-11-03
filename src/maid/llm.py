"""LLM scorer: K sampled 1-9 scores per company and criterion, each with a verified verbatim quote. It never ranks."""
import hashlib
import json
import math

from openai import OpenAI

from maid.cache import DiskCache
from maid.rubrics import PROMPT_VERSION, build_messages
from maid.state import CriterionScore
from maid.tenk import EXTRACTOR_VERSION, approx_tokens

QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})
MIN_PROMPT_RATIO = 0.7  # reported prompt tokens below this share of the estimate means the server truncated


class ScoringError(RuntimeError):
    """Too few valid samples for one company and criterion."""


class ContextTruncated(RuntimeError):
    """The server read fewer prompt tokens than were sent (for example Ollama's 4k default context)."""


def normalize(s: str) -> str:
    """Collapse whitespace and map curly quotes, dashes and non-breaking spaces to plain ASCII."""
    return " ".join(s.translate(QUOTES).split())


def quote_in_text(quote: str, text: str) -> bool:
    """True when the normalized quote is a non-empty substring of the normalized text."""
    q = normalize(quote)
    return bool(q) and q in normalize(text)


def parse_reply(content: str, text: str) -> tuple[int, str, str]:
    """(score, evidence, reasoning) from a JSON reply; ValueError when invalid or the quote is not in text."""
    c = content.strip()
    if c.startswith("```"):
        c = c[3:]
        if c[:4].lower() == "json":
            c = c[4:]
        c = c.removesuffix("```").strip()
    try:
        d = json.loads(c)
    except json.JSONDecodeError as e:
        raise ValueError(f"not valid JSON: {e.msg}") from None
    if not isinstance(d, dict):
        raise ValueError("reply is not a JSON object")
    s = d.get("score")
    if isinstance(s, float) and s.is_integer():
        s = int(s)
    if isinstance(s, bool) or not isinstance(s, int) or not 1 <= s <= 9:
        raise ValueError(f"score not an integer in 1-9: {s!r}")
    ev = d.get("evidence")
    if not isinstance(ev, str) or not normalize(ev):
        raise ValueError("evidence missing or empty")
    if len(normalize(ev)) > 300:
        raise ValueError("evidence longer than 300 characters")
    if not quote_in_text(ev, text):
        raise ValueError("evidence is not a verbatim quote from the excerpt")
    r = d.get("reasoning")
    return s, ev, (r[:600] if isinstance(r, str) else "")


class LLMScorer:
    """Scores with any OpenAI-compatible client; every reply is cached on disk and logged in self.log."""

    def __init__(self, client, model: str, cache: DiskCache, temperature: float = 0.7, max_attempts: int = 3,
                 seed: int = 0, max_tokens: int = 400):
        self.client, self.model, self.cache = client, model, cache
        self.temperature, self.max_attempts, self.seed, self.max_tokens = temperature, max_attempts, seed, max_tokens
        self.log: list[dict] = []

    def _call(self, messages: list[dict], seed: int) -> dict:
        """One chat completion (the only network call); raises ContextTruncated when the prompt was cut."""
        r = self.client.chat.completions.create(model=self.model, messages=messages, temperature=self.temperature,
                                                seed=seed, max_tokens=self.max_tokens,
                                                response_format={"type": "json_object"})
        usage = getattr(r, "usage", None)
        sent = approx_tokens("".join(m["content"] for m in messages))
        if usage is None or usage.prompt_tokens < MIN_PROMPT_RATIO * sent:
            raise ContextTruncated(f"server read {getattr(usage, 'prompt_tokens', None)} prompt tokens, sent ~{sent}; "
                                   "raise the context size (Ollama: Modelfile PARAMETER num_ctx 32768)")
        return {"content": r.choices[0].message.content or "", "model": r.model,
                "prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}

    def score(self, company: str, criterion: str, filing: str, k: int) -> list[CriterionScore]:
        """Return the valid samples among k (up to max_attempts tries each); ScoringError if fewer than ceil(k/2)."""
        messages = build_messages(criterion, company, filing)
        digest = hashlib.sha256(json.dumps(messages).encode()).hexdigest()
        valid = []
        for sample in range(k):
            for attempt in range(self.max_attempts):
                seed = self.seed + 1000 * sample + attempt
                key = DiskCache.llm_key(self.model, PROMPT_VERSION, EXTRACTOR_VERSION, criterion, company, digest,
                                        sample, attempt, self.temperature)
                reply = self.cache.get_or_compute(key, lambda seed=seed: self._call(messages, seed))
                rec = {"company": company, "criterion": criterion, "sample": sample, "attempt": attempt,
                       "model": reply["model"], "prompt_tokens": reply["prompt_tokens"],
                       "completion_tokens": reply["completion_tokens"]}
                try:
                    score, evidence, reasoning = parse_reply(reply["content"], filing)
                except ValueError as e:
                    self.log.append({**rec, "ok": False, "error": str(e), "score": None, "reasoning": ""})
                    continue
                valid.append(CriterionScore(company=company, criterion=criterion, score=score, evidence=evidence))
                self.log.append({**rec, "ok": True, "error": None, "score": score, "reasoning": reasoning})
                break
        if len(valid) < math.ceil(k / 2):
            raise ScoringError(f"{company} / {criterion}: {len(valid)} valid samples of {k}")
        return valid


def make_client(settings) -> OpenAI:
    """OpenAI client for the configured endpoint; a key is required unless the server is local."""
    local = settings.base_url.startswith(("http://localhost", "http://127.0.0.1"))
    if not settings.api_key and not local:
        raise ValueError("no LLM API key: set LLM_API_KEY or DEEPSEEK_API_KEY")
    return OpenAI(base_url=settings.base_url, api_key=settings.api_key or "none", timeout=600)
