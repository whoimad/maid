# Plan 030: 10-K text v2: Clorox-style headings, MD&A by reference, stronger anonymization, per-criterion inputs

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. The reviewer maintains `plans/README.md`; do not edit it.
>
> **Drift check (run first)**: `git diff --stat 20a063a..HEAD -- src/maid/tenk.py src/maid/sec.py src/maid/real_data.py scripts/fetch_filings.py tests/test_tenk.py tests/test_sec.py tests/test_real_data.py docs/architecture/data.md`
> → no output expected.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (pure functions plus one additive client method; offline tests)
- **Depends on**: plan 029 (DONE, merged `20a063a`)
- **Category**: direction
- **Planned at**: commit `20a063a` on branch `integration/prototype`, 2026-11-03

## Why this matters

MAID will have an LLM score three qualitative criteria (pricing power, strategy clarity, capital allocation) for 61
anonymized consumer-staples companies, from each company's 10-K as of 2025-03-31. **LLMs never rank; they only score,
quoting evidence.** Plan 029 built the text pipeline (`src/maid/tenk.py`). The reviewer then fetched all 61 real
filings and found four problems that this plan fixes:

1. **Headings written "Item 1.A." / "Item 7.A."** (Clorox) are not recognised, so Clorox's Item 1 swallowed the whole
   document and Item 1A is empty.
2. **MD&A incorporated by reference.** Clorox's Item 7 is one sentence ("This information appears under ..."); the real
   MD&A (13,294 words) is in a second document of the same filing, `clx-20240630_d2.htm`.
3. **Weak anonymization.** SEC registrant names don't match how companies write about themselves. Surviving mentions of
   the company's own name in its anonymized text: Clorox 50, Celsius 37, Pilgrim's 34, Smucker 32, Estée Lauder 29,
   Hormel 28, McCormick 20, Church & Dwight 18, P&G/Procter 14, Albertsons 7. Causes, with the SEC name: state tags
   (`CLOROX CO /DE/`, `HORMEL FOODS CORP /DE/`, `CHURCH & DWIGHT CO INC /DE/`), a dangling `&` (`MCCORMICK & CO INC` →
   `MCCORMICK &`), accents (`ESTEE` vs "Estée"), apostrophes (`PILGRIMS PRIDE` vs "Pilgrim's"), initials with periods
   (`J M SMUCKER` vs "J.M. Smucker"), and generic trailing words (`Celsius Holdings`, `Albertsons Companies`, but the
   text says "Celsius", "Albertsons").
4. **Length.** Median MD&A is ~15.5k tokens, but 16 of 61 exceed 24k (max ~64k). The owner's laptop GPU runs a local
   model with a 32k-token context, and both the local model and DeepSeek must get the **same** text so their scores
   can be compared. Each criterion therefore reads a focused, budgeted slice, cut by a fixed rule and logged.

The reviewer measured the slice rule on the real filings: splitting Item 7 at its "Liquidity and Capital Resources"
heading (first match after 20% of the section) gives an operations part (median 7.6k tokens, max 22k) and a liquidity
part (median 7.7k, max 50k); Item 1 has median 9.3k, max 21k. With a 24k-token budget only one slice is cut. Seven
companies (ACI, CLX, DAR, FLO, KO, PG, PM) have no matching liquidity heading and need the fallback in Step 5.

## Current state

`src/maid/tenk.py` (from plan 029), relevant parts:

```python
SECTIONS = {"1": ("1", ("1a", "1b", "1c", "2")), "1a": ("1a", ("1b", "1c", "2")), "7": ("7", ("7a", "8"))}
TITLES = {"1": r"business", "1a": r"risk\s+factors", "1b": r"unresolved", "1c": r"cybersecurity",
          "2": r"properties", "7": r"management", "7a": r"quantitative", "8": r"financial\s+statements"}
EXTRACTOR_VERSION = "1"  # bump when extraction rules change (cache keys and reports carry it)
SUFFIXES = r"(?:inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|l\.p|n\.v|s\.a)"

def heading(item: str) -> re.Pattern:
    """Pattern for a line-initial "Item N. Title" heading."""
    return re.compile(rf"^[ \t]*item\s*{item}(?![0-9a-z])\s*[\.:\-—–]?\s*{TITLES[item]}", re.I | re.M)

def find_section(text: str, item: str, ends: tuple[str, ...]) -> str:
    """Longest span from an Item heading to the next end heading (skips the table of contents)."""

def extract_sections(html: str) -> dict[str, str]:
def name_variants(names: list[str]) -> list[str]:
    """Registrant names without leading "The" and trailing legal suffixes, unique, longest first."""
def anonymize_text(text: str, names: list[str], ticker: str, label: str) -> tuple[str, int]:
    """Replace whole-word registrant names (case-insensitive) and the ticker (case-sensitive) with label."""
    count = 0
    guard = r"(?<![A-Za-z0-9]){}(?![A-Za-z0-9])"
    sep = r"[\s\-‐‑–]+"
    pats = [re.compile(guard.format(sep.join(map(re.escape, re.split(sep, v)))), re.I) for v in name_variants(names)]
    ...
def approx_tokens(text: str) -> int:
```

