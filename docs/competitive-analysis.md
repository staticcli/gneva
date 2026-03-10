# Neva Competitive Analysis: AI Meeting Intelligence & Organizational Memory

**Date:** March 10, 2026
**Product Vision:** AI team member that joins meetings, builds organizational memory, and eventually participates with voice.

---

## Market Overview

The AI Meeting Assistants market reached approximately **$3.0-3.5 billion in 2025** and is growing at a **25-35% CAGR**, projected to reach **$72 billion by 2034** (Market.us). The broader AI Agents market is growing at **43.3% annually through 2030** (GlobeNewsWire). Remote/hybrid work adoption continues to fuel demand.

---

## 1. Direct Competitors

### Tier 1: Mass-Market Meeting Notetakers

| Product | Pricing | Core Strength | Key Gap |
|---------|---------|---------------|---------|
| **Otter.ai** | Free / $17/mo Pro / $20/mo Business | Real-time transcription, OtterPilot bot joins meetings automatically | No organizational memory, no voice participation, no cross-meeting intelligence |
| **Fireflies.ai** | Free / $10/mo Pro / $19/mo Business / $39/mo Enterprise | 100+ language support, "Talk to Fireflies" (Perplexity-powered live search), CRM integrations | Hidden AI credit costs, no voice participation, per-meeting silo'd data |
| **Fathom** | Free (unlimited recording) / $15-29/mo paid | Generous free tier (unlimited recordings), 95% accuracy, 30-second summaries | No cross-meeting memory, no organizational knowledge graph, no voice features |
| **Granola.ai** | Free (25 meetings) / $18/mo Individual / $14/user/mo Business | Privacy-first (no bot, captures device audio), 90-92% accuracy, $250M valuation | No bot means no autonomous attendance, no voice participation, no team-wide memory |
| **Krisp** | Free (60 min/day) / from $8/mo | Best-in-class noise cancellation (40dB), local processing, accent conversion | Primarily an audio processing tool, limited meeting intelligence |
| **tl;dv** | Free (unlimited recording) / $24/mo Pro / $48/mo Business | Free unlimited recordings + AI summaries, strong clip/share workflow | No organizational memory, no voice features |
| **MeetGeek** | $15-59/user/mo | 50+ language transcription, engagement metrics, speaker analytics | No voice participation, no knowledge graph |
| **Tactiq** | Free / from $8/mo Pro | Chrome extension simplicity, 30+ languages | Limited to Chrome, no bot, no organizational memory |
| **Sembly AI** | Free / $10/mo Professional | Generates structured business artifacts (project plans, requirements docs) from meetings | No voice participation, no persistent organizational memory |
| **Grain** | $24/user/mo Pro / $48/user/mo Business | Video clip creation from transcripts, CRM auto-sync, team coaching | Sales-focused, no general organizational memory |

### Tier 2: Revenue Intelligence Platforms (Sales-Focused)

| Product | Pricing | Core Strength | Key Gap |
|---------|---------|---------------|---------|
| **Gong.io** | ~$1,300-1,400/user/year + $5K-50K platform fee | Deep sales conversation analytics, deal forecasting, coaching | Extremely expensive, sales-only, no general organizational memory, no voice |
| **Chorus.ai (ZoomInfo)** | $8,000/yr base (3 seats), ~$100/seat/mo additional | Real-time contact enrichment (100M+ contacts), call coaching libraries | Enterprise-only, sales-focused, 2-year lock-in, no voice participation |
| **Avoma** | Modular: Conversation Intel $29/seat/mo, Revenue Intel $39/seat/mo | End-to-end meeting lifecycle (agenda to follow-up), modular pricing | Sales/CS focused, no general organizational memory |

### Tier 3: Meeting Management & Workflow

| Product | Pricing | Core Strength | Key Gap |
|---------|---------|---------------|---------|
| **Fellow.app** | $7/mo Pro / $15/mo Business / $25/mo Enterprise | Meeting agendas, templates, action item tracking, HRIS integrations | Workflow tool more than intelligence tool, no voice, no deep AI memory |
| **Read.ai** | Free (5 recordings) / $15/mo Pro / $22.50/mo Enterprise | Cross-platform intelligence (meetings + emails + messages), personal knowledge graph | Closest to organizational memory but still individual-focused, no voice participation |

