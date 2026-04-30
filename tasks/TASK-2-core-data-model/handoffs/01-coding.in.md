# Coding Brief — TASK-2: Core data model

## Branch
Create and work on: `feature/TASK-2-core-data-model` (from `develop`)

## What to build
Implement all frozen dataclasses in `src/aiproxy/types.py`, `src/aiproxy/streaming.py`,
and the error hierarchy in `src/aiproxy/errors.py`. Then write unit tests in
`tests/unit/test_types.py` and `tests/unit/test_errors.py`.

## Full brief
See: /var/home/leo/Documents/aiproxy/tasks/TASK-2-core-data-model/brief.md

## Architecture reference
See: /var/home/leo/Documents/aiproxy/docs/architecture-brief.md (sections 2 and 9)

## Key requirements

### src/aiproxy/types.py
Exact architecture brief spec — frozen dataclasses:
```python
Role = Literal["system", "user", "assistant", "tool"]

@dataclass(frozen=True) TextPart: text, type="text"
@dataclass(frozen=True) ToolUsePart: id, name, arguments: dict[str, Any], type="tool_use"
@dataclass(frozen=True) ToolResultPart: tool_use_id, content, is_error=False, type="tool_result"

ContentPart = TextPart | ToolUsePart | ToolResultPart

@dataclass(frozen=True) Message: role, content: Sequence[ContentPart]
@dataclass(frozen=True) ToolSpec: name, description, parameters: dict[str, Any]
@dataclass(frozen=True) ChatRequest: model, messages, system=None, tools=(), temperature=None,
                                      max_tokens=None, stop=(), extra=field(default_factory=dict)
@dataclass(frozen=True) Usage: input_tokens, output_tokens
@dataclass(frozen=True) ChatResponse: model, content, finish_reason, usage, raw: dict[str, Any]
```

finish_reason: Literal["stop", "length", "tool_use", "error"]

### src/aiproxy/streaming.py
```python
@dataclass(frozen=True) TextDelta: text, type="text_delta"
@dataclass(frozen=True) ToolCallDelta: id, name: str|None, arguments_json, type="tool_call_delta"
@dataclass(frozen=True) StreamEnd: finish_reason, usage: Usage|None, type="end"

StreamEvent = TextDelta | ToolCallDelta | StreamEnd
```

### src/aiproxy/errors.py
```python
class AIProxyError(Exception): ...
class ConfigurationError(AIProxyError): ...
class ProviderError(AIProxyError):
    def __init__(self, msg, *, provider, status=None, raw=None): ...
class RateLimitError(ProviderError): ...
class AuthenticationError(ProviderError): ...
class TimeoutError_(ProviderError): ...   # trailing _ to avoid shadowing builtins
class ToolArgumentError(AIProxyError): ...
```

### Tests
- tests/unit/test_types.py: construct each dataclass, verify frozen, test union isinstance
- tests/unit/test_errors.py: verify ProviderError attributes, inheritance chain

## Verification
```bash
uv run pytest tests/unit/test_types.py tests/unit/test_errors.py -v
uv run ruff check src/aiproxy/types.py src/aiproxy/streaming.py src/aiproxy/errors.py
uv run mypy src/aiproxy/types.py src/aiproxy/streaming.py src/aiproxy/errors.py
```

## Output format
End your report with:
```yaml
---
handoff:
  result: ok
  branch: feature/TASK-2-core-data-model
  commit: {sha}
  db_models_touched: false
  files_created:
    - tests/unit/test_types.py
    - tests/unit/test_errors.py
  files_modified:
    - src/aiproxy/types.py
    - src/aiproxy/streaming.py
    - src/aiproxy/errors.py
  security_hints: []
  notes: ""
---
```
