"""Specialist agent tool definitions and executors.

Each core agent (Vex, Prism, Echo, Sage, Nexus) has its own set of tools
that it can use when answering questions via the agent router. These tools
are passed to Claude during specialist agent calls, allowing agents to
gather data before responding.

Architecture:
- AGENT_TOOLS[agent_name] = list of tool definitions (Anthropic format)
- execute_agent_tool(agent_name, tool_name, input, ctx) -> str
"""

import asyncio
import logging
import time
import uuid
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


def _escape_like(s: str) -> str:
    """Escape SQL LIKE/ILIKE wildcard characters."""
    return s.replace("%", r"\%").replace("_", r"\_")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VEX — Strategic Advisor (10 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VEX_TOOLS = [
    {
        "name": "analyze_market",
        "description": "Analyze a market: size, growth rate, key players, trends, and opportunities. Use when asked about market dynamics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "description": "Market or industry to analyze."},
                "focus": {"type": "string", "description": "Specific aspect to focus on (size, trends, players)."},
            },
            "required": ["market"],
        },
    },
    {
        "name": "competitor_lookup",
        "description": "Get a competitor profile: pricing, features, funding, strategy, strengths, weaknesses.",
        "input_schema": {
            "type": "object",
            "properties": {
                "competitor": {"type": "string", "description": "Competitor name or company."},
            },
            "required": ["competitor"],
        },
    },
    {
        "name": "swot_analysis",
        "description": "Generate a SWOT analysis for a product, initiative, or decision.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "What to analyze."},
                "context": {"type": "string", "description": "Business context."},
            },
            "required": ["subject"],
        },
    },
    {
        "name": "strategic_recommendation",
        "description": "Provide a weighted decision matrix with a clear recommendation. Use for strategic trade-offs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "description": "The decision to evaluate."},
                "options": {"type": "string", "description": "Options being considered (comma-separated)."},
                "criteria": {"type": "string", "description": "Evaluation criteria (comma-separated)."},
            },
            "required": ["decision"],
        },
    },
    {
        "name": "risk_assessment",
        "description": "Multi-dimension risk register with probability, impact, and mitigations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "initiative": {"type": "string", "description": "Initiative or decision to assess."},
            },
            "required": ["initiative"],
        },
    },
    {
        "name": "scenario_model",
        "description": "Best/likely/worst case scenario analysis with key assumptions and sensitivity factors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario": {"type": "string", "description": "What to model."},
                "variables": {"type": "string", "description": "Key variables to vary."},
            },
            "required": ["scenario"],
        },
    },
    {
        "name": "framework_apply",
        "description": "Apply a strategic framework (Porter's Five Forces, Ansoff Matrix, BCG, Jobs-to-be-Done, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "framework": {"type": "string", "description": "Which framework to apply."},
                "subject": {"type": "string", "description": "What to apply it to."},
            },
            "required": ["framework", "subject"],
        },
    },
    {
        "name": "decision_log_query",
        "description": "Search past strategic decisions from meeting history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "strategy_contradiction_check",
        "description": "Check if a proposed action contradicts stated strategy or past decisions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposal": {"type": "string", "description": "Proposed action to check."},
            },
            "required": ["proposal"],
        },
    },
    {
        "name": "okr_alignment_check",
        "description": "Map an initiative to company OKRs and assess alignment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "initiative": {"type": "string", "description": "Initiative to check alignment for."},
            },
            "required": ["initiative"],
        },
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRISM — Data Analyst (12 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRISM_TOOLS = [
    {
        "name": "query_database",
        "description": "Translate natural language to SQL and query the database. Read-only, PII-masked.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Natural language data question."},
                "tables_hint": {"type": "string", "description": "Tables to focus on (optional)."},
            },
            "required": ["question"],
        },
    },
    {
        "name": "create_chart",
        "description": "Describe a chart visualization for the data. Specify type, axes, and annotations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data_description": {"type": "string", "description": "What data to chart."},
                "chart_type": {"type": "string", "description": "bar, line, pie, scatter, heatmap."},
            },
            "required": ["data_description"],
        },
    },
    {
        "name": "statistical_analysis",
        "description": "Run descriptive or inferential statistics with plain-English interpretation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Statistical question to answer."},
                "data_source": {"type": "string", "description": "Where to get the data."},
            },
            "required": ["question"],
        },
    },
    {
        "name": "trend_detection",
        "description": "Detect trends: direction, change points, seasonality, and forecast.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "Metric to analyze."},
                "time_range": {"type": "string", "description": "Time range (e.g., 'last 90 days')."},
            },
            "required": ["metric"],
        },
    },
    {
        "name": "anomaly_detection",
        "description": "Flag unusual data points with possible explanations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "Metric to check for anomalies."},
            },
            "required": ["metric"],
        },
    },
    {
        "name": "forecast",
        "description": "Generate a time series forecast with confidence intervals.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "Metric to forecast."},
                "horizon": {"type": "string", "description": "How far ahead (e.g., '30 days', '3 months')."},
            },
            "required": ["metric"],
        },
    },
    {
        "name": "cohort_analysis",
        "description": "Retention curves, cohort comparison, segment analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cohort_type": {"type": "string", "description": "How to group cohorts (signup month, plan, etc)."},
                "metric": {"type": "string", "description": "Metric to track (retention, revenue, usage)."},
            },
            "required": ["cohort_type"],
        },
    },
    {
        "name": "funnel_analysis",
        "description": "Step-by-step conversion analysis with drop-off at each stage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "funnel": {"type": "string", "description": "Funnel to analyze (signup, onboarding, purchase)."},
            },
            "required": ["funnel"],
        },
    },
    {
        "name": "ab_test_analysis",
        "description": "Analyze A/B test results: statistical significance, practical significance, sample adequacy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "test_name": {"type": "string", "description": "Name or description of the test."},
                "control_rate": {"type": "string", "description": "Control conversion rate (if known)."},
                "variant_rate": {"type": "string", "description": "Variant conversion rate (if known)."},
            },
            "required": ["test_name"],
        },
    },
    {
        "name": "metric_definition",
        "description": "Define how a metric is calculated, its caveats, and industry benchmarks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "Metric to define."},
            },
            "required": ["metric"],
        },
    },
    {
        "name": "data_quality_check",
        "description": "Check data quality: nulls, duplicates, outliers, freshness, schema drift.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string", "description": "Dataset or table to check."},
            },
            "required": ["dataset"],
        },
    },
    {
        "name": "executive_dashboard",
        "description": "Generate a verbal summary of key business metrics for an exec audience.",
        "input_schema": {
            "type": "object",
            "properties": {
                "focus": {"type": "string", "description": "Focus area: revenue, growth, ops, product."},
            },
            "required": [],
        },
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ECHO — Organizational Historian (12 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ECHO_TOOLS = [
    {
        "name": "search_all_meetings",
        "description": "Semantic search across all meeting history — transcripts, summaries, decisions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for."},
                "time_range": {"type": "string", "description": "Optional time filter (e.g., 'last 30 days')."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "find_decision",
        "description": "Find the exact moment a decision was made — who, when, context, alternatives considered.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Decision topic to find."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "trace_topic_history",
        "description": "Complete timeline of a topic across all meetings — first mention, evolution, current status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to trace."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "who_said_what",
        "description": "Find who said something specific, when, and in what context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_text": {"type": "string", "description": "What was said (or topic)."},
                "speaker": {"type": "string", "description": "Optional: filter by speaker name."},
            },
            "required": ["search_text"],
        },
    },
    {
        "name": "find_commitment",
        "description": "Find promises and commitments made in meetings — who promised what to whom.",
        "input_schema": {
            "type": "object",
            "properties": {
                "person": {"type": "string", "description": "Person to check commitments for."},
                "topic": {"type": "string", "description": "Optional topic filter."},
            },
            "required": [],
        },
    },
    {
        "name": "org_knowledge_graph",
        "description": "Get relationships, projects, responsibilities for an entity (person, team, project).",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Person, team, or project name."},
            },
            "required": ["entity"],
        },
    },
    {
        "name": "meeting_diff",
        "description": "What changed between two meetings on the same topic — decisions, positions, action items.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to compare across meetings."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "tribal_knowledge_search",
        "description": "Search undocumented institutional knowledge from meetings — the stuff nobody writes down.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "What do you want to know?"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "decision_reversal_log",
        "description": "Find decisions that were later reversed, contradicted, or superseded.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Optional topic filter."},
            },
            "required": [],
        },
    },
    {
        "name": "institutional_memory",
        "description": "'Why do we do X this way?' — trace back to the original decision and reasoning.",
        "input_schema": {
            "type": "object",
            "properties": {
                "practice": {"type": "string", "description": "The practice or convention to trace."},
            },
            "required": ["practice"],
        },
    },
    {
        "name": "relationship_map",
        "description": "Who works with whom, how often, on what projects — based on meeting co-occurrence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "person": {"type": "string", "description": "Person to map relationships for."},
            },
            "required": ["person"],
        },
    },
    {
        "name": "context_for_new_hire",
        "description": "Generate onboarding context on a topic for someone new — history, key decisions, current state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to explain."},
                "depth": {"type": "string", "description": "brief or detailed."},
            },
            "required": ["topic"],
        },
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SAGE — Meeting Coach & Facilitator (12 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SAGE_TOOLS = [
    {
        "name": "talk_time_analysis",
        "description": "Analyze per-person talk time, interruptions, and silence ratio from the current meeting.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "engagement_score",
        "description": "Composite engagement score based on participation, questions asked, response latency.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "meeting_effectiveness",
        "description": "Score meeting effectiveness: decisions made, action items created, topics resolved.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "suggest_agenda",
        "description": "AI-generated meeting agenda from open action items, recent topics, and patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_type": {"type": "string", "description": "Type: standup, planning, retro, 1:1, all-hands."},
            },
            "required": [],
        },
    },
    {
        "name": "detect_going_off_topic",
        "description": "Detect if the meeting has drifted off the current topic, with redirect suggestion.",
        "input_schema": {
            "type": "object",
            "properties": {
                "original_topic": {"type": "string", "description": "What the topic should be."},
            },
            "required": [],
        },
    },
    {
        "name": "energy_check",
        "description": "Assess meeting energy and sentiment from the last few minutes of transcript.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "parking_lot",
        "description": "Add a topic to the meeting parking lot for later discussion.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to park."},
                "raised_by": {"type": "string", "description": "Who raised it."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "meeting_pattern_analysis",
        "description": "Analyze patterns across meetings: frequency, duration, time-in-meetings trends.",
        "input_schema": {
            "type": "object",
            "properties": {
                "time_range": {"type": "string", "description": "Time range to analyze."},
            },
            "required": [],
        },
    },
    {
        "name": "facilitation_move",
        "description": "Suggest a facilitation technique for the current situation: stuck, conflict, dominant speaker, low energy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "situation": {"type": "string", "description": "Current meeting dynamics issue."},
            },
            "required": ["situation"],
        },
    },
    {
        "name": "retrospective_guide",
        "description": "Generate a post-meeting retrospective: what went well, what to improve, action items.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "decision_forcing",
        "description": "Force convergence when a group is going in circles. Presents options clearly and asks for a vote.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic the group is stuck on."},
                "options": {"type": "string", "description": "Known options (comma-separated)."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "meeting_cost_calculator",
        "description": "Calculate the dollar cost of a meeting based on duration and estimated salaries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "attendee_count": {"type": "integer", "description": "Number of attendees."},
                "avg_salary": {"type": "integer", "description": "Average annual salary estimate."},
            },
            "required": ["attendee_count"],
        },
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NEXUS — Relationship & Sales Intelligence (13 tools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEXUS_TOOLS = [
    {
        "name": "crm_lookup",
        "description": "Look up a company or contact in the CRM. Returns account info, recent activity, deal history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Company or contact name."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "deal_status",
        "description": "Get deal pipeline status: stage, value, probability, days in stage, blockers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deal": {"type": "string", "description": "Deal or company name."},
            },
            "required": ["deal"],
        },
    },
    {
        "name": "customer_history",
        "description": "Complete timeline of a customer relationship from first touch to today.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer": {"type": "string", "description": "Customer name."},
            },
            "required": ["customer"],
        },
    },
    {
        "name": "competitive_positioning",
        "description": "Head-to-head comparison vs a competitor, tailored for a specific customer situation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "competitor": {"type": "string", "description": "Competitor to compare against."},
                "customer_context": {"type": "string", "description": "Customer's specific needs/situation."},
            },
            "required": ["competitor"],
        },
    },
    {
        "name": "proposal_draft",
        "description": "Draft a proposal or SOW based on the meeting discussion.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer": {"type": "string", "description": "Customer name."},
                "scope": {"type": "string", "description": "What was discussed/agreed."},
            },
            "required": ["customer", "scope"],
        },
    },
    {
        "name": "follow_up_sequence",
        "description": "Draft a follow-up email with next steps, resources, and timeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Who to follow up with."},
                "context": {"type": "string", "description": "Meeting context."},
            },
            "required": ["recipient"],
        },
    },
    {
        "name": "sentiment_toward_us",
        "description": "Aggregate sentiment analysis of a customer across all touchpoints.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer": {"type": "string", "description": "Customer name."},
            },
            "required": ["customer"],
        },
    },
    {
        "name": "objection_response",
        "description": "Generate categorized responses to a sales objection with evidence and examples.",
        "input_schema": {
            "type": "object",
            "properties": {
                "objection": {"type": "string", "description": "The objection raised."},
            },
            "required": ["objection"],
        },
    },
    {
        "name": "champion_map",
        "description": "Map contacts by influence: champions, blockers, decision makers, evaluators.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account to map."},
            },
            "required": ["account"],
        },
    },
    {
        "name": "contract_risk_flags",
        "description": "Flag risky terms in a deal or contract with market comparison.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deal": {"type": "string", "description": "Deal or contract to review."},
                "concerns": {"type": "string", "description": "Specific concerns."},
            },
            "required": ["deal"],
        },
    },
    {
        "name": "win_loss_analysis",
        "description": "Analyze win/loss patterns: why we win, why we lose, by segment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "segment": {"type": "string", "description": "Segment to analyze (optional)."},
            },
            "required": [],
        },
    },
    {
        "name": "upsell_opportunity",
        "description": "Identify expansion opportunities based on usage patterns and needs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer": {"type": "string", "description": "Customer to analyze."},
            },
            "required": ["customer"],
        },
    },
    {
        "name": "renewal_risk",
        "description": "Assess renewal probability, risk factors, and recommended save plays.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer": {"type": "string", "description": "Customer to assess."},
            },
            "required": ["customer"],
        },
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Registry
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AGENT_TOOLS: dict[str, list[dict]] = {
    "vex": VEX_TOOLS,
    "prism": PRISM_TOOLS,
    "echo": ECHO_TOOLS,
    "sage": SAGE_TOOLS,
    "nexus": NEXUS_TOOLS,
}