**Key insight:** Read.ai is the closest competitor to Neva's vision. They connect meetings, emails, messages, and documents into a personal knowledge graph with proactive agents. However, their focus is individual productivity, not team/organizational memory, and they have no voice participation capability.

---

## 2. Adjacent Products

### Platform Giants

| Product | Pricing | What They Do | What They Don't Do |
|---------|---------|-------------|-------------------|
| **Microsoft Copilot for Teams** | Included in M365 Copilot ($30/user/mo) | Customizable recap templates, smart scheduling, upcoming screen content analysis, interactive meeting agents | Locked to Microsoft ecosystem, no cross-platform memory, agents are Q&A not active participants with voice |
| **Google Gemini in Meet** | Business Standard+ plans | "Take notes for me" one-click, Ask Gemini for briefs/catch-ups, multi-language support | Google Workspace only, no cross-platform, no voice participation, no organizational memory across tools |

**Gap:** Both platform giants offer meeting AI only within their walled gardens. Neither builds persistent organizational memory across platforms, and neither offers voice participation.

### Memory & Knowledge Products

| Product | Pricing | What They Do | What They Don't Do |
|---------|---------|-------------|-------------------|
| **Notion AI** | $20/mo Business (AI included) | Workspace-wide AI with GPT-4.1 + Claude 3.7, AI Agents with persistent memory over Notion pages | Text-only memory, no meeting attendance, no audio/voice, requires manual capture |
| **Mem.ai** | ~$10-15/mo | Auto-organizing notes, AI surfaces relevant context | No meeting integration, no audio capture, individual-only |
| **Rewind.ai** | ~$19-20/mo Professional | Records everything on your screen, perfect recall | Privacy concerns (records everything), individual-only, no team memory, no meeting participation |
| **Experio** | Enterprise (custom) | Knowledge graphs for consulting firms, institutional memory preservation | Professional services focused, not a meeting tool |

**Gap:** Memory products don't attend meetings. Meeting products don't build organizational memory. This is the core gap Neva can exploit.

---

## 3. Voice AI Agent Platforms

| Platform | Pricing | Latency | Strength | Limitation |
|----------|---------|---------|----------|------------|
| **ElevenLabs Conversational AI** | $0.10/min, plans from $5/mo | <300ms streaming | Best voice quality, multimodal (voice+text), turn-taking model, HIPAA compliant, git-style agent branching | General-purpose, not meeting-specific |
| **Retell.ai** | $0.07/min | ~600ms (industry-leading for agents) | Lowest latency, transparent pricing, visual builder | Primarily for phone/call center agents |
| **Vapi** | ~$0.05/min base + STT/TTS/LLM costs (3-6x total) | Varies by provider stack | Maximum customization, multi-provider optimization | Complex pricing, high total cost, developer-heavy |
| **Bland.ai** | $0.09/min | avg 800ms, spikes to 2.5s | Simplest integration (10 lines of code), batch calling, CRM routing | Robotic-sounding voices, latency issues |

**Key insight:** Voice AI is mature enough for real-time conversation but NO ONE has applied it to meeting participation. All voice AI platforms focus on phone calls, customer service, and outbound sales. Meeting participation with voice is a completely unoccupied niche.

---

## 4. Infrastructure & Build Components

### Meeting Bot APIs/SDKs

| Platform | Pricing | Capability | Notes |
|----------|---------|-----------|-------|
| **Recall.ai** | $0.50/hr (pay-as-you-go) | Meeting bots for Zoom, Meet, Teams + new Desktop Recording SDK (no visible bot) | Most mature, Series B funded. Desktop SDK is new and eliminates bot visibility friction |
| **Nylas Notetaker API** | Custom pricing | Calendar sync + meeting bots + webhook notifications, unified API across platforms | Reduces integration from months to weeks. Abstracts away Zoom/Teams/Meet differences |
| **Zoom SDK** | Free (with limits) | Direct platform access | No direct live audio API access, complex OAuth, host presence rules |
| **Teams Graph API** | Free (with limits) | Meeting metadata, transcripts (if enabled) | No programmatic recording control, requires Real-time Media Platform for audio |