`src/maid/real_data.py` (from plan 029):

```python
def company_filing(client, cik, accn: str, ticker: str, label: str) -> tuple[dict, int]:
    """({"1", "1a", "7"} anonymized text, replacement count) for one company's 10-K."""
    from maid import tenk

    sections = tenk.extract_sections(client.filing_html(cik, accn))
    sub = client.submissions(cik)
    names = [sub["name"]] + [f["name"] for f in sub.get("formerNames", [])]
    out, total = {}, 0
    for k, text in sections.items():
        out[k], n = tenk.anonymize_text(text, names, ticker, label)
        total += n
    return out, total

def load_filings(decision_date: str, sector: str = "tech", client=None) -> tuple[dict, dict, dict]:
    ...  # calls company_filing per label; info[label] = {"accn": accn, "replacements": n}
```

`src/maid/sec.py`: `SecClient.filing_html(cik, accn)` (primary document, cached under key `("sec-doc", cik, accn)`);
`SecClient.cover(cik, accn)` shows how to read the filing index:
`self.fetch(f"{base}/index.json", self.user_agent)["directory"]["item"]` → list of `{"name": ..., "size": ...}`, where
`base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}"`.

`scripts/fetch_filings.py` prints per company `label ticker accn words_1 words_1a words_7 ~tokens_7 replacements flag`
and a summary; it calls `load_sec` then `company_filing` per company inside try/except.

Tests: `tests/test_tenk.py` (uses `tests/fixtures/tenk/mini_10k.htm`, fictional "ACME FOODS, Inc."),
`tests/test_sec.py` (fake `fetch`/`fetch_text` callables, `DiskCache(tmp_path)`), `tests/test_real_data.py`. All
tests are offline (an autouse fixture makes `urllib.request.urlopen` raise).

Conventions (CLAUDE.md): short module docstrings, one-line function docstrings, compact code, do not reformat existing
code, plain `assert`, no network in tests, lines ≤ 120 chars. Only `data/universe/*.csv` is committed among data files.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Setup | in your clean worktree: `git reset --hard 20a063a`; `git log --oneline -1` | `20a063a` |
| Tests | `PYTHONPATH=<worktree>/src /home/imad/maid/.venv/bin/python -m pytest -q` (run alone, not in a `&&` chain) | 158 passed, 1 skipped before your change |
| Lint | `/home/imad/maid/.venv/bin/ruff check .` | `All checks passed!` |

## Scope

In scope: `src/maid/tenk.py`, `src/maid/sec.py` (one new method), `src/maid/real_data.py` (`company_filing`,
`load_filings`), `scripts/fetch_filings.py`, new `data/universe/aliases.csv`, `tests/test_tenk.py`,
`tests/test_sec.py`, `tests/test_real_data.py`, new fixtures under `tests/fixtures/tenk/`, `docs/architecture/data.md`
(the "10-K text for the qualitative scorer" subsection only).

Out of scope: `graph.py`, `scoring.py`, `state.py`, `mcdm/`, `xbrl.py`, other `data/universe/*.csv`, `plans/`. No LLM
client, no prompts, no new dependencies, no network.

## Git workflow

Branch `feat/tenk-text-v2`. Conventional commits, body `Refs #16`, trailer
`Co-Authored-By: <your model name> <noreply@anthropic.com>`. Do not push or merge.

## Steps

### Step 1: dotted sub-item headings

