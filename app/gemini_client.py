"""
Gemini API Client — Content Strategist

Uses Gemini for:
- Full content optimization report (analysis + actionable recommendations)
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
    domain_pages: Optional[list] = None,
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
        parts.append("\n**Current page (scraped) — PRIMARY DATA SOURCE:**")
        title = scrape_result.get("title") or "(none)"
        meta = scrape_result.get("meta_description") or "(none)"
        parts.append(f"- Title: {title} [{len(title)} chars]")
        parts.append(f"- Meta description: {meta} [{len(meta)} chars]")
        parts.append(f"- H1: {scrape_result.get('h1') or '(none)'}")
        parts.append(f"- Word count: ~{scrape_result.get('word_count', 0)}")

        # Full heading hierarchy (H1-H6, classified)
        headings = scrape_result.get("headings", [])
        if headings:
            parts.append(f"\n**Full heading hierarchy (H1-H6):**")
            for h in headings:
                parts.append(f"- {h}")

        # Full body text (most important for content analysis)
        body_text = scrape_result.get("body_text", "")
        if body_text:
            parts.append(f"\n**Page body content (up to ~15000 words):**")
            parts.append(body_text[:60000])  # Character limit safety

        # Internal links on the page
        internal_links = scrape_result.get("internal_links", [])
        if internal_links:
            parts.append(f"\n**Internal links found on page ({len(internal_links)}):**")
            for link in internal_links[:30]:
                parts.append(f"- [{link['anchor']}]({link['url']})")

        # External links on the page
        external_links = scrape_result.get("external_links", [])
        if external_links:
            parts.append(f"\n**External links found on page ({len(external_links)}):**")
            for link in external_links[:15]:
                parts.append(f"- [{link['anchor']}]({link['url']})")

        # Rich content on target page
        rich = scrape_result.get("rich_content", {})
        if any(v > 0 for v in rich.values()):
            parts.append(f"\n**Rich content on target page:**")
            labels = {"tables": "Tables", "figures": "Figures", "images": "Images",
                      "iframes": "Embedded content", "canvas": "Canvas charts",
                      "svg": "SVG graphics", "videos": "Videos"}
            for key, count in rich.items():
                if count > 0:
                    parts.append(f"- {labels.get(key, key)}: {count}")

        # Issues
        issues = list(scrape_result.get("issues", []))
        if title and title != "(none)" and len(title) > 60:
            issues.append(f"Title too long — {len(title)} chars (target 50-60); will truncate in SERPs")
        if meta and meta != "(none)" and len(meta) > 160:
            issues.append(f"Meta description too long — {len(meta)} chars (target 150-160); will truncate in SERPs")
        h2h3 = [h for h in headings if h.lower().startswith(("h2:", "h3:"))]
        if not h2h3 and headings:
            issues.append("No H2/H3 headings — add subheadings for structure and keyword targeting")
        if issues:
            parts.append(f"\n- **Issues to fix (MUST include in report):** {' | '.join(issues)}")
        else:
            parts.append("\n- **Issues to fix:** No issues detected from scrape or metadata.")

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

    if domain_pages:
        parts.append(f"\n**Other pages on this domain (from Ahrefs top-pages, sorted by traffic) — USE FOR INBOUND LINKING:**")
        for p in domain_pages[:30]:
            traffic = p.get("traffic", 0)
            title = p.get("title", "")
            page_url = p.get("url", "")
            parts.append(f"- {page_url} (title: \"{title}\", traffic: {traffic})")

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
    domain_pages: Optional[list] = None,
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
        domain_pages=domain_pages,
    )

    client_section = ""
    client_overview_fields = ""
    if client_profile:
        from app.client_profiles import format_client_profile_for_prompt
        client_text = format_client_profile_for_prompt(client_profile)
        client_section = f"""

## CLIENT PROFILE — #1 PRIORITY (this overrides everything else)
**Client:** {client_name or 'Unknown'}

{client_text}

**CRITICAL — NON-NEGOTIABLE:** The ENTIRE report must be tailored to this client profile. Every recommendation, every heading suggestion, every meta description, every internal linking idea — ALL must align with this client's target audience, brand positioning, values, and voice. A generic report is UNACCEPTABLE. The reader must be able to tell which client this report is for just by reading any section.

**If "Specific content instructions" are listed above, you MUST address them explicitly throughout the report.** These are direct client requirements and take priority."""
        client_overview_fields = f"""
