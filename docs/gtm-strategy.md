# Kura Go-to-Market & Business Strategy

**Version:** 1.0
**Date:** 2026-03-10

---

## 1. Market Sizing

### TAM (Total Addressable Market)
- **$42B** — Workplace AI market (Gartner 2025)
- 3.3B knowledge workers globally, ~1B in meetings regularly

### SAM (Serviceable Addressable Market)
- **$3.0-3.5B** — AI Meeting Assistants market (Market.us, 2025)
- 25-35% CAGR, projected to reach $72B by 2034
- Driven by remote/hybrid work adoption (62% of companies now hybrid)

### SOM (Serviceable Obtainable Market)
- **$50-100M** — Teams wanting organizational memory + active AI participation
- Target: 10,000-50,000 paying users within 3 years
- Initially: English-speaking, tech-forward companies, 10-500 employees

---

## 2. Competitive Moat Analysis

### Moat 1: Organizational Memory (Data Network Effect)
- Every meeting makes Kura more valuable — it knows more context, surfaces better answers
- Unlike per-meeting notetakers, switching away means losing months/years of organizational knowledge
- **Switching cost increases over time** — the longer you use Kura, the harder it is to leave

### Moat 2: Voice Participation (First-Mover)
- No competitor offers AI that speaks in meetings
- Building this requires meeting bot + knowledge graph + voice synthesis + real-time context retrieval
- **Complex integration** that takes 6-12 months to build well — head start matters

### Moat 3: Cross-Meeting Intelligence
- Individual meeting summaries are a commodity (20+ tools do this)
- Cross-meeting intelligence requires entity resolution, temporal reasoning, contradiction detection
- **Algorithmic complexity** creates a barrier — can't be replicated by just adding a feature

### Moat 4: Trust & Growth Stages
- Kura's 5-stage growth model builds trust over time
- Users who reach Stage 3+ (async team member) have deep organizational memory
- **Behavioral lock-in** — team workflows adapt around Kura's presence

### Vulnerability Assessment
| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|------------|
| Read.ai adds voice | Medium (12-18 mo) | High | Move fast on voice, lock in org memory moat |
| Microsoft Copilot cross-platform | Low (18-24 mo) | Very High | Target non-Microsoft-only shops, emphasize privacy |
| New entrant copies Kura | Medium | Medium | Data network effects, 6-12 month head start |
| Meeting fatigue reduces meeting count | Low | Medium | Position as "fewer, better meetings" tool |

---

## 3. Pricing Deep Dive

### Tier Structure

| Tier | Monthly | Annual | Target Segment |
|------|---------|--------|---------------|
| **Free** | $0 | $0 | Individual trial (5 meetings/mo) |
| **Pro** | $29 | $24/mo ($288/yr) | Individual power user |
| **Team** | $49/user | $42/user/mo ($504/user/yr) | Teams 5-50 |
| **Enterprise** | $79+/user | Custom | Organizations 50+ |

### Pricing Rationale

**Free tier exists to:**
- Remove friction for trial (no credit card required)
- 5 meetings = ~1 week of light use, enough to experience the "memory" value
- Convert to Pro when user hits limit and wants more

**Pro at $29 because:**
- Below psychological $30 threshold
- 2x basic notetakers ($10-15) but justified by knowledge graph + @Kura
- Below Read.ai Enterprise ($22.50) but with more capability
- Target: professionals who expense software easily

**Team at $49/user because:**
- Organizational memory is the key value unlock — worth premium
- Comparable to productivity tools (Notion Team $20 + Otter Business $20 + Fellow $15 = $55)
- Kura replaces 2-3 tools, so $49 feels like consolidation savings

**Enterprise at $79+ because:**
- Voice participation is genuinely unique — premium feature
- On-prem deployment has infrastructure costs
- SSO/SAML/compliance is table stakes for enterprise and justifies premium
- Custom pricing allows volume discounts for large deployments

### Annual Discount
- 17% discount for annual commitment ($24 vs $29, $42 vs $49)
- Standard SaaS practice, improves cash flow predictability
- Enterprise: always annual or multi-year

---

## 4. Unit Economics

### Per-User Cost Model

