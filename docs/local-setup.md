# Local Setup

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) or `pyenv install 3.12` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | 24+ | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| Git | any | system package manager |

## Clone and Install

```bash
git clone <repo-url>
cd aiproxy

# Install all dependencies including dev tools
uv sync
```

`uv sync` reads `pyproject.toml` and installs into a local `.venv`. All subsequent commands use `uv run` to execute inside that environment.

## Run Tests

```bash
# All tests (unit only — no live services needed)
uv run pytest

# With coverage report (enabled by default via pyproject.toml addopts)
uv run pytest --cov=src --cov-report=term-missing

# Unit tests only
uv run pytest tests/unit/

# A specific test file
uv run pytest tests/unit/providers/test_anthropic.py

# A specific test by name
uv run pytest -k "test_chat_returns_text_response"

# Stop on first failure
uv run pytest -x
```

The test suite uses `pytest-asyncio` with `asyncio_mode = "auto"`, so async test functions run without any additional decorator.

Unit tests mock all HTTP calls — no network access or API keys are needed.

## Lint

```bash
uv run ruff check src/
uv run ruff check tests/
```

Fix auto-fixable issues:

```bash
uv run ruff check --fix src/
```

## Type Check

```bash
uv run mypy src/
```

mypy runs in strict mode (`strict = true` in `pyproject.toml`). All public functions must have type annotations.

## Run Ollama Integration Tests

Integration tests require a running Ollama instance and are kept separate from unit tests. They are not run by default in CI.

**Start Ollama with Docker:**

```bash
docker run -d \
  --name ollama \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama

# Pull a model (llama3 used in integration tests)
docker exec ollama ollama pull llama3

# Verify Ollama is ready
curl http://localhost:11434/api/tags
```

**Run integration tests:**

```bash
uv run pytest tests/integration/ -v
```

Integration tests are in `tests/integration/` and hit the real Ollama API at `http://localhost:11434`.

## Project Structure

```
aiproxy/
├── pyproject.toml            # project metadata, dependencies, tool config
├── uv.lock                   # locked dependency tree
├── README.md
├── docs/
│   ├── api-reference.md
│   ├── providers.md
│   ├── local-setup.md        # this file
│   └── archive/              # immutable design documents
└── src/aiproxy/
    ├── __init__.py           # public surface: Client, __version__
    ├── client.py             # Client facade (sync + async)
    ├── provider.py           # Provider protocol definition
    ├── registry.py           # name → factory mapping
    ├── types.py              # ChatRequest, ChatResponse, Message, etc.
    ├── streaming.py          # StreamEvent types
    ├── errors.py             # exception hierarchy
    └── providers/
        ├── __init__.py
        ├── anthropic.py      # AnthropicProvider + AnthropicSettings
        └── ollama.py         # OllamaProvider + OllamaSettings
tests/
├── conftest.py
├── unit/
│   ├── providers/
│   │   ├── test_anthropic.py   # SDK mocked with pytest-mock
│   │   └── test_ollama.py      # HTTP mocked with respx
│   ├── test_client.py
│   ├── test_errors.py
│   ├── test_registry.py
│   └── test_types.py
└── integration/
    └── test_ollama_live.py     # requires live Ollama
```

## Adding a Dependency

Runtime dependency:

```bash
uv add httpx
```

Dev-only dependency:

```bash
uv add --dev pytest-something
```

Commit both `pyproject.toml` and `uv.lock`.

## Common Issues

**`ModuleNotFoundError: No module named 'aiproxy'`**

Run commands via `uv run` rather than the system Python:

```bash
uv run pytest   # correct
pytest          # may fail if venv not activated
```

**`ANTHROPIC_API_KEY` validation error in tests**

Unit tests patch the env var via `pytest-mock`. If you see a `pydantic_settings.SecretsSettingsSource` error, ensure you are using the `provider` fixture defined in `tests/unit/providers/test_anthropic.py` rather than constructing `AnthropicProvider` directly.

**Ollama `connection refused` on port 11434**

The Ollama container is not running or not ready:

```bash
docker ps | grep ollama
docker logs ollama
```

**Port 11434 already in use**

```bash
lsof -ti:11434 | xargs kill -9
```

**mypy errors after adding a new provider**

Ensure `async def _stream_impl` returns `AsyncIterator[StreamEvent]` and `stream` returns the same type. The `Provider` protocol requires `stream` to return `AsyncIterator[StreamEvent]`, not `AsyncGenerator`.
