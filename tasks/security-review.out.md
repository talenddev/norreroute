SECURITY REVIEW REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Project:    aiproxy
Reviewed:   src/aiproxy/, .github/workflows/ci.yml, pyproject.toml
Date:       2026-04-30
Verdict:    APPROVED

Summary
  Critical:  0
  High:      0
  Medium:    1
  Low:       2
  Info:      1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MEDIUM FINDINGS
───────────────
MEDIUM — CICD-001: GitHub Actions not pinned to SHA digest
File:     .github/workflows/ci.yml:17,19,35
Code:     uses: actions/checkout@v6
          uses: astral-sh/setup-uv@v7
          uses: actions/upload-artifact@v7
Issue:    Actions pinned to mutable tags (v6, v7) — a tag can be updated to point
          to malicious code. SHA pinning is recommended for supply-chain safety.
Fix:      Pin each action to its SHA digest, e.g.
          uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4
          (use https://pin-github-actions.com or similar tool)

LOW FINDINGS
────────────
LOW — APP-001: api_key.get_secret_value() called in __init__ (not at use time)
File:     src/aiproxy/providers/anthropic.py:144
Issue:    The secret is extracted from SecretStr once at construction time and
          passed to the Anthropic SDK. The SDK then holds it in memory for the
          lifetime of the client. Acceptable for a library but worth documenting.
          Risk is limited — the value is never logged or serialised.
Note:     No fix required — this is the correct pattern for the SDK.

LOW — APP-002: base_url in OllamaSettings is not validated as a URL
File:     src/aiproxy/providers/ollama.py:27
Issue:    base_url accepts any string. An attacker who controls settings could
          point it at an internal network endpoint (SSRF). Since this is a
          library (caller controls config), risk is low — callers should validate
          their own input. Consider adding pydantic AnyHttpUrl validation.

INFO
────
INFO — CICD-002: No coverage badge or gate on docs/README
         Not a security issue, informational only.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEPLOYMENT GATE
  Status:   APPROVED — 0 critical, 0 high findings.
            1 medium (tracked as debt), 2 low findings.

No blockers. Proceed to documentation.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

---
handoff:
  result: ok
  critical: 0
  high: 0
  medium: 1
  low: 2
  debt:
    - "MEDIUM CICD-001: GitHub Actions pinned to mutable tags, not SHA digests"
    - "LOW APP-002: OllamaSettings.base_url not validated as a URL (SSRF hardening)"
