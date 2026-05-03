TASK-2: Token Counting / Cost Estimation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists:
    - src/norreroute/types.py — ChatRequest, ChatResponse, Usage, Message, TextPart
    - src/norreroute/errors.py — AIProxyError (base for new UnknownModelError)
  What this task enables: TASK-5 (Conversation) uses count_tokens_approx for trimming

DEPENDS ON
  none

OBJECTIVE
  Implement ModelPrice, CostEstimate, estimate_cost, and count_tokens_approx in pricing.py with pricing data in pricing_data.py, plus add UnknownModelError to errors.py.

ACCEPTANCE CRITERIA
  - [ ] ModelPrice is a frozen dataclass with fields: input_per_mtok_usd (float), output_per_mtok_usd (float)
  - [ ] CostEstimate is a frozen dataclass with fields: model (str), input_tokens (int), output_tokens (int), input_cost_usd (float), output_cost_usd (float), total_cost_usd (float), is_estimate (bool)
  - [ ] pricing_data.py defines MODEL_PRICING: dict[str, ModelPrice] with entries for: claude-3-5-sonnet-20241022 (3.00/15.00), claude-3-5-haiku-20241022 (0.80/4.00), claude-3-opus-20240229 (15.00/75.00), llama3.1 (0.0/0.0), qwen2.5 (0.0/0.0)
  - [ ] estimate_cost(response, pricing=None) looks up model in pricing arg first, then MODEL_PRICING, raises UnknownModelError if not found
  - [ ] estimate_cost uses response.usage token counts when usage is present; sets is_estimate=False
  - [ ] estimate_cost falls back to count_tokens_approx on the request when usage is absent (usage=None or zero tokens); sets is_estimate=True
  - [ ] estimate_cost math: input_cost = input_tokens / 1_000_000 * input_per_mtok_usd, output_cost similarly, total = sum
  - [ ] count_tokens_approx(request) returns int approximation via char/4 heuristic over all message text content
  - [ ] UnknownModelError(AIProxyError) added to errors.py and exported from __init__.py
  - [ ] ModelPrice, CostEstimate, estimate_cost, count_tokens_approx exported from norreroute/__init__.py
  - [ ] Table-driven unit tests verify correct cost math for each model in MODEL_PRICING with known token counts
  - [ ] Unit test: missing model raises UnknownModelError
  - [ ] Unit test: explicit pricing= arg overrides MODEL_PRICING
  - [ ] Unit test: count_tokens_approx returns floor(total_chars / 4)
  - [ ] Prefix-match fallback: Ollama model names not in MODEL_PRICING but starting with a known prefix (e.g. "llama3") resolve to that base model's pricing

FILES TO CREATE OR MODIFY
  - src/norreroute/pricing.py       <- new
  - src/norreroute/pricing_data.py  <- new
  - src/norreroute/errors.py        <- add UnknownModelError, JSONValidationError, ConversationOverflowError
  - src/norreroute/__init__.py      <- re-export new symbols
  - tests/unit/test_pricing.py      <- new

CONSTRAINTS
  - No new runtime dependencies (stdlib only: dataclasses, math)
  - estimate_cost is a free function — NOT a method on Client
  - No Pydantic, no tiktoken
  - pricing_data.py must be importable with zero side effects
  - Prices are per million tokens (mtok); cost formula: tokens / 1_000_000 * price_per_mtok

OUT OF SCOPE FOR THIS TASK
  - Real tokeniser integration
  - Streaming cost tracking
  - Per-provider pricing API calls
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-2-pricing  (branch from develop)
  Commit when done:
    feat(pricing): add ModelPrice, CostEstimate, estimate_cost and count_tokens_approx
  Open PR into: develop
