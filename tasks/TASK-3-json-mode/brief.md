TASK-3: Structured Output / JSON-Mode
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists:
    - src/norreroute/client.py — Client, _provider: Provider
    - src/norreroute/types.py — ChatRequest (has extra: dict), ChatResponse
    - src/norreroute/errors.py — AIProxyError (base for new JSONValidationError)
    - src/norreroute/provider.py — Provider Protocol with name: str attribute
  What this task enables: nothing depends on this task

DEPENDS ON
  none

OBJECTIVE
  Implement json_chat() in json_mode.py and expose client.provider_name property on Client; add JSONValidationError to errors.py.

ACCEPTANCE CRITERIA
  - [ ] json_chat(client, request, *, schema=None, strict=True) is an async function returning tuple[ChatResponse, T | dict | None]
  - [ ] json_chat merges provider-specific JSON hint into request.extra using dataclasses.replace before calling client.chat()
  - [ ] Anthropic hint: {"response_format": {"type": "json_object"}} merged into extra
  - [ ] Ollama hint: {"format": "json"} merged into extra
  - [ ] Unknown provider name: no hint merged (extra unchanged)
  - [ ] schema=None: returns (response, parsed_dict) where parsed_dict is json.loads of response text
  - [ ] schema is a dataclass class: returns (response, schema(**parsed_dict)) on success
  - [ ] schema is a TypedDict class: returns (response, parsed_dict) with shallow key presence check (best-effort; documented)
  - [ ] strict=True: raises JSONValidationError on invalid JSON or TypeError from dataclass construction
  - [ ] strict=False: returns (response, None) instead of raising on parse/coercion failure
  - [ ] client.provider_name returns the name attribute of the underlying _provider (read-only property on Client)
  - [ ] JSONValidationError(AIProxyError) added to errors.py (may be done in TASK-2 if that lands first; skip if already present)
  - [ ] json_chat exported from norreroute/__init__.py
  - [ ] Unit test: FakeProvider with name="anthropic" — assert merged extra contains response_format hint
  - [ ] Unit test: FakeProvider with name="ollama" — assert merged extra contains format hint
  - [ ] Unit test: FakeProvider with name="unknown" — assert extra unchanged
  - [ ] Unit test: dataclass coercion happy path
  - [ ] Unit test: dataclass coercion with missing required field, strict=True raises JSONValidationError
  - [ ] Unit test: invalid JSON in response, strict=True raises JSONValidationError
  - [ ] Unit test: invalid JSON in response, strict=False returns (resp, None)
  - [ ] Unit test: client.provider_name returns correct string

FILES TO CREATE OR MODIFY
  - src/norreroute/json_mode.py     <- new
  - src/norreroute/client.py        <- add provider_name property
  - src/norreroute/errors.py        <- add JSONValidationError if not present
  - src/norreroute/__init__.py      <- re-export json_chat
  - tests/unit/test_json_mode.py    <- new

CONSTRAINTS
  - Use dataclasses.replace to merge extra — do NOT mutate the original request
  - No Pydantic validation; TypedDict check is shallow key presence only
  - json_chat must not import from retry.py or pricing.py
  - provider_name is a @property on Client, reads self._provider.name
  - No new runtime dependencies

OUT OF SCOPE FOR THIS TASK
  - Pydantic schema validation
  - JSON schema generation from dataclasses
  - Streaming JSON support
  - Retry logic inside json_chat
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-3-json-mode  (branch from develop)
  Commit when done:
    feat(json-mode): add json_chat helper and client.provider_name property
  Open PR into: develop
