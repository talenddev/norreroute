TASK-3: Provider protocol, registry, errors, and Client facade
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: src/aiproxy/provider.py, registry.py, errors.py, client.py as empty stubs.
    aiproxy/types.py and aiproxy/streaming.py are fully implemented (TASK-2).
  What this task enables: TASK-4 and TASK-5 provider implementations, TASK-6 integration.

DEPENDS ON
  TASK-2

OBJECTIVE
  Implement the Provider Protocol, ProviderRegistry, error taxonomy, and Client facade
  exactly as specified in the architecture brief, with full unit tests using a mock provider.

ACCEPTANCE CRITERIA
  - [ ] provider.py: Provider is a @runtime_checkable Protocol with attributes:
        name: str, async chat(...), stream(...) returning AsyncIterator[StreamEvent], async aclose()
  - [ ] registry.py: register(name, factory), resolve(name, **kwargs), _load_entry_points()
        resolving from importlib.metadata entry_points(group="aiproxy.providers")
  - [ ] registry.py: resolve raises KeyError with message listing known providers when name unknown
  - [ ] errors.py: defines AIProxyError, ConfigurationError, ProviderError (with provider/status/raw kwargs),
        RateLimitError, AuthenticationError, TimeoutError_ (note trailing underscore), ToolArgumentError
  - [ ] client.py: Client.__init__ accepts str | Provider; if str calls resolve(); if Provider uses directly
  - [ ] Client.chat (async) delegates to provider.chat
  - [ ] Client.stream (async iterator) delegates to provider.stream
  - [ ] Client.chat_sync uses asyncio.run to call provider.chat
  - [ ] Client.stream_sync uses asyncio.new_event_loop and yields StreamEvents synchronously
  - [ ] Client.aclose delegates to provider.aclose
  - [ ] tests/unit/test_registry.py: register + resolve roundtrip, unknown name raises KeyError
  - [ ] tests/unit/test_client.py: using a MockProvider (in-test stub), tests chat, stream,
        chat_sync, stream_sync, aclose all delegate correctly
  - [ ] tests/unit/test_errors.py: constructs each error type, verifies inheritance chain
  - [ ] `uv run pytest tests/unit/test_registry.py tests/unit/test_client.py tests/unit/test_errors.py -v` exits 0
  - [ ] `uv run mypy src/aiproxy/provider.py src/aiproxy/registry.py src/aiproxy/errors.py src/aiproxy/client.py` exits 0
  - [ ] Coverage >= 90% on all four files

FILES TO CREATE OR MODIFY
  - src/aiproxy/provider.py                 ← implement
  - src/aiproxy/registry.py                 ← implement
  - src/aiproxy/errors.py                   ← implement
  - src/aiproxy/client.py                   ← implement
  - tests/unit/test_registry.py             ← new
  - tests/unit/test_client.py               ← new
  - tests/unit/test_errors.py               ← new

CONSTRAINTS
  - Use `from __future__ import annotations` in all modules
  - Provider is a typing.Protocol, NOT an ABC — no inheritance required
  - stream() on the protocol is NOT async-def; it returns AsyncIterator[StreamEvent] directly
  - chat_sync must use asyncio.run (not get_event_loop())
  - stream_sync must use asyncio.new_event_loop (not asyncio.run) per the brief's implementation
  - No Pydantic in any of these files
  - MockProvider in tests must satisfy isinstance(mock, Provider) check (runtime_checkable)

OUT OF SCOPE FOR THIS TASK
  - Real HTTP calls — this task has no httpx usage
  - Anthropic or Ollama provider implementations (TASK-4, TASK-5)
  - Config/settings classes (those live in the provider modules)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-3-provider-protocol-and-client  (branch from develop)
  Commit when done:
    feat(core): implement Provider protocol, registry, errors, and Client facade
  Open PR into: develop