# Merge Phase 5 specialist tools
from gneva.bot.specialist_tools import SPECIALIST_TOOLS
AGENT_TOOLS.update(SPECIALIST_TOOLS)


def get_tools_for_agent(agent_name: str) -> list[dict]:
    """Get tool definitions for a specific agent."""
    return AGENT_TOOLS.get(agent_name, [])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tool Executors
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def execute_agent_tool(
    agent_name: str,
    tool_name: str,
    tool_input: dict,
    org_id: str | None = None,
    meeting_id: str | None = None,
    transcript_buffer: list[dict] | None = None,
) -> str:
    """Execute a specialist agent's tool and return text result.

    Tools fall into three categories:
    1. DB-backed: query organizational data (Echo, some Sage)
    2. LLM-powered: use Claude for analysis (Vex, Prism, Nexus)
    3. Transcript-based: analyze current meeting transcript (Sage)
    """
    try:
        # Route to the right executor
        executor = _EXECUTORS.get(tool_name)
        if executor:
            return await executor(tool_input, org_id=org_id, meeting_id=meeting_id,
                                  transcript_buffer=transcript_buffer)

        # Check Phase 5 specialist tools
        from gneva.bot.specialist_tools import SPECIALIST_TOOLS, execute_specialist_tool
        for sp_name, sp_tools in SPECIALIST_TOOLS.items():
            if any(t["name"] == tool_name for t in sp_tools):
                return await execute_specialist_tool(
                    agent_name=sp_name, tool_name=tool_name, tool_input=tool_input,
                    org_id=org_id, meeting_id=meeting_id, transcript_buffer=transcript_buffer,
                )

        return f"Tool '{tool_name}' is not yet implemented."
    except Exception as e:
        logger.error(f"Agent tool execution failed [{agent_name}/{tool_name}]: {e}", exc_info=True)
        return f"Sorry, that tool didn't work right now. Please try again."


