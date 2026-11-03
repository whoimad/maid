# Plan 029: Fetch the decision-date 10-K text, extract Items 1, 1A and 7, and anonymize it (no LLM)

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. The reviewer maintains `plans/README.md`; do not edit it.
>
> **Drift check (run first)**: `git diff --stat b6bb576..HEAD -- src/maid/sec.py src/maid/real_data.py tests/test_sec.py tests/test_real_data.py docs/architecture/data.md`
> → no output expected.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (new module and additive methods; nothing existing changes behaviour)
- **Depends on**: plans 019–027 (DONE)
- **Category**: direction
- **Planned at**: commit `b6bb576` on branch `integration/prototype`, 2026-11-03

## Why this matters

MAID ranks companies with a deterministic MCDM engine. Today the real-data run (61 US consumer-staples companies,
decision date 2025-03-31) uses only four ratios from XBRL. The next step is LLM scores for three qualitative
criteria (pricing power, strategy clarity, capital allocation), read from the text of each company's 10-K. **LLMs
never rank; they score from text, with a quoted sentence as evidence.** Before any LLM is involved, the pipeline
needs the text itself: the same 10-K whose numbers are already used (latest 10-K filed on or before 2025-03-31), cut
into the sections a scorer reads, with the company's name and ticker replaced by its anonymous label
("Company 012"). This plan builds that, with offline tests. **No LLM, no API key, no network in tests.** The reviewer
runs the real fetch afterwards.

## Current state

- `src/maid/sec.py` — cached SEC client. Relevant parts:

  ```python
  # src/maid/sec.py:52-55
  def _get_text(url: str, user_agent: str) -> str:
      """GET a text URL (see _get_bytes)."""
      return _get_bytes(url, user_agent).decode("utf-8")
  ```

  ```python
  # src/maid/sec.py:62-98 (abridged)
  class SecClient:
      """Cached SEC JSON endpoints."""

      def __init__(self, cache: DiskCache | None = None, user_agent: str | None = None, fetch=_get_json,
                   fetch_text=_get_text):
          ...
      def submissions(self, cik) -> dict:
          """Filing submissions metadata for a CIK."""
          return self._cached(f"https://data.sec.gov/submissions/CIK{cik10(cik)}.json")

      def cover(self, cik, accn: str) -> dict:
          """Cover-page shares and symbols from the 10-K's inline XBRL instance (cached)."""
          def get():
              base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}"
              ...
          return self.cache.get_or_compute(DiskCache.key("sec-cover", cik, accn), get)
  ```

  `submissions(cik)` returns JSON with `"name"` (e.g. `"PROCTER & GAMBLE Co"`), `"formerNames"` (list of
  `{"name": ..., "from": ..., "to": ...}`), `"tickers"`, and `"filings": {"recent": {"accessionNumber": [...],
  "form": [...], "filingDate": [...], "primaryDocument": [...]}}` (parallel lists). The reviewer checked: for all 61
  staples companies the 10-K accession used for the numbers is in `filings.recent`, with form `10-K` and a
  `primaryDocument` such as `pg-20240630.htm`. The document URL is
  `https://www.sec.gov/Archives/edgar/data/<int cik>/<accn without dashes>/<primaryDocument>`.

- `src/maid/real_data.py` — frozen universe → labels → criteria:

  ```python
  # src/maid/real_data.py
  SECTORS = {"tech": (Path("data/universe/tech.csv"), TECH_CRITERIA, tech_criteria),
             "staples": (Path("data/universe/staples.csv"), STAPLES_CRITERIA, staples_criteria)}

  def read_universe(path=UNIVERSE) -> list[dict]: ...      # rows with "ticker", "cik", "decision_date", ...
  def anonymize(tickers: list[str]) -> dict[str, str]: ... # label -> ticker, "Company 001".. in ticker order
  def sec_quantitative(rows, companyfacts, decision_date, sector="tech") -> tuple[dict, dict, dict]:
      """(label -> ticker, label -> criterion -> value, label -> {accn, filed, period_end}); ..."""
  def load_sec(decision_date: str, sector: str = "tech", client=None) -> tuple[dict, dict, dict]:
      """sec_quantitative on the frozen universe of a sector with the cached SEC client."""
  ```

  The third return value's `accn` is the 10-K accession whose text this plan fetches.