| Component | Free | Pro | Team | Enterprise |
|-----------|------|-----|------|-----------|
| Meetings/month (avg) | 5 | 10 | 12 | 15 |
| Recall.ai ($0.50/hr, avg 45min) | $1.88 | $3.75 | $4.50 | $5.63 |
| Claude API (extraction + queries) | $0.50 | $3.00 | $4.00 | $5.00 |
| Compute (GPU amortized) | $0.25 | $1.00 | $1.00 | $1.50 |
| Storage + DB | $0.10 | $0.50 | $0.75 | $1.00 |
| **Total COGS** | **$2.73** | **$8.25** | **$10.25** | **$13.13** |
| **Revenue** | **$0** | **$29** | **$49** | **$79** |
| **Gross Margin** | **-$2.73** | **72%** | **79%** | **83%** |

### At Scale (5,000+ users)
- Bulk Recall.ai pricing: ~$0.35/hr (30% discount)
- GPU amortization drops 50%
- Per-user COGS drops to $5-8
- **Gross margins: 78-92%**

### Key Metrics Targets

| Metric | Month 3 | Month 6 | Month 12 | Month 24 |
|--------|---------|---------|----------|----------|
| Users (total) | 50 | 500 | 5,000 | 25,000 |
| Paying users | 5 | 50 | 500 | 3,000 |
| MRR | $145 | $1,950 | $20K | $120K |
| ARR | $1,740 | $23,400 | $240K | $1.44M |
| Churn (monthly) | — | 8% | 5% | 3% |
| CAC | $0 | $50 | $75 | $100 |
| LTV | — | $362 | $580 | $1,200 |
| LTV/CAC | — | 7.2x | 7.7x | 12x |

---

## 5. Customer Acquisition Strategy

### Phase 1: Founder-Led Sales (Months 1-6)

**Channels:**
1. **Product Hunt launch** (Month 3) — Target #1 Product of the Day
2. **Twitter/X** — Build in public, share development journey, meeting culture insights
3. **LinkedIn** — Targeted posts about meeting productivity, organizational memory
4. **Hacker News** — Launch post + Show HN
5. **Direct outreach** — Email 100 eng managers / PMs at target companies
6. **Communities** — Lenny's Newsletter Slack, Product School, Engineering Manager Slack groups

**Target customer profile:**
- Tech companies, 10-100 employees
- Engineering or product teams
- Remote or hybrid
- Already using Zoom/Teams/Meet
- Pain: too many meetings, decisions get lost

**CAC target:** <$50 (mostly time investment, no paid ads)

### Phase 2: Content + Community (Months 6-12)

**Channels:**
1. **Blog** — "Meeting intelligence" content (SEO play)
   - "How to track decisions across meetings"
   - "The hidden cost of re-litigating decisions"
   - "Meeting culture metrics that actually matter"
2. **Newsletter** — Weekly "Meeting Intelligence Report" with industry data
3. **Webinars** — "How [Company] cut meeting time 30% with organizational memory"
4. **Partnerships** — Calendar tool integrations (Calendly, SavvyCal, Motion)
5. **Referral program** — 1 month free for each referral (after Pro conversion)

**CAC target:** <$100

### Phase 3: Outbound + Enterprise (Months 12-24)

**Channels:**
1. **Enterprise outbound** — Target companies with 100+ employees, SDR function
2. **Channel partners** — IT consultancies, workplace tool resellers
3. **Conference presence** — SaaStr, Dreamforce, HR Tech
4. **Case studies** — Publish ROI data from early customers
5. **Paid acquisition** — Google Ads ("meeting intelligence", "organizational memory"), LinkedIn Ads (targeting eng managers, VPs)

**CAC target:** <$500 for enterprise ($79/user, 50+ seats = $3,950+/mo)

---

## 6. Month-by-Month Roadmap (Year 1)

### Month 1: Foundation
- [ ] Project setup (FastAPI + React + Docker)
- [ ] Database schema + migrations
- [ ] User auth (email + Google OAuth)
- [ ] Recall.ai integration
- **Milestone:** Can join a meeting and record audio

### Month 2: Core Pipeline
- [ ] Transcription pipeline (faster-whisper)
- [ ] Speaker diarization (pyannote)
- [ ] Entity extraction (Claude API)
- [ ] Meeting summaries
- [ ] Basic dashboard (meeting list + detail)
- **Milestone:** Full meeting → summary pipeline working