**Recommendation:** Use **Recall.ai** or **Nylas** rather than building direct platform integrations. Saves months of development. Recall.ai's Desktop Recording SDK could be particularly relevant for Neva's "no visible bot" approach.

### Real-Time Transcription

| Provider | Price/min | Latency | Best For |
|----------|-----------|---------|----------|
| **Deepgram** | $0.0125/min | <300ms | Real-time streaming, lowest latency |
| **AssemblyAI** | $0.0025/min ($0.15/hr) | Moderate | Batch + audio intelligence (diarization, entity detection, summarization) |
| **Rev.ai** | $0.002/min (Standard) | Moderate | Lowest cost entry point |
| **OpenAI Whisper** | Free (local) | Varies (not real-time native) | On-premise/privacy, needs engineering for real-time |

**Recommendation:** **Deepgram** for real-time meeting transcription (latency matters for voice participation). **Whisper** for on-prem/privacy-sensitive deployments. AssemblyAI if you need rich audio intelligence features on top of transcription.

### Voice Synthesis (TTS)

| Provider | Pricing | Latency | Quality | Notes |
|----------|---------|---------|---------|-------|
| **ElevenLabs** | $0.10/min conversational, plans from $5/mo | <300ms streaming | Industry-leading naturalness | Conversational AI 2.0 with turn-taking model |
| **Cartesia** | ~1/5th ElevenLabs cost | Competitive | Good quality | Best cost-performance ratio |
| **PlayHT** | Custom | Moderate | Good | API-first approach |
| **Local TTS (Coqui/XTTS)** | Free | Depends on hardware | Moderate-Good | Full privacy, no API dependency |

**Recommendation:** **ElevenLabs** for best voice quality and conversational features. **Cartesia** for cost optimization at scale. Local TTS for on-prem enterprise customers.

---

## 5. Feature Matrix: What Exists vs. What Doesn't

| Capability | Who Does It | Who Doesn't |
|-----------|-------------|-------------|
| Meeting recording & transcription | Everyone | - |
| AI summaries & action items | Everyone | - |
| CRM integration | Gong, Chorus, Fireflies, Grain, Avoma | Granola, Krisp, Tactiq |
| Cross-meeting search | Most tools | - |
| Cross-platform intelligence (meetings + email + docs) | Read.ai only | Everyone else |
| Organizational/team knowledge graph | **Nobody fully** | Everyone |
| Persistent institutional memory | **Nobody** | Everyone |
| Voice participation in meetings | **Nobody** | Everyone |
| Bot-free capture (device audio) | Granola, Krisp, Recall Desktop SDK | Most use visible bots |
| On-premise deployment | **Almost nobody** | Nearly everyone is cloud-only |
| Proactive insights surfacing | Read.ai (limited), Copilot | Everyone else |
| Multi-meeting pattern recognition | Gong/Chorus (sales only) | General-purpose tools |

---

## 6. Strategic Gaps Neva Can Exploit

### Gap 1: Organizational Memory (PRIMARY DIFFERENTIATOR)
**Current state:** Every tool treats meetings as isolated events. Summaries are generated per-meeting and dumped into a feed. No tool builds a persistent, evolving knowledge graph of organizational context -- who knows what, what was decided, how decisions evolved, what the team's institutional knowledge is.

**Neva opportunity:** Build a knowledge graph that connects entities (people, projects, decisions, commitments) across all meetings over time. When someone asks "What did we decide about the pricing strategy?" Neva doesn't just search transcripts -- it understands the arc of that discussion across 12 meetings over 3 months.

### Gap 2: Voice Participation (UNIQUE CAPABILITY)
**Current state:** Zero products offer an AI that speaks in meetings. Every tool is a passive observer. Microsoft is experimenting with "interactive agents" in Teams but these are text-based Q&A, not voice participants.

**Neva opportunity:** An AI that can speak up in meetings to provide context ("Last time this came up, the team decided X"), answer questions from organizational memory, or flag inconsistencies ("That contradicts what was agreed in the Q3 planning meeting"). This is genuinely novel.

### Gap 3: Cross-Platform, Cross-Channel Memory
**Current state:** Read.ai is the only tool connecting meetings + email + messages, but it's individual-focused. Platform giants (Microsoft, Google) only work within their ecosystems.

