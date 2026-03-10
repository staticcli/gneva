# Ggneva

**AI team member that joins your meetings, builds organizational memory, and grows from silent observer to active participant.**

## What is Ggneva?

Ggneva is not another meeting notetaker. It's a team member that learns. It joins your meetings, builds a knowledge graph connecting people, projects, decisions, and action items across every conversation, and grows more capable over time.

### Growth Stages

1. **Silent Observer** — Transcribes, summarizes, builds memory
2. **Post-Meeting Analyst** — Action items, pre-meeting briefs, pattern detection
3. **Async Team Member** — @Ggneva in Slack/Teams, answers from organizational memory
4. **Active Participant** — Voice in meetings, surfaces context, flags contradictions
5. **Autonomous PM** — Proactive management, represents absent members

## Documentation

See [`docs/`](docs/) for the full PRD:

- [PRD Overview](docs/PRD.md)
- [Competitive Analysis](docs/competitive-analysis.md)
- [Technical Architecture](docs/technical-architecture.md)
- [Security Architecture](docs/security-architecture.md)
- [Product Design & UX](docs/product-design.md)
- [GTM & Business Strategy](docs/gtm-strategy.md)

## Tech Stack

- **Backend:** FastAPI (Python)
- **Frontend:** React
- **Database:** PostgreSQL + pgvector
- **Meeting Bots:** Recall.ai
- **Transcription:** faster-whisper / Deepgram
- **Diarization:** pyannote
- **Embeddings:** nomic-embed-text-v1.5
- **LLM:** Claude API
- **Voice:** ElevenLabs (Stage 4+)

## Status

Planning phase. MVP target: 8-10 weeks.