- Test pattern: `tests/test_sec.py` (autouse `no_network` fixture that makes `urllib.request.urlopen` raise; fake
  `fetch`/`fetch_text` callables passed to `SecClient(cache=DiskCache(tmp_path), user_agent="t t@example.com", ...)`).
  Copy that fixture into the new test file. Exemplar:

  ```python
  def test_companyfacts_cached(tmp_path):
      calls = []

      def fake(url, ua):
          calls.append(url)
          return {"ok": 1}

      c = SecClient(cache=DiskCache(tmp_path), user_agent="t t@example.com", fetch=fake)
      assert c.companyfacts(320193) == {"ok": 1}
      assert c.companyfacts(320193) == {"ok": 1}
      assert len(calls) == 1
  ```

- Script pattern: `scripts/fetch_sec.py` (argparse, prints only, returns 1 on any failure, `SEC_USER_AGENT` errors go
  to stderr).

### What the reviewer learned from real filings (KO, PG, GIS, MO, FIZZ), which the code must handle

1. Every 10-K has a **table of contents** that repeats each "Item N. Title" heading, followed by a page number. The
   real section is the **longest** span from an "Item N" heading to the next end heading.
2. **Cross-references** such as "see Item 8 of this report" and quoted ones like `contained in “Item 8. Financial
   Statements and Supplementary Data”` must not count as headings. Two rules together fix this: a heading must
   **start a line** (after HTML-to-text conversion) **and** be followed by the item's title words.
3. Some filings (GIS) put **one word per HTML element**, so a heading can read `Item\n\n7\n\nManagement`. The heading
   regex must allow any whitespace, including newlines, between "Item", the number and the title.
4. Inline-XBRL filings start with a hidden `<ix:header>` block of machine data; drop its content.
5. `Item 1` must not match `Item 1A`, and `Item 7` must not match `Item 7A`.
6. Extracted sections are collapsed to single spaces (`re.sub(r"\s+", " ", s).strip()`), so quotes can be checked
   later with plain substring tests.

A prototype with these rules gave, in words (Item 1 / 1A / 7): KO 8021 / 13292 / 17357, PG 2010 / 5547 / 13820,
GIS 3346 / 4192 / 11150, MO 3601 / 9627 / 24210, FIZZ 3591 / 1326 / 2689. Each Item 7 ended on its real last sentence.

Conventions (CLAUDE.md): short module docstrings, one-line function docstrings, compact code; do not reformat existing
code; tests use plain `assert`, no network; lines ≤ 120 chars (ruff). Real downloaded data stays local under
`data/cache/` (gitignored); only hand-made fixtures go into `tests/fixtures/`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Setup | in your clean worktree: `git reset --hard b6bb576`; `git log --oneline -1` | `b6bb576` |
| Tests | `PYTHONPATH=$PWD/src /home/imad/maid/.venv/bin/python -m pytest -q` | 146 passed, 1 skipped before your change |
| Lint | `/home/imad/maid/.venv/bin/ruff check .` | `All checks passed!` |

If the harness refuses `PYTHONPATH=... cmd` inside a compound command, run it as a single separate command.

## Scope

In scope:
- new `src/maid/tenk.py` (pure functions, no I/O);
- `src/maid/sec.py`: one new method `SecClient.filing_html`;
- `src/maid/real_data.py`: one new function `load_filings`;
- new `scripts/fetch_filings.py`;
- new `tests/test_tenk.py`, new fixture `tests/fixtures/tenk/mini_10k.htm`;
- `tests/test_sec.py`, `tests/test_real_data.py`: add tests only;
- `docs/architecture/data.md`: one new subsection; `CLAUDE.md`: two Layout lines.

Out of scope — do not touch: `src/maid/graph.py`, `src/maid/scoring.py`, `src/maid/state.py`, `src/maid/mcdm/`,
`src/maid/xbrl.py`, `data/universe/*.csv`, `_get_text`, `plans/`. No LLM client, no prompts, no new dependencies
(stdlib `html.parser` and `re` only).

## Git workflow

Branch `feat/tenk-text`. Conventional commits (e.g. `feat(tenk): ...`, `docs(data): ...`), body `Refs #16`, each
ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push or merge.

## Steps

### Step 1: `src/maid/tenk.py` (pure)

