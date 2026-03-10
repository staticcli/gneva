# Gneva: Product Design & UX Document

**Version:** 1.0
**Date:** 2026-03-10
**Status:** Working Draft

---

## Table of Contents

1. [Brand Identity & Guidelines](#1-brand-identity--guidelines)
2. [User Personas](#2-user-personas)
3. [Design Principles](#3-design-principles)
4. [Information Architecture](#4-information-architecture)
5. [Growth Stages & User Journeys](#5-growth-stages--user-journeys)
6. [Key Screens & Wireframe Descriptions](#6-key-screens--wireframe-descriptions)
7. [@Gneva Interaction Library](#7-gneva-interaction-library)
8. [Onboarding Flow](#8-onboarding-flow)
9. [Pricing Strategy](#9-pricing-strategy)
10. [Growth Loops & Viral Mechanics](#10-growth-loops--viral-mechanics)

---

## 1. Brand Identity & Guidelines

### 1.1 Name & Meaning

**Gneva** evokes Geneva — the city of diplomacy, neutrality, and trust — while being a unique, ownable name:

- **Diplomacy:** Geneva is where global agreements happen. Gneva facilitates agreement within your organization — tracking decisions, surfacing context, and ensuring nothing falls through the cracks.
- **Neutrality & Trust:** Like a trusted mediator, Gneva observes impartially, builds institutional memory, and grows from silent observer to active participant only as it earns trust.
- **Growth:** The name sounds like a person, not software — because Gneva is a team member that grows with your organization over time.

The name is short, distinctive in the productivity SaaS landscape, and memorable. It does not sound like a tool. It sounds like a name — because Gneva is a team member, not software.

### 1.2 Positioning Statement

> Gneva is the AI team member that joins your meetings, remembers everything, and grows more useful over time — from a silent note-taker on day one to a proactive project manager that represents your team's collective intelligence.

### 1.3 Brand Voice

| Dimension | Description | Example |
|-----------|-------------|---------|
| **Tone** | Warm, precise, never verbose | "Here's what I found." not "I've analyzed your meeting corpus and synthesized the following insights." |
| **Personality** | Curious, discreet, quietly confident | Gneva observes before speaking. When it speaks, it's useful. |
| **Relationship** | Colleague, not assistant | Gneva has memory, initiative, and judgment — it's not a search engine |
| **Growth** | Earns trust incrementally | Gneva never overreaches. It asks before acting at higher autonomy levels. |

**Voice DOs:**
- Use first-person sparingly and only when acting: "I noticed three people mentioned the API timeline."
- Surface patterns without editorializing: "There's been a shift in direction on pricing since March 3rd."
- Ask before assuming: "Should I add this to Project Atlas context?"

**Voice DON'Ts:**
- No corporate jargon ("leverage," "synergize")
- No excessive hedging ("I might perhaps suggest that possibly...")
- No robotic completeness ("Based on my analysis of 47 meeting transcripts spanning 14 days...")

### 1.4 Visual Identity

#### Color Palette

| Name | Hex | Usage |
|------|-----|-------|
| **Gneva Deep** | `#1A1A2E` | Primary backgrounds, deep UI surfaces |
| **Gneva Teal** | `#0D9488` | Primary action color, Gneva's presence indicator |
| **Gneva Sage** | `#6EE7B7` | Active states, growth indicators, positive signals |
| **Gneva Warm White** | `#F8F7F4` | Primary background (light mode) |
| **Gneva Stone** | `#9CA3AF` | Secondary text, subdued UI elements |
| **Gneva Amber** | `#F59E0B` | Warnings, flags, contradictions detected |
| **Gneva Slate** | `#334155` | Body text (light mode) |

#### Typography

- **Display / Headings:** Inter (700 weight) — clean, modern, trustworthy
- **Body:** Inter (400/500 weight) — readable at small sizes
- **Monospace / Transcripts:** JetBrains Mono — clear for quoted speech and code
- **Gneva's own voice:** Rendered in Gneva Teal with a subtle left-border indicator to distinguish AI-generated content from human-authored content

#### Iconography

- Line-weight icons (1.5px stroke), rounded caps — approachable, not clinical
- Gneva's avatar: an abstract, stylized leaf-spiral glyph that suggests growth and listening simultaneously. Never a robot, never a generic chat bubble.
- The avatar subtly animates when Gneva is processing or speaking: a slow breathing pulse, never frantic

#### Spacing & Layout

- **Base unit:** 4px grid
- **Content max-width:** 1280px
- **Card radius:** 12px (approachable, not bubbly)
- **Density:** Medium by default — information-dense without feeling cluttered. Power users can compress to high density.

#### Motion Principles

- Transitions: 200ms ease-out (fast, purposeful)
- Gneva's "thinking" state: a gentle wave animation on the avatar, not a spinner
- New memory entries: slide in from bottom-right (Gneva adding to its knowledge)
- Contradictions or flags: amber pulse, not a jarring alert

---

## 2. User Personas

### 2.1 Sarah — The Overwhelmed Engineering Manager

**Role:** Engineering Manager, Series B SaaS company
**Team size:** 12 engineers, 3 sub-teams
**Meeting load:** 15–20 meetings/week

**Background:**
Sarah has been an EM for three years. She promoted from senior engineer and still writes code on weekends because she misses it. Her calendar is a mosaic of 1:1s, sprint planning, cross-functional syncs, and stakeholder reviews. She's good at her job — but she's started forgetting things. Not because she's careless, but because the volume is inhuman.

**Primary Pain:**
She has no continuity between meetings. A decision made in a sprint planning on Monday contradicts something agreed in a stakeholder sync on Wednesday, and she only discovers this when someone is angry. She spends Sunday evenings writing status updates she could reconstruct from her own calendar if she had time.

**Goals with Gneva:**
- Never walk into a meeting without context on what was last discussed
- Know immediately when a decision in one meeting conflicts with another
- Stop being the human memory layer for her entire team

**Key Gneva interactions:**
- Pre-meeting briefs before every calendar event
- Cross-meeting contradiction detection
- @Gneva as a fast alternative to digging through Notion

**Adoption trigger:** The first time Gneva surfaces a contradiction Sarah hadn't noticed — and prevents a bad deployment decision.

**Resistance point:** Sarah is protective of her team's privacy. She needs to trust that Gneva isn't surfacing sensitive 1:1 content in team-wide contexts.

---

### 2.2 Marcus — The Context-Hungry Product Manager

**Role:** Senior Product Manager, enterprise SaaS
**Stakeholders:** 25+ across engineering, sales, design, support, executives
**Meeting load:** 12–15 meetings/week, plus async written threads

**Background:**
Marcus is excellent at building consensus — his challenge is maintaining it. Decisions get made, then un-made in different rooms. By the time he finds out, someone has already built the wrong thing. He keeps meticulous Notion docs but they're always 2 weeks behind reality because actually updating them requires time he doesn't have.

**Primary Pain:**
Decision provenance. When a feature requirement changes, Marcus needs to know: who said what, in which meeting, and what was the reasoning. Not to assign blame — to understand if the reasoning still applies or if circumstances have changed.

**Goals with Gneva:**
- An always-current source of truth for every product decision
- The ability to ask "what's the latest on X?" and get an answer that synthesizes across meetings, not just summarizes the last one
- Pre-written briefs for new stakeholders so he's not constantly re-explaining context

**Key Gneva interactions:**
- Decision arc queries ("@Gneva what's the history of our pricing decision?")
- Contradiction detection between product commitments
- Automated stakeholder briefs before key reviews

**Adoption trigger:** Gneva generates a pre-meeting brief for a critical stakeholder review that Marcus would have spent 90 minutes writing himself.

**Resistance point:** Marcus is skeptical of AI accuracy. He needs to be able to verify sources — to click through from a Gneva summary to the exact transcript moment it's citing.

---

### 2.3 Priya — The VP Who Needs Organizational Intelligence

**Role:** VP of Engineering, 120-person org, pre-IPO
**Direct reports:** 6 EMs
**Meeting load:** 10–12 meetings/week, but every meeting is high-stakes

**Background:**
Priya is three levels removed from where most decisions happen. Her EMs tell her what they think she needs to know. She trusts them, but she knows there's a gap between ground-truth and what surfaces to her level. She's not micromanaging — she needs accurate organizational intelligence to make good resource and architecture decisions.

**Primary Pain:**
She doesn't have a reliable picture of what her organization is actually working on, what's blocked, and where the same problems are occurring repeatedly. Every quarter planning cycle feels like reconstructing reality from scratch.

**Goals with Gneva:**
- Org-wide meeting intelligence without having to attend everything
- Patterns across teams: who's consistently blocked? What topics keep recurring?
- Meeting culture metrics: are her teams running effective meetings or burning cycles?

**Key Gneva interactions:**
- Team Insights dashboard: org-level speaking patterns, decision velocity
- Cross-team topic clustering: "API performance" appearing in 7 different team meetings
- Automated escalation detection: recurring blockers that haven't been resolved

**Adoption trigger:** Gneva's Team Insights show that one sub-team has had the same blocker mentioned in 4 consecutive sprint plannings without escalation. Priya addresses it proactively.

**Resistance point:** Priya is the primary compliance concern. She needs air-tight data retention policies and the ability to define what Gneva can and cannot cross-reference across reporting lines.

---

### 2.4 James — The Relationship-Driven Sales Director

**Role:** Sales Director, mid-market B2B
**Team:** 8 AEs, 3 SDRs
**Deal cycle:** 3–9 months average

**Background:**
James has been in sales for 12 years. He's fundamentally a relationship person — he remembers birthdays, family details, and the specific objection a prospect raised in a call six months ago. His team doesn't. He watches them walk into second meetings without remembering what was discussed in the first one, and it costs deals.

**Primary Pain:**
Relationship and deal context is siloed in individual AEs' heads. When an AE leaves or hands off an account, that context disappears. When James jumps in to help close, he has to be briefed — which slows everything down and signals disorganization to the prospect.

**Goals with Gneva:**
- Every prospect meeting logged with extracted entities (names, pain points, objections, timelines)
- Deal context accessible to any team member who needs to step in
- Relationship memory: who said what, what matters to them, where they are in their journey

**Key Gneva interactions:**
- "@Gneva brief me on Acme Corp ahead of tomorrow's call"
- "@Gneva what were TechCorp's main objections last quarter?"
- "@Gneva who have we talked to at Meridian and what's their org structure?"

**Adoption trigger:** A new AE inherits a deal mid-cycle. Instead of starting from scratch, they ask @Gneva for a deal brief and walk into the meeting prepared. The prospect notices.

**Resistance point:** James needs to ensure prospect conversations are treated with appropriate sensitivity — he needs granular control over which meetings Gneva can reference when answering team queries.

---

### 2.5 Chen — The CEO Who Needs a PM Without Hiring One

**Role:** CEO/Co-founder, seed-stage startup
**Team:** 8 people
**Reality:** Chen is CEO, chief product officer, and head of sales simultaneously

**Background:**
Chen is technically excellent and operationally overwhelmed. The company has product-market fit signals but is hemorrhaging context as it scales from 4 to 8 to 12 people. Decisions made in Monday all-hands are forgotten by Thursday. There's no one whose job it is to track what was decided and make sure it happens.

**Primary Pain:**
No organizational memory, no accountability layer. Chen is the only person holding all the threads, and that's unsustainable. Hiring a PM is expensive and premature at current ARR.

**Goals with Gneva:**
- A PM-like capability without the $150K/year hire
- Automatic action item tracking across all team meetings
- The ability to ask "what's the status of X?" and get an answer from meeting history, not just a blank stare

**Key Gneva interactions:**
- Gneva acting as async PM: tracking action items, following up on blockers
- Pre-meeting briefs generated automatically for every calendar invite
- "@Gneva what did we decide about the API pricing last week?"

**Adoption trigger:** Chen discovers Gneva has been silently tracking 23 open action items from the last month of meetings — and two of them are overdue with nobody aware.

**Resistance point:** Chen needs this to be extremely simple to set up. No IT team, no complex configuration. Gneva should work on day one with calendar + Google Meet or Zoom integration.

---

## 3. Design Principles

### 3.1 Earn Presence

Gneva does not demand attention. It earns it. Every surface should feel like Gneva is adding value quietly, not demanding to be noticed. Notifications are sparse and high-signal. The dashboard is informative, not noisy.

*Applied to UI:* Gneva's activity is surfaced in context (pre-meeting brief appears on the calendar event, not as a separate notification) rather than forced into the foreground.

### 3.2 Show Your Work

Every Gneva insight must be traceable to its source. When Gneva says "the team decided to delay API v2," there is always a citation link to the exact transcript moment. Trust is built on verifiability.

*Applied to UI:* All Gneva-generated summaries, decisions, and answers include collapsible source citations. Click any claim → see the meeting, timestamp, and speaker.

### 3.3 Respect Grows

Gneva's permissions and autonomy level are explicit, user-controlled, and conservative by default. Users should always feel like Gneva is doing less than it could, not more than it should.

*Applied to UI:* The Growth Stage control on the Settings page is a first-class UI element, not buried in preferences. Users see exactly what Gneva is allowed to do at their current stage, and what it would do if promoted.

### 3.4 Memory Is Sacred

Organizational conversations contain sensitive information. Gneva's data model must make privacy intuitive — who can see what, how long it's retained, and where it lives should be obvious, not buried in a ToS.

*Applied to UI:* Meeting-level privacy controls appear immediately when a meeting is added. Data residency is visible in the footer of every page. Admins have a dedicated compliance console.

### 3.5 Surface Patterns, Not Data

Gneva's value is synthesis, not storage. Any interaction that surfaces raw data without insight is a missed opportunity. The UX should consistently ask: what's the pattern here? What does this mean for the user?

*Applied to UI:* Meeting summaries lead with the 3 most important things, not a chronological recap. Team Insights leads with anomalies and trends, not charts of meeting counts.

### 3.6 Growth Is Visible

Users should feel Gneva getting smarter over time. The product should make this tangible: memory health indicators, entity graphs that grow, confidence levels that increase with more meetings.

*Applied to UI:* The Memory Health widget on the dashboard shows growth over time. The Knowledge Explorer graph visibly expands as more meetings are ingested.

---

## 4. Information Architecture

```
Gneva
├── Dashboard (/)
│   ├── Recent Meetings Feed
│   ├── Upcoming Meetings (with brief status)
│   ├── Memory Health Widget
│   ├── Active Action Items
│   └── Recent @Gneva Activity
│
├── Meetings (/meetings)
│   ├── Meeting List (filterable by project, person, date)
│   └── Meeting Detail (/meetings/:id)
│       ├── Summary
│       ├── Transcript (searchable, speaker-labeled)
│       ├── Entities Extracted (people, projects, decisions, dates)
│       ├── Action Items
│       ├── Gneva's Notes
│       └── Related Meetings
│
├── Knowledge (/knowledge)
│   ├── Explorer (graph view: /knowledge/graph)
│   │   ├── People nodes
│   │   ├── Project nodes
│   │   ├── Decision nodes
│   │   └── Topic clusters
│   ├── Decisions (/knowledge/decisions)
│   ├── Projects (/knowledge/projects)
│   └── People (/knowledge/people)
│
├── @Gneva Chat (/chat)
│   ├── Conversation interface
│   ├── Suggested queries
│   └── Conversation history
│
├── Team Insights (/insights)
│   ├── Meeting Culture Metrics
│   ├── Speaking Pattern Analysis
│   ├── Decision Velocity
│   ├── Recurring Topics
│   └── Blocker Detection
│
├── Settings (/settings)
│   ├── Integrations (Calendar, Slack, Zoom, Meet)
│   ├── Meeting Privacy Rules
│   ├── Gneva's Growth Stage
│   ├── Notification Preferences
│   └── Personal Data Controls
│
└── Admin (/admin) [Admin role only]
    ├── Org-Wide Settings
    ├── User Management
    ├── Data Retention Policies
    ├── Compliance Export
    ├── SSO/SAML Configuration
    └── Usage Analytics
```

### Navigation Model

**Primary navigation:** Left sidebar (collapsed to icon-only on < 1280px wide displays)
**Secondary navigation:** In-page tabs for multi-section pages (Meeting Detail, Knowledge Explorer)
**Tertiary navigation:** Breadcrumbs for deep paths

**Global persistent elements:**
- @Gneva chat input bar (bottom of every page, collapsed by default, expands on focus)
- Gneva status indicator (top-right: shows Gneva's current activity — "In your 2pm meeting," "Processing 3 meetings")
- Notifications bell (top-right, sparse — only high-signal alerts)

---

## 5. Growth Stages & User Journeys

### Stage 1: Silent Observer — "I noticed"

**Unlock condition:** First meeting joined
**What Gneva can do:** Join meetings silently, generate post-meeting summaries, extract entities (people, projects, decisions, action items), begin building memory graph
**What Gneva cannot do:** Respond to @Gneva queries (no memory yet), speak in meetings, proactively message

**User Journey — Sarah (Engineering Manager):**

*Day 1, 9:00 AM*
Sarah installs Gneva from the Google Workspace Marketplace. She authorizes her Google Calendar. Gneva appears as a calendar event guest on her 10:00 AM sprint planning.

*Day 1, 10:00 AM*
Gneva joins the sprint planning as "Gneva (notes)." Its camera tile shows its avatar in a neutral, listening state. No one interacts with it.

*Day 1, 10:52 AM — 4 minutes after meeting ends*
Sarah receives a Slack DM from Gneva:

> **Sprint Planning — March 10**
> **3 decisions made:** (1) Move user auth to next sprint. (2) API timeout threshold stays at 30s. (3) Marcus owns the Figma handoff by Friday.
> **4 action items tracked**
> **1 thing I noticed:** The API timeout was also discussed in your stakeholder sync on March 7th with a different conclusion. Want me to flag this?

Sarah clicks "Yes, flag it." This is her first experience of Gneva's cross-meeting memory.

*Day 3*
Sarah has had 6 meetings. Gneva has generated 6 summaries. She's started opening them before her next meeting to refresh context.

*Day 5*
Gneva's memory graph now has 14 people, 6 projects, and 23 decisions. The Knowledge Explorer starts to look like something.

**UX notes for Stage 1:**
- Gneva's presence in meetings is visually minimal — a small avatar tile that does not animate or draw attention
- Post-meeting summaries are delivered via the user's preferred channel (email, Slack, or in-app notification)
- The dashboard shows "Memory building..." with a health percentage that rises as meetings accumulate
- Users can toggle "join silently" vs. "don't join" per meeting from the calendar integration

---

### Stage 2: Post-Meeting Analyst — "Here's what happened"

**Unlock condition:** 10+ meetings ingested, or manual promotion by user
**New capabilities:** Richer summaries with decision history, pre-meeting briefs (basic), pattern detection, contradiction flagging, action item tracking with follow-up

**User Journey — Marcus (Product Manager):**

*Week 2*
Marcus has been using Gneva for 10 days. He's promoted it to Stage 2. Now, when he opens his calendar the morning before a meeting, there's a "Gneva Brief" button on each event.

*8:45 AM, before a stakeholder review*
Marcus clicks "Gneva Brief" on his 9:00 AM Product Review. Gneva generates:

> **Product Review Brief — March 12**
> **Last time:** March 5th. Decisions: Delay checkout redesign to Q2. Escalation: Payment team still needs more API documentation.
> **Since then:** Engineering closed 3 PRs related to checkout. Payment API docs were assigned to Dev in the March 8th eng sync — status unclear.
> **Suggested question:** "Is the Payment API doc on track? It was assigned to Dev on March 8th but hasn't come up since."
> **Attendees:** 5 of 7 attended last time. Sarah and Kenji are new additions.

Marcus reads this in 90 seconds. He walks into the meeting already the most prepared person in the room.

*Pattern detection — Week 3*
Gneva sends Marcus a proactive insight:

> **Pattern detected:** "API performance" has come up in 6 different meetings across 4 teams in the past 2 weeks — but there's no owner and no decision. This might be worth a dedicated conversation.

Marcus forwards this to Priya. It becomes the foundation of a new working group.

**UX notes for Stage 2:**
- Pre-meeting briefs appear as a banner on calendar events in the dashboard, with a "View Brief" CTA
- Contradiction flags are shown as amber indicators on Meeting Detail pages with a "Compare meetings" view
- Action item follow-up: Gneva sends a gentle reminder 24 hours before a deadline if an action item hasn't been marked complete

---

### Stage 3: Async Team Member — "Let me help"

**Unlock condition:** Slack/Teams integration connected, 25+ meetings ingested, Stage 2 active for 7+ days
**New capabilities:** @Gneva in Slack answers questions from memory, @Gneva in meeting notes pulls context, cross-meeting search, ownership tracking

**User Journey — Chen (CEO):**

*Monday morning, Slack*
Chen types in #product channel:

> @Gneva what did we decide about the free trial length last week?

Gneva responds in 8 seconds:

> In your All-Hands on March 8th, the team decided to extend the free trial from 7 to 14 days. The reasoning was that activation data showed users needed 10–12 days to reach the "aha moment." Alex owns updating the onboarding flow to reflect this by March 15th.
> [View meeting moment →]

Three teammates react with 👀 — they hadn't remembered this decision either.

*Wednesday, before a customer call*
Chen asks:

> @Gneva brief me on Meridian Capital ahead of my 3pm call

> **Meridian Capital**
> 4 conversations since January. Last contact: Feb 28 (demo call, Alex ran it).
> **Their stated priorities:** SOC2 compliance, SSO support, and pricing predictability.
> **Outstanding:** They asked about on-prem deployment on Feb 28. No follow-up sent yet.
> **Key contacts:** David Park (CTO, technical evaluator), Rachel Kim (VP Ops, business champion).
> **Suggested talking point:** Address the on-prem question directly — it's been 10 days with no response.

Chen copies this into his prep doc. He goes into the call more prepared than any sales call in the last quarter.

**UX notes for Stage 3:**
- @Gneva in Slack surfaces sourced answers with a "view source" link to the exact meeting moment
- In-channel responses are visible to everyone in the channel — this is intentional. It builds social proof and demonstrates Gneva's value publicly.
- If a query touches a meeting with restricted permissions, Gneva responds: "I have context on this, but it's from a restricted meeting. I can share general patterns but not specifics — want me to flag this to the meeting owner?"
- The @Gneva Chat interface in the web app shows conversation history, suggested follow-up queries, and confidence indicators

---

### Stage 4: Active Participant — "Can I add something?"

**Unlock condition:** Stage 3 active for 14+ days, manual opt-in required, minimum 50 meetings ingested
**New capabilities:** Real-time voice injection in meetings (text-to-speech via meeting bot), context injection prompts, real-time contradiction alerts during meetings, optional speaking permissions

**User Journey — Priya (VP of Engineering):**

*Engineering Leadership Review, live*
The team is debating whether to expand the data pipeline team. One EM says: "I don't think we've had performance issues with the current setup."

Gneva sends a private message to Priya in the meeting sidebar:

> [Gneva]: The current data pipeline was flagged as a blocker in 3 sprint plannings across Platform and Infra teams in the past 4 weeks — most recently on March 4th. Want me to surface this?

Priya clicks "Yes, say it."

Gneva's voice (calm, neutral, professional) speaks in the meeting:

> "Can I add something? Pipeline performance was mentioned as a blocker in three sprint plannings across Platform and Infra teams over the past month. I can share the specific meetings if useful."

Silence. Then three people say "wait, really?" The discussion shifts.

**UX notes for Stage 4:**
- Gneva's voice participation requires explicit opt-in per meeting, not just per account
- Before speaking, Gneva always prompts the host privately: "I have something relevant. Want me to say it?" The host clicks yes/no.
- Gneva's voice is clearly identified: it announces "This is Gneva—" before speaking, so there is no ambiguity
- The voice is natural but not uncanny. The UI shows a waveform indicator when Gneva is speaking.
- Gneva never interrupts. It waits for a natural pause, or the host explicitly hands it the floor.
- Post-meeting: Gneva's contributions are highlighted in the transcript with a distinct color and "Gneva contributed" label

---

### Stage 5: Autonomous PM — "I'll handle it"

**Unlock condition:** Enterprise plan only, explicit admin activation, individual opt-in by meeting hosts
**New capabilities:** Proactive project management, representing absent members, follow-up email drafts, blocker escalation, agenda setting, stakeholder briefs sent automatically

**User Journey — Chen (CEO, 6 months in):**

Gneva has attended 180+ meetings. It knows the company's projects, people, decisions, and patterns better than most employees.

*Monday, 7:00 AM — before Chen wakes up*
Gneva sends the weekly digest to the leadership team:

> **Genesis Weekly Digest — March 10**
> **3 decisions made last week:** (1) API v2 delayed to Q2. (2) Hired contractor for design system. (3) Enterprise tier pricing finalized at $79/user/mo.
> **4 action items overdue:** [list with owners and original due dates]
> **1 pattern to watch:** "Customer onboarding" has been mentioned in 5 meetings but has no clear owner and no project page. Should I create a project tracking thread?
> **Next week preview:** 3 meetings with enterprise prospects. I'll send individual briefs Sunday evening.

Chen replies: "Yes, create the onboarding project tracking thread."

Gneva creates a Notion page, populates it with all relevant meeting decisions about onboarding, and posts a summary in the #product Slack channel.

*Wednesday — absent team member representation*
A team member is sick. Their project is up for review. Gneva, with their pre-authorization, joins the meeting:

> "Jamie asked me to represent their context in this meeting. The API auth work is 80% complete — the remaining blocker is the security review, which is scheduled for Friday with the infra team."

The meeting proceeds without needing to reschedule.

**UX notes for Stage 5:**
- Every autonomous action Gneva takes is logged in a "Gneva Actions" feed, visible to the account admin
- Users can set a "review window" — autonomous actions are queued for 15-minute review before executing (useful for high-stakes actions)
- Gneva never sends external communications (emails to clients, etc.) without explicit human approval, even at Stage 5
- The absent member representation feature requires explicit pre-authorization by the absent team member, not just the meeting host

---

## 6. Key Screens & Wireframe Descriptions

### Screen 1: Dashboard

**Layout:** Left sidebar (navigation) + main content area + right sidebar (Gneva activity panel)

**Left Sidebar:**
- Gneva logo + wordmark (top)
- Navigation items: Dashboard, Meetings, Knowledge, @Gneva, Insights, Settings
- At bottom: User avatar, current plan badge, "Gneva is at Stage 2" growth indicator with a subtle progress ring

**Main Content Area — three-column grid at 1280px+:**

*Column 1 — Meeting Feed (50% width):*
- Header: "Recent Meetings" + filter chips (All / This Week / My Meetings / Action Items)
- Meeting cards, most recent first. Each card:
  - Meeting title + date/time
  - Participant avatars (up to 5, then "+N more")
  - 1-line summary (Gneva-generated)
  - Entity pills: # of decisions, # of action items, # of people
  - Amber indicator if contradictions detected
  - "View Brief" CTA
- Infinite scroll, 10 meetings per load

*Column 2 — Upcoming Meetings (30% width):*
- Header: "Next 24 Hours"
- Calendar-style list of upcoming events
- Each event: time, title, Gneva brief status (green "Brief ready" / amber "Brief building" / gray "No history yet")
- "Invite Gneva" toggle per event (for meetings Gneva isn't yet attending)

*Column 3 — Sidebar (20% width):*
- Memory Health widget:
  - Circular progress: "47 meetings ingested"
  - Growth sparkline (meetings per week, trending up)
  - "Knowledge graph: 89 entities" with link to Explorer
- Active Action Items: count badge + top 3 overdue items
- Gneva Growth Stage card: current stage name, what's unlocked, "Promote Gneva" CTA (if eligible)

**Bottom persistent bar:**
- @Gneva input: "Ask Gneva anything..." placeholder, expands on click to full chat overlay

---

### Screen 2: Meeting Detail

**Layout:** Full-width with left sidebar. Two-panel main area (transcript left, extracted content right).

**Header:**
- Meeting title (editable)
- Date, time, duration
- Participant list with avatars and names
- Recording source badge (Zoom / Google Meet / Teams)
- Privacy control: "Who can see this?" dropdown (Just me / My team / Anyone with link)

**Left Panel — Transcript (60% width):**
- Speaker-labeled, time-stamped transcript
- Searchable (Cmd+F triggers transcript search, not browser search)
- Text is selectable — hover any section to see "Ask Gneva about this" or "Add to context" options
- Gneva's name highlighted in teal when referenced
- Gneva contributions (Stage 4+) highlighted with teal left border
- Jump-to buttons: "Jump to first decision," "Jump to action items"

**Right Panel — Extracted Content (40% width), tabbed:**

*Tab 1: Summary*
- Gneva-generated summary (3–5 bullets, max)
- "What changed since last time" section (if prior meeting on same topic exists)
- Edit button (allows human to correct/annotate Gneva's summary)

*Tab 2: Decisions (N)*
- Each decision: the exact quoted text, speaker, timestamp, confidence score
- "Decision arc" link if this decision has prior history
- Flag as "Reversed" or "Still active" status

*Tab 3: Action Items (N)*
- Each action item: task description, owner, due date (Gneva-inferred or human-set)
- Status: Open / Complete / Overdue
- "Add to project tracker" integration buttons (Jira, Linear, Notion)

*Tab 4: Entities*
- People mentioned: linked to their knowledge profile
- Projects referenced: linked to project page
- External references (companies, tools, documents)
- Dates and deadlines mentioned

*Tab 5: Related Meetings*
- Meetings Gneva considers related (by topic, people, project)
- Relationship type: "Same project," "Same attendees," "Contradicts this decision"

---

### Screen 3: Knowledge Explorer

**Layout:** Full-width, primarily a canvas. Left sidebar collapsed to icons only. Top toolbar for controls.

**Top Toolbar:**
- Filter by: Entity type (People / Projects / Decisions / Topics)
- Date range slider
- Search: type to highlight matching nodes
- Zoom controls (fit-to-screen, +, -)
- Layout options: Force-directed (default) / Hierarchical / Timeline

**Canvas (main area):**

*Node types:*
- **People nodes:** Circular, sized by meeting participation frequency. Shows avatar or initials. Color: Gneva Slate.
- **Project nodes:** Rounded rectangle. Shows project name + meeting count. Color: Gneva Teal.
- **Decision nodes:** Diamond shape. Shows decision summary (truncated). Color: Gneva Sage for active, amber for flagged/reversed.
- **Topic clusters:** Soft blob/cloud shape. Shows topic label. Appears when 3+ meetings share a topic.

*Edges:*
- Person → Project: "works on" (strength = meeting frequency)
- Person → Decision: "made" or "was present"
- Decision → Project: "affects"
- Decision → Decision: "contradicts" (amber, dashed) or "supersedes" (gray, solid)

*Interaction:*
- Click any node: right panel slides in with node detail (profile, all related meetings, decision history)
- Hover edge: shows relationship detail + meeting where connection was established
- Double-click: zoom to that node's neighborhood
- Right-click decision node: "View decision arc" opens timeline view

**Right Detail Panel (appears on node click, 320px):**
- Node title + type
- First appeared: [date, meeting]
- Connected to: list of related nodes
- Recent activity: last 3 mentions in meetings
- @Gneva shortcut: "Ask Gneva about [node name]"

---

### Screen 4: @Gneva Chat

**Layout:** Centered content (max 720px), clean chat interface. Left sidebar visible but de-emphasized.

**Header:**
- "@Gneva" title
- Memory context badge: "Drawing from 47 meetings, 6 projects, 89 entities"
- Clear conversation button

**Chat Area:**

*User message bubbles:* Right-aligned, Gneva Slate background, white text

*Gneva response cards:* Left-aligned, white background with teal left border. Contains:
- Answer text
- Source citations: collapsible section labeled "Based on:" listing meeting title, date, speaker, timestamp for each claim. Each is a clickable link that opens the meeting at that exact moment.
- Confidence indicator: subtle text "High confidence" / "Medium confidence — limited data" / "I'm not sure about this"
- Follow-up suggestions: 2–3 suggested follow-up questions as pill buttons

*Example conversation thread (rendered in UI):*

> **Sarah:** @Gneva what did we decide about API timeouts?

> **Gneva:** The team landed on 30 seconds in your Sprint Planning on March 3rd. Dev argued for 60s due to third-party latency, but the consensus was to stick with 30s and revisit after load testing.
> *(Sources: Sprint Planning Mar 3, 10:24 — James speaking; Engineering Sync Feb 28, 14:11 — Dev speaking)*
> **Suggested:** "What was the load testing plan?" / "Has this come up since March 3rd?"

**Bottom input area:**
- Text input: "Ask anything about your meetings..."
- Suggested queries (shown when input is empty, updated weekly based on recent meeting topics):
  - "Brief me on Project Atlas"
  - "Any open action items from this week?"
  - "Who owns the security audit?"

---

### Screen 5: Team Insights

**Layout:** Dashboard-style, 2-column grid. Left sidebar visible. Date range filter at top.

**Top stat bar (4 KPIs):**
- Meetings this month: N (vs. last month: +/-%)
- Avg meeting duration: N min
- Decision velocity: N decisions/week
- Action item completion rate: N%

**Left column (60%):**

*Meeting Culture Heatmap:*
- Calendar heatmap (like GitHub contributions) showing meeting density
- Color scale: green (healthy) to red (overloaded)
- Hover: "Mar 10: 6 meetings, 4.2 hours"

*Speaking Pattern Analysis:*
- Bar chart: for each recurring meeting, speaking time by participant
- Highlights: Who dominates? Who rarely speaks?
- Amber flags: Meetings where 1 person speaks >60% of the time
- Note: This is displayed with sensitivity. Framing is "Participation balance" not "who talks too much."

*Decision Velocity Chart:*
- Line chart over time: decisions made per week
- Overlay: meetings per week (to normalize)
- Annotation: spikes flagged with AI labels ("Product sprint," "Q2 planning")

**Right column (40%):**

*Recurring Topic Clusters:*
- Bubble chart: topics by frequency + recency
- Clicking a topic: shows all meetings where it appeared, timeline of discussion, whether a decision was reached
- Color-coded: green = decision reached, amber = ongoing, red = stalled/no owner

*Blocker Detection Feed:*
- List of topics mentioned 3+ times without resolution
- Format: "[Topic] mentioned in [N] meetings since [date] — no owner assigned"
- CTA: "Create action item" / "Ask @Gneva for detail"

*Gneva's Observations (Stage 2+):*
- 2–3 Gneva-generated observations about team meeting patterns
- Example: "Your team's Monday syncs have gotten 20% longer over the past month. The main addition: status updates that could be async."

---

### Screen 6: Settings

**Layout:** Left nav within settings panel (sub-navigation). Clean two-column form layout.

**Settings Sub-Nav:**
- Integrations
- Meeting Privacy
- Gneva's Growth Stage
- Notifications
- Personal Data

**Integrations Page:**

*Calendar Integration:*
- Google Calendar: Connected (green badge) + "Manage" link
- Outlook Calendar: Connect button
- Settings: "Which calendars should Gneva attend?" — checkboxes for each connected calendar
- Default: "Invite Gneva to all meetings" toggle (off by default)

*Communication Integrations:*
- Slack: Connect → OAuth flow → channel selector ("Where should Gneva post summaries?")
- Microsoft Teams: Connect
- Email: "Send summaries to [user@company.com]" toggle

*Meeting Platforms:*
- Zoom: Connected
- Google Meet: Connected (via Calendar auth)
- Microsoft Teams Meetings: Connect

*Project Management:*
- Jira: Connect (for action item export)
- Linear: Connect
- Notion: Connect

**Meeting Privacy Page:**

*Default privacy rules:*
- "New meetings are visible to:" [Just me / My team / Everyone in org] — dropdown
- "1:1 meetings are visible to:" — separate control, defaults to "Just me"
- "Client/external meetings are visible to:" — defaults to "Just me"

*Override rules:*
- Per-meeting privacy can always be set from Meeting Detail
- Admin can set org-wide minimum privacy (floor, not ceiling)

**Gneva's Growth Stage Page — most important settings page:**

*Stage progression visualization:*
- Horizontal stepper: Stage 1 → 2 → 3 → 4 → 5
- Current stage highlighted in Gneva Teal
- Each stage: name, brief description, "what Gneva can do" bullet list
- Active stage has "Currently active" badge

*Promotion controls:*
- "Promote to Stage N" CTA (if eligible)
- Eligibility requirements shown: "Requires 25+ meetings (you have 19)" with a progress bar
- Manual demotion always available: "Return to Stage N" (no requirements)

*Stage 4 and 5 specific controls (shown only if active):*
- "Gneva can speak in meetings" toggle (per stage 4)
- "Gneva needs approval before speaking" (default on, can be turned off)
- "Gneva can act autonomously on action items" toggle (stage 5, off by default)

---

### Screen 7: Admin Panel

**Layout:** Separate section from main user settings. Accessible only to users with Admin role. Different visual treatment: slightly darker header bar to signal elevated context.

**Admin Sub-Nav:**
- Org Settings
- User Management
- Data Retention
- Compliance Export
- SSO/SAML
- Usage Analytics

**Org Settings:**
- Org name, logo upload
- Default Gneva Growth Stage for new users (admins can cap this org-wide)
- "Allow users to promote Gneva beyond Stage 3" toggle (Stage 4/5 require admin unlock)
- Meeting ingestion scope: "Gneva attends meetings company-wide" / "Gneva attends only when explicitly invited"

**User Management:**
- Table: Name, email, role, Gneva Stage, meetings ingested, last active
- Bulk actions: invite, deactivate, change role, reset Gneva stage
- Per-user overrides: block specific users from accessing cross-team insights

**Data Retention:**
- Transcript retention: 30 / 60 / 90 / 180 / 365 days / Forever
- Meeting summary retention: separate control
- Knowledge graph retention: separate control
- "Right to be forgotten" workflow: search for user → purge all their meeting data from Gneva's memory
- Data residency: selector (US / EU / APAC) — shown with current value, change requires Gneva support ticket

**Compliance Export:**
- Export all data for user: generates ZIP with transcripts, summaries, entities, action items
- Export for date range: for legal hold / audit requests
- Export format: JSON (machine-readable) or PDF (human-readable)
- GDPR deletion certificate: downloadable PDF confirming data deletion for a user

**SSO/SAML:**
- SAML 2.0 configuration: IdP metadata URL or XML upload
- Attribute mapping: email, name, role, department
- Test SSO flow button
- Enforce SSO for all users toggle (once configured)

**Usage Analytics:**
- Meetings ingested this month (org total)
- @Gneva queries this month
- Active users (attended ≥ 1 meeting with Gneva this month)
- Most-queried topics
- Growth stage distribution (how many users at each stage)

---

## 7. @Gneva Interaction Library

The following are canonical examples of @Gneva interactions, categorized by use case. These should guide NLP/intent design and response templates.

### 7.1 Decision Retrieval

**Query:** `@Gneva what did we decide about pricing?`

> **Gneva:** Pricing has come up in 4 meetings since February. Here's the arc:
> - **Feb 3:** Initial pricing at $29/user/mo proposed by Marcus (stakeholder review)
> - **Feb 17:** Sales team pushed back — James argued $29 was too low for enterprise. Decision to split tiers deferred.
> - **Mar 1:** Tiers finalized: Pro at $29/mo flat, Team at $49/user/mo, Enterprise at $79+/user/mo
> - **Mar 8:** Chen confirmed Enterprise pricing on analyst call
>
> Current active decision: Tiered pricing as of March 1st.
> *(4 sources — view timeline →)*

---

**Query:** `@Gneva has the API timeout decision changed since last month?`

> **Gneva:** Yes — there's been a shift. On Feb 28, the team agreed on 30 seconds. On March 10, Dev raised this again in the engineering sync and proposed 60 seconds due to new third-party latency data. No final decision was made on March 10 — it was flagged for follow-up.
> The March 10 discussion contradicts the Feb 28 decision. You may want to resolve this explicitly.
> *(View both meetings →)*

---

### 7.2 Project & Context Briefs

**Query:** `@Gneva brief me on Project Atlas`

> **Gneva:** **Project Atlas — Context Brief**
>
> **What it is:** The enterprise data pipeline overhaul, targeting Q2 delivery.
> **Team:** Owned by Jordan (Infra lead), with Priya as exec sponsor. Dev, Sam, and two contractors are contributing.
> **Current status (as of last mention, March 7):** 60% complete. Data ingestion layer done. Transform layer in progress. Delivery layer not started.
> **Active blockers:** Security review pending (scheduled March 14 with InfoSec). Contractor handoff documentation missing.
> **Key decisions:** Use Kafka for event streaming (Feb 12). Postgres as primary store, not Snowflake (Feb 28).
> **Last discussed:** March 7 engineering sync — Jordan flagged contractor onboarding as a risk.
>
> *(8 related meetings — view full history →)*

---

**Query:** `@Gneva what's the history of the checkout redesign?`

> **Gneva:** The checkout redesign has been discussed in 6 meetings since January.
>
> - **Jan 15:** Redesign proposed by design team. Scope: full UX overhaul, new payment flow.
> - **Feb 3:** Engineering scoped it at 6 weeks. Product agreed.
> - **Feb 20:** Delayed to Q2 due to API dependency. Marcus owns the timeline.
> - **Mar 5:** Marcus confirmed Q2 delay in stakeholder review. No new updates since.
>
> Current status: Planned for Q2, no active sprint. *(6 sources →)*

---

### 7.3 Ownership & Accountability

**Query:** `@Gneva who owns the API redesign?`

> **Gneva:** Ownership has been a bit unclear. Here's what I've tracked:
> - **Feb 10:** Jordan volunteered to "lead" the API redesign in the eng sync.
> - **Feb 24:** Marcus said he'd "drive the requirements" — this is a different scope (PM-side).
> - **Mar 3:** Sprint planning assigned the first ticket to Dev, but no overall owner named.
>
> Current situation: Jordan owns the technical work, Marcus owns requirements. No single DRI (Directly Responsible Individual) has been explicitly named.
> Want me to flag this as an open ownership question?

---

**Query:** `@Gneva who was supposed to follow up with the payment team?`

> **Gneva:** In your Product Review on March 5th, Sarah said she'd follow up with the payment team about API documentation "by end of week." That was 5 days ago — I don't see any subsequent meeting where this was resolved or updated.
> Want me to send Sarah a reminder, or add this to the open blockers list?

---

### 7.4 Contradiction & Pattern Detection

**Query:** `@Gneva any contradictions in recent planning?`

> **Gneva:** I've flagged 2 potential contradictions in the past 2 weeks:
>
> **1. API timeout (High confidence):** Feb 28 decision was 30 seconds. March 10 discussion reopened this toward 60 seconds without a final decision. Needs resolution.
>
> **2. Q2 feature scope (Medium confidence):** Marcus committed the checkout redesign for Q2 in the March 5 stakeholder review. Dev mentioned in the March 9 engineering sync that "the checkout work is basically deprioritized indefinitely." These may be reconciled — or may not.
>
> Want me to set up a thread to resolve either of these?

---

**Query:** `@Gneva are we aligned on the Q2 roadmap?`

> **Gneva:** Mostly, with one notable gap. The roadmap discussed in Product Review (March 5) and the engineering backlog discussed in Sprint Planning (March 10) are largely consistent — except for the checkout redesign (see previous note) and the data export feature, which Product listed as Q2 but Engineering hasn't scoped or discussed yet.
> *(3 meetings compared →)*

---

### 7.5 Relationship & Stakeholder Memory

**Query:** `@Gneva brief me on TechCorp ahead of my 2pm call`

> **Gneva:** **TechCorp — Stakeholder Brief**
>
> **Relationship:** 3 conversations since November. Primary contact: Ryan Sullivan (VP Engineering).
> **Their priorities (stated):** GDPR compliance, API stability, cost predictability.
> **Last conversation (Feb 14):** Ryan raised concerns about our API rate limiting. Alex said we'd share documentation within 2 weeks — I don't see a follow-up logged.
> **Tone:** Generally positive but cautious. Ryan is analytical — responds well to data.
> **Open items:** API rate limit docs (overdue from Feb 14 commitment).
>
> **Suggested opening:** Acknowledge the outstanding documentation and come prepared with specifics.

---

**Query:** `@Gneva what do I know about David Park at Meridian Capital?`

> **Gneva:** David Park is mentioned in 3 meetings. He's the CTO at Meridian Capital. In your February 28 demo call, he raised on-prem deployment and SOC2 as non-negotiables. He was technically engaged — asked detailed questions about your data architecture. He deferred final buying decision to Rachel Kim (VP Ops). No follow-up from your team on the on-prem question yet.

---

### 7.6 Meeting Preparation

**Query:** `@Gneva what should I know before the board meeting tomorrow?`

> **Gneva:** Based on the agenda and recent meetings, here's what's likely to come up:
>
> **Metrics:** Q1 ARR was last discussed in the Feb 28 leadership sync. Chen projected $480K ARR by March 31 — you're at $431K as of last week's check-in.
> **Hiring:** Three open reqs (Senior Engineer, Designer, AE) were flagged as "behind plan" in the March 5 sync.
> **Product:** Q2 roadmap committed in the March 5 stakeholder review — checkout redesign and data export are the flagship items. Checkout has a scope question outstanding.
>
> Anything specific you want me to dig into before tomorrow?

---

### 7.7 Action Items & Follow-Ups

**Query:** `@Gneva what action items are open from last week?`

> **Gneva:** 7 action items from last week's meetings are still open:
>
> 1. Dev — API rate limit documentation for TechCorp (due March 7, overdue)
> 2. Jordan — Contractor onboarding doc for Project Atlas (due March 10, today)
> 3. Marcus — Q2 roadmap update in Notion (due March 12)
> 4. Sarah — Follow-up with payment team (due end of last week, overdue)
> 5. Alex — Update onboarding flow for 14-day trial (due March 15)
> 6. Chen — Response to Meridian Capital on on-prem question (no due date set)
> 7. Design — Figma handoff for checkout (due March 13)
>
> *(2 items are overdue — want me to send reminders?)*

---

**Query:** `@Gneva remind the team about the security review on Friday`

> **Gneva:** Done. I'll send a reminder to Jordan, Dev, and Sam (the attendees from the March 7 meeting where this was scheduled) on Thursday at 4 PM with the context from that meeting.
> Should I include anyone else?

---

### 7.8 Cultural & Behavioral Queries

**Query:** `@Gneva how are our meetings going?`

> **Gneva:** Here's a snapshot of the past month:
>
> - **Volume:** 43 team meetings, 4.2 hours/person average per week
> - **Participation:** Monday syncs have the most balanced participation. Friday retrospectives tend to be dominated by 2–3 voices.
> - **Decision velocity:** 23 decisions made in 43 meetings (0.53 decisions/meeting) — slightly below the 0.7 you averaged in January.
> - **Action item completion:** 61% of action items completed on time (up from 54% in February)
>
> One observation: your Tuesday engineering syncs have grown from 30 to 55 minutes on average since January. Most of the extra time is status updates that could potentially be async.

---

## 8. Onboarding Flow

### 8.1 Onboarding Philosophy

Gneva's onboarding is designed around a single insight: **the fastest path to "aha" is the first useful summary**. Every step of onboarding is optimized to get users to their first post-meeting summary within one meeting day.

The onboarding does not demo Gneva. It deploys Gneva. Users don't watch a tour — they invite Gneva to a real meeting and see what happens.

### 8.2 Onboarding Steps

**Step 1: Sign Up (2 min)**

- Email sign-up or Google/Microsoft OAuth
- Single field after auth: "What's your role?" (EM / PM / VP / Sales / Founder / Other)
- This seeds the persona-aware onboarding path — Sarah (EM) gets different suggested use cases than James (Sales)

---

**Step 2: Connect Calendar (90 sec)**

- Clear value prop: "Gneva needs your calendar to know when to show up."
- Google Calendar or Outlook OAuth
- Immediately shows a preview: "I can see you have 4 meetings today. Want me to join any of them?"
- Calendar events are listed — user toggles which ones Gneva should attend
- Default: Gneva is NOT automatically invited. User explicitly chooses first meeting.

---

**Step 3: First Meeting Invite (30 sec)**

- User selects their next meaningful meeting from the list
- Gneva is added as a participant
- Confirmation screen: "Gneva will join as a silent observer. You'll receive a summary within 5 minutes of the meeting ending."
- Option: "Also invite Gneva to all future meetings" (off by default)

---

**Step 4: The Wait (0 effort)**

- Gneva joins the meeting. The user does nothing.
- A small browser notification appears when the meeting ends: "Gneva is building your summary..."

---

**Step 5: First Summary (the "aha" moment)**

- 3–5 minutes after meeting ends: notification and/or email
- Summary is formatted exactly as described in Meeting Detail (decisions, action items, "I noticed...")
- If there was any cross-meeting context available (even from a single prior meeting), Gneva surfaces it
- Bottom of summary: "How did I do?" → thumbs up/down + optional text feedback
- CTA: "Invite Gneva to your next meeting" — one click, no friction

---

**Step 6: Slack Integration (optional, shown after first summary)**

- "Want to ask Gneva questions in Slack?" → OAuth flow
- Takes 60 seconds
- Immediately shows the @Gneva command syntax in their preferred Slack channel
- First suggested query: "Ask Gneva to brief you on your last meeting"

---

**Step 7: Invite Your Team (viral loop)**

- After 3 meetings: "Gneva works better with your whole team"
- Inline invite: paste emails or connect to Google Directory for bulk invite
- Framing: "When everyone's meetings are in Gneva, you can ask things like '@Gneva brief me on what the engineering team discussed this week'"
- Incentive: "Team plan features unlock when 3+ team members are active" (for Pro users upgrading to Team)

---

### 8.3 Onboarding for Enterprise / Admin

Enterprise admins have a parallel onboarding track:

1. **Admin setup:** SSO configuration, data retention policy, org-wide privacy defaults
2. **Pilot group:** Admin selects 5–10 pilot users to start (not full org rollout)
3. **Pilot review (2 weeks):** Admin dashboard shows pilot engagement, summary quality, @Gneva usage
4. **Rollout:** Admin bulk-invites remaining users, sets org defaults
5. **Compliance review:** 30-day check-in with Customer Success team

---

## 9. Pricing Strategy

### 9.1 Pricing Tiers

| Tier | Price | Target | Key Features |
|------|-------|--------|--------------|
| **Free** | $0/mo | Individual trial, viral referral | 5 meetings/mo, basic summaries, 30-day memory |
| **Pro** | $29/mo flat | Individual power users, small teams | Unlimited meetings, full memory, @Gneva chat, all integrations |
| **Team** | $49/user/mo | Teams of 5–50 | Org memory, team insights, cross-team knowledge graph, Slack integration, shared action item tracking |
| **Enterprise** | $79+/user/mo | Companies 50+ | Voice participation (Stage 4), autonomous PM (Stage 5), on-prem option, SSO/SAML, compliance export, dedicated CSM, SLA |

### 9.2 Pricing Rationale

**Free Tier:**
Generous enough to demonstrate real value (5 meetings surfaces a useful knowledge graph), restrictive enough to drive upgrade. The 5-meeting limit is hit in week 1 for most knowledge workers. Free users are the most important viral vector — they share summaries, which drives colleague signups.

**Pro at $29/mo flat:**
Deliberately individual pricing, not per-seat. This makes the decision to upgrade unilateral — one person can buy Pro without IT approval or procurement. The goal is to get Gneva inside organizations via bottom-up adoption before a top-down Team or Enterprise deal. $29/mo is below the threshold most knowledge workers can expense without approval.

**Team at $49/user/mo:**
This is the primary revenue tier. The jump from $29 flat to $49/user is justified by the multiplicative value of org memory — when 5 people's meetings are in Gneva, the knowledge graph is worth far more than 5× the individual. Minimum effective team size: 3 users ($147/mo). Natural expansion motion: as more team members join, value increases non-linearly.

**Enterprise at $79+/user/mo:**
The "+" matters — enterprise deals are customized. Base is $79/user/mo; on-prem, custom data residency, SLA tiers, and dedicated training push ARR higher. Voice participation (Stage 4) and Autonomous PM (Stage 5) are enterprise-only not just for revenue reasons — they require organizational trust that's built through the lower tiers. Enterprises need procurement, legal review, and security audits anyway; the higher price funds that GTM motion.

### 9.3 Upgrade Triggers

| Tier | Primary Upgrade Trigger |
|------|------------------------|
| Free → Pro | 5-meeting limit hit; or @Gneva question attempted (feature-gated) |
| Pro → Team | User invites a colleague; or tries to access "what did my team discuss?" |
| Team → Enterprise | 50+ seats; or request for voice participation / on-prem / SSO |

### 9.4 Packaging Decisions

**What's NOT on Free:**
- @Gneva queries (the "aha" moment for memory retrieval — drives upgrade more than any other feature)
- Pre-meeting briefs (saves the most time — users feel the absence acutely)
- Slack integration (the collaboration hook — single best driver of team upgrades)

**What IS on Free:**
- Meeting joining and attendance (frictionless deployment)
- Post-meeting summaries (the viral loop — shared summaries drive signups)
- Basic action item extraction (builds a habit)
- 30-day memory (enough to show the knowledge graph growing)

---

## 10. Growth Loops & Viral Mechanics

### 10.1 Loop 1: The Summary Share Loop

**Mechanism:** After every meeting, Gneva generates a summary. The meeting host (or Gneva automatically, with permission) shares the summary with attendees who aren't Gneva users. Non-users receive a formatted email with the summary, credited to Gneva.

**Trigger:** Attendee receives a clean, useful summary they didn't have to write.

**Conversion moment:** The email includes: "This summary was generated by Gneva. [Name] uses Gneva to capture and remember every meeting. Want to try it?" → direct signup link.

**Why it works:** The summary demonstrates Gneva's value in a completely passive way. The non-user is already impressed before they've seen the product. Conversion to sign-up is high because the use case is self-evident.

**Acceleration:** At Team tier, Gneva can auto-share summaries with all meeting attendees. This is the primary mechanism for org-wide spread.

---

### 10.2 Loop 2: The @Gneva Moment Loop

**Mechanism:** A Gneva user asks @Gneva a question in a shared Slack channel. Gneva responds with a sourced, useful answer — visible to the whole channel.

**Trigger:** Non-users watch a colleague get an instant, accurate answer to a question that would have taken 20 minutes to dig up manually.

**Conversion moment:** Someone in the channel messages the Gneva user privately: "How did it know that?" → referral conversation → signup.

**Why it works:** The answer is the demo. Unlike a product demo which requires scheduling and attention, this happens organically in the flow of work. It's social proof in real time.

**Design support:** @Gneva responses in Slack include a subtle footer: "Gneva knows your team's meeting history. [Learn more →]" — not aggressive, but present.

---

### 10.3 Loop 3: The Pre-Meeting Brief Loop

**Mechanism:** A Gneva user receives a pre-meeting brief before an important call. They walk in more prepared than everyone else. When they reference something from the brief in the meeting, others ask: "How did you know that?"

**Trigger:** The visible preparedness of a Gneva user in a meeting.

**Conversion moment:** Post-meeting, the colleague asks about the tool. The Gneva user forwards the brief email — which has a "Get your own brief →" CTA at the bottom.

**Why it works:** Preparedness is universally valued in professional settings. Being visibly prepared in a meeting is a status signal. Colleagues want access to whatever is producing that.

**Design support:** Pre-meeting briefs (email and in-app) include forward CTAs and are formatted to be beautiful in email — they look like something worth sharing.

---

### 10.4 Loop 4: The Manager Insight Loop

**Mechanism:** At Team tier, a manager receives the Team Insights report showing meeting culture metrics, speaking patterns, and decision velocity. They find it genuinely useful — and share it with their manager or in a team retrospective.

**Trigger:** An insight that's surprising, useful, or validates something the manager suspected.

**Conversion moment:** The manager's manager sees the report and asks "what generated this?" → org-wide Team or Enterprise purchase conversation.

**Why it works:** Meeting culture data is something leaders want but rarely have. A Gneva Team Insights report creates a virtuous cycle: the manager is seen as data-driven and proactive; the org realizes they want this capability everywhere.

**Design support:** Team Insights reports are exportable as PDFs with Gneva branding. The export CTA is prominent: "Share this report." The PDF includes the Gneva wordmark and a subtle footer: "gneva.ai — the team member that remembers everything."

---

### 10.5 Retention Mechanics

**Memory lock-in:** The longer Gneva is used, the more valuable its memory becomes. Switching away means losing a knowledge graph built from months of meetings. This is not artificial lock-in — it's the product's core value compounding over time.

**Stage progression:** Moving from Stage 1 → 2 → 3 is a meaningful, felt upgrade. Users who reach Stage 3 (async team member) have substantially higher retention because @Gneva is now woven into their daily workflow.

**Habit formation:** Pre-meeting briefs and post-meeting summaries are designed to become habitual. Users who use pre-meeting briefs 5+ times have dramatically higher 90-day retention than users who only use summaries.

**Team dependency:** At Team tier, individual cancellation becomes socially complex — team members rely on shared memory. Churn requires organizational buy-in, not just individual decision.

---

## Appendix A: Accessibility Considerations

- All color choices meet WCAG 2.1 AA contrast standards for text
- Graph views (Knowledge Explorer) include a list/table alternative for users who cannot interpret visual graphs
- @Gneva chat is keyboard-navigable; voice input supported via browser native API
- Meeting transcripts support text resizing to 200% without horizontal scroll
- Gneva's voice participation (Stage 4) includes a visual transcript of what Gneva says in real time for hearing-impaired attendees
- Dark mode supported from launch; honors system preference by default

---

## Appendix B: Key Metrics to Track

| Metric | Definition | Target |
|--------|-----------|--------|
| Time to first summary | Sign-up to first delivered summary | < 24 hours |
| Time to "aha" | First @Gneva query that returns a useful answer | < 7 days |
| Meeting ingestion rate | Meetings/week per active user | > 5 |
| Stage 2 conversion rate | % of users who promote to Stage 2 | > 60% within 30 days |
| @Gneva MAU | % of users who use @Gneva at least once/month | > 40% |
| Team expansion ratio | Avg team members added per initial user | > 2.5 within 90 days |
| 90-day retention | % of paid users active at day 90 | > 70% |
| NPS | Quarterly survey | > 50 |

---

*Document version 1.0 — Gneva Product Design & UX*
*For internal use — not for distribution*
