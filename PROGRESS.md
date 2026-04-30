# Build Progress

**Project:** norreroute v0.2
**Started:** 2026-04-30
**Status:** In Progress

## Task Summary

| # | Task | Stage | Coverage | Review iter | Test iter | Depends on |
|---|------|-------|----------|-------------|-----------|------------|
| 1 | Retry / Exponential Backoff | pending | — | 0 | 0 | — |
| 2 | Token Counting / Cost Estimation | pending | — | 0 | 0 | — |
| 3 | Structured Output / JSON-Mode | pending | — | 0 | 0 | — |
| 4 | Observability (OpenTelemetry) | pending | — | 0 | 0 | — |
| 5 | Conversation / Session Persistence | pending | — | 0 | 0 | — |

## Blockers

None.

## Security debt

- MEDIUM CICD-001: GitHub Actions pinned to mutable tags, not SHA digests (carried from v0.1)
- LOW APP-002: OllamaSettings.base_url not validated as URL (carried from v0.1)