**Neva opportunity:** Team-wide memory that spans Zoom, Teams, Meet, Slack, email, and documents. Platform-agnostic organizational brain.

### Gap 4: On-Premise / Privacy-First Deployment
**Current state:** Nearly every tool is cloud-only. Granola and Krisp process audio locally but still send data to cloud for AI. Enterprise customers in regulated industries (healthcare, finance, government, defense) have no good options.

**Neva opportunity:** Offer hybrid or fully on-premise deployment using local Whisper + local LLM. The tech is now mature enough (Whisper runs on consumer hardware, LLMs run on single GPUs). This unlocks regulated verticals that current competitors can't serve.

### Gap 5: Proactive Intelligence
**Current state:** All tools are reactive -- you ask, they answer. Read.ai and Copilot are starting to surface proactive insights but it's rudimentary.

**Neva opportunity:** Before a meeting, Neva proactively briefs participants: "Here's what was discussed last time, here are the open action items, here's relevant context from other meetings." During a meeting, it flags: "This topic was discussed in 3 previous meetings without resolution."

### Gap 6: Team Dynamics & Meeting Culture
**Current state:** Some tools track speaking time. None provide genuine team dynamics intelligence -- who dominates, who gets interrupted, which meetings are productive vs. ceremonial.

**Neva opportunity:** Ongoing team health metrics and recommendations. "Your sprint planning meetings have 40% more productive time than your status updates. Consider restructuring status updates."

---

## 7. Competitive Positioning Map

```
                    PASSIVE                          ACTIVE
                    (Records only)                   (Participates)
                    |                                |
   INDIVIDUAL -----+--------------------------------+------
                    | Otter, Fireflies, Fathom,      | (empty)
                    | Granola, Krisp, tl;dv,          |
                    | Tactiq, MeetGeek               |
                    |                                |
   TEAM -----------+--------------------------------+------
                    | Fellow, Grain, Avoma           | (empty)
                    | Read.ai                        |
                    |                                |
   ORG-WIDE -------+--------------------------------+------
                    | Gong, Chorus (sales only)      | ** NEVA **
                    | Microsoft Copilot, Gemini      |
                    | (platform-locked)              |
                    |                                |
```

Neva occupies the only empty quadrant: **Organization-wide + Active participation.** No existing product combines persistent organizational memory with voice participation capability.

---

## 8. Recommended Neva Tech Stack

| Layer | Recommended | Alternative | Rationale |
|-------|-------------|-------------|-----------|
| Meeting Access | Recall.ai API ($0.50/hr) | Nylas Notetaker API | Fastest to market, Desktop SDK for bot-free option |
| Real-time STT | Deepgram ($0.0125/min) | Whisper (local, free) | <300ms latency critical for voice participation |
| Voice Synthesis | ElevenLabs Conv AI ($0.10/min) | Cartesia (cheaper) | Best turn-taking model, sub-300ms |
| Knowledge Graph | Neo4j / custom graph DB | PostgreSQL with pgvector | Purpose-built for entity relationships |
| LLM (Cloud) | Claude / GPT-4 | - | Reasoning over organizational context |
| LLM (On-prem) | Llama 3 / Mistral | Qwen | For privacy-sensitive deployments |
| Embeddings | OpenAI / Cohere | Local sentence-transformers | Semantic search over meeting history |

**Estimated per-meeting cost (1hr meeting):**
- Recall.ai: $0.50
- Deepgram: $0.75
- ElevenLabs (5 min participation): $0.50
- LLM processing: ~$0.20
- **Total: ~$1.95/hr meeting**

---

## 9. Go-to-Market Priorities

**Phase 1 - Silent Observer + Memory (Months 1-6)**
- Join meetings via Recall.ai, transcribe via Deepgram
- Build knowledge graph from meeting content
- Cross-meeting search and proactive pre-meeting briefs
- Differentiate on organizational memory alone

**Phase 2 - Text Participation (Months 6-9)**
- Neva posts in meeting chat: context, reminders, relevant past decisions
- Slack/Teams integration for async follow-up
- Meeting culture analytics

**Phase 3 - Voice Participation (Months 9-15)**
- ElevenLabs voice synthesis for spoken contributions
- Start with opt-in moments: "Neva, what did we decide about X?"
- Graduate to proactive voice: flagging contradictions, providing context

