TASK-3: xlsx source loader with merged-cell unmerge
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: pyproject.toml has pandas>=3.0.2 and openpyxl>=3.1.5. TASK-1 provides the package skeleton/stubs. TASK-2 provides VendorConfig.
  What this task enables: TASK-4 (normalize) depends on a working DataFrame from load_source.

DEPENDS ON
  TASK-2

OBJECTIVE
  Implement the xlsx source loader that unmerges cells, respects header_row config, auto-detects headers when header_row is None, and returns a clean pandas DataFrame. Wire it into sources/__init__.py's load_source dispatcher.

ACCEPTANCE CRITERIA
  - [ ] src/vendor_normalizer/sources/xlsx.py implements load_xlsx(cfg: VendorConfig, path: str) -> pd.DataFrame
  - [ ] Merged cells are unmerged via openpyxl before pandas reads the file: merged ranges are split and top-left value is forward-filled across the merged area (both row-wise and column-wise)
  - [ ] When cfg.source.header_row is set, that row (0-indexed) is used as the pandas header
  - [ ] When cfg.source.header_row is None, auto-detect: find the first row with more than 3 non-null string cells and use it as the header
  - [ ] Rows above the header row are discarded
  - [ ] Blank rows (all cells NaN/None) are dropped from the resulting DataFrame
  - [ ] src/vendor_normalizer/sources/__init__.py implements load_source(cfg: VendorConfig, path: str) -> pd.DataFrame that dispatches to load_xlsx for type="xlsx" and raises NotImplementedError for type="gsheet"
  - [ ] src/vendor_normalizer/sources/gsheet.py remains a stub with load_gsheet raising NotImplementedError
  - [ ] tests/fixtures/acme_orders.xlsx exists: a small hand-crafted xlsx with >= 5 data rows, at least one merged cell in a header area, at least one blank row, matching the acme.yaml column aliases
  - [ ] tests/test_sources.py covers: happy path loads correct number of rows, merged cells are resolved correctly, blank rows are dropped, header auto-detection works on a fixture without explicit header_row, wrong path raises SourceError (a custom exception or ValueError), gsheet dispatch raises NotImplementedError
  - [ ] uv run pytest tests/test_sources.py passes with >= 90% coverage on sources/xlsx.py and sources/__init__.py

FILES TO CREATE OR MODIFY
  - src/vendor_normalizer/sources/xlsx.py       <- implement (was stub)
  - src/vendor_normalizer/sources/__init__.py   <- implement dispatcher (was stub)
  - src/vendor_normalizer/sources/gsheet.py     <- keep as NotImplementedError stub
  - tests/fixtures/acme_orders.xlsx             <- new (use openpyxl to create programmatically in a conftest or fixture-builder script)
  - tests/test_sources.py                       <- new

CONSTRAINTS
  - Use openpyxl to unmerge cells BEFORE handing off to pandas.read_excel — do NOT rely on pandas to handle merged cells
  - Use a temporary file or io.BytesIO when passing the unmerged workbook to pandas to avoid mutating the original file
  - No new pyproject.toml dependencies — openpyxl and pandas are already declared
  - If creating the xlsx fixture programmatically, place the creation logic in tests/fixtures/create_fixtures.py and also commit the resulting .xlsx so tests don't require running the creator script

OUT OF SCOPE FOR THIS TASK
  - Column alias resolution (TASK-4)
  - Any transform logic
  - gsheet real implementation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-3-xlsx-source  (branch from develop)
  Commit when done:
    feat(sources): implement xlsx loader with merged-cell unmerge and header detection
  Open PR into: develop
