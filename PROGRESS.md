# Build Progress

**Project:** norreroute vision/multimodal support (v0.3 feature branch)
**Started:** 2026-05-05
**Status:** Complete

## Task Summary — Vision build (TASK-1 through TASK-4)

| # | Task | Stage | Coverage | Review iter | Test iter | Depends on |
|---|------|-------|----------|-------------|-----------|------------|
| 1 | ImagePart, ChatResponse.text, Message.user/system | done | 100% (types.py) | 0 | 0 | — |
| 2 | Ollama vision serialisation | done | 91% (ollama.py) | 0 | 0 | TASK-1 |
| 3 | Anthropic vision serialisation | done | 93% (anthropic.py) | 0 | 0 | TASK-1 |
| 4 | Capability guard + retry forwarding | done | 100% (errors.py, retry.py) | 0 | 0 | TASK-1, TASK-2, TASK-3 |

## Prior build tasks (v0.2)

| # | Task | Stage | Coverage | Review iter | Test iter | Depends on |
|---|------|-------|----------|-------------|-----------|------------|
| 1 | Retry / Exponential Backoff | done | 100% | 0 | 0 | — |
| 2 | Token Counting / Cost Estimation | done | 100% | 0 | 0 | — |
| 3 | Structured Output / JSON-Mode | done | 96% | 0 | 0 | — |
| 4 | Observability (OpenTelemetry) | done | 100% | 0 | 0 | — |
| 5 | Conversation / Session Persistence | done | 91% | 0 | 0 | — |

## Blockers

None.

## Security debt

- MEDIUM CICD-001: GitHub Actions pinned to mutable tags, not SHA digests (carried from v0.1)
- LOW APP-002: OllamaSettings.base_url not validated as URL (carried from v0.1)
- Pending: global security review of vision build new files (TASK-1 through TASK-4)

## Final test run (vision build)

243 passed, 0 failed. Overall coverage: 95%.