# ── Shared utilities ─────────────────────────────────────────────────────────

async def _llm_analyze(prompt: str, system: str, model: str = "claude-haiku-4-5-20251001",
                        max_tokens: int = 300) -> str:
    """Call Claude for analysis tasks shared across agents."""
    from gneva.services import llm_analyze
    return await llm_analyze(prompt, system, model=model, max_tokens=max_tokens)


async def _search_decisions(org_id: str | None, query: str, limit: int = 5) -> list[dict]:
    """Search decisions in the database."""
    if not org_id:
        return []
    from gneva.db import async_session_factory
    from gneva.models.entity import Decision
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(
            select(Decision)
            .where(Decision.org_id == uuid.UUID(org_id),
                   Decision.statement.ilike(f"%{_escape_like(query)}%"))
            .order_by(Decision.created_at.desc())
            .limit(limit)
        )
        return [
            {"statement": d.statement[:200], "status": d.status,
             "rationale": (d.rationale or "")[:150],
             "date": d.created_at.strftime("%b %d")}
            for d in result.scalars().all()
        ]


async def _search_transcripts(org_id: str | None, query: str, limit: int = 5) -> list[dict]:
    """Search transcript segments across meetings."""
    if not org_id:
        return []
    from gneva.db import async_session_factory
    from gneva.models.meeting import TranscriptSegment, Meeting
    from sqlalchemy import select

    async with async_session_factory() as session:
        from gneva.models.meeting import Meeting
        result = await session.execute(
            select(TranscriptSegment)
            .join(Meeting, Meeting.id == TranscriptSegment.meeting_id)
            .where(
                Meeting.org_id == uuid.UUID(org_id),
                TranscriptSegment.text.ilike(f"%{_escape_like(query)}%"),
            )
            .order_by(TranscriptSegment.created_at.desc())
            .limit(limit)
        )
        return [
            {"speaker": s.speaker_label or "unknown", "text": s.text[:200],
             "date": s.created_at.strftime("%b %d %H:%M") if s.created_at else ""}
            for s in result.scalars().all()
        ]


async def _search_entities(org_id: str | None, query: str, entity_type: str | None = None,
                            limit: int = 5) -> list[dict]:
    """Search entities in the knowledge graph."""
    if not org_id:
        return []
    from gneva.db import async_session_factory
    from gneva.models.entity import Entity, EntityRelationship
    from sqlalchemy import select, or_

    async with async_session_factory() as session:
        q = select(Entity).where(
            Entity.org_id == uuid.UUID(org_id),
            or_(Entity.name.ilike(f"%{_escape_like(query)}%"), Entity.description.ilike(f"%{_escape_like(query)}%")),
        )
        if entity_type:
            q = q.where(Entity.type == entity_type)
        result = await session.execute(q.order_by(Entity.last_seen.desc()).limit(limit))
        entities = result.scalars().all()

        items = []
        for e in entities:
            # Get relationships
            rels = await session.execute(
                select(EntityRelationship)
                .where((EntityRelationship.source_id == e.id) | (EntityRelationship.target_id == e.id))
                .limit(5)
            )
            rel_list = [{"type": r.relation_type, "target": str(r.target_id)}
                        for r in rels.scalars().all()]
            items.append({
                "name": e.name, "type": e.type,
                "description": (e.description or "")[:150],
                "relationships": rel_list[:3],
            })
        return items


