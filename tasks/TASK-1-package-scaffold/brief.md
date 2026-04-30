TASK-1: Package scaffold
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: pyproject.toml (name="src", minimal deps), src/__init__.py (empty),
               tests/conftest.py (generic project_root fixture).
  What this task enables: All subsequent tasks (TASK-2 through TASK-7) — they all
                          need a properly named package, working test runner, and
                          pyproject.toml with correct deps.

DEPENDS ON
  none

OBJECTIVE
  Replace the placeholder scaffold with a proper `aiproxy` package layout: rename
  the package, configure pyproject.toml with all required dependencies, create all
  stub source files, and verify the test suite runs (zero tests, exit 0).

ACCEPTANCE CRITERIA
  - [ ] pyproject.toml: name="aiproxy", version="0.1.0", requires-python=">=3.12"
  - [ ] pyproject.toml runtime deps: httpx>=0.27, anthropic>=0.28, pydantic-settings>=2.3
  - [ ] pyproject.toml dev deps: pytest>=8, pytest-asyncio>=0.23, pytest-cov>=5,
        respx>=0.21, ruff>=0.4, mypy>=1.10, anyio>=4
  - [ ] src/aiproxy/__init__.py exists (may be empty or export __version__)
  - [ ] src/aiproxy/types.py stub exists (empty or with placeholder comment)
  - [ ] src/aiproxy/streaming.py stub exists
  - [ ] src/aiproxy/provider.py stub exists
  - [ ] src/aiproxy/registry.py stub exists
  - [ ] src/aiproxy/client.py stub exists
  - [ ] src/aiproxy/errors.py stub exists
  - [ ] src/aiproxy/providers/__init__.py exists
  - [ ] src/aiproxy/providers/anthropic.py stub exists
  - [ ] src/aiproxy/providers/ollama.py stub exists
  - [ ] tests/__init__.py exists
  - [ ] tests/unit/__init__.py exists
  - [ ] tests/unit/providers/__init__.py exists
  - [ ] tests/integration/__init__.py exists
  - [ ] pyproject.toml [tool.pytest.ini_options] testpaths=["tests"], asyncio_mode="auto"
  - [ ] pyproject.toml [tool.ruff.lint.isort] known-first-party=["aiproxy"]
  - [ ] pyproject.toml [tool.mypy] has packages=["aiproxy"]
  - [ ] uv run pytest exits 0 (no collection errors even with zero tests)
  - [ ] uv run ruff check src/ exits 0
  - [ ] Old src/__init__.py (non-aiproxy) removed or replaced

FILES TO CREATE OR MODIFY
  - pyproject.toml                            <- modify
  - src/aiproxy/__init__.py                   <- new
  - src/aiproxy/types.py                      <- new (stub)
  - src/aiproxy/streaming.py                  <- new (stub)
  - src/aiproxy/provider.py                   <- new (stub)
  - src/aiproxy/registry.py                   <- new (stub)
  - src/aiproxy/client.py                     <- new (stub)
  - src/aiproxy/errors.py                     <- new (stub)
  - src/aiproxy/providers/__init__.py         <- new
  - src/aiproxy/providers/anthropic.py        <- new (stub)
  - src/aiproxy/providers/ollama.py           <- new (stub)
  - tests/__init__.py                         <- new (empty)
  - tests/unit/__init__.py                    <- new (empty)
  - tests/unit/providers/__init__.py          <- new (empty)
  - tests/integration/__init__.py             <- new (empty)
  - src/__init__.py                           <- delete (old placeholder)

CONSTRAINTS
  - Use uv for any new dependencies (uv add <pkg>)
  - Stubs must be valid Python (parseable) — no syntax errors
  - Do not implement any logic in stubs — that is TASK-2 through TASK-7
  - Preserve existing tests/conftest.py (do not delete it)
  - pyproject.toml [build-system] must keep hatchling
  - hatchling must be configured to find src/aiproxy: add [tool.hatch.build.targets.wheel] packages = ["src/aiproxy"]

OUT OF SCOPE FOR THIS TASK
  - Any actual implementation of types, providers, client, or registry
  - CI workflow changes
  - README content
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-1-package-scaffold  (branch from develop)
  Commit when done:
    feat(scaffold): initialise aiproxy package layout with stub files
  Open PR into: develop
