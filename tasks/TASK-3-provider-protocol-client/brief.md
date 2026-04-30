TASK-3: Provider protocol + Client facade + Registry
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: src/aiproxy/types.py, streaming.py, errors.py from TASK-2.
  What this task enables: TASK-4 (Anthropic) and TASK-5 (Ollama) — they both
                          implement Provider and self-register in the registry.
                          TASK-6 uses Client to route requests.

DEPENDS ON
  TASK-2

OBJECTIVE
  Implement src/aiproxy/provider.py (Protocol), src/aiproxy/registry.py
  (register/resolve/entry-point discovery), and src/aiproxy/client.py (sync+async
  facade), exactly as specified in the architecture brief sections 3, 4, and 5.

ACCEPTANCE CRITERIA
  - [ ] src/aiproxy/provider.py: Provider is a @runtime_checkable Protocol with
        name: str, async chat(), stream() returning AsyncIterator[StreamEvent],
        async aclose()
  - [ ] src/aiproxy/registry.py: _FACTORIES dict, register(), resolve() with
        lazy entry-point discovery via importlib.metadata, KeyError on unknown
  - [ ] src/aiproxy/client.py: Client.__init__ accepts str | Provider,
        async chat(), stream() (delegates to provider), chat_sync() via
        asyncio.run, stream_sync() via new_event_loop + run_until_complete,
        async aclose()
  - [ ] Unit tests in tests/unit/test_registry.py:
        - register() then resolve() returns correct factory result
        - resolve() unknown name raises KeyError
        - register() overwrites existing name
  - [ ] Unit tests in tests/unit/test_client.py:
        - Client accepts a Provider instance directly (no registry lookup)
        - Client with str name routes through registry
        - chat_sync() returns ChatResponse from a mock provider
        - stream_sync() yields StreamEvents from a mock provider
        - aclose() calls provider.aclose()
  - [ ] Mock provider in tests must satisfy isinstance(mock, Provider) check
        (use a concrete stub class, not MagicMock, so Protocol check passes)
  - [ ] uv run pytest tests/unit/test_registry.py tests/unit/test_client.py
  - [ ] uv run ruff check src/aiproxy/provider.py src/aiproxy/registry.py src/aiproxy/client.py
  - [ ] uv run mypy src/aiproxy/provider.py src/aiproxy/registry.py src/aiproxy/client.py

FILES TO CREATE OR MODIFY
  - src/aiproxy/provider.py           <- implement
  - src/aiproxy/registry.py           <- implement
  - src/aiproxy/client.py             <- implement
  - tests/unit/test_registry.py       <- new
  - tests/unit/test_client.py         <- new

CONSTRAINTS
  - from __future__ import annotations at top of each file
  - Provider must use @runtime_checkable so isinstance() works
  - stream() on Provider returns AsyncIterator[StreamEvent], NOT an async generator
    (the protocol signature uses AsyncIterator, implementations may use async def)
  - stream_sync() must create a new event loop (not asyncio.run) — see brief section 4
  - registry._FACTORIES is module-level; tests must reset it or use a fresh import

OUT OF SCOPE FOR THIS TASK
  - Actual provider implementations (TASK-4, TASK-5)
  - Pydantic settings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-3-provider-protocol-client  (branch from develop)
  Commit when done:
    feat(core): implement Provider protocol, registry, and Client facade
  Open PR into: develop
