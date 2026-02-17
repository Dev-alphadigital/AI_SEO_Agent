# AI Layer: Gemini-Powered SEO Recommendations

## Context

The data pipeline is complete — scraper, Ahrefs API, competitor analysis, gap analysis, and brief generator all work end-to-end. The brief currently outputs hardcoded template recommendations ("How to {keyword}..."). The client wants AI-powered recommendations from their custom Gemini Gem.

**Blocker:** Gemini API key and Gem ID are pending from client. We build everything except the live API call, using a pluggable interface so it works the moment credentials arrive.

**Acceptance criteria source:** `Previsible _ Reoptimization Brief Criteria .xlsx` — 22 criteria across P1/P2/P3.

---

## What the AI Layer Must Produce (from P1/P2/P3 Criteria)

### P1 — Must ship with these (Gemini output):
- **Recommended title + meta description** (not template formulas)
- **Recommended heading structure** as side-by-side comparison table vs current
- **No hallucinations** — no fake stats, "guaranteed #1," unsupported claims
- **Tone aligned** to client's voice guidelines
- **Keyword targets with MSV** included

### P2 — Must be consistent:
- Headings map to keyword intent (primary → H1/H2, secondary → H2/H3)
- One H1 only, no skipped heading levels
- Metadata within length ranges (title 50-60, desc 150-160)
- No generic hype/clickbait
- Audience-appropriate language
- Human-first headings

### P3 — Nice-to-haves:
- PAA-style subtopics
- Flag obvious issues ("no H1," thin content)
- Consistent heading casing

### User's additional requirements:
- Top backlinks from competitor pages (linking domains)
- Missing search intent / terms (LSI keywords)
- Strategies for top ranking
- CTA improvements
- Page speed / responsiveness
- Semantic blog cluster suggestions
- Keywords to target (LSI)

---

## Step 1: New Data Models

**File: `app/models/schemas.py`**

Add `AIRecommendations` model to hold structured LLM output:

```python
class AIRecommendations(BaseModel):
    """Structured AI-generated recommendations for the brief."""
    recommended_title: str = ""
    recommended_meta_description: str = ""
    recommended_h1: str = ""
    recommended_headings: list[dict] = []  # [{"level": "H2", "text": "...", "keyword_target": "..."}]
    lsi_keywords: list[str] = []
    missing_intent_terms: list[str] = []
    ranking_strategy: str = ""  # Multi-paragraph strategic analysis
    cta_improvements: list[str] = []
    blog_cluster_suggestions: list[dict] = []  # [{"pillar": "...", "clusters": ["...", "..."]}]
    content_recommendations: list[str] = []  # Specific content changes
    issues_to_fix: list[str] = []  # P3: flagged obvious issues
    paa_subtopics: list[str] = []  # P3: PAA-style question headings
```

Update `SEOBrief` model:
```python
class SEOBrief(BaseModel):
    # ... existing fields ...
    ai_recommendations: AIRecommendations | None = None  # NEW
```

---

## Step 2: Prompt Builder Service

**New file: `app/services/prompt_builder.py`**

Compiles all pipeline data into a structured prompt for the LLM. This is the intelligence — it determines what the AI sees and how it reasons.

Function: `build_seo_prompt(brief_data: SEOBrief, client_profile: dict | None = None) -> str`

The prompt includes:
1. **Target page snapshot** — URL, title, meta, H1, H2/H3 list, word count, robots tag
2. **Ahrefs metrics** — DR, backlinks, referring domains, organic keywords/traffic
3. **Keyword data** — volume, difficulty, CPC, intent, traffic potential
4. **Competitor comparison table** — top 10 with DR, word count, H2 count, backlinks
5. **Gap analysis summary** — missing topics, word count gap, quality issues
6. **Client voice/tone** (when available) — from client profile
7. **Explicit instructions** — what to output, format requirements, constraints (no hallucinations, no guarantees, length limits for title/description)

The prompt asks the LLM to return **structured JSON** matching `AIRecommendations` schema.

---

## Step 3: Gemini Service (Interface + Stub)

**New file: `app/services/llm_client.py`**

Provider-agnostic interface with Gemini as the implementation:

```python
async def get_ai_recommendations(prompt: str) -> AIRecommendations:
    """Send prompt to LLM, parse structured response."""
    settings = get_settings()

    if not settings.gemini_api_key:
        logger.warning("No Gemini API key — returning empty recommendations")
        return AIRecommendations()

    # Call Gemini API
    raw = await _call_gemini(prompt, settings.gemini_api_key)

    # Parse JSON response into AIRecommendations
    return _parse_response(raw)
```

**Config additions** (`app/config.py`):
```python
gemini_api_key: str = ""
gemini_model: str = "gemini-2.0-flash"  # or client's Gem ID when provided
```

**`.env.example` additions:**
```
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2.0-flash
```

