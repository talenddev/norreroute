TASK-4: Unsupported-capability guard + retry forwarding
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: src/norreroute/errors.py with AIProxyError hierarchy,
               src/norreroute/client.py with Client.chat() and Client.stream(),
               src/norreroute/retry.py with RetryingProvider that mirrors inner.name,
               OllamaProvider and AnthropicProvider with no supports_vision attribute.
               TASK-1, 2, 3 will have landed ImagePart and provider serialisation.
  What this task enables: callers get a typed pre-flight error instead of opaque HTTP 400

DEPENDS ON
  TASK-1, TASK-2, TASK-3

OBJECTIVE
  Add UnsupportedCapabilityError, supports_vision class attribute on both providers,
  supports_vision forwarding in RetryingProvider, and _validate_request pre-flight
  check in Client.

ACCEPTANCE CRITERIA
  - [ ] UnsupportedCapabilityError(capability, provider=...) has .capability and .provider attrs
  - [ ] UnsupportedCapabilityError message: "Provider '{provider}' does not support capability '{capability}'"
  - [ ] UnsupportedCapabilityError is subclass of AIProxyError
  - [ ] "UnsupportedCapabilityError" appended to __all__ in errors.py
  - [ ] OllamaProvider.supports_vision = True class attribute exists
  - [ ] AnthropicProvider.supports_vision = True class attribute exists
  - [ ] RetryingProvider.__init__ sets self.supports_vision from getattr(inner, "supports_vision", True)
  - [ ] Client._validate_request raises UnsupportedCapabilityError when provider.supports_vision
        is False and request contains any ImagePart
  - [ ] Guard fires before any HTTP call (no provider invocations when guard triggers)
  - [ ] Guard is no-op when no ImagePart present (passes through normally)
  - [ ] Guard is no-op when provider.supports_vision is True
  - [ ] Works through RetryingProvider wrapper (supports_vision propagated)
  - [ ] `from norreroute import UnsupportedCapabilityError` works
  - [ ] UnsupportedCapabilityError added to from .errors import (...) and __all__ in __init__.py
  - [ ] _validate_request called as first line of chat() and stream()
  - [ ] mypy --strict passes on src/norreroute
  - [ ] ruff check passes on src/ and tests/

FILES TO CREATE OR MODIFY
  - src/norreroute/errors.py                   ← modify
  - src/norreroute/client.py                   ← modify
  - src/norreroute/retry.py                    ← modify
  - src/norreroute/providers/ollama.py         ← modify
  - src/norreroute/providers/anthropic.py      ← modify
  - src/norreroute/__init__.py                 ← modify
  - tests/test_capability_guard.py             ← new

CONSTRAINTS
  - Use uv for any new dependencies
  - No external HTTP calls without mocking in tests
  - Follow existing patterns in src/ if any exist
  - Use getattr(inner, "supports_vision", True) for safe forwarding in RetryingProvider

OUT OF SCOPE FOR THIS TASK
  - Model-level vision capability checking (only provider-level)
  - Any changes to types.py beyond what TASK-1 already delivered
  - Any changes to _messages_to_ollama or _messages_to_anthropic beyond what TASK-2/3 delivered
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-4-capability-guard  (branch from develop after TASK-1,2,3 merged)
  Commit when done:
    feat(client): add UnsupportedCapabilityError and vision capability guard
  Open PR into: develop
