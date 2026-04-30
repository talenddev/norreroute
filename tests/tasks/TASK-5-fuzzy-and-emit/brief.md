TASK-5: fuzzy.py column suggestions and emit.py output writer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: OutputRecord, RowError (TASK-1), VendorConfig (TASK-2), normalize/validate (TASK-4).
  What this task enables: TASK-6 (CLI) calls emit() as the final pipeline step.

DEPENDS ON
  TASK-4

OBJECTIVE
  Implement fuzzy.py (rapidfuzz-based column suggestions) and emit.py (CSV + error report writer). Wire fuzzy suggestions into the normalize stage's missing-column path.

ACCEPTANCE CRITERIA
  - [ ] src/vendor_normalizer/fuzzy.py implements suggest_column(canonical: str, aliases: list[str], available: list[str]) -> str | None
  - [ ] suggest_column uses rapidfuzz.process.extractOne with a score cutoff of 70 to find the best match among available columns for any of the aliases; returns the matched column name or None if no match above cutoff
  - [ ] src/vendor_normalizer/normalize.py is updated: when a canonical field's aliases are not found in df.columns, call suggest_column and if a suggestion exists, store it in a _suggestions dict keyed by canonical field name; that suggestion is passed through to validate.py so RowError.suggestion can be populated
  - [ ] src/vendor_normalizer/validate.py is updated: accept an optional suggestions: dict[str, str] parameter (or store it in each row dict under _suggestions) and populate RowError.suggestion when a fuzzy hint is available for the missing field
  - [ ] src/vendor_normalizer/emit.py implements emit(records: list[OutputRecord], errors: list[RowError], out_dir: Path) -> None
  - [ ] emit() creates out_dir if it does not exist
  - [ ] emit() writes out_dir/out.csv with all OutputRecord fields as columns, one row per record
  - [ ] emit() writes out_dir/errors.csv with all RowError fields as columns; if errors is empty, writes the file with header only (no data rows)
  - [ ] emit() returns None; it does not raise on empty records (valid output is an empty out.csv with header)
  - [ ] rapidfuzz added to pyproject.toml dependencies via uv add rapidfuzz
  - [ ] typer added to pyproject.toml dependencies via uv add typer (CLI dependency, needed in TASK-6 but add here to avoid a later separate dep step)
  - [ ] tests/test_fuzzy.py covers: exact match returns column, fuzzy match above cutoff returns best candidate, no match returns None, empty available list returns None
  - [ ] tests/test_emit.py covers: creates out_dir if missing, out.csv has correct headers and row count, errors.csv has correct headers (present even with 0 errors), both files written on mixed valid/error input
  - [ ] uv run pytest tests/test_fuzzy.py tests/test_emit.py passes with >= 90% coverage on fuzzy.py and emit.py

FILES TO CREATE OR MODIFY
  - src/vendor_normalizer/fuzzy.py        <- new
  - src/vendor_normalizer/emit.py         <- new
  - src/vendor_normalizer/normalize.py    <- update (add fuzzy suggestion path)
  - src/vendor_normalizer/validate.py     <- update (populate suggestion in RowError)
  - tests/test_fuzzy.py                   <- new
  - tests/test_emit.py                    <- new
  - pyproject.toml                        <- add rapidfuzz, typer

CONSTRAINTS
  - Use uv add rapidfuzz and uv add typer to add dependencies
  - Fuzzy suggestions are advisory only — never auto-rename columns
  - emit.py must use csv.DictWriter or pandas to_csv, not raw string formatting
  - Do not delete out_dir if it already exists

OUT OF SCOPE FOR THIS TASK
  - JSONL output (out.jsonl) — mentioned in architecture but not in milestone 1 acceptance criteria
  - CLI (TASK-6)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-5-fuzzy-and-emit  (branch from develop)
  Commit when done:
    feat(emit): add fuzzy column suggestions and CSV output writer
  Open PR into: develop
