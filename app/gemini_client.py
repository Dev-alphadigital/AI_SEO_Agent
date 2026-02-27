"""
Gemini API Client — SEO Agent

Uses Gemini for:
- Full SEO report generation (analysis + optimization strategy)
- Tactical recommendations (title, meta, headings, PAA subtopics)

Requires GEMINI_API_KEY in .env
"""

import json
import os
from pathlib import Path
from typing import Optional


def _load_env():
    """Load .env from project root if GEMINI_API_KEY not set."""
    if os.environ.get("GEMINI_API_KEY"):
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _get_model():
    """Lazy load Gemini model."""
    _load_env()
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None, "GEMINI_API_KEY not set in .env"
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        return model, None
    except ImportError as e:
        return None, "Install: pip install google-generativeai"
    except Exception as e:
        return None, str(e)


def _build_report_context(
    url: str,
    primary_keyword: str,
    secondary_keywords: Optional[str] = None,
    notes: Optional[str] = None,
    scrape_result: Optional[dict] = None,
    gsc_result: Optional[dict] = None,
    keyword_msv_context: Optional[str] = None,
    competitor_context: Optional[str] = None,
) -> str:
    """Build context string for Gemini from scraped + GSC + Ahrefs MSV data."""
    parts = [
        f"**Target URL:** {url}",
        f"**Primary keyword:** {primary_keyword}",
    ]
    if secondary_keywords:
        parts.append(f"**Secondary keywords:** {secondary_keywords}")
    if keyword_msv_context:
        parts.append(f"\n{keyword_msv_context}")
    # Always include notes status so Gemini knows whether notes were provided
    if notes and notes.strip():
        parts.append(f"\n**Form notes (user-provided):** {notes.strip()}")
    else:
        parts.append("\n**Form notes (user-provided):** (none provided)")

    if scrape_result and scrape_result.get("success"):
        parts.append("\n**Current page (scraped) — P1 #3 metadata, P1 #4 headings:**")
        title = scrape_result.get("title") or "(none)"
        meta = scrape_result.get("meta_description") or "(none)"
        parts.append(f"- Title: {title} [{len(title)} chars]")
        parts.append(f"- Meta description: {meta} [{len(meta)} chars]")
        parts.append(f"- H1: {scrape_result.get('h1') or '(none)'}")
        parts.append(f"- Word count: ~{scrape_result.get('word_count', 0)}")
        headings = scrape_result.get("headings", [])
        if headings:
            parts.append(f"- Heading hierarchy (H1/H2/H3): {', '.join(headings[:20])}")
        issues = list(scrape_result.get("issues", []))
        # Inferred issues from metadata/structure (always surface these)
        if title and title != "(none)" and len(title) > 60:
            issues.append(f"Title too long — {len(title)} chars (target 50-60); will truncate in SERPs")
        if meta and meta != "(none)" and len(meta) > 160:
            issues.append(f"Meta description too long — {len(meta)} chars (target 150-160); will truncate in SERPs")
        h2h3 = [h for h in headings if h.lower().startswith(("h2:", "h3:"))]
        if not h2h3 and headings:
            issues.append("No H2/H3 headings — add subheadings for structure and keyword targeting")
        elif not headings or not any(h.lower().startswith("h1:") for h in headings):
            pass  # No H1 already in scrape issues
        if issues:
            parts.append(f"- **Issues to fix (MUST include in report):** {' | '.join(issues)}")
        else:
            parts.append("- **Issues to fix:** No issues detected from scrape or metadata.")

    if gsc_result and gsc_result.get("success") and gsc_result.get("data"):
        d = gsc_result["data"]
        parts.append("\n**GSC performance data:**")
        parts.append(f"- Clicks: {d.get('clicks', 0)} | Impressions: {d.get('impressions', 0)} | Avg position: {d.get('avg_position', 'N/A')} | CTR: {d.get('ctr', 0)}%")
        qs = d.get("top_queries", [])
        if qs:
            queries = [q.get("query", q) if isinstance(q, dict) else str(q) for q in qs]
            parts.append(f"- Top queries: {', '.join(queries)}")
    else:
        parts.append("\n**GSC data:** Not available (use keyword research and page analysis)")

    if competitor_context:
        parts.append(f"\n{competitor_context}")
    else:
        parts.append("\n**Competitive Analysis Data (Ahrefs):** Not available (skipped or API unavailable)")

    return "\n".join(parts)


