# Coding Output: TASK-2

## Files created/modified
- `src/norreroute/providers/ollama.py` — added `import base64`, `ImagePart` to imports, image_parts collection in _messages_to_ollama, base64 serialisation in non-tool branch, comments for dropped images in tool branches
- `tests/test_ollama_vision.py` — new file with 9 tests

## Test results
- 9 passed, 0 failed
- ollama.py coverage: 91%

## Quality gates
- mypy --strict: passed
- ruff check: passed

---
handoff:
  result: ok
  db_models_touched: false
