# AI SEO Agent

## What This Is

An AI-powered SEO content agent that automates keyword research, competitor analysis, and content brief generation for a content team of traditional and SEO writers. Given a URL and target keyword (or a batch), it gathers data from multiple sources, analyzes competitor pages, scores content quality, and produces structured Google Docs that writers use to reoptimize existing pages or create new content.

## Core Value

Writers receive a complete, data-backed content brief — keywords, structure, gaps, and scores — without doing manual research, cutting content production time significantly.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Accept URL + target keyword as input (single or batch via spreadsheet)
- [ ] Pull ranking data from Google Search Console API
- [ ] Scrape top 10 SERP results for headings/structure, word count, keywords covered, domain rating, traffic, authority score
- [ ] Gather questions from People Also Ask, related searches, AlsoAsked, and competitor pages
- [ ] Identify secondary/supporting keywords for the target keyword
- [ ] Score existing page content quality against top competitors
- [ ] Analyze competitor gaps — what competitors cover that the page doesn't
- [ ] Generate suggested H2/H3 content structure template based on competitor analysis
- [ ] Include backlink data in output
- [ ] Produce structured Google Doc as output (auto-generated, dropped in shared folder)
- [ ] Support both reoptimization briefs (existing pages) and new content briefs
- [ ] n8n orchestration layer for triggering workflows (webhooks, manual, scheduled)
- [ ] Python backend for AI processing, scraping, and data analysis
- [ ] n8n ↔ Python communication via HTTP endpoints

### Out of Scope

- Ahrefs API integration — start with free/local alternatives, architect for future plug-in
- Content writing/generation — the agent produces briefs, not finished content
- User authentication/multi-tenancy — single client deployment
- Mobile app or complex UI — output is Google Docs, trigger is n8n interface

## Context

- **Client:** Content team with traditional writers and SEO writers. Some AI exposure, comfortable with low-code tools (Zapier/n8n). They do not need a custom UI — Google Docs and n8n dashboard are sufficient.
- **Current process:** Manual keyword research, manual competitor analysis, manual brief creation. Time-consuming and inconsistent.
- **Data source strategy:** Google Search Console via API (client has access). Ahrefs deferred — use free alternatives initially (Google Keyword Planner, scraping). Architect data layer so Ahrefs API plugs in later.
- **Architecture:** Python AI agents handle heavy lifting (scraping, analysis, AI processing). n8n acts as orchestration/trigger layer. Communication via HTTP (n8n calls Python endpoints, Python returns results). n8n also handles Google Docs generation and delivery.
- **Timeline:** ~2 weeks, capped hours. Iterative — deliver, get feedback, refine.

## Constraints

- **Tech stack**: Python (AI/backend) + n8n (orchestration/triggers) — client requirement
- **Timeline**: ~2 weeks with capped hours — iterative delivery, not waterfall
- **Data access**: No Ahrefs API initially — must work with free alternatives
- **Output format**: Google Docs — non-negotiable, this is what writers use
- **Users**: Low-code comfort level — n8n interface is the interaction point, no CLI

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + n8n architecture | Client specified; Python for AI/scraping, n8n for workflow orchestration | — Pending |
| Free data sources first | Client may not have Ahrefs API; architect for future plug-in | — Pending |
| Google Docs as output | Writers already work in Google Docs; no new tools to learn | — Pending |
| HTTP communication between n8n and Python | Standard, simple, well-supported by both platforms | — Pending |

---
*Last updated: 2026-02-10 after initialization*