**Phase 4 - Full AI Team Member (Months 15+)**
- Attends meetings autonomously, builds and maintains organizational brain
- Can represent absent team members ("Sarah couldn't make it, but she wanted to raise...")
- On-prem deployment option for enterprise

---

## 10. Pricing Strategy Suggestion

| Tier | Price | Includes |
|------|-------|----------|
| **Starter** | $15/user/mo | Meeting transcription + AI summaries + cross-meeting search |
| **Team** | $29/user/mo | Organizational memory + proactive briefs + team analytics |
| **Enterprise** | $49/user/mo | Voice participation + on-prem option + SSO/SAML + custom integrations |
| **Enterprise+** | Custom | Dedicated instance + HIPAA/SOC2 + custom voice persona |

Price positioned between Fireflies Pro ($10) and Gong ($108+), reflecting the unique value of organizational memory + voice.

---

## Sources

- [Otter.ai Pricing](https://otter.ai/pricing)
- [Fireflies.ai Pricing](https://fireflies.ai/pricing)
- [Granola.ai Pricing](https://www.granola.ai/pricing)
- [Read.ai Plans & Pricing](https://www.read.ai/plans-pricing)
- [Fathom Pricing](https://www.fathom.ai/pricing)
- [Gong Pricing](https://www.gong.io/pricing)
- [Avoma Pricing](https://www.avoma.com/pricing)
- [Fellow.ai Pricing](https://fellow.ai/pricing)
- [Krisp Pricing](https://krisp.ai/pricing/)
- [Grain Pricing](https://grain.com/pricing)
- [Chorus.ai Pricing (ZoomInfo)](https://www.zoominfo.com/products/chorus/pricing)
- [Recall.ai Pricing](https://www.recall.ai/pricing)
- [Recall.ai Meeting Bot API](https://www.recall.ai/product/meeting-bot-api)
- [Nylas Notetaker API](https://www.nylas.com/products/notetaker-api/)
- [Deepgram Speech-to-Text APIs Guide](https://deepgram.com/learn/best-speech-to-text-apis-2026)
- [AssemblyAI Real-Time Transcription](https://www.assemblyai.com/blog/best-api-models-for-real-time-speech-recognition-and-transcription)
- [ElevenLabs Conversational AI 2.0](https://elevenlabs.io/blog/conversational-ai-2-0)
- [ElevenLabs vs Cartesia](https://elevenlabs.io/blog/elevenlabs-vs-cartesia)
- [Bland vs Vapi vs Retell Comparison](https://www.whitespacesolutions.ai/content/bland-ai-vs-vapi-vs-retell-comparison)
- [AI Meeting Assistants Market Forecast](https://market.us/report/ai-meeting-assistant-market/)
- [AI Agents Market Growth](https://www.globenewswire.com/news-release/2026/01/05/3213141/0/en/AI-Agents-Market-to-Grow-43-3-Annually-Through-2030.html)
- [Microsoft Teams February 2026 Update](https://techcommunity.microsoft.com/blog/microsoftteamsblog/what%E2%80%99s-new-in-microsoft-teams--february-2026/4497206)
- [Google Gemini in Meet](https://workspace.google.com/solutions/ai/ai-note-taking/)
- [Notion AI Review 2026](https://max-productive.ai/ai-tools/notion-ai/)
- [Jabra: AI as Meeting Participant](https://www.jabra.com/blog/the-future-of-ai-in-the-workplace-ai-as-a-meeting-participant/)
- [Read.ai Knowledge Management Tools](https://www.read.ai/articles/knowledge-management-tools)
- [Experio Organizational Memory Platform](https://www.experiolabs.ai/about)
- [Meeting Bot API Comparison 2026](https://skribby.io/blog/meeting-bot-api-comparison-2026)
- [Fireflies Pricing Hidden Costs](https://www.outdoo.ai/blog/fireflies-ai-pricing)
- [Granola AI Review](https://tldv.io/blog/granola-review/)
- [Fathom Review 2026](https://max-productive.ai/ai-tools/fathom/)
- [tl;dv Sembly Alternatives](https://tldv.io/blog/sembly-ai-alternatives/)
- [Whisper Real-Time Transcription](https://github.com/collabora/WhisperLive)
