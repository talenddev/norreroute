TASK-7: Tool-call support (ToolSpec/ToolUsePart/ToolResultPart wired into both providers)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: Both providers implemented (TASK-4, TASK-5), integration tests
               established (TASK-6). ToolSpec, ToolUsePart, ToolResultPart already
               defined in types.py (TASK-2) but not yet wired into providers.
  What this task enables: Final milestone — first-class tool calling for both providers.

DEPENDS ON
  TASK-6

OBJECTIVE
  Wire ToolSpec → provider tool definitions and parse tool_use responses into
  ToolUsePart in ChatResponse.content, for both AnthropicProvider and OllamaProvider.
  Add one tool-call test per provider.

ACCEPTANCE CRITERIA
  - [ ] AnthropicProvider.chat(): when ChatRequest.tools is non-empty, sends
        tools array in the API request (Anthropic native tool format)
  - [ ] AnthropicProvider.chat(): when response contains tool_use block,
        ChatResponse.content includes ToolUsePart with correct id, name, arguments
  - [ ] AnthropicProvider.chat(): finish_reason == "tool_use" when stop_reason
        is "tool_use"
  - [ ] OllamaProvider.chat(): when ChatRequest.tools is non-empty, sends
        tools array in OpenAI-compatible format (Ollama uses OpenAI tool schema)
  - [ ] OllamaProvider.chat(): when response contains tool_calls, ChatResponse.content
        includes ToolUsePart with correct id, name, arguments (parsed from JSON)
  - [ ] OllamaProvider.chat(): finish_reason == "tool_use" when done_reason is
        "tool_calls" or response has tool_calls
  - [ ] ToolResultPart is accepted in ChatRequest.messages content (no validation
        error) — providers must handle it in message serialization:
        Anthropic: role="tool" with tool_use_id; Ollama: role="tool" with content
  - [ ] Unit test in tests/unit/providers/test_anthropic.py:
        - chat() with a get_weather ToolSpec returns ToolUsePart in content
        - finish_reason == "tool_use"
  - [ ] Unit test in tests/unit/providers/test_ollama.py:
        - chat() with a get_weather ToolSpec returns ToolUsePart in content
        - finish_reason == "tool_use"
  - [ ] uv run pytest tests/unit/providers/ -- all pass (existing + new tool tests)
  - [ ] uv run ruff check src/aiproxy/providers/
  - [ ] uv run mypy src/aiproxy/providers/

FILES TO CREATE OR MODIFY
  - src/aiproxy/providers/anthropic.py    <- modify (add tool wiring)
  - src/aiproxy/providers/ollama.py       <- modify (add tool wiring)
  - tests/unit/providers/test_anthropic.py <- modify (add tool-call tests)
  - tests/unit/providers/test_ollama.py   <- modify (add tool-call tests)

CONSTRAINTS
  - Anthropic tool format: {"name": str, "description": str, "input_schema": JSON-Schema}
  - Ollama tool format (OpenAI-compatible): {"type": "function", "function":
    {"name": str, "description": str, "parameters": JSON-Schema}}
  - ToolResultPart in message: Anthropic serializes as content block with type
    "tool_result"; Ollama serializes as {"role": "tool", "content": result_str}
  - ToolUsePart.arguments must be a dict[str, Any] — parse from JSON string if
    needed when deserializing tool_calls from Ollama
  - Streaming tool-call support is OUT OF SCOPE (only non-streaming chat)

OUT OF SCOPE FOR THIS TASK
  - Streaming tool-call deltas (ToolCallDelta)
  - Multi-tool parallel calls in a single response
  - Tool result validation / schema enforcement
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-7-tool-call-support  (branch from develop)
  Commit when done:
    feat(tools): wire ToolSpec and ToolUsePart into Anthropic and Ollama providers
  Open PR into: develop