def generate_full_seo_report(
    url: str,
    primary_keyword: str,
    secondary_keywords: Optional[str] = None,
    notes: Optional[str] = None,
    scrape_result: Optional[dict] = None,
    gsc_result: Optional[dict] = None,
    heading_casing: Optional[str] = None,
    client_profile: Optional[dict] = None,
    client_name: Optional[str] = None,
    keyword_msv_context: Optional[str] = None,
    competitor_context: Optional[str] = None,
) -> dict:
    """
    Generate a full SEO analysis and optimization strategy report using Gemini.

    Gemini acts as an SEO agent: analyzes the data, determines what to optimize,
    and produces a complete markdown report with analysis and recommendations.

    Returns:
        {"success": bool, "error": str | None, "report": str}
    """
    model, err = _get_model()
    if err:
        return {"success": False, "error": err, "report": ""}

    context = _build_report_context(
        url=url,
        primary_keyword=primary_keyword,
        secondary_keywords=secondary_keywords,
        notes=notes,
        scrape_result=scrape_result,
        gsc_result=gsc_result,
        keyword_msv_context=keyword_msv_context,
        competitor_context=competitor_context,
    )

    client_section = ""
    client_report_instruction = ""
    if client_profile:
        from app.client_profiles import format_client_profile_for_prompt
        client_text = format_client_profile_for_prompt(client_profile)
        client_section = f"""

## CLIENT PROFILE — #1 PRIORITY (this overrides everything else)
**Client:** {client_name or 'Unknown'}

{client_text}

**CRITICAL — NON-NEGOTIABLE:** The ENTIRE report must be tailored to this client profile. Every recommendation, every heading suggestion, every meta description, every internal linking idea — ALL must align with this client's target audience, brand positioning, values, and voice. A generic report is UNACCEPTABLE. The reader must be able to tell which client this report is for just by reading any section."""
        client_report_instruction = f"""
1. **Client profile** — MANDATORY WHEN CLIENT PROVIDED. Display the client name, target audience, brand positioning, values, and value proposition. Then state: "All recommendations in this report are tailored to this client profile." This section comes FIRST (before Executive Summary numbering) because client alignment is the #1 priority. If no client profile was provided, omit this section entirely."""
    else:
        client_section = ""
        client_report_instruction = ""

    casing_note = ""
    if heading_casing:
        c = heading_casing.lower()
        if c == "title":
            casing_note = " Use Title Case for all suggested headings."
        elif c == "sentence":
            casing_note = " Use Sentence case for all suggested headings."

    prompt = f"""You are an SEO agent. Your job is to analyze the data below and produce a complete SEO optimization report that satisfies ALL Priority 1 criteria.

**Your role:** Think strategically. Decide which things to optimize and why. The report must contain your analysis and clear recommendations to improve SEO.{client_section}

## Input data
{context}

## Priority 1 — MANDATORY criteria (every report MUST satisfy these)
1. **URL verification** — Confirm the target URL and page match. Include a short line: "Target URL: [url] — verified."
2. **GSC data** — If GSC data is provided, include a table/summary with: Clicks, Impressions, Avg position, Top queries. If not available, state "GSC data not available."
3. **Current metadata** — Must include exact current title + meta description (from scrape), with character counts. This is the baseline for comparison.
4. **Current heading structure** — Must show H1/H2/H3 hierarchy as scraped. One H1; logical order. No broken hierarchy.
5. **Recommended title + description** — Required fields with character counts and rationale. Include a side-by-side: Current vs Recommended.
6. **Heading comparison table** — MANDATORY format: | Current Heading | Recommended Heading | Rationale |. Include all main headings.
7. **Keyword targets with MSV** — Primary + secondary keywords from input. USE the exact MSV values from "Keyword targets (with MSV from Ahrefs)" in the context when provided. If MSV is "(MSV not available)", say that — never invent numbers.
8. **No hallucinations** — No fake stats, no "guaranteed #1," no unsupported claims. Ground every recommendation in the data provided.
9. **Tone & client alignment** — If a client profile was provided, the ENTIRE report must be tailored to it. Match their voice, formality, target audience, and brand positioning throughout. Every recommendation (titles, metas, headings, internal links) must reflect the client's audience and values.
10. **Competitive analysis** — If SERP competitor data from Ahrefs is provided, you MUST analyze the actual ranking competitors: who they are, their DR/backlinks/traffic, WHY they rank higher than the target, the competitive gap, and specific steps to outrank them. If keyword competition data is also provided, include difficulty/CPC/volume analysis. Compare the target domain directly against each competitor. A generic report without real competitor comparison = a FAILED report. If data not available, state that.

## Priority 2 — MANDATORY (SEO best practice)
**Recommended metadata MUST be within sensible length ranges to prevent truncation:**
- **Title tag:** 50–60 characters (strictly; do not exceed 60)
- **Meta description:** 150–160 characters (strictly; do not exceed 160)
If your first draft exceeds these limits, shorten it. Always show the character count in brackets and verify it falls within range.

## Your task
Write a full SEO optimization report in Markdown. You MUST include ALL of the following sections:
{client_report_instruction}
1. **Executive summary** — 2-3 sentences on the main findings and top priorities.

2. **Notes (form)** — MANDATORY: This section is for the "Form notes (user-provided)" from the input data — NOT the client profile. If form notes were provided (i.e. not "(none provided)"), display them VERBATIM here first, then explain how they are incorporated into the report. If form notes say "(none provided)", state "*(Not provided / not used)*". The client profile is a SEPARATE thing and must NOT be placed in this section. Never omit this section.

3. **URL & GSC** — (P1 #1, #2) Target URL verification + GSC performance summary (clicks, impressions, avg position, top queries) or "GSC not available."

4. **Current state** — (P1 #3, #4) Current metadata (title + meta with chars) and current heading structure (H1/H2/H3 hierarchy). What the page does well and what's missing.

5. **Keyword targets (with MSV)** — (P1 #7) MANDATORY table: Keyword | MSV (est) | Intent | Placement. Include primary + secondary from input. Use the MSV values from "Keyword targets (with MSV from Ahrefs)" in the context. If Ahrefs MSV was provided (e.g. "1,200 MSV"), output that number. If "(MSV not available)", say that — do NOT invent numbers.

6. **Optimization strategy** — Which areas to prioritize and why. Be specific.

7. **Recommendations** — (P1 #5, #6) Concrete, actionable. (P2: strict length limits — prevents truncation.)
   - **Title tag** — MUST be 50–60 chars (never over 60). Show character count in brackets. Current vs Recommended table.
   - **Meta description** — MUST be 150–160 chars (never over 160). Show character count in brackets. Current vs Recommended table.
   - **Heading comparison table** — MANDATORY: | Current Heading | Recommended Heading | Rationale |
   - 1-3 question-style H2/H3 for PAA/snippet coverage (when relevant)
   - Content depth or structure suggestions if thin content detected

8. **Internal linking opportunities** — MANDATORY table: Anchor text | Target page/URL | Rationale (3-5 links).

9. **Competitive Analysis** — (P1 #10) MANDATORY when competitor data is provided. This is a CRITICAL section. Include ALL of the following:

   **CRITICAL DATA RULES:**
   - Use ONLY the exact numbers from the Ahrefs data provided in context. NEVER invent, estimate, or hallucinate DR, backlinks, referring domains, or traffic numbers.
   - If a value shows "—" in the data, display it as "N/A" in the report. If it says "n/a (low vol)", display "N/A (low volume)" — this means Ahrefs does not calculate that metric for keywords with very low search volume. Do NOT make up numbers.
   - If the data says SERP competitors are for a BROADER keyword (not the exact keyword), you MUST clearly state this at the top of the competitive analysis section. Example: "Note: Ahrefs has no SERP tracking data for the exact keyword 'bpo services in florida'. The competitor data below is for the broader keyword 'bpo services' and may not perfectly reflect the local competitive landscape."

   **a) SERP Competitor Overview** — If SERP competitor data is provided, create a table with these EXACT columns:
   | # | Domain | DR | Backlinks | Ref. Domains | Traffic | Word Count | Why They Rank |
   Copy the exact numbers from the data. The "#" column MUST be sequential (these are the top organic results). For each competitor, analyze WHY they rank higher based on their real metrics. Be specific: "Domain X ranks #1 with DR 85 and 12,000 backlinks — their authority dwarfs the target site's DR 35."

   **b) Competitive Gap Analysis** — Compare the target domain against the SERP competitors:
   - DR gap: How does the target's DR compare to the SERP average?
   - Backlink gap: How many more backlinks/referring domains are needed?
   - Is the target currently ranking? If not, what's needed to break in?
   - Identify the weakest competitors that are realistic targets to outrank

   **c) Content Length Comparison** — MANDATORY when word count data is available.
   Compare the target page's word count against SERP competitor word counts. Include:
   - Your page word count vs SERP average word count
   - Whether you need more or less content to be competitive
   - Which top-ranking pages have the most content and what that implies
   Use the exact word count numbers from the data. Do NOT invent word counts.

   **d) Why Competitors Rank Higher** — For the top 3 competitors, explain specifically why they outrank the target:
   - Domain authority advantage
   - Backlink profile strength
   - Content depth/word count advantage
   - What the target must do differently

   **e) Keyword Competition Table** — Keyword | Search Volume | Difficulty | CPC | Traffic Potential | Global Volume — USE exact data from context

   **f) Strategic Recommendations** — 3-5 actionable steps:
   - Which competitors to target first (weakest in SERP)
   - Backlink acquisition targets (how many referring domains needed)
   - Content strategy to close the gap (including word count targets)
   - Quick wins vs long-term plays

   If competitor data says "Not available", state that and skip the detailed analysis.

10. **Issues to fix** — MANDATORY: Include ALL issues from "Issues to fix (MUST include in report)" in the context. List each as a bullet. Only say "None found" if the context explicitly states there are no issues. Do NOT leave this section empty when issues exist.

11. **Quick reference** — URL | Primary keyword | Priorities | Heading casing (if applicable).

Rules:
- **#1 RULE — Client profile alignment:** If a client profile was provided, EVERY section must be tailored to it. Recommended titles, metas, headings, internal links, strategy — all must reflect the client's target audience, brand voice, values, and positioning. Do NOT produce generic recommendations. A reader should immediately recognize which client this report is for.
- P2: Recommended title MUST be 50–60 chars; recommended meta MUST be 150–160 chars. Truncation = bad UX.
- Issues to fix: Use every issue from the context. Never say "None found" when the scrape/context lists issues.
- Ground all recommendations in the data provided. No hallucinations. (P1 #8)
- No guarantees (e.g. "will rank #1"). No fake stats. Be realistic.
- Use markdown: headers, tables, lists, bold where helpful.{casing_note}
- Output the full report only — no preamble or "Here is the report"."""

    try:
        response = model.generate_content(prompt)
        report = (response.text or "").strip()
        if report.startswith("```"):
            report = report.split("```", 2)[1]
            if report.startswith("markdown"):
                report = report[8:]
            report = report.strip()
        return {"success": True, "error": None, "report": report}
    except Exception as e:
        return {"success": False, "error": str(e), "report": ""}