def _get_transcript_text(transcript_buffer: list[dict] | None, last_n: int = 30) -> str:
    """Extract recent transcript text."""
    if not transcript_buffer:
        return "(no transcript available)"
    recent = transcript_buffer[-last_n:]
    return "\n".join(f"{s['speaker']}: {s['text']}" for s in recent)


# ── VEX executors ─────────────────────────────────────────────────────────────

async def _vex_analyze_market(inp: dict, **ctx) -> str:
    market = inp.get("market", "")
    focus = inp.get("focus", "")
    return await _llm_analyze(
        f"Analyze the {market} market. {f'Focus on: {focus}' if focus else ''}\n"
        "Cover: market size, growth rate, key players (top 5), recent trends, and opportunities.",
        system="You are a strategic market analyst. Be specific with numbers and players. "
               "Speak in 4-6 concise sentences suitable for a meeting. No markdown.",
    )


async def _vex_competitor_lookup(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Competitor profile for: {inp.get('competitor', '')}\n"
        "Cover: what they do, pricing model, key features, funding/revenue, strategic direction, "
        "strengths, weaknesses, and how we compare.",
        system="You are a competitive intelligence analyst. Be specific and factual. "
               "4-6 sentences, suitable for spoken delivery.",
    )


async def _vex_swot(inp: dict, **ctx) -> str:
    subject = inp.get("subject", "")
    context = inp.get("context", "")
    return await _llm_analyze(
        f"SWOT analysis for: {subject}\n{f'Context: {context}' if context else ''}\n"
        "Provide 2-3 items per quadrant. Prioritize the most impactful.",
        system="You are a strategy consultant. Structure as: Strengths, Weaknesses, Opportunities, Threats. "
               "Be specific and actionable. Spoken format, no markdown.",
    )


async def _vex_strategic_recommendation(inp: dict, **ctx) -> str:
    decision = inp.get("decision", "")
    options = inp.get("options", "")
    criteria = inp.get("criteria", "")
    prompt = f"Decision: {decision}"
    if options:
        prompt += f"\nOptions: {options}"
    if criteria:
        prompt += f"\nCriteria: {criteria}"
    return await _llm_analyze(
        prompt,
        system="You are a strategy advisor. Evaluate the options against criteria. "
               "Provide a clear recommendation with reasoning. 4-6 spoken sentences.",
    )


async def _vex_risk_assessment(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Risk assessment for: {inp.get('initiative', '')}\n"
        "Identify top 3-5 risks with probability (low/medium/high), impact, and mitigation strategy.",
        system="You are a risk management specialist. Be practical, not theoretical. "
               "Rank by risk score (probability x impact). Spoken format.",
    )


async def _vex_scenario_model(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Scenario model for: {inp.get('scenario', '')}\n"
        f"Key variables: {inp.get('variables', 'not specified')}\n"
        "Best case, likely case, worst case. Key assumptions for each.",
        system="You are a scenario planning specialist. Be specific with numbers where possible. "
               "Highlight the key decision drivers. Spoken format.",
    )


async def _vex_framework(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Apply {inp.get('framework', '')} framework to: {inp.get('subject', '')}",
        system="You are a strategy consultant. Apply the framework rigorously but explain it simply. "
               "Give the key insight, not just the structure. 4-6 spoken sentences.",
    )


async def _vex_decision_log(inp: dict, **ctx) -> str:
    query = inp.get("query", "")
    decisions = await _search_decisions(ctx.get("org_id"), query)
    if not decisions:
        return f"No past decisions found matching '{query}'."
    lines = [f"- {d['date']}: {d['statement']} [{d['status']}]" for d in decisions]
    return "Past decisions:\n" + "\n".join(lines)


async def _vex_contradiction_check(inp: dict, **ctx) -> str:
    proposal = inp.get("proposal", "")
    decisions = await _search_decisions(ctx.get("org_id"), proposal, limit=8)
    if not decisions:
        return "No relevant past decisions found to check against."
    decisions_text = "\n".join(f"- {d['statement']} ({d['date']})" for d in decisions)
    return await _llm_analyze(
        f"Proposed action: {proposal}\n\nPast decisions:\n{decisions_text}\n\n"
        "Does this proposal contradict any past decisions? If so, which ones and how?",
        system="You are a strategy consistency checker. Be specific about contradictions. "
               "If no contradiction, say so clearly. Spoken format, 2-4 sentences.",
    )


async def _vex_okr_check(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Check OKR alignment for: {inp.get('initiative', '')}\n"
        "How does this map to typical company OKRs? What objectives does it serve? "
        "Rate alignment: strong/moderate/weak.",
        system="You are an OKR specialist. Be practical about alignment. "
               "Suggest how to frame the initiative in OKR terms. Spoken format.",
    )


# ── PRISM executors ───────────────────────────────────────────────────────────

async def _prism_query_database(inp: dict, **ctx) -> str:
    question = inp.get("question", "")
    # In production this would generate and run SQL. For now, use LLM analysis.
    return await _llm_analyze(
        f"Data question: {question}\n"
        "What SQL query would answer this? What tables/columns would be needed? "
        "If you can estimate the answer from general knowledge, do so.",
        system="You are a data analyst. Explain what data would be needed and how to query it. "
               "If the question can be answered from context, provide the answer. Spoken format.",
    )


async def _prism_create_chart(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Describe a chart for: {inp.get('data_description', '')}\n"
        f"Chart type: {inp.get('chart_type', 'auto-select')}\n"
        "Describe what the chart would look like: axes, labels, key data points, annotations.",
        system="You are a data visualization expert. Describe the chart verbally since this is a meeting. "
               "Suggest the best chart type if not specified. 3-4 sentences.",
    )


async def _prism_statistical_analysis(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Statistical analysis: {inp.get('question', '')}\n"
        f"Data source: {inp.get('data_source', 'not specified')}",
        system="You are a statistician who explains things in plain English. "
               "Include the key statistical finding and what it means practically. Spoken format.",
    )


async def _prism_trend_detection(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Trend analysis for metric: {inp.get('metric', '')}\n"
        f"Time range: {inp.get('time_range', 'recent')}",
        system="You are a trend analyst. Describe: direction, any change points, seasonality, "
               "and short-term forecast. Be specific. Spoken format.",
    )


