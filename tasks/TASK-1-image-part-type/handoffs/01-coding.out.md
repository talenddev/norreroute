# Coding Output: TASK-1

## Files created/modified
- `src/norreroute/types.py` — added ImagePart dataclass, extended ContentPart union, added ChatResponse.text property, added Message.user/system classmethods, appended "ImagePart" to __all__
- `src/norreroute/providers/anthropic.py` — replaced bare `else` with `elif isinstance(part, ToolResultPart)` to maintain mypy strict compliance after ContentPart union expansion; added ToolResultPart to import group
- `tests/test_vision_types.py` — new file with 14 tests

## Test results
- 214 passed, 0 failed
- types.py coverage: 100%

## Quality gates
- mypy --strict: passed (no issues in 17 source files)
- ruff check: passed

---
handoff:
  result: ok
  db_models_touched: false
  files_modified:
    - src/norreroute/types.py
    - src/norreroute/providers/anthropic.py
    - tests/test_vision_types.py
  test_count: 14
  coverage_new_files: "100%"