### Month 3: Beta Launch
- [ ] Knowledge graph storage + basic search
- [ ] @Kura query interface (web)
- [ ] Pre-meeting briefs
- [ ] Onboarding flow
- [ ] Landing page
- [ ] Product Hunt launch
- **Milestone:** 50 beta users, first feedback

### Month 4: Iterate
- [ ] Improve entity extraction accuracy based on feedback
- [ ] Action item tracking with reminders
- [ ] Better search (semantic + keyword)
- [ ] Email notifications (summary + brief)
- [ ] Mobile-responsive dashboard
- **Milestone:** 80% summary accuracy, users returning daily

### Month 5: Monetize
- [ ] Stripe integration (Pro tier)
- [ ] Usage metering (meeting count)
- [ ] Upgrade prompts (free → Pro)
- [ ] Slack integration (Stage 3 start)
- **Milestone:** First paying customers, $500 MRR

### Month 6: Team Features
- [ ] Slack @Kura bot
- [ ] Organization/team management
- [ ] Shared organizational memory
- [ ] Team insights (speaking patterns, productivity)
- [ ] Team tier launch ($49/user)
- **Milestone:** 50 paying users, $2K MRR

### Month 7: Growth
- [ ] Referral program
- [ ] Blog + content engine
- [ ] Outlook calendar integration
- [ ] Improved knowledge graph (contradictions, patterns)
- [ ] API for integrations
- **Milestone:** 100 paying users, $5K MRR

### Month 8: Scale
- [ ] Teams bot integration
- [ ] Advanced action item tracking (cross-meeting)
- [ ] Weekly digest emails
- [ ] Performance optimization (sub-10min processing)
- **Milestone:** 200 paying users, $8K MRR

### Month 9: Voice Beta
- [ ] ElevenLabs integration for voice synthesis
- [ ] Voice participation prototype (reactive: respond when asked)
- [ ] Voice settings (enable/disable, voice persona selection)
- [ ] Beta test with 10 trusted users
- **Milestone:** Voice working in real meetings

### Month 10: Voice Launch
- [ ] Proactive voice (flag contradictions, provide context)
- [ ] Voice quality tuning
- [ ] Enterprise tier launch ($79+/user)
- [ ] SSO/SAML integration
- **Milestone:** Voice feature launched, first enterprise pilot

### Month 11: Enterprise
- [ ] Admin panel (user management, compliance, audit)
- [ ] Data retention policies
- [ ] SOC 2 Type I preparation
- [ ] On-premise deployment documentation
- **Milestone:** 2 enterprise pilots, $15K MRR

### Month 12: Scale
- [ ] Horizontal scaling (multiple GPU workers)
- [ ] Multi-language support (Stage 1: Spanish, French, German)
- [ ] Advanced analytics dashboard
- [ ] Customer success playbook
- **Milestone:** 500 paying users, $20K+ MRR

---

## 7. Financial Projections

### Year 1

| Month | Users | Paying | MRR | Cumulative Revenue | Expenses | Net |
|-------|-------|--------|-----|-------------------|----------|-----|
| 1 | 0 | 0 | $0 | $0 | $2,000 | -$2,000 |
| 2 | 0 | 0 | $0 | $0 | $2,000 | -$4,000 |
| 3 | 50 | 5 | $145 | $145 | $2,500 | -$6,355 |
| 4 | 100 | 12 | $350 | $495 | $2,500 | -$8,505 |
| 5 | 200 | 30 | $870 | $1,365 | $3,000 | -$10,635 |
| 6 | 350 | 50 | $1,950 | $3,315 | $3,500 | -$12,185 |
| 7 | 600 | 100 | $3,900 | $7,215 | $4,000 | -$12,285 |
| 8 | 1,000 | 200 | $6,800 | $14,015 | $5,000 | -$10,485 |
| 9 | 1,500 | 300 | $9,500 | $23,515 | $6,000 | -$6,985 |
| 10 | 2,500 | 400 | $14,000 | $37,515 | $8,000 | -$985 |
| 11 | 3,500 | 450 | $17,500 | $55,015 | $9,000 | $7,515 |
| 12 | 5,000 | 500 | $22,000 | $77,015 | $10,000 | $19,515 |

