TASK-4: Observability (OpenTelemetry)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists:
    - src/norreroute/client.py — Client with _provider: Provider, chat(), stream()
    - src/norreroute/types.py — ChatRequest, ChatResponse
    - src/norreroute/errors.py — AIProxyError
    - pyproject.toml — dev dependencies group
  What this task enables: nothing depends on this task

DEPENDS ON
  none

OBJECTIVE
  Implement lazy-import OTel tracing in tracing.py and wire it into Client via trace= / tracer= kwargs, with opentelemetry-api as an optional dep.

ACCEPTANCE CRITERIA
  - [ ] tracing.py does NOT import opentelemetry at module scope (lazy import only inside functions)
  - [ ] get_tracer(enabled: bool, custom) returns a tracer when enabled or custom is provided; returns None when both are off
  - [ ] When trace=True and opentelemetry is not installed, AIProxyError is raised with message indicating pip install norreroute[otel]
  - [ ] chat_span(tracer, request) is a context manager; when tracer is None it is a no-op (does not raise)
  - [ ] stream_span(tracer, request) is a context manager; when tracer is None it is a no-op
  - [ ] chat_span sets gen_ai span attributes on start: gen_ai.system, gen_ai.request.model, gen_ai.request.max_tokens, gen_ai.request.temperature
  - [ ] chat_span sets gen_ai span attributes on end: gen_ai.usage.input_tokens, gen_ai.usage.output_tokens, gen_ai.response.finish_reason, gen_ai.response.model
  - [ ] chat_span records exception and sets span status=ERROR on exception, then re-raises
  - [ ] stream_span closes the span exactly once even when caller breaks out of the iteration early
  - [ ] Client(provider="anthropic", trace=True) wraps chat/stream calls in chat_span/stream_span
  - [ ] Client(provider="anthropic", tracer=my_tracer) uses the provided tracer object
  - [ ] Client(provider="anthropic") with no trace kwargs has no OTel overhead
  - [ ] pyproject.toml gains [project.optional-dependencies] otel = ["opentelemetry-api>=1.25"]
  - [ ] pyproject.toml dev group gains opentelemetry-sdk for tests
  - [ ] Unit test using in-memory span exporter: chat call produces a span with correct attributes
  - [ ] Unit test: trace=False path succeeds without opentelemetry installed (monkeypatch sys.modules)
  - [ ] Unit test: stream span closes exactly once when caller breaks early

FILES TO CREATE OR MODIFY
  - src/norreroute/tracing.py       <- new
  - src/norreroute/client.py        <- add trace= and tracer= kwargs; wrap calls
  - pyproject.toml                  <- add [otel] optional dep and sdk to dev
  - tests/unit/test_tracing.py      <- new

CONSTRAINTS
  - NEVER import opentelemetry at module top-level in tracing.py — only inside functions/methods that need it
  - tracing.py must import cleanly with zero OTel installed
  - Use contextlib.contextmanager for chat_span and stream_span
  - gen_ai attribute names must match the semantic conventions listed in the brief exactly
  - No new required runtime deps — opentelemetry-api is optional only

OUT OF SCOPE FOR THIS TASK
  - Metrics (only traces/spans)
  - Log correlation
  - Baggage propagation
  - Exporter configuration (SDK concern, not library)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-4-tracing  (branch from develop)
  Commit when done:
    feat(tracing): add lazy OTel tracing with chat_span and stream_span
  Open PR into: develop