Under **Overview**, include:
- **Client:** {client_name or 'Unknown'}
- **Target audience:** from client profile
Then state: "All recommendations in this report are tailored to this client profile.\""""
    else:
        client_section = ""
        client_overview_fields = ""

    casing_note = ""
    if heading_casing:
        c = heading_casing.lower()
        if c == "title":
            casing_note = " Use Title Case for all suggested headings."
        elif c == "sentence":
            casing_note = " Use Sentence case for all suggested headings."

    prompt = f"""You are a Senior Enterprise SEO Strategist and Content Optimization Planner.
Your sole responsibility is to analyze existing content (blogs and landing pages) and produce a prioritized, risk-aware reoptimization plan designed to improve:
- Search visibility & rankings
- Organic traffic quality
- Alignment with modern search systems (AI Overviews, E-E-A-T, Search Intent)

You do NOT write final content. You only plan, prioritize, and justify changes.
You are analytical, conservative, and data-driven.
If the risk of reoptimization outweighs the upside, you must explicitly recommend no major changes.

**SCOPE BOUNDARY — CRITICAL:** Do NOT recommend off-page strategies. Never suggest backlink building, domain authority improvement, link outreach, PR campaigns, guest posting, or any off-page SEO strategy. SERP competitor data is used to understand what content to create and how to structure it — not to suggest SEO campaigns. Focus only on what content changes can close the gap.{client_section}

## Global Guardrails (Non-Negotiable)
- Do NOT rewrite or alter: legal disclaimers, regulated claims, definitions demonstrating first-hand expertise, compliance-sensitive language.
- Do NOT recommend keyword stuffing or forced insertion.
- Do NOT recommend full rewrites unless performance data strongly supports it.
- Always favor incremental, intent-aligned improvements.
- No hallucinations — no fake stats, no "guaranteed #1," no unsupported claims.
- Use ONLY exact data provided — never invent DR, backlinks, traffic, MSV, or word count numbers. Use "(not available)" if missing.
- Metadata limits — Title: 50–60 chars (never over 60). Meta description: 150–160 chars (never over 160). Do NOT show character counts in the output.

## Input data
{context}

## ANALYTICAL WORKFLOW (Internal Processing — Follow These Steps Sequentially)

**STEP 0: Reoptimization Viability Check (Required)**
Before producing the report, assess risk vs reward:
- If the page ranks positions 1–5 AND engagement metrics are at or above benchmark, explicitly recommend no structural content changes. Limit recommendations to metadata, internal linking, or SERP alignment tweaks.
- Proceed with full reoptimization only if justified.

**STEP 1: Current State Analysis (Intent & Performance)**
- Analyze the existing content body and current primary keyword.
- Classify the dominant search intent (Informational, Commercial, Navigational) using keyword modifiers and SERP pattern heuristics.
- Identify the primary cause of underperformance: Intent mismatch, Content depth gap, Structural issues, Metadata misalignment, or Poor internal linking.

**STEP 2: Metadata Evaluation**
- Evaluate current title tag and meta description against the target keyword strategy.
- Generate optimized alternatives that include the primary keyword, improve CTR potential, and remain brand-safe and non-sensational.

**STEP 3: Content Reoptimization Plan**
Analyze using these five lenses:
1. Content Structure — Identify 3-5 specific H2/H3 headings to add or revise. Each must map to: search intent, identified content gap, or keyword theme.
2. Visual & Trust Elements — Identify 3 specific asset types that would improve E-E-A-T or engagement (comparison tables, data visualizations, diagrams).
3. Internal Linking — Identify anchor text → destination URL pairs for contextual placement. Flag missing internal content opportunities.
4. FAQs — Generate natural user-intent questions aligned to the article topic, incorporating semantic keyword variations.
5. Key Takeaways — Identify the most critical strategic changes needed.

**STEP 4: Impact Assessment**
- Assess expected SEO impact (visibility, rankings, AI discoverability).
- Assess expected behavioral impact (CTR, engagement, conversion).

Use the analysis from Steps 0-4 to populate EVERY section of the output below. Every recommendation must be grounded in specific findings from this analytical process.

## Your task
Write a content reoptimization brief in Markdown following this EXACT template structure. Do NOT add extra sections. Do NOT reorder sections. Do NOT output labels like "SECTION 1:", "SECTION 2:", "STEP 1:", "STEP 2:" etc. — just use the heading names directly.
{client_overview_fields}

## Overview
- **Client:** {client_name or '(not provided)'}
- **Target URL:** [the target URL]
- **Primary Objective:** Based on the page's body content, what is this page trying to achieve? What topic does it cover, what angle does it take, and for whom? (This is the page intent analysis — 2-3 sentences.)
- **Target Audience:** from client profile if provided, otherwise derive from page content.

---

## Content & SERP Insights
Write a concise executive summary combining SERP intent analysis and SERP observations. This MUST be no more than half a page long. Structure it as flowing paragraphs with bold labels — NOT as a bullet list of headings. Use this format:

**SERP Intent:** Write 2-3 sentences describing what users are looking for when they search this keyword. Include the classified search intent type (Informational/Commercial/Navigational).

**Alignment & Strengths:** Write 2-3 sentences about where the current page aligns well with SERP intent. Be specific — reference actual page sections by heading name.

**Divergence & Gaps:** Write 2-3 sentences about where the page falls short compared to competitors. Be specific — name the topics, sections, or questions competitors address that this page does not. Reference the primary cause of underperformance identified in your analysis.

**Additional Content Investments (Competitor Analysis):** List 3-5 specific sections recommended for addition or expansion based on competitor heading gap analysis. Use a bullet list ONLY for this part.

Keep it condensed and strategic — no fluff.

---

## SEO Improvements

### Keywords

**Currently ranking keyword(s):** List top 5 keywords the article ranks for from GSC data (format: keyword / MSV / KW difficulty). If GSC data is not available, state "GSC data not available."

**Recommended Primary Keyword (non-branded):**
- [primary keyword] / [search volume]

**Recommended Secondary Keywords (non-branded):**
- [keyword] / [search volume]
- [keyword] / [search volume]
- [keyword] / [search volume]
(Use exact MSV from Ahrefs data. Never invent numbers.)

### Metadata

Use a table with two columns. The left column shows the current value, the right column shows the recommendations. Format EXACTLY like this:

| Current Meta Title: | Recommended Meta Title: |
|---|---|
| [exact current title] | 1. [first recommendation] <br> 2. [second recommendation] <br> 3. [third recommendation] |

| Current Meta Description: | Recommended Meta Description: |
|---|---|
| [exact current meta description] | 1. [first recommendation] <br> 2. [second recommendation] <br> 3. [third recommendation] |

| Current H1: | Recommended H1: |
|---|---|
| [exact current H1] | [recommended H1 or "Keep as is" with rationale] |

IMPORTANT: Use <br> between recommendations to keep all 3 options in ONE table row. Do NOT split recommendations into separate table rows.

Rules:
- Do NOT include character counts in the output. No "[XX chars]" annotations.
- Do NOT use HTML tags like <br>.
- Title recommendations must be 50-60 characters. Meta description recommendations must be 150-160 characters.
- All metadata recommendations MUST include the primary target keyword.
- **CRITICAL — PIPE CHARACTER:** If any title or description contains a pipe "|" character (e.g., "Hot Desking Guide | OfficeSpace"), you MUST replace the pipe with a dash "–" in the table output (e.g., "Hot Desking Guide – OfficeSpace"). This prevents the markdown table from breaking. Apply this to BOTH current values and recommendations.

### Headers

THIS IS A MANDATORY SECTION — it must ALWAYS be present and must NEVER be empty.

Heading comparison table format: | Level (H1/H2/H3) | Current Heading | Recommended Heading | Rationale |

Include EVERY heading from the scraped page data (the "Full heading hierarchy" in the input). You MUST use the actual headings — never show "(none)" as a current heading if headings were provided in input.

**CRITICAL — ANALYZE EACH HEADING INDIVIDUALLY:**
- For EVERY heading, evaluate whether it can be improved for keyword targeting, conciseness, clarity, or alignment with search intent.
- Do NOT default to "Keep as is" — actively look for improvements. At minimum, 40-60% of headings should have a recommended change.
- Improvements include: making headings more concise, adding keyword relevance, aligning with SERP competitor patterns, making them more action-oriented for the target audience.
- "Keep as is" is ONLY acceptable when a heading is genuinely well-optimized already. Even then, provide a brief rationale like "Already well-optimized for target keyword."
- Every row MUST have a rationale — never leave the Rationale column empty.
- Promotional/non-topical headings (e.g., "Subscribe", "Continue reading", newsletter banners) should be marked "Remove" with rationale.

If the scraped page returned NO headings (empty heading list), you MUST still populate this table by:
1. Looking at the page body content to identify the actual structure
2. Using SERP competitor data to recommend a complete heading structure
3. Marking all entries as **[new header]** with recommended content descriptions

After listing ALL current headings, add 3-5 NEW recommended H2 headings at the bottom of the table.

**ABSOLUTE RULES FOR NEW HEADERS IN THIS TABLE:**
- Each new header = exactly ONE row. NEVER add H3 sub-rows in this table. H3 details go ONLY in "Content Structure & Additional Content".
- Leave "Current Heading" column blank. Put **[new header]** at the end of the Rationale column.
- Example: | H2 |  | Creating a Hot Desking Policy | Addresses implementation gap. **[new header]** |

**ABSOLUTE RULES FOR HEADING LENGTH:**
- Every recommended heading MUST be 3-8 words maximum. Count the words. If over 8 words, shorten it.
- BAD (too long): "Overcoming Hot Desking Challenges: Practical Solutions for Employers" (9 words)
- GOOD (concise): "Solving Common Hot Desking Challenges" (5 words)
- BAD (too long): "Hot Desking Software: Streamlining Workplace Management for Efficiency" (8+ words)
- GOOD (concise): "Hot Desking Software Solutions" (4 words)

All promotional headings (Subscribe, Continue reading, newsletter, exclusive insights) MUST be marked "Remove" — never rename them.{casing_note}

| Level (H1/H2/H3) | Current Heading | Recommended Heading | Rationale |
|---|---|---|---|
| ... | ... | ... | ... |

### Internal Linking

THIS IS A MANDATORY SECTION — it must ALWAYS be present with real, full URLs.

This section must recommend NEW internal links to add — do NOT just list existing links on the page.

**CRITICAL URL RULES:**
- You MUST use complete, real URLs (e.g., https://www.example.com/features/desk-booking/)
- NEVER use placeholder text like [OfficeSpace blog post about X] or [URL] or [OfficeSpace feature page]
- Get URLs from: (1) "Other pages on this domain" data, (2) internal links found on the scraped page, (3) SERP competitor data showing the target domain's pages
- If you cannot find real URLs from the data provided, construct logical URLs based on the domain structure (e.g., if the domain is officespacesoftware.com and you're recommending a link to a desk booking feature, use https://www.officespacesoftware.com/features/desk-booking/)

**Links to add ON this page (pointing to other pages on the site):** Recommend 3-5 new internal links to add within the content of this page. Check the page body text to see if the anchor text already exists on the page. For each link:
- If the anchor text ALREADY EXISTS on the page, mark it as [EXISTING] and specify where to find it
- If the anchor text needs to be ADDED as new content, mark it as [NEW] and specify where in the page structure it should be added

| Anchor Text | Link To (Destination URL) | Where to place new anchor text |
|---|---|---|
| [EXISTING] anchor text OR [NEW] anchor text | [full real URL] | Use existing text in [section name] OR Add new phrase in [section name] |

**Links to add on OTHER pages (pointing back to this page):** Recommend 3-5 pages on the same domain that should add a link pointing TO this page. For each recommendation, check if the anchor text would naturally exist in that page's content. Specify placement clearly.

| From Page (Source URL) | Anchor Text | Where to place new anchor text |
|---|---|---|
| [full real URL of the other page] | [anchor text to use] | Use existing text in [section name] OR Add new phrase in [section name] |

If no strong internal link match exists for a recommendation, flag it as a missing internal content opportunity.

---

## Content Improvements

### Key Takeaways
List 3-6 key takeaways as simple, clear bullet points. Summarize the main lessons and insights FROM the blog content itself — what would a reader learn from reading this article? Do NOT write SEO recommendations or what the page "needs to improve" here. Each takeaway should reflect the actual content and the value it delivers to readers.

Example of GOOD key takeaways:
- Hot desking is a flexible workspace strategy that maximizes office space efficiency and can reduce real estate costs.
- Implementing hot desking requires clear policies, technology solutions (badge systems, desk booking software), and strong communication with employees.
- Hot desking works best when combined with other workplace strategies like activity-based working and flexible scheduling.
- Employee experience is critical — provide proper training, clear desk protocols, and adequate storage solutions to ensure adoption.
- Hot desking can improve collaboration and reduce the rigid boundaries between departments.

Example of BAD key takeaways (do NOT write like this):
- The page needs to address common challenges in implementing hot desking. (This is an SEO recommendation, not a content lesson)
- Improve SEO by adding keywords throughout the content. (This is generic SEO advice, not content insight)

Keep them clean, specific, and readable. Each should be a standalone statement about what the article teaches.

### Multimodal Assets and/or Image Alt Text
Recommend only small, effective visual elements that enhance clarity and E-E-A-T without over-complicating the layout. Keep suggestions simple and practical. For each recommendation, explain WHY it improves E-E-A-T or engagement:
- Simple comparison tables (e.g., X vs Y vs Z)
- Relevant images or diagrams with descriptive alt text
- Basic charts showing key data points
Limit to 3-5 specific, actionable suggestions. For each, describe what it should show and where on the page it should go.

### FAQs
Generate 3-5 FAQ questions that a user would naturally ask about the article topic. These should be:
- Natural questions that arise from reading the article content
- Aligned with user intent for this topic
- NOT just copied from People Also Ask — generate questions that feel organic to the article
- Each with a concise suggested answer (2-3 sentences)
- Ready for FAQ Schema implementation
- Incorporating semantic variations of the primary keyword

### Content Structure & Additional Content
Provide specific, detailed content changes needed on the page. This section must be comprehensive and actionable. Structure this section EXACTLY like this:

First, list 3-5 specific heading changes with bullet points. Be detailed — include H3 sub-headings for each new H2:
- Add a new H2 heading: "[heading name]". [Explain what content gap it fills and what SERP/competitor data supports it.]
  - Include the following H3 headings:
  - [H3 heading 1]
  - [H3 heading 2]
  - [H3 heading 3]
- Revise the H2 heading: "[old heading]" to "[new heading]". [Explain why based on competitor analysis or SERP patterns.]
  - Add the following H3 headings:
  - [H3 heading 1]
  - [H3 heading 2]

Then add a sub-section:

**Content to add, remove, or restructure:**
- Add: [what to add and where — be specific about placement]
- Expand: [what to expand and what to include — reference competitor content or SERP gaps]
- Remove: [what to remove and why — explain how it detracts from the page]
- Restructure: [what to restructure and how — explain the improved flow]

Then add:

**Recommended new headings:**
- [heading name] — [reasoning grounded in specific SERP findings or competitor content patterns]

(Do NOT include visual content recommendations here — those go in Multimodal Assets above.)

---

## Impact Summary
Based on the analysis, provide:
- **Expected SEO Impact:** 1-2 sentences on expected improvement in visibility, rankings, and AI discoverability.
- **Expected Behavioral Impact:** 1-2 sentences on expected improvement in CTR, engagement, and conversion.

---

## OUTPUT RULES
- **#1 RULE — Focus on the primary URL.** Every recommendation must be about improving THIS specific page's content.
- **#2 RULE — CONTENT ONLY.** Never recommend off-page strategies.
- **#3 RULE — FOLLOW THE TEMPLATE.** Output ONLY the sections above (Overview, Content & SERP Insights, SEO Improvements, Content Improvements, Impact Summary). Do NOT add extra sections. Do NOT output "SECTION 1:", "SECTION 2:", "STEP 1:", "STEP 2:" or similar labels — just use heading names.
- **#4 RULE — USE ACTUAL DATA.** For the Headers table, you MUST use the actual headings from the scraped page data. Never show "(none)" as a current heading if headings were provided in the input data. Every heading from the scraped page must appear in the table.
- **#5 RULE — BE ANALYTICAL, NOT LAZY.** Do NOT default to "Keep as is" for most headings. Actively analyze every heading and recommend concrete improvements. At minimum 40-60% of headings should have a recommended change. Every Rationale cell must contain a reason — never leave it empty.
- **#6 RULE — BE SPECIFIC AND DATA-DRIVEN.** Avoid generic SEO advice. Every recommendation must reference specific data from the input: competitor content, SERP patterns, keyword volumes, content gaps, or page performance metrics. Generic statements like "add more keywords" or "improve SEO" are unacceptable.
- If a client profile was provided, EVERY section must be tailored to it.
- Ground all recommendations in the data provided. No hallucinations. No guarantees.
- Use markdown: headers, tables, lists, bold where helpful.
- Do NOT use HTML tags (no <br>, no <p>, no <table>). Use only markdown formatting.
- The Content & SERP Insights section must be no more than half a page — keep it condensed and strategic.
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
