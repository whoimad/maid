"""Tiny on-disk JSON cache keyed by a hash, so API/data calls are never paid for twice."""
import hashlib
import json
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

    def get_or_compute(self, key: str, fn: Callable[[], Any]) -> Any:
        path = self.root / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text())
        value = fn()
        path.write_text(json.dumps(value))
        return value
