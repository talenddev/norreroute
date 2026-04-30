# Coding Brief — TASK-1: Package scaffold

## Branch
Create and work on: `feature/TASK-1-package-scaffold` (from `develop`)

## What to build
Reconfigure pyproject.toml for the `aiproxy` package and create the complete `src/aiproxy/`
package tree with empty module stubs. This is pure scaffolding — no logic yet.

## Full brief
See: /var/home/leo/Documents/aiproxy/tasks/TASK-1-package-scaffold/brief.md

## Key requirements

### pyproject.toml changes
- project name: "aiproxy"
- packages: src/aiproxy (hatchling src layout)
- runtime deps: `httpx>=0.27`, `pydantic-settings>=2.3`
- dev deps: pytest, pytest-cov, pytest-asyncio, respx, ruff, mypy (already present: keep them)
- pytest config: `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- ruff: target-version = "py312"
- mypy: strict = true

### Files to create
All of these must exist after this task (stubs — module docstring or `pass` only):
```
src/aiproxy/__init__.py
src/aiproxy/types.py
src/aiproxy/streaming.py
src/aiproxy/provider.py
src/aiproxy/registry.py
src/aiproxy/errors.py
src/aiproxy/client.py
src/aiproxy/providers/__init__.py
src/aiproxy/providers/anthropic.py
src/aiproxy/providers/ollama.py
```

### Verification commands
```bash
uv run python -c "import aiproxy"
uv run pytest --no-header -q   # zero tests, but must collect without errors
uv run ruff check src/
```

## Output format
End your report with this YAML block (I will parse it to update state.json):

```yaml
---
handoff:
  result: ok           # or: error
  branch: feature/TASK-1-package-scaffold
  db_models_touched: false
  files_created:
    - src/aiproxy/__init__.py
    - src/aiproxy/types.py
    - src/aiproxy/streaming.py
    - src/aiproxy/provider.py
    - src/aiproxy/registry.py
    - src/aiproxy/errors.py
    - src/aiproxy/client.py
    - src/aiproxy/providers/__init__.py
    - src/aiproxy/providers/anthropic.py
    - src/aiproxy/providers/ollama.py
  files_modified:
    - pyproject.toml
  notes: ""
---
```
