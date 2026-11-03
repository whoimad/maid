import pathlib

import pytest

from maid.cache import DiskCache
from maid.config import get_settings


def test_settings_read_env_at_call_time(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "m-test")
    assert get_settings().model == "m-test"
    monkeypatch.setenv("LLM_MODEL", "m-other")
    assert get_settings().model == "m-other"


def test_llm_defaults_are_local(monkeypatch):
    for k in ("LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    s = get_settings()
    assert s.model == "qwen2.5-32k"
    assert s.base_url == "http://localhost:11434/v1"


def test_settings_cache_dir_is_path(monkeypatch, tmp_path):
    monkeypatch.setenv("MAID_CACHE_DIR", str(tmp_path))
    assert get_settings().cache_dir == tmp_path


def test_corrupt_cache_file_is_recomputed(tmp_path):
    cache = DiskCache(tmp_path)
    k = cache.key("x")
    (tmp_path / f"{k}.json").write_text('{"trunc')
    assert cache.get_or_compute(k, lambda: {"ok": 1}) == {"ok": 1}
    import json

    assert json.loads((tmp_path / f"{k}.json").read_text()) == {"ok": 1}


def test_interrupted_write_leaves_no_file(tmp_path, monkeypatch):
    cache = DiskCache(tmp_path)
    k = cache.key("y")
    real = pathlib.Path.write_text

    def half_then_crash(self, data, *a, **kw):
        real(self, data[: len(data) // 2], *a, **kw)
        raise KeyboardInterrupt

    monkeypatch.setattr(pathlib.Path, "write_text", half_then_crash)
    with pytest.raises(KeyboardInterrupt):
        cache.get_or_compute(k, lambda: {"long": "x" * 100})
    monkeypatch.undo()
    assert list(tmp_path.glob("*.json")) == []
    assert list(tmp_path.glob("*.tmp")) == []
    assert cache.get_or_compute(k, lambda: {"ok": 1}) == {"ok": 1}


def test_llm_key_depends_on_model_and_prompt_version():
    base = DiskCache.llm_key("m1", "v1", "p")
    assert base != DiskCache.llm_key("m2", "v1", "p")
    assert base != DiskCache.llm_key("m1", "v2", "p")
    assert base == DiskCache.llm_key("m1", "v1", "p")