def generate_seo_recommendations(
    url: str,
    primary_keyword: str,
    secondary_keywords: Optional[str] = None,
    current_title: Optional[str] = None,
    current_h1: Optional[str] = None,
    current_headings: Optional[list] = None,
    gsc_top_queries: Optional[list] = None,
    heading_casing: Optional[str] = None,
) -> dict:
    """
    Generate SEO recommendations using Gemini.

    Args:
        heading_casing: "title" for Title Case, "sentence" for Sentence case (client preference).

    Returns:
        {
            "success": bool,
            "error": str | None,
            "recommended_title": str,
            "recommended_meta": str,
            "heading_suggestions": str (markdown table),
            "paa_subtopics": list[str] — 1-3 question-style H2/H3 for snippet/PAA coverage
        }
    """
    model, err = _get_model()
    if err:
        return {
            "success": False,
            "error": err,
            "recommended_title": "",
            "recommended_meta": "",
            "heading_suggestions": "",
            "paa_subtopics": [],
        }

    context_parts = [f"URL: {url}", f"Primary keyword: {primary_keyword}"]
    if secondary_keywords:
        context_parts.append(f"Secondary keywords: {secondary_keywords}")
    if current_title:
        context_parts.append(f"Current title: {current_title}")
    if current_h1:
        context_parts.append(f"Current H1: {current_h1}")
    if current_headings:
        context_parts.append(f"Current headings: {', '.join(current_headings[:10])}")
    if gsc_top_queries:
        queries = [q.get("query", q) if isinstance(q, dict) else q for q in gsc_top_queries[:5]]
        context_parts.append(f"Current top GSC queries: {', '.join(queries)}")

    context = "\n".join(context_parts)

    casing_rule = ""
    if heading_casing:
        c = heading_casing.lower()
        if c == "title":
            casing_rule = "\n- Use Title Case for all recommended headings (e.g. Best Perfumes in Pakistan)"
        elif c == "sentence":
            casing_rule = "\n- Use Sentence case for all recommended headings (e.g. Best perfumes in Pakistan)"

    paa_instruction = ""
    if gsc_top_queries:
        paa_instruction = ''',
  "paa_subtopics": ["Question-style H2 or H3 for snippet 1", "Question for snippet 2", "Optional third"]'''

    prompt = f"""You are an SEO expert. Generate SEO recommendations for this page.

Context:
{context}

Output ONLY valid JSON in this exact format (no markdown, no code block):
{{
  "recommended_title": "Title here, 50-60 chars, include primary keyword",
  "recommended_meta": "Meta description here, 150-160 chars, keyword + CTA",
  "heading_suggestions": "| Current Heading | Recommended Heading | Rationale |\\n| ... | ... | ... |"{paa_instruction}
}}

Rules:
- Title: 50-60 chars, primary keyword near front
- Meta: 150-160 chars, keyword + benefit + CTA
- Heading table: 3-5 rows, improve for SEO without losing meaning{casing_rule}"""
    if gsc_top_queries:
        prompt += """
- paa_subtopics: 1-3 question-style H2 or H3 headings (e.g. What is the best perfume in Pakistan?) to target featured snippets / PAA based on GSC queries. Only include when relevant to queries."""
    prompt += "\n- Output valid JSON only, no extra text"

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Strip markdown code block if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        data = json.loads(text)
        paa = data.get("paa_subtopics", [])
        if isinstance(paa, str):
            paa = [s.strip() for s in paa.split("\n") if s.strip()] if paa else []

        return {
            "success": True,
            "error": None,
            "recommended_title": data.get("recommended_title", ""),
            "recommended_meta": data.get("recommended_meta", ""),
            "heading_suggestions": data.get("heading_suggestions", ""),
            "paa_subtopics": paa if isinstance(paa, list) else [],
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Gemini returned invalid JSON: {e}",
            "recommended_title": "",
            "recommended_meta": "",
            "heading_suggestions": "",
            "paa_subtopics": [],
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "recommended_title": "",
            "recommended_meta": "",
            "heading_suggestions": "",
            "paa_subtopics": [],
        }