async def _prism_anomaly_detection(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Check for anomalies in: {inp.get('metric', '')}",
        system="You are a data quality analyst. Describe any anomalies, "
               "possible explanations, and whether they need attention. Spoken format.",
    )


async def _prism_forecast(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Forecast: {inp.get('metric', '')} for {inp.get('horizon', 'next quarter')}\n"
        "Include best/likely/worst case with key assumptions.",
        system="You are a forecasting analyst. Be clear about assumptions and confidence. "
               "Give a range, not just a point estimate. Spoken format.",
    )


async def _prism_cohort(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Cohort analysis by: {inp.get('cohort_type', '')}\n"
        f"Metric: {inp.get('metric', 'retention')}",
        system="You are a growth analyst. Describe cohort patterns, which cohorts perform best, "
               "and what drives the differences. Spoken format.",
    )


async def _prism_funnel(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Funnel analysis for: {inp.get('funnel', '')}",
        system="You are a conversion analyst. Describe each step, drop-off rates, "
               "and the biggest opportunity for improvement. Spoken format.",
    )


async def _prism_ab_test(inp: dict, **ctx) -> str:
    test = inp.get("test_name", "")
    control = inp.get("control_rate", "")
    variant = inp.get("variant_rate", "")
    prompt = f"A/B test: {test}"
    if control and variant:
        prompt += f"\nControl: {control}, Variant: {variant}"
    return await _llm_analyze(
        prompt,
        system="You are an experimentation analyst. Assess statistical significance, "
               "practical significance, and recommendation. Note if sample size is sufficient. Spoken format.",
    )


async def _prism_metric_definition(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Define the metric: {inp.get('metric', '')}\n"
        "How is it calculated? What are the caveats? What's a good benchmark?",
        system="You are a metrics specialist. Give a clear definition, formula, "
               "common pitfalls, and industry benchmarks. Spoken format.",
    )


async def _prism_data_quality(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Data quality check for: {inp.get('dataset', '')}",
        system="You are a data quality analyst. Check for: nulls, duplicates, outliers, "
               "freshness, and schema issues. Prioritize by business impact. Spoken format.",
    )


async def _prism_dashboard(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Executive dashboard summary. Focus: {inp.get('focus', 'overall business health')}",
        system="You are a business analyst presenting to executives. "
               "Cover the 3-5 most important metrics, their trend, and one key insight. Spoken format.",
    )


# ── ECHO executors ────────────────────────────────────────────────────────────

async def _echo_search_meetings(inp: dict, **ctx) -> str:
    query = inp.get("query", "")
    results = await _search_transcripts(ctx.get("org_id"), query, limit=5)
    decisions = await _search_decisions(ctx.get("org_id"), query, limit=3)

    parts = []
    if results:
        parts.append("From transcripts:")
        for r in results:
            parts.append(f"  {r['date']} — {r['speaker']}: \"{r['text']}\"")
    if decisions:
        parts.append("Related decisions:")
        for d in decisions:
            parts.append(f"  {d['date']}: {d['statement']} [{d['status']}]")
    return "\n".join(parts) if parts else f"Nothing found matching '{query}'."


async def _echo_find_decision(inp: dict, **ctx) -> str:
    topic = inp.get("topic", "")
    decisions = await _search_decisions(ctx.get("org_id"), topic, limit=3)
    if not decisions:
        return f"No decision found about '{topic}'."
    lines = []
    for d in decisions:
        lines.append(f"Decision ({d['date']}): {d['statement']}")
        if d['rationale']:
            lines.append(f"  Rationale: {d['rationale']}")
        lines.append(f"  Status: {d['status']}")
    return "\n".join(lines)


async def _echo_trace_topic(inp: dict, **ctx) -> str:
    topic = inp.get("topic", "")
    transcripts = await _search_transcripts(ctx.get("org_id"), topic, limit=8)
    decisions = await _search_decisions(ctx.get("org_id"), topic, limit=5)

    if not transcripts and not decisions:
        return f"No history found for '{topic}'."

    parts = [f"History of '{topic}':"]
    all_items = []
    for t in transcripts:
        all_items.append(f"  {t['date']} — {t['speaker']}: \"{t['text'][:100]}\"")
    for d in decisions:
        all_items.append(f"  {d['date']} — DECISION: {d['statement'][:100]}")
    parts.extend(all_items[:8])
    return "\n".join(parts)


async def _echo_who_said_what(inp: dict, **ctx) -> str:
    search = inp.get("search_text", "")
    speaker_filter = inp.get("speaker", "")
    results = await _search_transcripts(ctx.get("org_id"), search, limit=5)
    if speaker_filter:
        results = [r for r in results if speaker_filter.lower() in r["speaker"].lower()]
    if not results:
        return f"No matches for '{search}'" + (f" by {speaker_filter}" if speaker_filter else "") + "."
    lines = [f"  {r['date']} — {r['speaker']}: \"{r['text']}\"" for r in results]
    return "Found:\n" + "\n".join(lines)


async def _echo_find_commitment(inp: dict, **ctx) -> str:
    person = inp.get("person", "")
    topic = inp.get("topic", "")
    query = person or topic or "commitment"
    # Search action items as proxy for commitments
    if not ctx.get("org_id"):
        return "No organization context."
    from gneva.db import async_session_factory
    from gneva.models.entity import ActionItem
    from sqlalchemy import select

    async with async_session_factory() as session:
        q = select(ActionItem).where(
            ActionItem.org_id == uuid.UUID(ctx["org_id"]),
            ActionItem.description.ilike(f"%{_escape_like(query)}%"),
        ).order_by(ActionItem.created_at.desc()).limit(5)
        result = await session.execute(q)
        items = result.scalars().all()

    if not items:
        return f"No commitments found for '{query}'."
    lines = [f"  - {it.description[:100]} [{it.status}]" for it in items]
    return "Commitments found:\n" + "\n".join(lines)


async def _echo_knowledge_graph(inp: dict, **ctx) -> str:
    entity = inp.get("entity", "")
    results = await _search_entities(ctx.get("org_id"), entity)
    if not results:
        return f"No information found for '{entity}'."
    parts = []
    for e in results:
        parts.append(f"{e['type'].title()}: {e['name']}")
        if e['description']:
            parts.append(f"  {e['description']}")
        if e['relationships']:
            rels = ", ".join(r['type'] for r in e['relationships'])
            parts.append(f"  Relationships: {rels}")
    return "\n".join(parts)


