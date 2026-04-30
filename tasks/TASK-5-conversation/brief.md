TASK-5: Conversation / Session Persistence
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists:
    - src/norreroute/client.py — Client with chat() and stream()
    - src/norreroute/types.py — Message, ChatRequest, ChatResponse, TextPart, Role
    - src/norreroute/streaming.py — StreamEvent, TextDelta, StreamEnd
    - src/norreroute/errors.py — AIProxyError (base for ConversationOverflowError)
    - src/norreroute/pricing.py (TASK-2) — count_tokens_approx (used for trimming)
  What this task enables: nothing depends on this task

DEPENDS ON
  none

OBJECTIVE
  Implement Conversation and TrimStrategy in conversation.py with send/stream/to_json/from_json; add ConversationOverflowError to errors.py.

ACCEPTANCE CRITERIA
  - [ ] TrimStrategy is a frozen dataclass with fields: max_input_tokens (int), keep_system (bool=True), keep_last_n (int=2)
  - [ ] Conversation.__init__ accepts: client, model, system=None, trim=None, history=None
  - [ ] Conversation.messages returns a tuple[Message, ...] (immutable view of history)
  - [ ] Conversation.send(text, **extra) builds a user Message, appends to history, calls client.chat(), appends assistant Message, returns ChatResponse
  - [ ] Conversation.send_message(msg, **extra) does the same but accepts a pre-built Message
  - [ ] Conversation.stream(text, **extra) yields StreamEvent; only appends assistant message to history after a StreamEnd event; partial response on interrupted stream is NOT appended
  - [ ] Trimming runs at send() / send_message() / stream() time (not at history append time)
  - [ ] Trimming algorithm: pin system message if keep_system=True; always keep last keep_last_n messages; drop oldest until count_tokens_approx <= max_input_tokens; raise ConversationOverflowError if budget unsatisfiable without dropping pinned/kept messages
  - [ ] to_json() returns a JSON string with schema {"version": 1, "model": "...", "system": "...", "trim": {...}, "messages": [...]}
  - [ ] from_json(data, client) reconstructs a Conversation from that JSON string
  - [ ] round-trip: from_json(conv.to_json(), client).messages == conv.messages
  - [ ] ConversationOverflowError(AIProxyError) added to errors.py and exported from __init__.py
  - [ ] Conversation and TrimStrategy exported from norreroute/__init__.py
  - [ ] Unit test: send appends user + assistant messages in order
  - [ ] Unit test: trim drops oldest, pins system, keeps last_n
  - [ ] Unit test: ConversationOverflowError raised when budget impossible
  - [ ] Unit test: round-trip to_json/from_json
  - [ ] Unit test: stream interruption (break before StreamEnd) does NOT append to history
  - [ ] count_tokens_approx import: import from pricing.py if it exists, else implement inline fallback (char/4)

FILES TO CREATE OR MODIFY
  - src/norreroute/conversation.py  <- new
  - src/norreroute/errors.py        <- add ConversationOverflowError if not present
  - src/norreroute/__init__.py      <- re-export Conversation, TrimStrategy
  - tests/unit/test_conversation.py <- new

CONSTRAINTS
  - No persistence backend — to_json/from_json is the only serialisation contract
  - No summarisation
  - history is a faithful log; trimming only affects what is sent to the provider, not what is stored
  - Immutable view: messages property returns a tuple, never a list
  - Message serialisation is a pure function in conversation.py — do NOT modify types.py
  - import count_tokens_approx from .pricing; if that module is unavailable (not yet merged), use inline char/4 fallback
  - No new runtime dependencies

OUT OF SCOPE FOR THIS TASK
  - Summarisation
  - Tool-use turns in conversation (history may contain them but send() only handles text input)
  - Persistence backends (DB, file, Redis)
  - Async context manager interface
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-5-conversation  (branch from develop)
  Commit when done:
    feat(conversation): add Conversation and TrimStrategy with JSON persistence
  Open PR into: develop
