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
    client_report_instruction = ""
    if client_profile:
        from app.client_profiles import format_client_profile_for_prompt
        client_text = format_client_profile_for_prompt(client_profile)
        client_section = f"""

## CLIENT PROFILE — #1 PRIORITY (this overrides everything else)
**Client:** {client_name or 'Unknown'}

{client_text}

**CRITICAL — NON-NEGOTIABLE:** The ENTIRE report must be tailored to this client profile. Every recommendation, every heading suggestion, every meta description, every internal linking idea — ALL must align with this client's target audience, brand positioning, values, and voice. A generic report is UNACCEPTABLE. The reader must be able to tell which client this report is for just by reading any section.

**If any profile field says "(infer from page content and SERP data)", you MUST infer a real, specific value from the scraped page content, SERP competitors, and keyword context.** Replace every "(infer...)" placeholder with a concrete description (e.g., target audience, brand positioning, values) based on what you learn from the data. Never output "(infer from page content and SERP data)" in the final report.

**If "Specific content instructions" are listed above, you MUST address them explicitly in the Additional Recommendations section.** These are direct client requirements and take priority."""
        client_report_instruction = f"""
1. **Client profile** — MANDATORY WHEN CLIENT PROVIDED. Use EXACTLY this format (no bullet points, no dashes):

## Client Profile

**Client:** [Client Name]

**Target audience:** [target audience description]

**Brand positioning:** [brand positioning description]

**Values:** [comma-separated values]

**Value proposition:** [value proposition description]

All recommendations in this report are tailored to this client profile.

This section comes FIRST (before Executive Summary numbering) because client alignment is the #1 priority. If no client profile was provided, omit this section entirely."""
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

    prompt = f"""You are a content strategist focused ONLY on content optimization. Your scope is limited to what can be changed ON THE PAGE: headings, body copy, metadata, internal links, FAQs, visual content, and content structure.

**Your role:** Analyze the target page content and SERP data below, then produce a comprehensive content optimization report focused on the PRIMARY URL. Every recommendation must be about improving THIS page's content. Summarize WHY each recommendation matters.

**SCOPE BOUNDARY — CRITICAL:** Do NOT recommend off-page strategies. Never suggest backlink building, domain authority improvement, link outreach, PR campaigns, guest posting, or any off-page SEO strategy. SERP competitor data is used to understand what content to create and how to structure it — not to suggest SEO campaigns. If competitors rank due to higher DA or more backlinks, do NOT mention that as a recommendation — focus only on what content changes can close the gap.{client_section}

## Input data
{context}

## MANDATORY rules
- **CONTENT-ONLY SCOPE** — Every recommendation must be about on-page content changes. Never recommend backlink building, domain authority improvement, link outreach, PR campaigns, or any off-page SEO strategy. If you catch yourself writing "build backlinks", "improve domain authority", or "create a link building campaign" — DELETE IT.
- **No hallucinations** — No fake stats, no "guaranteed #1," no unsupported claims. Ground every recommendation in the data provided.
- **Tone & client alignment** — If a client profile was provided, tailor the ENTIRE report to it.
- **Metadata limits** — Title: 50–60 chars (never over 60). Meta description: 150–160 chars (never over 160). Always show character counts in brackets.
- **Use ONLY exact data** — Never invent DR, backlinks, traffic, MSV, or word count numbers. Use "(not available)" if missing.
- **Heading recommendations must be direct** — No verbose marketing-speak. Clear, keyword-focused headings. If a current heading is fine, say "Keep as is" instead of inventing a worse alternative.

## Your task
Write a full content optimization report in Markdown. You MUST include ALL of the following sections:
{client_report_instruction}
1. **Executive Summary** — Begin with: "As a content strategist, here is my analysis of [URL]..." Then summarize what was found on the page and from the SERP. Explain WHY each major recommendation is being made — ground it in specific content gaps or SERP findings. 2-3 sentences that give context for the entire report.

2. **Notes (form)** — MANDATORY: Display "Form notes (user-provided)" VERBATIM if provided, then explain how incorporated. If "(none provided)", state "*(Not provided / not used)*". Never mix with client profile.

3. **URL & GSC** — Target URL verification + GSC performance summary (clicks, impressions, avg position, top queries) or "GSC not available."

4. **Current State Analysis** — The most important analytical section. Based on the scraped body content:
   - **Current metadata:** Exact current title + meta description with character counts.
   - **Current heading structure:** List EVERY heading from the scraped page with its H-level (H1, H2, H3, H4). Do not summarize or skip any — show the complete hierarchy exactly as scraped.
   - **Page intent:** Based on the full body content, what is this page trying to achieve? What topic does it cover, what angle does it take, and for whom?
   - **SERP intent:** Based on SERP competitor data, what does Google think users want when they search this keyword? State this separately, then explicitly compare it to the page's current intent — where do they align and where do they diverge?
   - **Strengths:** What the page does well from a content perspective.
   - **Gaps:** What content is missing compared to what SERP competitors cover. Be specific — name the topics, sections, or questions competitors address that this page does not.

5. **Keyword Targets (with MSV)** — MANDATORY table: Keyword | MSV (est) | Intent | Placement. Use exact MSV from Ahrefs context. Never invent numbers.

6. **Optimization Strategy** — THE WHY SECTION. Explain the overall strategic approach for optimizing this page. This must include:
   - **Primary goal:** What is the main objective for this page? (e.g., "Improve ranking for 'hot desking' from #8 to top 5 by closing content gaps")
   - **Strategic pillars:** 3-5 numbered strategic pillars that summarize HOW the goal will be achieved. Each pillar should be a short heading followed by 1-2 sentences. Examples: "1. Optimize title tag and meta description to include primary and secondary keywords while communicating value to [target audience]", "2. Expand content depth to match or exceed SERP competitors' coverage of [specific topics]", "3. Add visual content (infographics, comparison tables) to increase engagement and dwell time", "4. Structure content for AI citation and featured snippet capture", "5. Strengthen internal linking to boost page authority and user navigation"
   - Ground each pillar in specific data from the analysis (SERP patterns, content gaps, keyword data).

7. **SERP Analysis** — Based on the SERP competitor data, provide a rundown of:
   - **a) SERP Observations Summary** — Start with a numbered list of 5-8 key observations from the SERP data. What patterns do you see? What content approaches dominate? What topics are consistently covered? What content formats are common? These must be content-level observations only.
   - **b) General search intent** — What Google thinks users want when searching this keyword/topic. Summarize in 2-3 bullet points.
   - **c) Competitor heading gap analysis** — List the key headers/topics that top SERP pages cover. Specifically highlight which headers/topics our page is MISSING. Also note what content angle competitors take (how they frame the topic). Format as a table: | Competitor Heading Topic | Present on Our Page? | Action Needed |
   - **d) Rich content opportunities** — Based on the "Rich Content Found on Competitor Pages" data, list what rich content (charts, tables, graphs, data visualizations, videos) competitors have that our article lacks. Recommend specific rich content to add with descriptions of what each should contain.
   - **e) People Also Ask** — List all PAA questions from context with brief suggested answers (2-3 sentences each). If none available, generate 3-5 relevant FAQ questions based on the keyword and content.
   - **f) Actionable content changes from SERP** — Numbered list of specific content changes to make on our primary URL based on the SERP analysis above. Each item must reference a specific section, heading, or content gap. No generic advice.
   - **SERP Competitor Overview table** — If data provided: | # | Domain | DR | Backlinks | Ref. Domains | Traffic | Word Count | Content Approach |. Include backlink and referring domain counts if available in the data. The "Content Approach" column should describe what content/topics/structure each competitor uses — NOT why they rank from an SEO authority perspective.
   - **Keyword Competition Table** — If data provided: Keyword | Search Volume | Difficulty | CPC | Traffic Potential | Global Volume.
   - **Competitive Gap Analysis** — MANDATORY subsection within SERP Analysis. Must include:
     - **DR gap:** Calculate the difference between the target page's DR and the SERP average DR. State both numbers.
     - **Content length comparison:** Compare target page word count vs SERP average and longest competitor. State: "Your page: X words | SERP average: Y words | Longest: Z words (domain.com)".
     - **Weakest competitors:** Identify 2-3 competitors in the SERP that are realistic targets to outrank based on lower DR, thinner content, or fewer backlinks. Explain WHY each is beatable from a content perspective.
     - **Content positioning opportunities:** Based on the gap analysis, what specific content angles or depth improvements would help close the gap? Be specific — reference competitor topics, word counts, and content structures.
   CRITICAL: Do NOT include any off-page recommendations like "build more backlinks", "improve domain authority", or "pursue link building." Content-level observations ONLY. Frame all competitive gaps in terms of CONTENT improvements.

8. **Recommendations** — Concrete, actionable content changes for the primary page:
   - **Title tag alternatives** — Provide **2-5 alternative title tags**, each 50–60 chars. Each must include the primary keyword. Each alternative must be meaningfully different (not just word order swaps). If the current title is already strong, the first option can be "No Changes" with a rationale explaining why. Include a table: | # | Recommended Title | Chars | Rationale |
   - **Meta description alternatives** — Provide **2-5 alternative meta descriptions**, each 150–160 chars. Each must be meaningfully different. If the current meta is already strong, the first option can be "No Changes". Include a table: | # | Recommended Meta Description | Chars | Rationale |
   - **Heading comparison table** — MANDATORY format: | Level (H1/H2/H3) | Current Heading | Recommended Heading | Rationale |. Include ALL headings from the scraped page. Recommended headings must be concise (max 8-10 words) and direct — no creative marketing flair. If a heading is already good, write "Keep as is" in the Recommended column. If a heading should be removed, write "Remove" with rationale. Always classify the heading level (H1, H2, H3). The Rationale column must reference a specific finding (competitor topic, SERP pattern, content gap, or keyword data) — never write generic reasons like "improved clarity" or "better keyword targeting".

9. **Content Reoptimization** — Specific content changes needed on the page:
   - Which existing sections need new or revised H2/H3 headings — for each, state the recommended heading (max 8-10 words) AND explain what specific content gap it fills or what SERP/competitor data supports the change (e.g. "5 of 10 SERP competitors cover this topic" or "addresses PAA question about X")
   - Visual content recommendations: specific charts, graphs, tables, or infographics to add — describe exactly what data each visual should show and where on the page it should go
   - Content to add, remove, or restructure — be specific about which sections, reference them by heading name
   - Recommended new headings with reasoning grounded in specific SERP findings or competitor content patterns (never generic reasoning like "for better structure")

10. **Internal Linking** — Bidirectional internal linking analysis. MANDATORY table format: | Direction | Anchor Text | URL | Rationale |
   - **Outbound (from this page to other internal pages):** List internal links already on the page (from scraped data). Recommend 3-5 additional internal links to add — use specific anchor text and target URLs from the same domain (based on the internal links found during scraping and the "Other pages on this domain" list if provided).
   - **Inbound (from other pages to this page):** Recommend 3-5 pages on the same domain that should link TO this page. You MUST use real URLs from the "Other pages on this domain" data if provided — do NOT use placeholder URLs. For each, provide the source URL, specific anchor text, and rationale for why that page should link here.

11. **FAQs** — Create an FAQ section for the article:
    - Use "People Also Ask" questions from SERP data if available.
    - If PAA questions are not available or insufficient, create 3-5 catered FAQ questions relevant to the keyword and content intent.
    - For each FAQ, provide the question AND a brief suggested answer (2-3 sentences).

12. **Key Takeaways** — List exactly 5-7 key takeaways. Each must be a specific content finding from the analysis (not generic SEO advice). Format as actionable bullet points that reference specific sections, headings, or content gaps identified in this report.

13. **Additional Recommendations** — THE MOST IMPORTANT SECTION. Numbered list of specific content changes to implement on the primary URL. Each item MUST:
    - Specify WHAT to change (heading, paragraph, section, image, table, etc.)
    - Specify WHERE on the page (reference the section by heading name)
    - Explain WHY (what gap it fills, what SERP data supports it)
    - Be a concrete edit to the EXISTING page — NOT creation of new standalone assets
    - Examples of GOOD items: "Add a comparison table under the 'Types of X' section showing...", "Replace the intro paragraph with...", "Remove the outdated statistics in the 'Benefits' section and replace with...", "Add a mid-post CTA after the 'Benefits' section linking to the product demo page"
    - EXPLICITLY FORBIDDEN: Do NOT recommend creating downloadable checklists, separate landing pages, new blog posts, glossary pages, or any standalone assets. Do NOT recommend social media promotion, LinkedIn posts, PR campaigns, email marketing, or distribution strategies. Focus ONLY on editing the existing page content.

14. **AEO/GEO Recommendations** — Recommendations for Answer Engine Optimization and Generative Engine Optimization (content-level only). Use the "SERP Features Detected" data if provided. This section MUST include concrete tables and figures — not just prose:
    - **Current AI/Featured Snippet presence:** If AI Overview or Featured Snippet data was detected in the SERP, describe what Google is currently showing (the title, source URL, and what content is being cited). If no SERP features detected, state that.
    - **How to win/maintain the featured snippet or AI citation:** Based on the detected SERP features, what specific content structure, formatting, or additions would help this page get cited? Reference the actual snippet content if available.
    - **AI Extractability Audit table** — MANDATORY. Create a table: | Element | Current State | Recommended Change | Priority |. Audit these elements: Definition at top of page, FAQ schema/section, Structured lists, Data tables, Concise answer paragraphs (<50 words), "What is X?" headings, Comparison tables, Statistics/data points. For each, assess whether it exists on the page and what to add/change.
    - **Recommended Visual Content for AI Citation table** — MANDATORY. Create a table: | Visual Type | Description | Placement | Why AI Engines Prefer This |. List 3-5 specific charts, graphs, tables, or infographics with exact descriptions of what data each should contain, where on the page it should go, and why AI engines are likely to cite it.
    - **Content formatting changes** — Specific changes to improve AI extractability: lists, tables, concise definitions, "What is X?" patterns.

15. **Quick Reference** — URL | Primary keyword | Priorities | Heading casing (if applicable).

Rules:
- **#1 RULE — Focus on the primary URL.** Every recommendation must be about improving THIS specific page's content.
- **#2 RULE — CONTENT ONLY.** Never recommend backlink building, domain authority improvement, link outreach, guest posting, PR campaigns, or any off-page strategy. All recommendations must be about on-page content changes.
- If a client profile was provided, EVERY section must be tailored to it.
- Heading recommendations must be DIRECT — no verbose marketing headers like "Unlock the Power of X." Use clear, search-intent-focused headings. Say "Keep as is" when a heading is already good.
- Ground all recommendations in the data provided. No hallucinations.
- No guarantees (e.g. "will rank #1"). Be realistic.
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