In `tenk.py`, items `"1a" "1b" "1c" "7a"` must also match `1.A`, `1. A`, `7.A`. Add a helper
`_num(item)` that returns `re.escape(item)` for plain numbers and `rf"{item[:-1]}\.?\s*{item[-1]}"` when the item ends
in a letter; use it in `heading()` in place of `{item}`. `heading("1")` must still not match "Item 1.A. Risk Factors"
(the title check does this) nor "Item 1A".

Tests (`tests/test_tenk.py`): `heading("1a").search("Item 1.A. Risk Factors")`, `heading("1a").search("ITEM 1. A RISK
FACTORS")` and `heading("7a").search("Item 7.A. Quantitative and Qualitative")` all match;
`heading("1").search("Item 1.A. Risk Factors") is None`.

### Step 2: MD&A by reference

`tenk.py`: add

```python
MDNA_HEAD = re.compile(r"^[ \t]*management[’']s\s+discussion\s+and\s+analysis\s+of\s+financial\s+condition", re.I | re.M)
MDNA_END = re.compile(r"^[ \t]*(?:report\s+of\s+independent\s+registered|consolidated\s+statements?\s+of\s+"
                      r"(?:earnings|income|operations))", re.I | re.M)
MIN_WORDS = 1000

def find_mdna(html: str) -> str:
    """MD&A from a document that is not a 10-K body (e.g. an annual-report exhibit): longest span head -> end."""
```

Same longest-span logic as `find_section`, on `html_to_text(html)`, whitespace collapsed. The reviewer checked this on
Clorox's `clx-20240630_d2.htm`: 13,294 words.

`sec.py`: add `SecClient.filing_documents(cik, accn) -> list[dict]` returning `{"name": str, "size": int}` for the `.htm` items in the filing index (size `0` when missing or not a number)
(cached under `DiskCache.key("sec-index", cik, accn)`), and `SecClient.document_html(cik, accn, name) -> str` (cached
under `DiskCache.key("sec-doc", cik, accn, name)`). Tests with fakes, as for `filing_html`.

`real_data.company_filing`: if Item 7 has fewer than `tenk.MIN_WORDS` words, try the other documents of the filing:
`.htm` names, excluding the primary document and names matching `^R\d+\.htm$`, sorted by size descending, at most
3 documents (the primary document name comes from `submissions`, as in `filing_html`); take the first whose
`find_mdna` has at least `MIN_WORDS` words and use it as Item 7. Record the source:
`"body"` or `"exhibit:<name>"`. If none qualifies, keep the short Item 7 and source `"body"`.
`company_filing` now returns `(sections, info)` where `info = {"replacements": int, "mdna_source": str,
"residual": int}` (residual: Step 4). Update `load_filings` to merge `info` with `{"accn": ...}`.

