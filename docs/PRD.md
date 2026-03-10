# Gneva — Product Requirements Document

**Version:** 1.0
**Date:** 2026-03-10
**Author:** Solo Founder
**Status:** Draft

---

## Executive Summary

Gneva is an AI team member that joins meetings, builds organizational memory, and evolves from a silent observer into an active participant and autonomous PM. Unlike existing meeting tools that treat each meeting as an isolated event, Gneva builds a persistent knowledge graph connecting people, projects, decisions, and action items across every conversation over time.

The name "Gneva" evokes Geneva — the city of diplomacy, neutrality, and trust — reflecting the product's role as a trusted, impartial team member that facilitates collaboration and guards organizational knowledge.

---

## The Problem

**For teams:**
- Institutional knowledge walks out the door when people leave
- Decisions get re-litigated because no one remembers what was decided
- New team members take months to absorb organizational context
- Meetings are isolated events — no cross-meeting intelligence
- Action items fall through the cracks between meetings

**For managers:**
- 15+ meetings/week with no way to track decisions across them
- Context-switching between projects with no persistent memory
- Can't be in every meeting, miss critical context
- No visibility into meeting culture health

**Current solutions fail because:**
- Meeting notetakers (Otter, Fireflies, Fathom) produce per-meeting summaries but no organizational memory
- Knowledge tools (Notion, Confluence) require manual input and go stale
- Revenue intelligence (Gong, Chorus) only works for sales
- Platform tools (Copilot, Gemini) are walled-garden, no cross-platform memory
- **No product combines persistent org memory with active meeting participation**

---

## The Solution

Gneva is not a tool — it's a team member that learns. It grows through 5 stages:

| Stage | Persona | Capability |
|-------|---------|------------|
| 1. Silent Observer | "I noticed" | Joins meetings, transcribes, builds memory silently |
| 2. Post-Meeting Analyst | "Here's what happened" | Summaries, action items, pre-meeting briefs, pattern detection |
| 3. Async Team Member | "Let me help" | @Gneva in Slack/Teams, answers from organizational memory |
| 4. Active Participant | "Can I add something?" | Voice in meetings, surfaces context, flags contradictions |
| 5. Autonomous PM | "I'll handle it" | Proactive management, represents absent members, owns follow-ups |

Each stage builds trust before unlocking the next. Users control the pace.

---

## Market Opportunity

- **TAM:** $42B (workplace AI)
- **SAM:** $3.0-3.5B (AI meeting assistants, 25-35% CAGR)
- **SOM:** $50-100M (teams wanting organizational memory + active AI)

### Competitive Position

```
                    PASSIVE                          ACTIVE
                    (Records only)                   (Participates)
                    |                                |
   INDIVIDUAL -----+--------------------------------+------
                    | Otter, Fireflies, Fathom,      | (empty)
                    | Granola, Krisp, tl;dv           |
                    |                                |
   TEAM -----------+--------------------------------+------
                    | Fellow, Grain, Avoma           | (empty)
                    | Read.ai                        |
                    |                                |
   ORG-WIDE -------+--------------------------------+------
                    | Gong, Chorus (sales only)      | ** GNEVA **
                    | Microsoft Copilot, Gemini      |
                    | (platform-locked)              |
                    |                                |
```

Gneva occupies the only empty quadrant: **Organization-wide + Active participation.**

---

## Key Differentiators

1. **Organizational Memory** — Not per-meeting notes, but a knowledge graph that connects entities across all meetings over time
2. **Voice Participation** — No competitor offers an AI that speaks in meetings (genuinely novel)
3. **Growth Stages** — Builds trust progressively, not an overwhelming feature dump on day one
4. **Cross-Platform** — Works across Zoom, Teams, Meet, Slack — not walled-garden
5. **On-Premise Option** — Unlocks regulated verticals (healthcare, finance, government)

---

## Pricing

| Tier | Price | Target | Includes |
|------|-------|--------|----------|
| **Free** | $0 | Individual try | 5 meetings/month, basic summaries |
| **Pro** | $29/mo | Power user | Unlimited meetings, full memory, @Gneva chat |
| **Team** | $49/user/mo | Teams 5-50 | Org memory, team insights, Slack integration |
| **Enterprise** | $79+/user/mo | Org 50+ | Voice participation, on-prem, SSO/SAML |

**Unit economics:** ~$1.85/user/month cost, 78-92% gross margins.

---

## PRD Document Index

This PRD is structured across 5 companion documents:

| Document | Description |
|----------|-------------|
| [Competitive Analysis](competitive-analysis.md) | Market landscape, 30+ competitors, 6 strategic gaps |
| [Technical Architecture](technical-architecture.md) | System design, database schema, API, deployment |
| [Security Architecture](security-architecture.md) | Encryption, auth, compliance, threat model, on-prem |
| [Product Design & UX](product-design.md) | Personas, user journeys, screens, @Gneva interactions |
| [GTM & Business Strategy](gtm-strategy.md) | Market sizing, pricing, financials, roadmap |

---

## MVP Scope (Stage 1: Silent Observer)

**Timeline:** 8-10 weeks

**In scope:**
- Calendar integration (Google Calendar, Outlook)
- Meeting bot joins via Recall.ai (Zoom, Teams, Meet)
- Real-time transcription with speaker diarization
- Post-meeting summary generation (Claude API)
- Entity extraction: people, decisions, action items, topics
- Knowledge graph storage (PostgreSQL + pgvector)
- Web dashboard: meeting feed, search, knowledge explorer
- Basic @Gneva query interface
- User authentication (email + password, Google OAuth)

**Out of scope for MVP:**
- Voice participation (Stage 4)
- Slack/Teams integration (Stage 3)
- On-premise deployment
- Team/org features
- Advanced analytics

---

## Success Metrics

### MVP (Month 3)
- 50 beta users
- 500+ meetings processed
- >80% summary accuracy rating
- <5 min processing time per meeting

### Growth (Month 6)
- 500 users, 50 paying
- $1,500 MRR
- NPS > 40
- 3+ meetings/user/week average

### Scale (Month 12)
- 5,000 users, 500 paying
- $20K+ MRR
- Voice participation beta launched
- First enterprise pilot

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Recording consent laws vary by jurisdiction | Legal/regulatory | Two-party consent engine, clear notifications, per-org policies |
| Meeting platform API changes | Technical | Recall.ai abstracts platform differences; fallback to desktop recording |
| AI hallucination in summaries | Trust | Always link to source transcript, confidence scores, user corrections |
| Privacy breach | Existential | Envelope encryption, per-tenant keys, SOC2 from day 1 |
| Read.ai adds voice features | Competitive | Move fast, lock in org memory moat before they pivot |
| User resistance to AI in meetings | Adoption | Growth stages build trust gradually; always opt-in |

---

## Decision Log

| Decision | Rationale | Date |
|----------|-----------|------|
| PostgreSQL + pgvector over Neo4j | Single DB simplifies ops, pgvector good enough for MVP, can add Neo4j later | 2026-03-10 |
| Recall.ai over direct platform APIs | Saves months of integration work, Desktop SDK for bot-free option | 2026-03-10 |
| Claude API over OpenAI | Better at structured extraction, reasoning over long context | 2026-03-10 |
| FastAPI + React over Next.js | Separate backend enables future mobile/API clients | 2026-03-10 |
| Bootstrap over fundraise | Margins support it, maintain control, prove PMF first | 2026-03-10 |
| Growth stages over feature dump | Build trust progressively, reduce adoption friction | 2026-03-10 |
