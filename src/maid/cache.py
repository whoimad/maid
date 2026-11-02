"""Tiny on-disk JSON cache keyed by a hash, so API/data calls are never paid for twice."""
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable


class DiskCache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(*parts: Any) -> str:
        blob = json.dumps(parts, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()

    @staticmethod
    def llm_key(model: str, prompt_version: str, *parts: Any) -> str:
        """Key for LLM calls: model and prompt version are mandatory (design decision D7)."""
        return DiskCache.key("llm", model, prompt_version, *parts)

    def get_or_compute(self, key: str, fn: Callable[[], Any]) -> Any:
        path = self.root / f"{key}.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                pass  # corrupt/truncated file: recompute
        value = fn()
        blob = json.dumps(value)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        try:
            tmp.write_text(blob)
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)  # no-op after a successful replace
        return value