Module docstring: `"""10-K text: HTML to plain text, Item 1 / 1A / 7 extraction, name anonymization (pure, no I/O)."""`

Implement exactly these public names:

```python
SECTIONS = {"1": ("1", ("1a", "1b", "1c", "2")), "1a": ("1a", ("1b", "1c", "2")), "7": ("7", ("7a", "8"))}
TITLES = {"1": r"business", "1a": r"risk\s+factors", "1b": r"unresolved", "1c": r"cybersecurity",
          "2": r"properties", "7": r"management", "7a": r"quantitative", "8": r"financial\s+statements"}
EXTRACTOR_VERSION = "1"  # bump when extraction rules change (cache keys and reports carry it)
```

- `html_to_text(html: str) -> str`: an `html.parser.HTMLParser` subclass (`convert_charrefs=True`) that drops the
  content of `script`, `style` and `ix:header` (nesting counter), emits `"\n"` at the start and end of the block
  tags `p, div, br, tr, li, h1..h6, table, td`, and keeps other text. After joining: replace `"\xa0"` with a space,
  collapse runs of spaces/tabs to one space, collapse blank-line runs to one blank line. Line structure must survive
  (heading detection needs it).
- `heading(item: str) -> re.Pattern`: `re.compile(rf"^[ \t]*item\s*{item}(?![0-9a-z])\s*[\.:\-—–]?\s*{TITLES[item]}", re.I | re.M)`.
- `find_section(text: str, item: str, ends: tuple[str, ...]) -> str`: for every match of `heading(item)`, find the
  earliest match of any `heading(e)` for `e` in `ends` after it; among those spans take the **longest**; return it
  collapsed with `re.sub(r"\s+", " ", span).strip()`. Return `""` if there is none.
- `extract_sections(html: str) -> dict[str, str]`: `{"1": ..., "1a": ..., "7": ...}` using `SECTIONS`.
- `name_variants(names: list[str]) -> list[str]`: for each registrant name (current and former): strip a leading
  `"The "`, strip trailing punctuation and one or more trailing legal suffixes from
  `Inc, Incorporated, Corp, Corporation, Co, Company, Ltd, Limited, plc, LLC, L.P., N.V., S.A.` (case-insensitive,
  with optional comma/period around them). Keep the variant if it has at least 4 characters. Return unique variants,
  longest first. Example: `["PROCTER & GAMBLE Co"]` → `["PROCTER & GAMBLE"]`; `["ALTRIA GROUP, INC."]` →
  `["ALTRIA GROUP"]`.
- `anonymize_text(text: str, names: list[str], ticker: str, label: str) -> tuple[str, int]`: replace every
  case-insensitive, whole-word occurrence of each variant from `name_variants(names)` (longest first), and of the
  ticker if it has at least 2 characters (case-**sensitive**, whole word), with `label`. Whole word means
  `(?<![A-Za-z0-9])...(?![A-Za-z0-9])`; escape variants with `re.escape`, and let a single space in a variant
  match any whitespace (`\s+`). Return `(new_text, number_of_replacements)`.
- `approx_tokens(text: str) -> int`: `(len(text) + 3) // 4`.

Verify: `PYTHONPATH=$PWD/src /home/imad/maid/.venv/bin/python -c "import maid.tenk"` → exit 0.

### Step 2: fixture and tests for `tenk`

Create `tests/fixtures/tenk/mini_10k.htm` (hand-written, fictional company "ACME FOODS, Inc.", ticker `ACME`) that
contains, in this order:
1. `<ix:header><div>SECRET-HIDDEN-FACT</div></ix:header>`;
2. a table of contents: `<table><tr><td>Item 1.</td><td>Business</td><td>3</td></tr>` and rows for `Item 1A.` Risk
   Factors, `Item 1B.` Unresolved Staff Comments, `Item 2.` Properties, `Item 7.` Management’s Discussion and
   Analysis, `Item 7A.` Quantitative and Qualitative Disclosures, `Item 8.` Financial Statements;
