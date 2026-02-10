# AI SEO Agent — Project Instructions

## Git Branching

**MANDATORY:** Before working on any phase, create a new branch from `main`:

```
git checkout -b phase-{N}-{short-description}
```

Example: `phase-1-project-setup`, `phase-2-data-collection`

- Never commit phase work directly to `main`
- Merge to `main` only after phase verification is complete
- Each phase gets its own branch

## Tech Stack

- **Python** — AI processing, web scraping, data analysis
- **n8n** — Workflow orchestration, triggers, webhooks
- **Communication** — Python exposes HTTP endpoints, n8n calls them

## Project Structure

- `.planning/` — Planning docs (not tracked in git)
- Source code goes in project root organized by function
