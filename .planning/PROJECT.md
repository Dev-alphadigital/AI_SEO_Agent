# AI SEO Agent

## What This Is

An AI-powered SEO reoptimization brief generator for a multi-client agency. Given a URL and target keyword, it gathers GSC performance data, scrapes competitors, extracts existing page SEO elements, compiles everything into a structured table, sends it to the client's Gemini Gem for recommendations, and produces a standardized Google Doc brief that writers/strategists can execute with minimal edits.

## Core Value

Generate ready-to-implement SEO reoptimization briefs by automating manual data gathering — improving search performance and LLM visibility while staying aligned to each client's positioning and audience. Writers receive a complete, data-backed brief without doing manual research.

## Requirements

### Validated

(None yet — ship to validate with client's 10-15 test URLs)

### Active

- [ ] Accept URL + target keyword as input
- [ ] Extract existing SEO elements from target page (metadata, title, description, H1/H2/H3)
- [ ] ~~Pull ranking data from Google Search Console API~~ — REMOVED: client decision, Claudia Guada updating workflow
- [ ] Scrape top 10 SERP results for headings/structure, word count, keywords covered
- [ ] Gather questions from People Also Ask, related searches
- [ ] Identify secondary/supporting keywords for the target keyword
- [ ] Score existing page content quality against top competitors
- [ ] Analyze competitor gaps — what competitors cover that the page doesn't
- [ ] Generate suggested H2/H3 content structure based on competitor analysis
- [ ] Include backlink/domain authority data (via Ahrefs API)
- [ ] Compile all data into automated structured table
- [ ] Send table to client's Gemini Gem for AI-powered recommendations
- [ ] Produce structured Google Doc with current state + recommended state side-by-side
- [ ] Per-client configuration: templates, brand/voice context, Drive folder, Slack channel
- [ ] Per-client access isolation — each client only sees their own briefs
- [ ] Slack notification when brief is ready
- [ ] n8n orchestration layer for triggering workflows
- [ ] Python backend for scraping, analysis, and data processing
- [ ] n8n ↔ Python communication via HTTP endpoints

### Out of Scope

- ~~Ahrefs API integration~~ — MOVED TO ACTIVE: client provided API key
- Content writing/generation — the agent produces briefs, not finished content
- New content briefs — v2 feature, v1 focuses on reoptimization
- Mobile app or complex UI — output is Google Docs, trigger is n8n interface
- Universal SEO guidelines — multi-client environment, tone/brand applied dynamically per client

## Context

- **Client:** Multi-client agency with traditional writers and SEO writers. Some AI exposure, comfortable with low-code tools (Zapier/n8n). No custom UI needed — Google Docs and n8n dashboard are sufficient.
- **Environment:** Multi-client — different clients have different templates, brand voices, and positioning. No single universal SEO guide; brief acceptance criteria serve as build requirements, tone/brand guidance applied dynamically from client profile.
- **Current process:** Manual keyword research, manual competitor analysis, manual brief creation. Time-consuming and inconsistent.
- **Data source strategy:** Google Search Console via API (client has access). Ahrefs deferred — use free alternatives initially. Architect data layer so Ahrefs API plugs in later.
- **Gemini integration:** Client has already created a custom Gemini Gem. Workflow sends compiled data to the Gem and includes its recommendations in the brief output.
- **Architecture:** Python backend handles scraping, analysis, data processing. n8n acts as orchestration/trigger layer. Communication via HTTP. n8n also handles Google Docs generation and delivery.
- **Testing:** Client providing 10-15 historical URLs with approved briefs (mix of performing/underperforming) for validation. Some include approved briefs as "expected output" reference.
- **Client-provided assets:** Brief templates, sample approved briefs, client profile documents (to be received).
- **Timeline:** ~2 weeks, capped hours. Iterative — deliver, get feedback, refine. 1-3 business day feedback SLA.

## Constraints

- **Tech stack**: Python (AI/backend) + n8n (orchestration/triggers) — client requirement
- **Timeline**: ~2 weeks with capped hours — iterative delivery, not waterfall
- **Data access**: No Ahrefs API initially — must work with free alternatives
- **Output format**: Google Docs — non-negotiable, this is what writers use
- **Users**: Low-code comfort level — n8n interface is the interaction point, no CLI
- **Multi-client**: Must support per-client templates, Drive folders, Slack channels, and access isolation
- **Gemini dependency**: Recommendations come from client's existing Gemini Gem, not our own LLM

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + n8n architecture | Client specified; Python for AI/scraping, n8n for workflow orchestration | Confirmed |
| Ahrefs API for SEO data | Client provided API key; replaces free alternatives plan | Updated 2026-02-16 |
| GSC removed from workflow | Client decision — risks access to client data; Claudia Guada updating workflow | Updated 2026-02-16 |
| Google Docs as output | Writers already work in Google Docs; no new tools to learn | Confirmed |
| HTTP communication between n8n and Python | Standard, simple, well-supported by both platforms | Confirmed |
| Gemini Gem for recommendations | Client already built the Gem; we feed it data, it returns recommendations | Confirmed |
| Multi-client config | Agency environment requires per-client templates and isolation | Confirmed |
| Reoptimization first, new content v2 | Focus v1 on reoptimization briefs; new content briefs deferred to v2 | Confirmed |
| Current state + recommended state format | Brief shows side-by-side comparison so writers see exactly what to change | Confirmed |

## Pending from Client

- [ ] 10-15 historical test URLs with approved briefs
- [ ] Brief templates per client
- [ ] Client profile documents (brand/voice/tone)
- [x] ~~GSC/API access credentials~~ — Skipped per client decision
- [x] Ahrefs API key — Received
- [ ] Gemini Gem access details (API key, Gem ID)
- [ ] Shared Google Drive folder(s) per client
- [ ] Slack channel webhook(s) per client

---
*Last updated: 2026-02-11 after client interview — refined to multi-client reoptimization focus with Gemini Gem integration*