**Year 1 Total Revenue:** ~$77K
**Year 1 Total Expenses:** ~$57.5K
**Year 1 Net:** ~$19.5K (break-even Month 10)

### Monthly Expenses Breakdown

| Category | Months 1-3 | Months 4-6 | Months 7-12 |
|----------|-----------|-----------|-------------|
| Infrastructure (GPU, DB, hosting) | $500 | $1,000 | $2,000-5,000 |
| API costs (Claude, Recall.ai) | $0 | $500 | $1,000-3,000 |
| Tools & services | $200 | $300 | $500 |
| Domain, email, misc | $100 | $100 | $100 |
| Marketing (Month 7+) | $0 | $0 | $500-1,000 |
| Legal (Month 9+) | $0 | $0 | $500 |
| **Total** | **$800-2,000** | **$1,900-3,500** | **$4,600-10,000** |

Note: Assumes solo founder, no salary. Founder takes distributions from profit.

### Year 2-3 Projections

| Metric | Year 1 | Year 2 | Year 3 |
|--------|--------|--------|--------|
| Total users | 5,000 | 25,000 | 100,000 |
| Paying users | 500 | 3,000 | 12,000 |
| ARR | $264K | $1.44M | $5.76M |
| Gross margin | 72% | 80% | 85% |
| Team size | 1 | 3-5 | 8-12 |
| Monthly burn | $10K | $50K | $150K |

---

## 8. Risk Analysis

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Recall.ai API instability | Low | High | Fallback to Nylas; desktop recording SDK |
| Transcription accuracy <90% | Medium | High | Combine faster-whisper + Deepgram; user correction loop |
| Claude API cost overrun | Medium | Medium | Batch processing; cache common extractions; local LLM fallback |
| pgvector scaling limits | Low | Medium | Migrate to dedicated vector DB if needed (Qdrant) |
| Real-time voice latency >2s | Medium | Medium | Deepgram streaming + ElevenLabs <300ms; optimize context retrieval |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Low free→paid conversion | Medium | High | Improve onboarding; A/B test paywalls; shorter free limit |
| Enterprise sales cycle >6 months | High | Medium | Focus on self-serve; enterprise is bonus, not dependency |
| Competitor copies features | Medium | Medium | Data network effect moat; move fast; voice first-mover advantage |
| Solo founder burnout | Medium | High | Hire first engineer at $10K MRR; automate ops; take breaks |

### Regulatory Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Recording consent violations | Medium | Very High | Per-meeting consent engine; jurisdiction-aware policies |
| GDPR data subject requests | High | Medium | Automated data export/deletion; data processing agreements |
| AI regulation (EU AI Act) | Low (near-term) | Medium | Transparency by design; human override always available |

---

## 9. Legal Considerations

### Recording Consent Laws

| Jurisdiction | Consent Type | Requirement |
|-------------|-------------|-------------|
| **California** | Two-party | All participants must consent |
| **New York** | One-party | One participant must consent |
| **Illinois** | Two-party | All participants must consent |
| **EU (GDPR)** | Informed consent | Clear notice + legitimate interest or consent |
| **UK** | Informed consent | Similar to GDPR |
| **Canada** | One-party (federal) | Varies by province |
| **Australia** | Mixed | Varies by state (most are one-party) |

### Kura's Approach
1. **Always announce** — Kura introduces itself when joining: "Hi, I'm Kura, an AI assistant that will be taking notes for this meeting."
2. **Opt-out button** — Any participant can say "Kura, stop recording" or click opt-out in meeting chat
3. **Org policy** — Admins configure default consent mode per jurisdiction
4. **Audit trail** — All consent decisions logged for compliance

### Other Legal Requirements
- **Terms of Service** — Clear data processing terms, AI use disclosure
- **Privacy Policy** — GDPR-compliant, data retention policies, right to deletion
- **Data Processing Agreement (DPA)** — Required for enterprise/EU customers
- **SOC 2 Type I** — Target Month 9-12 (required for enterprise)
- **Business insurance** — Errors & omissions, cyber liability

---

## 10. Bootstrapping vs. Fundraising

### Bootstrap Path (Recommended)

**Advantages:**
- Full ownership and control
- Forces focus on revenue from day 1
- Unit economics support it (72-83% gross margins)
- No dilution, no board, no fundraising distraction
- Can reach profitability at ~50 Pro users ($1,450 MRR covers infrastructure)

