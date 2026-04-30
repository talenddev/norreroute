TASK-2: VendorConfig YAML loader and acme.yaml fixture
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: pyproject.toml with pyyaml>=6.0.3 and pydantic>=2.12.5. TASK-1 provides OutputRecord and RowError.
  What this task enables: TASK-3 (xlsx loader), TASK-4 (normalize), TASK-6 (CLI) all need VendorConfig.

DEPENDS ON
  TASK-1

OBJECTIVE
  Implement VendorConfig pydantic model that validates per-vendor YAML files at load time, plus create vendors/acme.yaml as the first vendor fixture.

ACCEPTANCE CRITERIA
  - [ ] src/vendor_normalizer/config.py defines VendorConfig as a pydantic BaseModel
  - [ ] VendorConfig.source is a nested model with fields: type (Literal["xlsx","gsheet"]), sheet_name (str | None), header_row (int | None, default None = auto-detect), unmerge (bool, default False)
  - [ ] VendorConfig.columns is dict[str, list[str]] mapping canonical field name to list of alias strings
  - [ ] VendorConfig.transforms is dict[str, dict] (transform specs per field, optional)
  - [ ] VendorConfig.drop_rows_if is list[dict] (drop-row rules, optional, default [])
  - [ ] VendorConfig.vendor_id is str
  - [ ] VendorConfig.load(path: str) classmethod reads YAML, validates with model_validate, raises ValueError with path info on failure
  - [ ] vendors/acme.yaml exists with vendor_id=acme, source.type=xlsx, sheet_name="Orders", header_row=3, unmerge=true, columns mapping all 6 canonical fields with realistic aliases, transforms for delivery_date/unit_price/currency, drop_rows_if sku is_blank
  - [ ] tests/test_config.py covers: load valid acme.yaml, missing required field raises error, unknown source type raises error, columns with empty alias list rejected or handled, load nonexistent file raises error
  - [ ] uv run pytest tests/test_config.py passes with >= 90% coverage on config.py

FILES TO CREATE OR MODIFY
  - src/vendor_normalizer/config.py    <- new
  - vendors/acme.yaml                  <- new
  - tests/test_config.py               <- new

CONSTRAINTS
  - Use PyYAML for loading (already in pyproject.toml)
  - Pydantic v2: use model_validator or field_validator as needed
  - VendorConfig.load() must raise a clear ValueError (not raw pydantic error) when YAML is structurally invalid, wrapping the underlying pydantic error message
  - Do not add new pyproject.toml dependencies unless strictly required

OUT OF SCOPE FOR THIS TASK
  - Reading xlsx files
  - Normalize/validate logic
  - A second vendor YAML (globex.yaml comes after milestone 1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-2-vendor-config  (branch from develop)
  Commit when done:
    feat(config): add VendorConfig pydantic loader and acme vendor YAML
  Open PR into: develop
