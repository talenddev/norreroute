TASK-6: CLI wiring and end-to-end integration test
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: All pipeline stages complete (TASK-1 through TASK-5). typer already added to pyproject.toml.
  What this task enables: The tool is usable end-to-end from the command line.

DEPENDS ON
  TASK-5

OBJECTIVE
  Wire all pipeline stages into a typer CLI command with correct exit codes, and add an end-to-end integration test that runs the full pipeline against the real acme fixture.

ACCEPTANCE CRITERIA
  - [ ] src/vendor_normalizer/cli.py defines a typer app with a normalize command
  - [ ] normalize command accepts: vendor (str, positional), input_path (Path, positional), out_dir (Path, option, default=Path("./out")), strict (bool, option, default=False)
  - [ ] normalize command loads VendorConfig from vendors/{vendor}.yaml (path relative to cwd)
  - [ ] normalize command calls load_source, normalize, validate, emit in order
  - [ ] Exit codes: sys.exit(0) if no errors, sys.exit(1) if row errors exist, sys.exit(2) if VendorConfig raises ValueError (config error), sys.exit(3) if load_source raises (source error)
  - [ ] --strict flag: after the first RowError is found in validate output, print the error and sys.exit(1) immediately without writing output files
  - [ ] pyproject.toml [project.scripts] entry: vendor-normalizer = "vendor_normalizer.cli:app"
  - [ ] tests/test_integration.py covers an end-to-end test: run the normalize command against tests/fixtures/acme_orders.xlsx with vendor=acme, assert exit code 0 (or 1 if fixture has intentional bad rows), assert out.csv exists and has at least 1 data row, assert errors.csv exists
  - [ ] tests/test_cli.py covers: config error path returns exit code 2, missing input file returns exit code 3, all-valid input returns exit code 0, input with bad rows returns exit code 1
  - [ ] uv run pytest tests/test_cli.py tests/test_integration.py passes with >= 90% coverage on cli.py
  - [ ] uv run vendor-normalizer acme tests/fixtures/acme_orders.xlsx runs without crashing (manual smoke test reported in handoff)

FILES TO CREATE OR MODIFY
  - src/vendor_normalizer/cli.py    <- new
  - pyproject.toml                  <- add [project.scripts] entry
  - tests/test_cli.py               <- new
  - tests/test_integration.py       <- new

CONSTRAINTS
  - Use typer.testing.CliRunner for unit tests (no subprocess in test_cli.py)
  - Use subprocess or typer.testing.CliRunner for the integration test
  - vendors/ directory must exist at cwd when CLI runs — tests should create a tmp dir with a vendors/ symlink or copy, or patch the config path
  - Do not catch all exceptions with a bare except — only catch ValueError (config) and specific source exceptions

OUT OF SCOPE FOR THIS TASK
  - Google Sheets support
  - Second vendor (globex)
  - JSONL output
  - Docker / packaging
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-6-cli-wiring  (branch from develop)
  Commit when done:
    feat(cli): wire typer CLI with exit codes and end-to-end integration test
  Open PR into: develop
