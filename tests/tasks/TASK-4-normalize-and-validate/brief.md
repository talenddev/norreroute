TASK-4: normalize.py and validate.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: OutputRecord (TASK-1), VendorConfig (TASK-2), load_source returning raw DataFrame (TASK-3).
  What this task enables: TASK-5 (emit) and TASK-6 (CLI) both consume the (valid, errors) tuple.

DEPENDS ON
  TASK-3

OBJECTIVE
  Implement normalize.py (column alias resolution, transform application, row cleanup) and validate.py (feed normalized dicts through OutputRecord, collect RowErrors).

ACCEPTANCE CRITERIA
  - [ ] src/vendor_normalizer/normalize.py implements normalize(df: pd.DataFrame, cfg: VendorConfig) -> list[dict]
  - [ ] normalize() resolves column names: for each canonical field in cfg.columns, find the first alias present in df.columns (case-insensitive match); if none found, the field is absent from the row dict (will fail validation)
  - [ ] normalize() applies transforms from cfg.transforms:
      - type=date: try each format in formats list via datetime.strptime; if all fail, leave raw string (validator will catch it)
      - type=decimal: strip the decimal_separator (comma) and any thousand separators before casting to Decimal
      - type=string with upper=true: call .upper() on the value
  - [ ] normalize() applies drop_rows_if rules: if column value is blank (None, NaN, empty string after strip), skip the row entirely (not added to output list)
  - [ ] normalize() strips whitespace from all string cells before processing
  - [ ] normalize() injects vendor_id from cfg.vendor_id into every row dict
  - [ ] Row index tracking: each row dict includes a _row_index key (1-based, counting from the raw DataFrame index + header offset) for error reporting
  - [ ] src/vendor_normalizer/validate.py implements validate(rows: list[dict], vendor_id: str) -> tuple[list[OutputRecord], list[RowError]]
  - [ ] validate() calls OutputRecord.model_validate(row) for each row; on ValidationError, creates one RowError per validation failure with row_index from _row_index, field name, raw value, and human error message
  - [ ] validate() excludes _row_index from the dict before passing to model_validate
  - [ ] tests/test_normalize.py covers: happy path with acme fixture data, missing column in DataFrame produces absent field, date transform parses both formats, decimal with comma separator, currency uppercased, drop_rows_if blank sku removes the row, whitespace stripping, vendor_id injected
  - [ ] tests/test_validate.py covers: all-valid rows produce empty errors list, missing required field produces RowError, negative quantity produces RowError, bad currency pattern produces RowError, bad date type produces RowError, mixed valid/invalid rows split correctly
  - [ ] uv run pytest tests/test_normalize.py tests/test_validate.py passes with >= 90% coverage on normalize.py and validate.py

FILES TO CREATE OR MODIFY
  - src/vendor_normalizer/normalize.py   <- new
  - src/vendor_normalizer/validate.py    <- new
  - tests/test_normalize.py             <- new
  - tests/test_validate.py              <- new

CONSTRAINTS
  - No pandas operations in validate.py — it receives list[dict] only
  - Row index must be preserved end-to-end for correct error reporting
  - Do not auto-correct bad values — only collect errors
  - Fuzzy suggestions in RowError.suggestion: leave as None in this task (TASK-5 adds fuzzy.py)
  - Use only already-declared dependencies

OUT OF SCOPE FOR THIS TASK
  - fuzzy.py column suggestions
  - emit.py (TASK-5)
  - CLI (TASK-6)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-4-normalize-and-validate  (branch from develop)
  Commit when done:
    feat(pipeline): implement normalize and validate pipeline stages
  Open PR into: develop