**Dependency:** `pip install google-genai` (Google's Gemini SDK)

When credentials aren't set, the service returns empty `AIRecommendations` and the brief falls back to the existing template output — graceful degradation, same pattern as Ahrefs.

---

## Step 4: Update Brief Generator

**File: `app/services/brief_generator.py`**

Add new sections to `_build_markdown()` when `ai_recommendations` is present:

1. **Recommended Metadata** (P1.5)
   - Current title vs AI-recommended title (side-by-side)
   - Current meta description vs AI-recommended (side-by-side)

2. **Recommended Heading Structure** (P1.6)
   - Side-by-side comparison table: Current H1/H2/H3 vs Recommended H1/H2/H3
   - Each recommended heading shows its keyword target (P2.1)

3. **LSI Keywords to Target**
   - List of semantically related terms the page should incorporate

4. **Ranking Strategy**
   - AI-generated multi-paragraph strategic analysis based on competitive data

5. **CTA Improvements**
   - Specific suggestions for improving calls-to-action

6. **Blog Cluster Suggestions**
   - Pillar page + supporting cluster topics for topical authority

7. **Issues to Fix** (P3.3)
   - Critical issues flagged (noindex, missing H1, thin content, robots blocking snippets)

8. **PAA Subtopics** (P3.1)
   - Question-style H2/H3 suggestions from search intent analysis

Keep existing template recommendations as fallback when AI recommendations are empty.

---

## Step 5: Wire Into Pipeline

**File: `app/routers/analyze.py`**

Add AI step between gap analysis and brief generation:

```
POST /api/v1/analyze  { url, keyword }
  1. Scrape target page → PageSEO
  2. Get Ahrefs metrics → AhrefsMetrics
  3. Get keyword metrics → KeywordMetrics
  4. Competitor analysis → CompetitorPage[]
  5. Gap analysis → GapAnalysis
  6. *** NEW: AI recommendations → AIRecommendations ***
  7. Generate brief → SEOBrief (now includes AI recs)
```

The AI step:
1. Assemble partial SEOBrief (without AI recs)
2. Call `build_seo_prompt()` to create the prompt
3. Call `get_ai_recommendations()` to get structured recs
4. Attach to the brief before generating Markdown

---

## Step 6: P1/P2/P3 Validation

**New file: `app/services/brief_validator.py`**

Automated scoring of the generated brief against acceptance criteria:

```python
def validate_brief(brief: SEOBrief) -> dict:
    """Score brief against P1/P2/P3 criteria. Returns {score, p1_results, p2_results, p3_results}."""
```

**P1 checks (automated):**
- URL matches page title/H1
- Current metadata captured (title + meta desc non-empty)
- Current heading structure present (H1 exists, H2s non-empty)
- Recommended title + description present
- Recommended heading structure present
- Keyword targets with MSV present
- No hallucination markers (scan for "guaranteed," "100%," "#1 ranking")
- GSC data present → N/A (removed from workflow)
- Tone alignment → requires client profile (future)

**P2 checks (automated):**
- Recommended headings have keyword mapping
- One H1 in recommendations
- Title 50-60 chars, description 150-160 chars
- Hype word scan (flag "ultimate," "best ever," etc.)

**P3 checks (automated):**
- PAA subtopics present when intent is informational
- Issues flagged when detected

Output: validation report appended to brief with Pass/Fail per criterion.

---

## Step 7: PageSpeed Integration

**New file: `app/services/pagespeed.py`**

Uses Google PageSpeed Insights API (free, no key required for basic usage):

```python
async def get_pagespeed_metrics(url: str) -> dict:
    """Fetch Core Web Vitals and performance score."""
    # GET https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}
    # Returns: performance_score, FCP, LCP, CLS, TBT
```

Add to pipeline step 1 (parallel with scrape + Ahrefs).
Add `pagespeed_score` and `core_web_vitals` fields to `SEOBrief` model.

---

## Files Summary

| File | Action | What |
|------|--------|------|
| `app/models/schemas.py` | Modify | Add `AIRecommendations`, update `SEOBrief` |
| `app/services/prompt_builder.py` | New | Compile pipeline data into LLM prompt |
| `app/services/llm_client.py` | New | Gemini API client (stub until credentials) |
| `app/services/brief_validator.py` | New | P1/P2/P3 automated scoring |
| `app/services/pagespeed.py` | New | PageSpeed Insights API client |
| `app/services/brief_generator.py` | Modify | Add AI recommendation sections to Markdown |
| `app/routers/analyze.py` | Modify | Add AI + PageSpeed steps to pipeline |
| `app/config.py` | Modify | Add gemini_api_key, gemini_model |
| `.env.example` | Modify | Add GEMINI_API_KEY, GEMINI_MODEL |
| `requirements.txt` | Modify | Add google-genai |

## Implementation Order

1. Step 1 (models) — must be first
2. Steps 2 + 3 (prompt builder + LLM client) — independent, sequential
3. Step 7 (PageSpeed) — independent, can parallel with 2+3
4. Step 4 (brief generator updates) — depends on models
5. Step 5 (wire pipeline) — depends on everything
6. Step 6 (validator) — can be last, independent of LLM

---

## Verification

1. **Without Gemini key:** Pipeline still works, brief falls back to template recommendations, AI section shows "AI recommendations unavailable — configure GEMINI_API_KEY"
2. **With Gemini key:** Full brief with AI-powered title, meta, heading structure, LSI keywords, strategy, CTAs, blog clusters
3. **Validation:** Each brief includes P1/P2/P3 scorecard showing Pass/Fail per criterion
4. **PageSpeed:** Performance score and Core Web Vitals appear in brief
5. **Test command:**
   ```
   curl -X POST http://localhost:8000/api/v1/analyze \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.inktel.com/bpo-services/", "keyword": "bpo services"}'
   ```
   Verify: AI recommendations populated (or graceful fallback), validation scorecard present, PageSpeed metrics included