3. `<p>Item 1. Business</p><p>ACME Foods sells cereal. Acme Foods, Inc. raised prices 5% while volume held.</p>`;
4. `<p>Item 1A. Risk Factors</p><p>Input costs may rise.</p>`;
5. `<p>Item 1B. Unresolved Staff Comments</p><p>None.</p>`, `<p>Item 2. Properties</p><p>Plants in Ohio.</p>`;
6. Item 7 written **one word per span inside divs**:
   `<div><span>Item</span></div><div><span>7.</span></div><div><span>Management’s</span></div>...` then
   `<p>Our strategy is to grow ACME brands. See Item 8 of this report.</p>`
   `<p>Details are contained in “Item 8. Financial Statements and Supplementary Data”.</p>`
   `<p>We returned cash through dividends.</p>`;
7. `<p>Item 7A. Quantitative and Qualitative Disclosures</p><p>Rates.</p>`, `<p>Item 8. Financial Statements</p><p>Numbers.</p>`.

Note the quoted cross-reference in (6): with `html_to_text`, the `“Item 8` is not at the start of a line, so it
must not end Item 7. If it does end Item 7 in your implementation, re-read rule 2 and Step 1; do not loosen the test.

`tests/test_tenk.py` (copy the `no_network` fixture from `tests/test_sec.py`), at least these tests:
- `test_html_to_text_drops_hidden_header`: `"SECRET-HIDDEN-FACT" not in html_to_text(fixture)`.
- `test_extract_skips_toc_and_cross_references`: `s = extract_sections(fixture)`;
  `s["1"].startswith("Item 1. Business")`, `"raised prices 5%" in s["1"]`, `"Input costs" not in s["1"]`;
  `s["1a"].startswith("Item 1A. Risk Factors")`; `"We returned cash through dividends." in s["7"]`,
  `"Rates." not in s["7"]`, `"\n" not in s["7"]`.
- `test_item1_does_not_match_1a`: `heading("1").search("Item 1A. Risk Factors") is None`.
- `test_name_variants`: the two examples from Step 1, and `name_variants(["The Hershey Company"]) == ["Hershey"]`.
- `test_anonymize_text`: on `s["1"]` with names `["ACME FOODS, Inc."]`, ticker `"ACME"`, label `"Company 007"`:
  result contains `"Company 007 sells cereal"`, contains no `"ACME"`/`"Acme"` at all, and the count is 2.
  Also `anonymize_text("ACMEX and acme", ["ACME FOODS"], "ACME", "L")[1] == 0` (whole words only, ticker
  case-sensitive, and "ACME" alone is not a name variant).
- `test_approx_tokens`: `approx_tokens("abcd") == 1`, `approx_tokens("") == 0`.

Verify: `pytest -q tests/test_tenk.py` → all pass.

### Step 3: `SecClient.filing_html(cik, accn)`

Add to `SecClient` (after `cover`):

```python
def filing_html(self, cik, accn: str) -> str:
    """Primary document (HTML) of a filing, located via submissions (cached)."""
```

- Find `accn` in `self.submissions(cik)["filings"]["recent"]["accessionNumber"]`; if absent raise
  `ValueError(f"{accn} not in recent submissions of CIK {cik}")`.
- If the form at that index is not `"10-K"` raise `ValueError` naming the form.
- URL: `https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/{primaryDocument}`.
- Fetch with `self.fetch_text(url, self.user_agent)` inside
  `self.cache.get_or_compute(DiskCache.key("sec-doc", cik, accn), ...)` and return the string.

Tests in `tests/test_sec.py` (fake `fetch` returning a submissions dict, fake `fetch_text` counting calls):
`test_filing_html_cached` (second call does not fetch again; URL ends with the primary document name) and
`test_filing_html_unknown_accn_raises`, `test_filing_html_wrong_form_raises`.

### Step 4: `real_data.load_filings`

```python
def load_filings(decision_date: str, sector: str = "tech", client=None) -> tuple[dict, dict, dict]:
    """(label -> ticker, label -> {"1", "1a", "7"} anonymized text, label -> {accn, replacements}) for the 10-K in use."""
```

- `labels, _, meta = load_sec(decision_date, sector, client)` with a shared `client = client or SecClient()`
  (import `SecClient` inside the function, as `load_sec` does).
- For each label: `cik` from the universe row of its ticker; `html = client.filing_html(cik, meta[label]["accn"])`;
  `sections = tenk.extract_sections(html)`; `sub = client.submissions(cik)`;
  `names = [sub["name"]] + [f["name"] for f in sub.get("formerNames", [])]`; anonymize each section with
  `tenk.anonymize_text(text, names, ticker, label)`; record the summed replacement count.
