# Kura Product Design & UX

**Version:** 1.0
**Date:** 2026-03-10

---

## 1. Brand Identity

### Name
**Kura** — "to grow/nurture" in Maori, "treasure" in Japanese. Reflects both the product's growth-stage architecture and its role as guardian of organizational knowledge.

### Personality
- **Helpful, not pushy** — Offers context when useful, stays quiet when not
- **Discreet** — Handles sensitive meeting content with care
- **Growing** — Gets more useful over time, like a team member learning the ropes
- **Trustworthy** — Always cites sources, admits uncertainty, never fabricates

### Voice & Tone
- Conversational but professional
- Concise — respects people's time
- Uses "I" — speaks as a team member, not a tool
- Never uses corporate jargon or filler

### Design Language
- **Colors:** Deep navy (#1a1a2e) primary, warm amber (#f5a623) accent, clean whites
- **Typography:** Inter for UI, JetBrains Mono for data/transcripts
- **Aesthetic:** Clean, minimal, information-dense. More Bloomberg terminal than Notion
- **Logo concept:** Abstract "K" that suggests both a knowledge graph node and a person

---

## 2. Design Principles

1. **Trust through transparency** — Always show where information comes from. Link to source transcript timestamps.
2. **Progressive disclosure** — Start simple, reveal depth on demand. Don't overwhelm.
3. **Memory over features** — Every screen should make organizational memory visible and useful.
4. **Respect attention** — Only surface information that's relevant right now. No notification spam.
5. **Grow with the user** — Kura's capabilities unlock as trust is established, not behind paywalls.

---

## 3. User Personas

### Sarah — Engineering Manager
- **Age:** 34, manages team of 8
- **Meetings:** 15-18/week (standups, 1:1s, planning, cross-team syncs)
- **Pain:** Can't remember what was decided 3 meetings ago. Spends 20 min before each meeting reviewing notes. Action items fall through cracks.
- **Goal:** Cross-meeting memory so she can walk into any meeting with full context
- **Kura moment:** "Kura, what did we decide about the API migration timeline?" → Surfaces decision from 3 different meetings over 2 weeks

### Marcus — Product Manager
- **Age:** 29, works with 4 engineering teams + design + leadership
- **Meetings:** 12-15/week, heavy on stakeholder alignment
- **Pain:** Decisions get re-litigated. Different teams have different understanding of what was agreed. Spends hours writing meeting recaps no one reads.
- **Goal:** Single source of truth for product decisions across all stakeholders
- **Kura moment:** "Kura, any contradictions between what engineering said about the timeline and what we told leadership?" → Flags that eng estimated 8 weeks but PM told leadership 6

### Priya — VP of Engineering
- **Age:** 42, oversees 40 engineers across 5 teams
- **Meetings:** 10-12/week, mostly leadership + skip-levels
- **Pain:** Too many meetings to attend. Misses critical context from meetings she can't join. Needs organizational intelligence, not just meeting notes.
- **Goal:** Understand team health, decision patterns, and project status without attending every meeting
- **Kura moment:** "Kura, what's happening with Project Atlas? I haven't been in those meetings for 2 weeks." → Comprehensive brief: recent decisions, blockers, team sentiment, action items

### James — Sales Director
- **Age:** 38, manages 6 AEs + 2 SDRs
- **Meetings:** 20+/week (deal calls, team syncs, pipeline reviews)
- **Pain:** Reps forget commitments made to prospects. Deal context lives in people's heads. CRM is always outdated.
- **Goal:** Automatic deal memory — what was promised, who said what, next steps
- **Kura moment:** After a customer call: "Kura, what did we promise Acme Corp about the integration timeline?" → Surfaces exact quote from call 3 weeks ago

### Chen — Startup CEO
- **Age:** 31, 12-person startup, wears every hat
- **Meetings:** 8-10/week but high context-switching
- **Pain:** No PM, no chief of staff. Decisions made in meetings aren't tracked. New hires take months to onboard because institutional knowledge is in founders' heads.
- **Goal:** Kura IS the PM — tracks decisions, follows up on action items, onboards new team members with organizational context
- **Kura moment:** New hire asks "Why did we choose Postgres over MongoDB?" → Kura surfaces the original technical discussion from 6 months ago with full reasoning

---

## 4. Growth Stages — User Experience

### Stage 1: Silent Observer — "I noticed"
**What the user sees:**
- Kura joins meetings automatically (or on invite)
- After each meeting: summary email/notification with key points
- Dashboard shows meeting feed with searchable transcripts
- Entities start appearing: people mentioned, topics discussed

**Trust signal:** "Kura is learning your organization. 12 meetings processed, 3 projects identified, 47 decisions tracked."

**UX tone:** Quiet, unobtrusive. "I'm just here to listen and remember."

### Stage 2: Post-Meeting Analyst — "Here's what happened"
**What the user sees:**
- Richer summaries with decision tracking and action items
- Pre-meeting briefs: "Before your 2pm with marketing, here's what was discussed last time..."
- Pattern detection: "The API migration has been discussed in 5 meetings without resolution"
- Action item tracking with follow-up reminders

**Trust signal:** "Kura has identified 3 overdue action items from last week's planning meeting."

**UX tone:** Proactive but not overwhelming. "Here's context I thought you'd find useful."

### Stage 3: Async Team Member — "Let me help"
**What the user sees:**
- @Kura in Slack/Teams — ask questions, get answers from organizational memory
- Cross-meeting search: "What did we decide about..." works across all meetings
- Kura can answer questions from people who weren't in a meeting
- Weekly digest: key decisions, open items, project updates

**Trust signal:** Someone asks @Kura a question in Slack, gets a perfect answer with source meeting links. "How did it know that?!"

**UX tone:** Conversational, like messaging a knowledgeable colleague. "Based on the Q3 planning meeting on March 5th, the team decided..."

### Stage 4: Active Participant — "Can I add something?"
**What the user sees:**
- Kura speaks in meetings (opt-in, configurable)
- Starts with reactive: "Kura, what did we decide about X?" → speaks answer
- Graduates to proactive: "Just a note — this contradicts what was agreed in last week's planning meeting"
- Has a distinct, professional voice

**Trust signal:** Kura catches a contradiction that would have caused a week of wasted work.

**UX tone:** Confident but respectful. "I want to flag something from our previous discussion..."

### Stage 5: Autonomous PM — "I'll handle it"
**What the user sees:**
- Kura proactively follows up on action items via Slack DM
- Generates weekly project status reports from meeting content
- Can represent absent team members: "Sarah couldn't make it, but she wanted to raise..."
- Maintains and updates project documentation automatically

**Trust signal:** Kura sends a summary of a meeting you couldn't attend, with exactly the context you needed.

**UX tone:** Professional, autonomous. "I've updated the project tracker based on today's discussion. Here are 3 items that need your attention."

---

## 5. @Kura Conversation Examples

### Decision Retrieval
```
User: @Kura what did we decide about the pricing model?
Kura: The pricing model has evolved across 4 discussions:

  1. Feb 12 (Product Sync) — Marcus proposed freemium with $29 Pro tier
  2. Feb 19 (Leadership) — Priya pushed for higher Team tier ($49/user)
  3. Feb 26 (Product Sync) — Team agreed on 3 tiers: Free, Pro ($29), Team ($49)
  4. Mar 5 (Board Prep) — Chen confirmed this structure for board deck

  Current decision: 3-tier model (Free / $29 Pro / $49 Team)
  Status: Active, confirmed by CEO
  Source: Board Prep meeting, Mar 5 [link]
```

### Person Lookup
```
User: @Kura who owns the API redesign?
Kura: The API redesign is owned by Alex Chen (Backend Lead).

  - Assigned: Feb 19 sprint planning
  - Last update: Mar 3 standup — "On track for end of sprint, v2 endpoints done"
  - Blockers mentioned: Waiting on auth team for OAuth scope changes
  - Related: Sarah approved the architecture in the Mar 1 design review
```

### Project Brief
```
User: @Kura brief me on Project Atlas
Kura: Project Atlas — Mobile App Redesign

  Status: In Progress (Sprint 3 of estimated 6)
  Owner: Marcus (PM), Design lead: Jamie

  Recent decisions:
  - Mar 5: Decided to drop offline mode from v1 (saves 2 sprints)
  - Mar 3: Approved new navigation pattern (bottom tabs)
  - Feb 28: Moved launch from April to May due to auth dependency

  Open action items (3):
  - Jamie: Final mockups for settings screen (due Mar 12)
  - Alex: API endpoint for push notifications (due Mar 15)
  - Marcus: Stakeholder review deck (due Mar 10)

  Risk flag: The May launch depends on auth team finishing OAuth by Apr 1.
  Last discussed: Mar 5 sprint planning [link]
```

### Contradiction Detection
```
User: @Kura any contradictions in recent planning?
Kura: I found 2 potential contradictions:

  1. Timeline conflict:
     - Mar 3 (Eng standup): Alex said "API redesign needs 3 more weeks"
     - Mar 5 (Leadership): Marcus told Priya "API will be done next sprint" (2 weeks)
     Severity: High — 1 week gap could affect downstream planning

  2. Scope conflict:
     - Feb 26 (Product sync): Team agreed to cut offline mode from v1
     - Mar 4 (Customer call): James told Acme Corp "offline support is planned for launch"
     Severity: Medium — external commitment vs internal decision
```

### Action Item Status
```
User: @Kura what action items are overdue?
Kura: 4 overdue action items:

  1. Jamie — Settings screen mockups (due Mar 8, 2 days overdue)
     Source: Mar 1 design review
  2. DevOps — Set up staging environment (due Mar 5, 5 days overdue)
     Source: Feb 26 sprint planning
  3. Marcus — Write product brief for Board (due Mar 7, 3 days overdue)
     Source: Feb 28 leadership sync
  4. Sarah — Review Alex's API architecture doc (due Mar 6, 4 days overdue)
     Source: Mar 1 design review

  Want me to send reminders via Slack?
```

### Meeting Culture
```
User: @Kura how productive are our meetings?
Kura: Meeting analysis for your team (last 30 days):

  Total meetings: 47 | Total hours: 38h
  Avg decisions per meeting: 1.8
  Action items generated: 34 (67% completed on time)

  Most productive: Sprint planning (3.2 decisions/meeting)
  Least productive: Weekly status (0.4 decisions/meeting)

  Speaking distribution:
  - Sarah: 28% (most in 1:1s, least in large meetings)
  - Alex: 22%
  - Marcus: 31% (dominates product syncs)
  - Others: <10% each

  Suggestion: Weekly status meetings average 0.4 decisions and could
  potentially be replaced with async updates.
```

### New Hire Onboarding
```
User: @Kura I'm new. What should I know about how this team works?
Kura: Welcome! Here's what I've learned about the team:

  Team structure: 8 engineers, 1 PM (Marcus), 1 design (Jamie)
  Manager: Sarah Chen

  Key projects:
  - Project Atlas (mobile redesign) — Sprint 3, launching May
  - API v2 redesign — Alex leading, 3 weeks out
  - Auth service migration — blocked on OAuth scope decision

  Team norms I've observed:
  - Standups: 9:15am, kept to 15 min
  - Sprint planning: Mondays 2pm, usually runs long
  - Code reviews expected within 24h
  - Decisions are made in product syncs (Tuesdays), not standups

  Recent big decisions:
  - Dropped offline mode from Atlas v1 (Feb 26)
  - Moving to PostgreSQL from MongoDB (Jan decision)
  - Adopted feature flags via LaunchDarkly (Feb 12)

  Ask me anything about past meetings or decisions!
```

### Pre-Meeting Brief
```
Kura: Pre-meeting brief for "Sprint Planning" (2:00 PM today)

  Last meeting: Feb 26 (Sprint 2 planning)
  Attendees then: Sarah, Alex, Marcus, Jamie, Dev, Priya

  Open items from last time:
  ✅ Alex: API endpoint scaffolding (completed Mar 1)
  ❌ Jamie: Settings mockups (overdue, due Mar 8)
  ✅ Marcus: Priority ranking for Sprint 3 (completed Feb 28)

  Topics likely to come up:
  - Sprint 3 scope (Marcus prepared backlog)
  - Atlas timeline review (May launch at risk)
  - Auth team dependency (still unresolved)

  Context you might need:
  - Priya asked about Atlas timeline in leadership sync (Mar 5)
  - Alex mentioned potential tech debt in standup (Mar 7)
```

---

## 6. Key Screens

### 6.1 Dashboard
**Purpose:** Home base — what happened recently, what's coming up

**Layout:**
- **Left sidebar:** Navigation (Dashboard, Meetings, Knowledge, @Kura, Insights, Settings)
- **Main area — top:** Upcoming meetings (next 24h) with "Join" buttons and pre-meeting brief links
- **Main area — center:** Meeting feed (recent meetings, latest first) — each card shows title, date, participant avatars, key topics, action item count
- **Main area — right:** Kura memory health (entities tracked, decisions this week, overdue items)
- **Bottom bar:** Quick @Kura input — "Ask Kura anything..."

### 6.2 Meeting Detail
**Purpose:** Deep dive into a single meeting

**Layout:**
- **Header:** Meeting title, date, duration, participants (avatars), recording status
- **Tab bar:** Transcript | Summary | Entities | Action Items
- **Transcript tab:** Speaker-attributed transcript with timestamps. Click timestamp to jump to audio. Hover to see speaker info. Highlighted entities (decisions in blue, action items in amber, topics in green)
- **Summary tab:** AI summary with key points, each linked to transcript timestamp
- **Entities tab:** Cards for each extracted entity — decisions, action items, people mentioned, topics. Each links to its knowledge graph entry
- **Action items tab:** List with assignee, due date, status. "Mark complete" button

### 6.3 Knowledge Explorer
**Purpose:** Browse and search organizational memory

**Layout:**
- **Search bar:** Semantic search across all entities ("pricing decisions", "what Alex said about...")
- **Filter tabs:** All | People | Projects | Decisions | Action Items | Topics
- **Results list:** Cards showing entity details, related meetings, temporal history
- **Graph view toggle:** Interactive node graph showing relationships between entities. Nodes = entities, edges = relationships. Click node to see details. Zoom/pan
- **Timeline view:** Decisions and action items on a timeline, showing how they evolved

### 6.4 @Kura Chat
**Purpose:** Conversational interface for queries

**Layout:**
- **Chat interface:** Message bubbles, Kura's responses include formatted cards for structured data
- **Source citations:** Each answer includes clickable links to source meetings + timestamps
- **Suggested queries:** "Try asking..." prompts based on recent meetings
- **Confidence indicator:** Visual indicator of how confident Kura is in the answer
- **Feedback:** Thumbs up/down on each response for quality improvement

### 6.5 Team Insights
**Purpose:** Meeting culture metrics and team health

**Layout:**
- **Top cards:** Total meetings this period, total hours, decisions made, action items completed
- **Meeting productivity chart:** Decisions per meeting over time
- **Speaking distribution:** Bar chart by person across meetings
- **Meeting types:** Breakdown (standup, planning, 1:1, sync, etc.) with productivity scores
- **Action item completion rate:** Trend line over time
- **Recommendations:** AI-generated suggestions ("Consider making weekly status async — 0.4 decisions/meeting avg")

### 6.6 Settings
**Purpose:** Configure integrations, permissions, Kura's behavior

**Sections:**
- **Profile:** Name, email, notification preferences
- **Calendar:** Connected calendars, which meetings Kura should join
- **Integrations:** Slack, Teams connection status
- **Kura behavior:** Growth stage selection, proactivity level, voice settings (Stage 4)
- **Privacy:** Data retention, export, deletion
- **Billing:** Current plan, usage, upgrade

### 6.7 Admin Panel (Team/Enterprise)
**Purpose:** Org-wide management

**Sections:**
- **Members:** User list, roles, invite links
- **Security:** SSO/SAML configuration, 2FA enforcement
- **Data:** Retention policies, export, compliance settings
- **Usage:** Org-wide meeting stats, API usage, storage
- **Audit log:** Who accessed what data, when
- **Billing:** Org subscription, seat management

---

## 7. Information Architecture

```
Kura App
├── Dashboard
│   ├── Upcoming meetings
│   ├── Recent meeting feed
│   ├── Memory health stats
│   └── Quick @Kura input
├── Meetings
│   ├── Meeting list (filterable by date, project, person)
│   └── Meeting detail
│       ├── Transcript
│       ├── Summary
│       ├── Entities
│       └── Action items
├── Knowledge
│   ├── Search
│   ├── People directory
│   ├── Projects
│   ├── Decisions (timeline)
│   ├── Action items (kanban/list)
│   ├── Topics
│   └── Graph view
├── @Kura Chat
│   ├── Conversation
│   ├── Suggested queries
│   └── History
├── Insights (Team+)
│   ├── Meeting productivity
│   ├── Speaking patterns
│   ├── Action item tracking
│   └── Recommendations
├── Settings
│   ├── Profile
│   ├── Calendar connections
│   ├── Integrations
│   ├── Kura behavior
│   ├── Privacy
│   └── Billing
└── Admin (Team+)
    ├── Members
    ├── Security
    ├── Data & compliance
    ├── Usage
    ├── Audit log
    └── Billing
```

---

## 8. Onboarding Flow

### Step 1: Sign Up (30 seconds)
- Email/password or Google OAuth
- "What's your role?" (dropdown: Engineering, Product, Sales, Leadership, Other)

### Step 2: Connect Calendar (60 seconds)
- "Connect your Google Calendar so Kura knows which meetings to join"
- OAuth flow → calendar list → select which calendars to monitor
- Toggle: "Join all meetings" vs "Only meetings I invite Kura to"

### Step 3: First Meeting (automatic)
- Kura joins next meeting automatically
- After meeting: push notification "Your first meeting summary is ready!"
- Dashboard shows the meeting with summary, transcript, entities

### Step 4: Discover Memory (day 3-5)
- After 3+ meetings: "Kura is building your organizational memory. 12 people identified, 5 decisions tracked."
- Prompt: "Try asking @Kura a question about your recent meetings"

### Step 5: Invite Team (day 7)
- "Kura works better with your whole team. Invite colleagues to build shared organizational memory."
- Invite flow with personalized message

---

## 9. Pricing Strategy

| Tier | Price | Target | Value Proposition |
|------|-------|--------|-------------------|
| **Free** | $0 | Try before buy | 5 meetings/month, basic summaries — enough to see value |
| **Pro** | $29/mo | Individual power user | Unlimited meetings, full knowledge graph, @Kura chat — replaces manual note-taking |
| **Team** | $49/user/mo | Teams 5-50 | Shared organizational memory, team insights, Slack — replaces knowledge management overhead |
| **Enterprise** | $79+/user/mo | 50+ employees | Voice participation, on-prem, SSO, compliance — replaces part of PM function |

**Why these prices:**
- Free tier proves value without friction (5 meetings = ~1 week of light use)
- Pro at $29 is below Gong ($100+) but above basic notetakers ($10-15) — positioned on memory, not transcription
- Team at $49 reflects organizational value (shared memory > individual notes)
- Enterprise at $79+ justified by voice participation + compliance + on-prem — unique in market

---

## 10. Growth Loops

### Loop 1: Summary Share
```
User has meeting → Kura sends summary → User shares with absent colleague
→ Colleague says "This is great, where's it from?" → Signs up
```
**Mechanic:** "Share summary" button in every meeting card. Shared link works without login (read-only). CTA: "Get Kura for your meetings"

### Loop 2: Memory Surprise
```
User asks @Kura a question → Gets perfect answer with source citations
→ "How did it know that?!" → Tells colleague → Colleague signs up
```
**Mechanic:** Every answer includes source meeting links. Answers are shareable. The "wow" moment drives word-of-mouth.

### Loop 3: Pre-Meeting Brief
```
User gets pre-meeting brief → Walks in prepared → Team notices
→ "How do you always know what happened last time?" → "It's Kura"
```
**Mechanic:** Briefs sent 15 min before meetings. Include "Powered by Kura" footer when shared.

### Loop 4: Manager Cascade
```
Manager sees team insights → Shares with their manager → VP wants it for all teams
→ Top-down adoption → Enterprise deal
```
**Mechanic:** Team insights exportable as PDF/Slack post. Include org-level benchmarks to drive expansion.

---

## 11. Accessibility

- WCAG 2.1 AA compliance
- Full keyboard navigation
- Screen reader support for all interactive elements
- High contrast mode
- Transcript font size adjustable
- Color-blind friendly palette (no red/green only distinctions)
