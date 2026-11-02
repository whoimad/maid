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


def test_graph_doc_diagram_matches_code():
    from maid.graph import build_graph

    text = (ROOT / "docs/architecture/graph.md").read_text(encoding="utf-8")
    marker = "<!-- current-graph: kept in sync with build_graph() by tests/test_docs.py -->"
    block = text.split(marker, 1)[1].split("```mermaid", 1)[1].split("```", 1)[0]
    doc_edges = set(re.findall(r"^\s*(\w+)\s*-->\s*(\w+)\s*;?\s*$", block, re.M))
    assert doc_edges == {(e.source, e.target) for e in build_graph().get_graph().edges}