Test (`tests/test_real_data.py`): a fake client whose primary document is a new fixture
`tests/fixtures/tenk/byref_10k.htm` (fictional "BLEACHCO CO /DE/", headings "Item 1.", "Item 1.A.", "Item 1.B.",
"Item 2.", "Item 7." with the single sentence "This information appears under Management's Discussion and Analysis in
Exhibit 99.1.", "Item 7.A.", "Item 8.") and whose second document `byref_d2.htm` contains an MD&A heading followed by
at least 1000 words (generate them in the fixture file with a repeated sentence such as "Net sales grew because
prices rose." ×200), then "Report of Independent Registered Public Accounting Firm". Assert `mdna_source ==
"exhibit:byref_d2.htm"`, Item 7 has ≥ 1000 words, and Item 1A is non-empty.

### Step 3: stronger name variants

Rewrite `name_variants(names, aliases=())`. For each registrant name:
1. strip a leading "The ";
2. remove state tags `/[A-Z]{2,}/` anywhere (e.g. `/DE/`);
3. repeatedly strip trailing legal suffixes (existing `SUFFIXES`) and trailing punctuation **and a trailing `&`**;
4. keep the result if ≥ 4 characters (**full variant**);
5. **core variant**: from the full variant, repeatedly drop a trailing generic word from
   `GENERIC = {"companies", "company", "holdings", "holding", "group", "foods", "food", "brands", "international",
   "corporation", "inc", "co", "products", "beverages", "beverage", "industries", "enterprises"}`; keep it if it
   differs from the full variant and is ≥ 4 characters.
Then add every alias. Unique, longest first.

Expected (assert in tests): `CLOROX CO /DE/` → contains `CLOROX`; `MCCORMICK & CO INC` → `MCCORMICK`;
`CHURCH & DWIGHT CO INC /DE/` → `CHURCH & DWIGHT`; `HORMEL FOODS CORP /DE/` → `HORMEL FOODS` and `HORMEL`;
`Celsius Holdings, Inc.` → `Celsius Holdings` and `Celsius`; `Albertsons Companies, Inc.` → `Albertsons`;
`J&J SNACK FOODS CORP` → `J&J SNACK FOODS` and `J&J SNACK`.

### Step 4: tolerant matching, aliases, residual count

`anonymize_text(text, names, ticker, label, aliases=())`:
- separators between words of a variant: `[\s\-‐‑–.]+` (adds the period, so `J M SMUCKER` matches "J.M. Smucker");
- inside a word: a final `s` may be preceded by an optional apostrophe (`['’]?s`), so `PILGRIMS` matches "Pilgrim's"
  and "Pilgrim’s";
- vowels and `c`/`n` match their accented forms: `e→[eéèêë] a→[aáàâä] o→[oóòôö] i→[iíìîï] u→[uúùûü] c→[cç] n→[nñ]`
  (so `ESTEE LAUDER` matches "Estée Lauder");
- `&` matches `&` or `and` with optional spaces (`\s*(?:&|and)\s*`);
- whole-word guards, case-insensitive, longest variant first: unchanged.

`residual_mentions(text, names, aliases=()) -> int`: the number of case-insensitive whole-word occurrences, in the
**anonymized** text, of every word of ≥ 4 letters taken from the full variants and aliases that is not in `GENERIC`
and not in `{"general", "national", "american", "united", "pride", "snack", "dwight", "church"}`. Apply the same
accent/apostrophe tolerance. Used only for reporting.

Aliases: create `data/universe/aliases.csv` with header `ticker,alias` and exactly these rows (reviewer-chosen
short forms the rules cannot derive):

```
ticker,alias
PG,P&G
PG,Procter & Gamble
SJM,Smucker
EL,Estée Lauder
KO,Coca-Cola
```

`real_data`: `read_aliases(path=Path("data/universe/aliases.csv")) -> dict[str, list[str]]`; `company_filing` passes
the company's aliases to `anonymize_text` and fills `info["residual"] = residual_mentions(<all three sections
joined>, names, aliases)`.

Tests: each failure case from "Why this matters" as one assertion on a short sentence: "The Clorox Company",
"Pilgrim’s Pride", "The J.M. Smucker Company", "Estée Lauder", "McCormick & Company", "Church and Dwight",
"Celsius", "Albertsons" → all replaced (no original name left); `residual_mentions` is 0 after anonymization and > 0
before it for "Hormel Foods sells Hormel chili" with names `["HORMEL FOODS CORP /DE/"]`.

### Step 5: per-criterion text

```python
CRITERIA_TEXT = {"strategy_clarity": "1", "pricing_power": "7_ops", "capital_allocation": "7_liq"}
BUDGET_TOKENS = 24000
LIQ_HEAD = re.compile(r"liquidity\s+and\s+(?:capital\s+resources|financial\s+condition)|liquidity,\s+capital\s+"
                      r"resources|financial\s+(?:condition|position)\s+and\s+liquidity|capital\s+resources\s+and\s+"
                      r"liquidity|liquidity\s+and\s+capital", re.I)

def split_mdna(mdna: str) -> tuple[str, str, bool]:
    """(operations part, liquidity part, split found): split at the first liquidity heading after 20% of the text."""

def clip(text: str, budget: int = BUDGET_TOKENS, tail: bool = False) -> tuple[str, bool]:
    """Keep at most budget tokens (approx_tokens), cut at a sentence boundary; tail=True keeps the end."""

def criterion_text(sections: dict, criterion: str, budget: int = BUDGET_TOKENS) -> dict:
    """{"text", "source", "truncated", "split_found", "tokens"} for one criterion (same input for every model)."""
```

- `split_mdna`: first `LIQ_HEAD` match whose start is > 20% of `len(mdna)`; if found, ops = before, liq = from the
  match; else ops = liq = the whole MD&A and `split_found = False`.
- `clip`: if `approx_tokens(text) <= budget` return `(text, False)`. Otherwise keep `budget * 4` characters (from the
  start, or from the end when `tail=True`) and cut back to the nearest sentence boundary (`". "`) inside the kept part
  (start after it when `tail=True`); return `(clipped, True)`.
- `criterion_text`: `strategy_clarity` → `clip(sections["1"])`; `pricing_power` → `clip(ops)`;
  `capital_allocation` → `clip(liq)`, but with `tail=True` **when `split_found` is False** (in long MD&As without a
  liquidity heading, the liquidity discussion is near the end). `source` is `"1"`, `"7_ops"` or `"7_liq"`
  (`"7_tail"` in that fallback).

Tests: a synthetic MD&A with a liquidity heading at 50% splits there; one with the heading only in the first 10%
(a table of contents) does not split there; `clip` of a 30k-token text returns ≤ 24k tokens, ends with "." and is
flagged; a short text is unchanged and not flagged; `tail=True` keeps the last sentence.

### Step 6: script and version

- `EXTRACTOR_VERSION = "2"`.
- `scripts/fetch_filings.py` row: `label ticker accn words_1 words_1a words_7 mdna_source replacements residual
  tok_strategy tok_pricing tok_capital split truncated flag` where `tok_*` come from `criterion_text`, `split` is
  `y`/`n`, `truncated` lists the criteria that were clipped (or `-`). Summary line adds: count of exhibit MD&As,
  count without split, count truncated, max residual, and `extractor=2 budget=24000`.

### Step 7: docs

Update the "10-K text for the qualitative scorer" subsection in `docs/architecture/data.md`: dotted headings, MD&A by
reference (exhibit rule), anonymization v2 (state tags, `&`, accents, apostrophes, initials, core names, the
committed alias list with its five rows and why), the residual count, and the per-criterion slices with the 24k
budget and the fallback, stating that every model receives the same slice. Keep the existing known-limitation
bullet about brand names.

### Step 8: gates

Full tests pass, ruff clean, commit(s).

## Done criteria

- `pytest -q`: all pass, at least 15 new tests; `ruff check .` clean.
- `git diff --stat 20a063a..HEAD` lists only in-scope files.
- `scripts/fetch_filings.py --help` works (do not run it without `--help`).
- `grep -c . data/universe/aliases.csv` → `6`.

## STOP conditions

- Drift check shows changes.
- A Step 3 or Step 4 expected result cannot be met without changing the rules as written: report the case.
- Anything needs network access, a new dependency, or an out-of-scope file.

## Maintenance notes

- After merge the reviewer runs `python scripts/fetch_filings.py --sector staples` on the real filings and checks
  residual counts; aliases may be added for leftovers (data change + a line in `data.md`, never per-company code).
- `criterion_text` defines what the scorer (next plan) sees. Changing the budget or the split changes every score:
  bump `EXTRACTOR_VERSION` and include it in the scorer's cache key.
- Brand names that are not the company name (Tide, Sprite) remain; the leakage probes measure recognition.

## Revision 1 (2026-11-03, reviewer, after the real fetch at `030c82d`)

The real run (`fetch_filings.py --sector staples` on branch `feat/tenk-text-v2` at `030c82d`) passed the coverage checks: 61 ok, CLX
MD&A from `exhibit:clx-20240630_d2.htm`, 3 without split, 3 truncated. Anonymization had three problems. Fix them on top of
`030c82d`, on the same branch name `feat/tenk-text-v2`, and change only these files: `src/maid/tenk.py`, `tests/test_tenk.py`,
`data/universe/aliases.csv`, `docs/architecture/data.md`.

**R1. Core variants that are common English words.** The real run made `Post` (Post Holdings), `CORN` (former name
Corn Products International) and `NATIONAL` (National Beverage) into core variants, so "post-retirement", "corn" and
"national" were replaced by the label. A length rule cannot catch `NATIONAL`, so use a stop-list. In `src/maid/tenk.py`,
add this constant next to `GENERIC`:

```python
COMMON_CORES = {"post", "corn", "national", "general", "united", "american", "global", "first", "best"}
```

Then in `_core`, return `""` when `core.lower() in COMMON_CORES`. The current function is:

```python
def _core(full: str) -> str:
    """Full variant minus trailing generic words ("" when nothing is dropped or the result is too short)."""
    words = full.split()
    while len(words) > 1 and words[-1].lower().strip(",.") in GENERIC:
        words.pop()
    core = " ".join(words)
    return core if core != full and len(core) >= 4 else ""
```

Change only the final `return` line to:
`return core if core != full and len(core) >= 4 and core.lower() not in COMMON_CORES else ""`. Also update the
docstring to `("" when nothing is dropped, the result is too short or a common word)`.

**R2. Dotless `SA` / `NV` suffixes, and "Global".** `Bunge Global SA` kept `SA`, so no core variant was made and "Bunge"
was left 193 times. In `SUFFIXES`, replace `n\.v|s\.a` with `n\.?v|s\.?a` (nothing else in that regex changes). Add
`"global"` to `GENERIC`. The variants for `Bunge Global SA` then become `["Bunge Global", "Bunge"]`.

**R3. Aliases for distinctive leftovers** (a data change, as the maintenance note allows). Append these rows to
`data/universe/aliases.csv`, in this order, after the existing five:

```
SFM,Sprouts
KDP,Keurig
PPC,Pilgrims
CL,Colgate
IMKTA,Ingles
EL,Lauder
EPC,Edgewell
WMK,Weis
TAP,Coors
TAP,Molson
CPB,Campbell
KHC,Kraft
KHC,Heinz
TR,Tootsie
MNST,Hansen
```

(`Pilgrims` without an apostrophe on purpose: the matcher already lets a final `s` take an optional `'` or `’`.)
Deliberately **not** aliased: COKE's "Coca-Cola" (it names the franchisor, The Coca-Cola Company, which is a different
entity; replacing it would merge the two) and BF-B's "Brown" (a family name and a common word). Both stay as known
recognition cues for the leakage probes.

**Tests (add to `tests/test_tenk.py`, in the style of `test_name_variants_v2`; do not change existing assertions):**
- `name_variants(["Post Holdings, Inc."]) == ["Post Holdings"]`
- `name_variants(["CORN PRODUCTS INTERNATIONAL INC"]) == ["CORN PRODUCTS INTERNATIONAL"]`
- `name_variants(["NATIONAL BEVERAGE CORP"]) == ["NATIONAL BEVERAGE"]`
- `name_variants(["Bunge Global SA"]) == ["Bunge Global", "Bunge"]`
- `anonymize_text("Post Holdings funds post-retirement plans.", ["Post Holdings, Inc."], "POST", "Company 045")[0] == "Company 045 funds post-retirement plans."`
- `anonymize_text("Bunge sells grain.", ["Bunge Global SA"], "BG", "Company 004")[0] == "Company 004 sells grain."`
- an alias with the apostrophe rule: `anonymize_text("Pilgrim’s chicken", ["PILGRIMS PRIDE CORP"], "PPC", "Company 046", aliases=["Pilgrims"])[0] == "Company 046 chicken"`

**Docs:** in `docs/architecture/data.md`, replace the aliases bullet (currently it says "five rows: P&G, Procter & Gamble,
Smucker, Estée Lauder, Coca-Cola") so it says there are 20 rows: the five short forms plus 15 distinctive single words
found by the residual count on the real fetch (2026-11-03). Name COKE's "Coca-Cola" and BF-B's "Brown" as deliberately
not aliased, with the reason above. Add one sentence: core variants that are common words (`COMMON_CORES`) are never
used, because they would replace ordinary text.

**Done criteria (revision):**
- `pytest -q` all pass (at least 7 more tests than at `030c82d`: 182 passed then); `ruff check .` clean.
- `grep -c . data/universe/aliases.csv` → `21`.
- `git diff --stat 030c82d..HEAD` lists only the four files above.
- Do not run `fetch_filings.py` (network); the reviewer re-runs it.

**STOP** if any existing test fails after R1/R2 for a reason other than an expected-variant list that now legitimately
contains a new entry. Report it; do not edit the old assertion.

**Revision 1 amendment (reviewer):** `tests/test_real_data.py::test_read_aliases_real_file` pins the old alias file.
It is in scope for this revision: change its assertion to
`a["PG"] == ["P&G", "Procter & Gamble"] and a["EL"] == ["Estée Lauder", "Lauder"] and len(a) == 16`.
