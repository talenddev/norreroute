TASK-1: OutputRecord schema and RowError model
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: pyproject.toml with pydantic>=2.12.5 already declared. No src/ directory yet.
  What this task enables: TASK-3, TASK-4, TASK-5 all import OutputRecord and RowError.

DEPENDS ON
  none

OBJECTIVE
  Create the package skeleton plus the two core data models: OutputRecord (pydantic) and RowError (pydantic).

ACCEPTANCE CRITERIA
  - [ ] src/vendor_normalizer/__init__.py exists (may be empty)
  - [ ] src/vendor_normalizer/schema.py defines OutputRecord with fields: sku (str, min_length=1), product_name (str), quantity (int, ge=0), unit_price (Decimal, ge=0), currency (str, pattern="^[A-Z]{3}$"), delivery_date (date), vendor_id (str)
  - [ ] OutputRecord.strip_strings field_validator applies to sku, product_name, currency (mode="before", strips whitespace)
  - [ ] src/vendor_normalizer/errors.py defines RowError with fields: row_index (int), field (str | None), value (str | None), error (str), suggestion (str | None)
  - [ ] src/vendor_normalizer/sources/__init__.py exists (stub, no implementation required)
  - [ ] src/vendor_normalizer/sources/xlsx.py exists (stub)
  - [ ] src/vendor_normalizer/sources/gsheet.py exists (stub)
  - [ ] tests/__init__.py and tests/fixtures/ directory exist
  - [ ] tests/test_schema.py covers: valid OutputRecord construction, strip_strings validator, invalid sku (empty), invalid quantity (negative), invalid currency (lowercase), invalid unit_price (negative), valid RowError construction
  - [ ] uv run pytest tests/test_schema.py passes with >= 90% coverage on schema.py and errors.py

FILES TO CREATE OR MODIFY
  - src/vendor_normalizer/__init__.py       <- new
  - src/vendor_normalizer/schema.py         <- new
  - src/vendor_normalizer/errors.py         <- new
  - src/vendor_normalizer/sources/__init__.py  <- new stub
  - src/vendor_normalizer/sources/xlsx.py      <- new stub
  - src/vendor_normalizer/sources/gsheet.py    <- new stub
  - tests/__init__.py                       <- new
  - tests/fixtures/.gitkeep                 <- new
  - tests/test_schema.py                    <- new

CONSTRAINTS
  - Use uv for any new dependencies (typer, rapidfuzz, gspread not needed yet — do not add them)
  - Follow pydantic v2 patterns (model_validate, field_validator with mode="before")
  - No external HTTP calls
  - No business logic in schema.py beyond the validator

OUT OF SCOPE FOR THIS TASK
  - VendorConfig (TASK-2)
  - Any xlsx reading logic
  - CLI
  - normalize/validate/emit logic
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-1-schema-and-errors  (branch from develop)
  Commit when done:
    feat(schema): add OutputRecord and RowError pydantic models
  Open PR into: develop
