"""Centralized defaults for the multi-agent bot system.

All magic numbers extracted here so they can be overridden via settings or per-org config.
"""

# ── LLM Models ────────────────────────────────────────────────────────────
DEFAULT_MODEL = "claude-sonnet-4-6"
LITE_MODEL = "claude-haiku-4-5-20251001"

# ── Token Limits ──────────────────────────────────────────────────────────
DEFAULT_MAX_TOKENS = 300
SYNTHESIS_MAX_TOKENS = 250
ANALYSIS_MAX_TOKENS = 400
LITE_MAX_TOKENS = 200

# ── Agent Routing ─────────────────────────────────────────────────────────
BOOST_PHRASE_SCORE = 3.0
KEYWORD_MATCH_SCORE = 1.0
CONTEXT_MATCH_SCORE = 0.3
CONFIDENCE_NORMALIZATION = 3.0
ROUTING_CONFIDENCE_THRESHOLD = 0.3
DEFAULT_AGENT_CONFIDENCE = 0.8

# ── Tool Use ──────────────────────────────────────────────────────────────
MAX_TOOL_USE_ROUNDS = 2
TRANSCRIPT_CONTEXT_LINES = 10

# ── Buffers ───────────────────────────────────────────────────────────────
MESSAGE_HISTORY_MAXLEN = 500
MESSAGE_BUS_LOG_MAXLEN = 500

# ── Deliberation Protocol ─────────────────────────────────────────────────
DELIBERATION_INITIAL_PCT = 0.40
DELIBERATION_CROSS_PCT = 0.30
DELIBERATION_REVISE_PCT = 0.30