async def _echo_meeting_diff(inp: dict, **ctx) -> str:
    topic = inp.get("topic", "")
    results = await _search_transcripts(ctx.get("org_id"), topic, limit=10)
    if len(results) < 2:
        return f"Not enough meeting data to compare for '{topic}'."
    return await _llm_analyze(
        f"Topic: {topic}\n\nMeeting mentions:\n" +
        "\n".join(f"{r['date']} — {r['speaker']}: {r['text']}" for r in results),
        system="You are an organizational historian. Compare what was said across these meetings. "
               "What changed? What stayed the same? Any reversals? Spoken format, 3-5 sentences.",
    )


async def _echo_tribal_knowledge(inp: dict, **ctx) -> str:
    question = inp.get("question", "")
    transcripts = await _search_transcripts(ctx.get("org_id"), question, limit=5)
    if not transcripts:
        return f"No tribal knowledge found for '{question}'."
    context = "\n".join(f"{t['speaker']}: {t['text']}" for t in transcripts)
    return await _llm_analyze(
        f"Question: {question}\n\nRelevant meeting excerpts:\n{context}",
        system="You are an organizational memory expert. Synthesize the tribal knowledge from these "
               "meeting excerpts into a clear answer. Note where info might be outdated. Spoken format.",
    )


async def _echo_decision_reversals(inp: dict, **ctx) -> str:
    topic = inp.get("topic", "decision")
    decisions = await _search_decisions(ctx.get("org_id"), topic, limit=10)
    reversed_decisions = [d for d in decisions if d["status"] in ("reversed", "superseded")]
    if not reversed_decisions:
        return "No reversed or superseded decisions found."
    lines = [f"  {d['date']}: {d['statement']} [{d['status']}]" for d in reversed_decisions]
    return "Reversed/superseded decisions:\n" + "\n".join(lines)


async def _echo_institutional_memory(inp: dict, **ctx) -> str:
    practice = inp.get("practice", "")
    transcripts = await _search_transcripts(ctx.get("org_id"), practice, limit=8)
    decisions = await _search_decisions(ctx.get("org_id"), practice, limit=5)
    if not transcripts and not decisions:
        return f"No origin story found for '{practice}'."

    context_parts = []
    if decisions:
        context_parts.append("Decisions: " + "; ".join(d["statement"][:80] for d in decisions))
    if transcripts:
        context_parts.append("Discussions: " + "; ".join(
            f"{t['speaker']}: {t['text'][:80]}" for t in transcripts[:5]
        ))

    return await _llm_analyze(
        f"Why does the team do: '{practice}'?\n\nHistorical context:\n" + "\n".join(context_parts),
        system="You are an organizational historian. Trace back to the original reason. "
               "Be honest if the trail goes cold. Spoken format, 3-5 sentences.",
    )


async def _echo_relationship_map(inp: dict, **ctx) -> str:
    person = inp.get("person", "")
    entities = await _search_entities(ctx.get("org_id"), person, entity_type="person")
    if not entities:
        return f"No relationship data found for '{person}'."
    e = entities[0]
    parts = [f"{e['name']}:"]
    if e["description"]:
        parts.append(f"  Role: {e['description']}")
    if e["relationships"]:
        parts.append(f"  Connected to: {', '.join(r['type'] for r in e['relationships'])}")
    return "\n".join(parts)


async def _echo_new_hire_context(inp: dict, **ctx) -> str:
    topic = inp.get("topic", "")
    depth = inp.get("depth", "brief")
    transcripts = await _search_transcripts(ctx.get("org_id"), topic, limit=8 if depth == "detailed" else 4)
    decisions = await _search_decisions(ctx.get("org_id"), topic, limit=5)

    context_parts = []
    if decisions:
        context_parts.extend(f"Decision: {d['statement']}" for d in decisions)
    if transcripts:
        context_parts.extend(f"{t['speaker']}: {t['text'][:100]}" for t in transcripts)

    if not context_parts:
        return f"No background found for '{topic}'."

    return await _llm_analyze(
        f"Explain '{topic}' for a new hire.\n\nContext:\n" + "\n".join(context_parts),
        system="You are onboarding a new team member. Explain the history, current state, "
               "and key people involved. Be welcoming and clear. "
               f"{'Detailed explanation, 5-8 sentences.' if depth == 'detailed' else '3-4 sentences.'}",
    )


# ── SAGE executors ────────────────────────────────────────────────────────────

async def _sage_talk_time(inp: dict, **ctx) -> str:
    transcript = ctx.get("transcript_buffer") or []
    if not transcript:
        return "No transcript data available for talk time analysis."
    speakers: dict[str, int] = {}
    for seg in transcript:
        sp = seg.get("speaker", "unknown")
        speakers[sp] = speakers.get(sp, 0) + len(seg.get("text", "").split())

    total = sum(speakers.values()) or 1
    lines = []
    for sp, words in sorted(speakers.items(), key=lambda x: -x[1]):
        pct = round(100 * words / total)
        lines.append(f"  {sp}: {pct}% ({words} words)")
    return "Talk time breakdown:\n" + "\n".join(lines)


async def _sage_engagement_score(inp: dict, **ctx) -> str:
    transcript = ctx.get("transcript_buffer") or []
    if not transcript:
        return "No transcript data for engagement analysis."
    speakers = set(seg.get("speaker", "") for seg in transcript)
    questions = sum(1 for seg in transcript if "?" in seg.get("text", ""))
    total_segs = len(transcript)

    score = min(100, int((len(speakers) * 15) + (questions * 5) + (total_segs * 0.5)))
    return (f"Engagement score: {score}/100. "
            f"{len(speakers)} participants, {questions} questions asked, "
            f"{total_segs} speaking turns.")


async def _sage_meeting_effectiveness(inp: dict, **ctx) -> str:
    transcript_text = _get_transcript_text(ctx.get("transcript_buffer"), last_n=50)
    return await _llm_analyze(
        f"Assess this meeting's effectiveness:\n{transcript_text}",
        system="You are a meeting coach. Score effectiveness on: decisions made, "
               "action items generated, topics resolved, participation balance. "
               "Give a score out of 10 and one specific suggestion. Spoken format, 3-4 sentences.",
    )


async def _sage_suggest_agenda(inp: dict, **ctx) -> str:
    meeting_type = inp.get("meeting_type", "general")
    # Pull open items for context
    org_id = ctx.get("org_id")
    items_text = ""
    if org_id:
        from gneva.db import async_session_factory
        from gneva.models.entity import ActionItem
        from sqlalchemy import select
        async with async_session_factory() as session:
            result = await session.execute(
                select(ActionItem)
                .where(ActionItem.org_id == uuid.UUID(org_id),
                       ActionItem.status.in_(["open", "in_progress"]))
                .limit(10)
            )
            items = result.scalars().all()
            if items:
                items_text = "Open items:\n" + "\n".join(f"- {it.description[:80]}" for it in items)

    return await _llm_analyze(
        f"Generate agenda for a {meeting_type} meeting.\n{items_text}",
        system="You are a meeting facilitator. Create a focused agenda with time allocations. "
               "Prioritize by urgency. Include an 'any other business' slot. Spoken format.",
    )


