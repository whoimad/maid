"""Docs checks: relative Markdown links must resolve."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_relative_markdown_links_resolve():
    files = sorted((ROOT / "docs").rglob("*.md")) + [ROOT / "README.md"]
    broken = []
    for md in files:
        for target in re.findall(r"\]\(([^)]+)\)", md.read_text(encoding="utf-8")):
            if target.startswith(("http", "#", "mailto:")):
                continue
            path = target.split("#", 1)[0]
            if not (md.parent / path).exists():
                broken.append(f"{md.relative_to(ROOT)} -> {target}")
    assert broken == []