**Break-even timeline:**
- Month 10 at current projections
- Conservative: Month 12-14

**When to consider fundraising:**
- If growth outpaces ability to serve (good problem)
- If a competitor raises significant funding and starts copying
- If enterprise demand requires sales team before revenue supports it
- Target: Seed round at $1M+ ARR, $20M valuation, 5% dilution

### Fundraise Path (Alternative)

**If raising, target:**
- **Pre-seed:** $250-500K at $5M valuation (Month 3-6, with beta users + traction)
- **Seed:** $1-2M at $15-20M valuation (Month 12-18, with $500K+ ARR)
- **Series A:** $5-10M at $50M+ valuation (Month 24-30, with $2M+ ARR)

**Use of funds:**
- 60% Engineering (hire 2-3 engineers)
- 20% GTM (first sales hire, content, events)
- 20% Infrastructure + ops

**Investors to target:**
- Solo GP funds that invest in AI/SaaS (Jason Lemkin's SaaStr Fund, Elad Gil, etc.)
- AI-focused micro VCs
- Angels: former founders of Otter, Grain, or similar tools

---

## 11. Solo Founder Execution Guide

### Time Allocation (Months 1-6)

| Activity | Hours/Week | Notes |
|----------|-----------|-------|
| Engineering | 30-35 | Core product development |
| Customer conversations | 5-8 | Beta user calls, support |
| Content/marketing | 3-5 | Twitter, LinkedIn, blog |
| Admin/ops | 2-3 | Billing, legal, infra |
| **Total** | **40-50** | Sustainable pace |

### Tools for Solo Founder

| Need | Tool | Cost |
|------|------|------|
| Error tracking | Sentry (free tier) | $0 |
| Analytics | PostHog (free tier) | $0 |
| Email | Resend | $0 (free tier) |
| Payments | Stripe | 2.9% + $0.30 |
| Auth | Auth.js (self-hosted) | $0 |
| Hosting | Fly.io or Railway | $20-100/mo |
| GPU | RunPod or Lambda | $0.40-0.80/hr |
| Domain + DNS | Cloudflare | $10/yr |
| Legal | Termly (privacy/terms gen) | $10/mo |

### First Hire

**When:** $8-10K MRR (Month 7-8)
**Role:** Full-stack engineer (strong backend, comfortable with ML ops)
**Comp:** $130-150K + 1-2% equity
**Why:** Unblock voice features, handle scale, let founder focus on product + GTM

### Key Decisions Timeline

| When | Decision |
|------|----------|
| Month 1 | Cloud hosting provider (Fly.io vs Railway vs Render) |
| Month 3 | Launch strategy (PH first vs invite-only beta) |
| Month 5 | Pricing adjustments based on conversion data |
| Month 6 | Hire or not (based on MRR trajectory) |
| Month 8 | Enterprise: build or wait? |
| Month 10 | Fundraise or continue bootstrapping? |
| Month 12 | Year 2 strategy: vertical (industry-specific) or horizontal (features)? |

---

## 12. Key KPIs to Track

### Product Metrics
- **Activation rate:** % of signups who have 1+ meeting processed within 7 days
- **Weekly active users:** Users who view dashboard or query @Kura in past 7 days
- **Meetings per user per week:** Indicator of engagement depth
- **@Kura query count:** Usage of knowledge retrieval (key value indicator)
- **Summary accuracy rating:** User feedback on summary quality

### Business Metrics
- **MRR / ARR:** Monthly and annual recurring revenue
- **Free → Pro conversion rate:** Target 5-10% within 30 days
- **Pro → Team expansion rate:** Individual users bringing their team
- **Monthly churn:** Target <5% for Pro, <3% for Team
- **Net Revenue Retention:** Target >110% (expansion > churn)
- **CAC payback period:** Target <4 months
- **LTV/CAC:** Target >5x

### Operational Metrics
- **Processing time:** Audio to complete summary (<15 min target)
- **API uptime:** >99.5% (target 99.9% by Month 12)
- **Support response time:** <4 hours for Pro, <1 hour for Enterprise
- **Bug resolution time:** P0 <4 hours, P1 <24 hours