async def _sage_off_topic(inp: dict, **ctx) -> str:
    original = inp.get("original_topic", "")
    transcript_text = _get_transcript_text(ctx.get("transcript_buffer"), last_n=10)
    return await _llm_analyze(
        f"Original topic: {original}\n\nRecent discussion:\n{transcript_text}\n\n"
        "Is the discussion on topic? If drifted, suggest a redirect.",
        system="You are a meeting facilitator. Assess topic drift diplomatically. "
               "If off topic, suggest a gentle redirect. Spoken format, 2-3 sentences.",
    )


async def _sage_energy_check(inp: dict, **ctx) -> str:
    transcript_text = _get_transcript_text(ctx.get("transcript_buffer"), last_n=10)
    return await _llm_analyze(
        f"Assess meeting energy from this recent exchange:\n{transcript_text}",
        system="You are a meeting coach. Assess: energy level (high/medium/low), "
               "sentiment (positive/neutral/negative), any tension. "
               "Suggest one action if energy is low. Spoken format, 2-3 sentences.",
    )


async def _sage_parking_lot(inp: dict, **ctx) -> str:
    topic = inp.get("topic", "")
    raised_by = inp.get("raised_by", "someone")
    # Store as a GnevaMessage with channel="parking_lot"
    org_id = ctx.get("org_id")
    meeting_id = ctx.get("meeting_id")
    if org_id and meeting_id:
        try:
            from gneva.db import async_session_factory
            from gneva.models.entity import GnevaMessage
            async with async_session_factory() as session:
                msg = GnevaMessage(
                    org_id=uuid.UUID(org_id),
                    meeting_id=uuid.UUID(meeting_id),
                    channel="parking_lot",
                    direction="system",
                    content=topic,
                    metadata_json={"raised_by": raised_by},
                )
                session.add(msg)
                await session.commit()
        except Exception as e:
            logger.debug(f"Failed to persist parking lot item: {e}")
    return f"Parked: '{topic}' (raised by {raised_by}). We'll come back to this."


async def _sage_meeting_patterns(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Analyze meeting patterns. Time range: {inp.get('time_range', 'recent')}",
        system="You are a meeting analytics expert. Discuss: frequency, average duration, "
               "types of meetings, time-in-meetings trends, and one recommendation. Spoken format.",
    )


async def _sage_facilitation_move(inp: dict, **ctx) -> str:
    situation = inp.get("situation", "")
    return await _llm_analyze(
        f"Meeting situation: {situation}\nSuggest a facilitation technique.",
        system="You are an expert meeting facilitator. For the given situation, suggest: "
               "1) A specific technique, 2) Exact words to say, 3) What outcome to expect. "
               "Spoken format, 3-4 sentences. Be practical, not theoretical.",
    )


async def _sage_retrospective(inp: dict, **ctx) -> str:
    transcript_text = _get_transcript_text(ctx.get("transcript_buffer"), last_n=50)
    return await _llm_analyze(
        f"Generate a meeting retrospective from this transcript:\n{transcript_text}",
        system="You are a meeting coach. Structure as: what went well, what could improve, "
               "one specific action for next time. Be constructive. Spoken format, 4-5 sentences.",
    )


async def _sage_decision_forcing(inp: dict, **ctx) -> str:
    topic = inp.get("topic", "")
    options = inp.get("options", "")
    prompt = f"Topic the group is stuck on: {topic}"
    if options:
        prompt += f"\nKnown options: {options}"
    return await _llm_analyze(
        prompt,
        system="You are a facilitator forcing a decision. Present the options clearly with "
               "pros/cons, propose a default, and frame the decision. "
               "Spoken format, 3-5 sentences. End with a call for decision.",
    )


async def _sage_meeting_cost(inp: dict, **ctx) -> str:
    count = inp.get("attendee_count", 5)
    avg_salary = inp.get("avg_salary", 120000)
    transcript = ctx.get("transcript_buffer") or []
    duration_min = len(transcript) * 0.5  # rough estimate: ~0.5 min per segment
    if duration_min < 5:
        duration_min = 30  # fallback

    hourly = avg_salary / 2080  # work hours per year
    cost = round(hourly * count * (duration_min / 60), 2)
    return (f"This meeting costs roughly ${cost:.0f} "
            f"({count} people, ~{duration_min:.0f} minutes, "
            f"at ~${hourly:.0f}/hr average).")


# ── NEXUS executors ───────────────────────────────────────────────────────────

async def _nexus_crm_lookup(inp: dict, **ctx) -> str:
    query = inp.get("query", "")
    # Search entities for customer/company data
    entities = await _search_entities(ctx.get("org_id"), query)
    if entities:
        parts = []
        for e in entities:
            parts.append(f"{e['type'].title()}: {e['name']}")
            if e['description']:
                parts.append(f"  {e['description']}")
        return "From organizational memory:\n" + "\n".join(parts)
    return f"No CRM data found for '{query}'. CRM integration not yet configured."


async def _nexus_deal_status(inp: dict, **ctx) -> str:
    deal = inp.get("deal", "")
    return await _llm_analyze(
        f"Provide a deal status assessment for: {deal}",
        system="You are a sales analyst. Assess: deal stage, velocity, probability, "
               "key blockers, and next action. If you lack specifics, describe what to check. "
               "Spoken format, 3-4 sentences.",
    )


async def _nexus_customer_history(inp: dict, **ctx) -> str:
    customer = inp.get("customer", "")
    transcripts = await _search_transcripts(ctx.get("org_id"), customer, limit=5)
    entities = await _search_entities(ctx.get("org_id"), customer)
    if not transcripts and not entities:
        return f"No history found for '{customer}'."
    parts = []
    if entities:
        for e in entities:
            parts.append(f"{e['name']}: {e['description']}")
    if transcripts:
        parts.append("Meeting mentions:")
        for t in transcripts:
            parts.append(f"  {t['date']} — {t['speaker']}: {t['text'][:100]}")
    return "\n".join(parts)


async def _nexus_competitive_positioning(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Competitive positioning vs {inp.get('competitor', '')}.\n"
        f"Customer context: {inp.get('customer_context', 'general')}",
        system="You are a competitive intelligence analyst for sales. "
               "Give 3-4 key differentiators and how to position against this competitor. "
               "Be specific to the customer's situation. Spoken format.",
    )