- Return `(labels, texts, info)` where `info[label] = {"accn": ..., "replacements": int}`.

Test in `tests/test_real_data.py`: build a fake client object (a small class with `companyfacts`, `submissions`,
`filing_html` methods) on a 2-row universe, following how the existing tests in that file fake `companyfacts`
(read them first and reuse their fixture helpers). Check that labels match `anonymize`, that the fixture's Item 1
comes back anonymized, and that `replacements > 0`. If faking `load_sec` end to end needs more than the existing
helpers provide, monkeypatch `maid.real_data.load_sec` to return fixed `(labels, {}, meta)` instead.

### Step 5: `scripts/fetch_filings.py`

Docstring: what it does, `Usage: python scripts/fetch_filings.py [--sector tech|staples] [--date 2025-03-31]`,
"Needs SEC_USER_AGENT; downloads are cached under data/cache (local only). Prints only."

- Calls `load_filings(date, sector)`; for each label prints one row:
  `label ticker accn words_1 words_1a words_7 ~tokens_7 replacements flag`, where words = `len(text.split())`,
  `~tokens_7 = approx_tokens(texts[label]["7"])`, and `flag` is `SHORT` if Item 1 or Item 7 has fewer than 1000
  words, `EMPTY` if either is empty, else `ok`.
- Ends with a summary line: counts of ok / SHORT / EMPTY, and the max and median of `~tokens_7`.
- Returns 1 if any row is `EMPTY` or any exception occurred per company (print `label ticker ERROR ...` and
  continue), else 0. `SEC_USER_AGENT` errors print to stderr and return 1 (as in `fetch_sec.py`).

Verify: `PYTHONPATH=$PWD/src /home/imad/maid/.venv/bin/python scripts/fetch_filings.py --help` → usage text. **Do not
run it without `--help`** (it needs the network; the reviewer runs it).

### Step 6: docs

- `docs/architecture/data.md`: add a subsection `### 10-K text for the qualitative scorer (plan 029)` right before
  `## Local-only data`, 6–10 bullets: source (primary document of the same 10-K accession as the numbers), sections
  (Items 1, 1A, 7), extraction rules 1–6 above in one line each, anonymization (registrant current and former names
  minus legal suffixes, and the ticker, replaced by the label), **known limitation: brand names and short forms
  (for example "P&G") are not removed; plan 031 measures whether the model recognises companies**, local-only cache,
  and `python scripts/fetch_filings.py --sector staples` to fetch and check coverage.
- `CLAUDE.md` Layout: add `- \`src/maid/tenk.py\`: 10-K HTML -> Items 1/1A/7 text, anonymization (pure)` and
  `- \`scripts/fetch_filings.py\`: fetch and check 10-K text coverage for a universe (prints only)`, next to the
  other `src/maid` and `scripts` lines.

### Step 7: gates

Full tests pass (146 + your new tests, 1 skipped). Ruff clean. Commit.

## Done criteria

- `pytest -q` passes with at least 10 new tests; `ruff check .` clean.
- `git diff --stat b6bb576..HEAD` lists only in-scope files.
- `grep -rn "import openai\|import requests\|ollama\|deepseek" src/maid/tenk.py src/maid/real_data.py` → nothing.
- `scripts/fetch_filings.py --help` prints usage.
- The test that checks the quoted cross-reference passes without being weakened.

## STOP conditions

- The drift check shows changes.
- The extraction tests can only pass by changing the rules in Step 1 (report which rule fails and why).
- Any step seems to need a network call, a new dependency, or a change to an out-of-scope file.

## Maintenance notes

- The reviewer runs `scripts/fetch_filings.py --sector staples` after merge. Expected trouble spots: filings that
  incorporate MD&A by reference to an exhibit (Item 7 then SHORT), and unusual heading formats. Fix those in a
  follow-up with a fixture per failure and bump `EXTRACTOR_VERSION`. Never hand-edit a company's text.
- The LLM scorer (plan 030) reads these sections. Item 7 can exceed 30k tokens (MO about 24k words), which matters
  for local models with small context windows.
- Anonymization is deliberately simple. Its residual leakage is measured (plan 031), not engineered away here.