async def _nexus_proposal_draft(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Draft proposal outline for {inp.get('customer', '')}.\n"
        f"Scope: {inp.get('scope', '')}",
        system="You are a sales operations specialist. Draft a proposal outline: "
               "executive summary, scope, timeline, pricing structure, terms. "
               "Keep it high-level for meeting discussion. Spoken format, 5-6 sentences.",
        max_tokens=400,
    )


async def _nexus_follow_up(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Draft follow-up for: {inp.get('recipient', '')}.\n"
        f"Context: {inp.get('context', '')}",
        system="You are a sales professional. Draft a follow-up email: "
               "thank them, recap key points, list next steps, include timeline. "
               "Professional but warm. 4-6 sentences.",
        max_tokens=300,
    )


async def _nexus_sentiment(inp: dict, **ctx) -> str:
    customer = inp.get("customer", "")
    transcripts = await _search_transcripts(ctx.get("org_id"), customer, limit=5)
    if not transcripts:
        return f"No interaction data to assess sentiment for '{customer}'."
    context = "\n".join(f"{t['speaker']}: {t['text']}" for t in transcripts)
    return await _llm_analyze(
        f"Assess customer sentiment for {customer} from these interactions:\n{context}",
        system="You are a customer intelligence analyst. Assess overall sentiment: "
               "positive/neutral/negative, trend, and key signals. Spoken format, 3-4 sentences.",
    )


async def _nexus_objection_response(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Sales objection: \"{inp.get('objection', '')}\"",
        system="You are a sales coach. Provide 2-3 response options: "
               "one empathetic, one evidence-based, one reframing. "
               "Include specific talking points. Spoken format.",
    )


async def _nexus_champion_map(inp: dict, **ctx) -> str:
    account = inp.get("account", "")
    entities = await _search_entities(ctx.get("org_id"), account, entity_type="person")
    if entities:
        parts = [f"Known contacts at {account}:"]
        for e in entities:
            role = e.get("description", "unknown role")
            parts.append(f"  - {e['name']}: {role}")
        return "\n".join(parts)
    return f"No contact data found for '{account}'. Map champions manually from this call."


async def _nexus_contract_risk(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Flag contract risks for deal: {inp.get('deal', '')}\n"
        f"Concerns: {inp.get('concerns', 'general review')}",
        system="You are a deal desk analyst. Flag top 3 risky terms and compare to market standard. "
               "Suggest negotiation approach. Spoken format, 3-4 sentences.",
    )


async def _nexus_win_loss(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Win/loss analysis. Segment: {inp.get('segment', 'all')}",
        system="You are a sales analyst. Identify top 3 reasons we win and top 3 reasons we lose. "
               "Include specific patterns and recommendations. Spoken format.",
    )


async def _nexus_upsell(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Identify upsell opportunities for: {inp.get('customer', '')}",
        system="You are a customer expansion specialist. Identify 2-3 expansion opportunities "
               "based on typical usage patterns. Include approach and timing. Spoken format.",
    )


async def _nexus_renewal_risk(inp: dict, **ctx) -> str:
    return await _llm_analyze(
        f"Renewal risk assessment for: {inp.get('customer', '')}",
        system="You are a customer retention analyst. Assess renewal probability, "
               "top 3 risk factors, and recommended save plays. Spoken format, 3-4 sentences.",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Executor registry — maps tool_name -> async executor
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_EXECUTORS = {
    # Vex
    "analyze_market": _vex_analyze_market,
    "competitor_lookup": _vex_competitor_lookup,
    "swot_analysis": _vex_swot,
    "strategic_recommendation": _vex_strategic_recommendation,
    "risk_assessment": _vex_risk_assessment,
    "scenario_model": _vex_scenario_model,
    "framework_apply": _vex_framework,
    "decision_log_query": _vex_decision_log,
    "strategy_contradiction_check": _vex_contradiction_check,
    "okr_alignment_check": _vex_okr_check,
    # Prism
    "query_database": _prism_query_database,
    "create_chart": _prism_create_chart,
    "statistical_analysis": _prism_statistical_analysis,
    "trend_detection": _prism_trend_detection,
    "anomaly_detection": _prism_anomaly_detection,
    "forecast": _prism_forecast,
    "cohort_analysis": _prism_cohort,
    "funnel_analysis": _prism_funnel,
    "ab_test_analysis": _prism_ab_test,
    "metric_definition": _prism_metric_definition,
    "data_quality_check": _prism_data_quality,
    "executive_dashboard": _prism_dashboard,
    # Echo
    "search_all_meetings": _echo_search_meetings,
    "find_decision": _echo_find_decision,
    "trace_topic_history": _echo_trace_topic,
    "who_said_what": _echo_who_said_what,
    "find_commitment": _echo_find_commitment,
    "org_knowledge_graph": _echo_knowledge_graph,
    "meeting_diff": _echo_meeting_diff,
    "tribal_knowledge_search": _echo_tribal_knowledge,
    "decision_reversal_log": _echo_decision_reversals,
    "institutional_memory": _echo_institutional_memory,
    "relationship_map": _echo_relationship_map,
    "context_for_new_hire": _echo_new_hire_context,
    # Sage
    "talk_time_analysis": _sage_talk_time,
    "engagement_score": _sage_engagement_score,
    "meeting_effectiveness": _sage_meeting_effectiveness,
    "suggest_agenda": _sage_suggest_agenda,
    "detect_going_off_topic": _sage_off_topic,
    "energy_check": _sage_energy_check,
    "parking_lot": _sage_parking_lot,
    "meeting_pattern_analysis": _sage_meeting_patterns,
    "facilitation_move": _sage_facilitation_move,
    "retrospective_guide": _sage_retrospective,
    "decision_forcing": _sage_decision_forcing,
    "meeting_cost_calculator": _sage_meeting_cost,
    # Nexus
    "crm_lookup": _nexus_crm_lookup,
    "deal_status": _nexus_deal_status,
    "customer_history": _nexus_customer_history,
    "competitive_positioning": _nexus_competitive_positioning,
    "proposal_draft": _nexus_proposal_draft,
    "follow_up_sequence": _nexus_follow_up,
    "sentiment_toward_us": _nexus_sentiment,
    "objection_response": _nexus_objection_response,
    "champion_map": _nexus_champion_map,
    "contract_risk_flags": _nexus_contract_risk,
    "win_loss_analysis": _nexus_win_loss,
    "upsell_opportunity": _nexus_upsell,
    "renewal_risk": _nexus_renewal_risk,
}
