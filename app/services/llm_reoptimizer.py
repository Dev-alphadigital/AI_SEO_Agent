"""LLM-powered reoptimization brief generator using OpenRouter + DeepSeek R1."""
import logging
import re

import httpx

from app.config import get_settings
from app.models.schemas import (
    AhrefsMetrics,
    CompetitorPage,
    GapAnalysis,
    KeywordMetrics,
    PageSEO,
    SerpEntry,
)

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are a Senior Enterprise SEO Strategist specializing in content reoptimization for established websites. You produce structured, actionable reoptimization briefs.

## Guardrails
- NO keyword stuffing — recommend natural, contextual keyword placement only
- NO full content rewrites unless data clearly justifies it — prefer incremental improvements
- NO hallucinated data — only reference metrics and content provided in the input data
- Every recommendation must be grounded in the provided data (competitor analysis, keyword metrics, gap analysis)
- If data is missing or unavailable, explicitly state "N/A — data not available" rather than guessing
- GSC data is NOT available for this analysis — do not reference CTR, impressions, or click data from GSC"""


def _strip_thinking(text: str) -> str:
    """Strip DeepSeek R1 <think> blocks from the response."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def build_reoptimization_prompt(
    target_seo: PageSEO,
    ahrefs_metrics: AhrefsMetrics,
    keyword_metrics: KeywordMetrics,
    serp_results: list[SerpEntry],
    competitors: list[CompetitorPage],
    gap_analysis: GapAnalysis,
    keyword: str,
    secondary_keywords: list[str],
    notes: str = "",
) -> str:
    """Assemble the master prompt from collected SEO data."""

    # --- Input Data Block ---
    lines: list[str] = []
    a = lines.append

    a("## Input Data")
    a("")
    a("### Target Page")
    a(f"- **URL:** {target_seo.url}")
    a(f"- **Title:** {target_seo.title or '(none)'} [{target_seo.title_length} chars]")
    a(f"- **Meta Description:** {target_seo.meta_description or '(none)'} [{target_seo.meta_description_length} chars]")
    a(f"- **H1:** {target_seo.h1 or '(none)'}")
    a(f"- **H2s:** {', '.join(target_seo.h2s) if target_seo.h2s else '(none)'}")
    a(f"- **H3s:** {', '.join(target_seo.h3s) if target_seo.h3s else '(none)'}")
    a(f"- **Word Count:** {target_seo.word_count}")
    a(f"- **Internal Links:** {target_seo.internal_links}")
    a(f"- **External Links:** {target_seo.external_links}")
    a(f"- **Images:** {target_seo.image_count} ({target_seo.images_with_alt} with alt text)")
    a(f"- **Schema Markup:** {', '.join(target_seo.schema_types) if target_seo.schema_types else 'None'}")
    a("")

    a("### Keyword Data")
    a(f"- **Primary Keyword:** {keyword}")
    a(f"- **Secondary Keywords:** {', '.join(secondary_keywords) if secondary_keywords else '(none provided)'}")
    a(f"- **Search Volume:** {keyword_metrics.volume}")
    a(f"- **Keyword Difficulty:** {keyword_metrics.difficulty}")
    a(f"- **CPC:** ${keyword_metrics.cpc:.2f}")
    a(f"- **Traffic Potential:** {keyword_metrics.traffic_potential}")
    a(f"- **Search Intent:** {keyword_metrics.intent or 'unknown'}")
    a("")

    a("### Ahrefs Metrics (Target Domain)")
    a(f"- **Domain Rating:** {ahrefs_metrics.domain_rating}")
    a(f"- **Backlinks:** {ahrefs_metrics.backlinks}")
    a(f"- **Referring Domains:** {ahrefs_metrics.referring_domains}")
    a(f"- **Organic Keywords:** {ahrefs_metrics.organic_keywords}")
    a(f"- **Organic Traffic:** {ahrefs_metrics.organic_traffic}")
    a("")

    a("### Competitor Landscape (Top 5)")
    if competitors:
        for i, comp in enumerate(competitors[:5], 1):
            a(f"**Competitor {i}: {comp.url}**")
            a(f"  - Title: {comp.page_seo.title or '(none)'}")
            a(f"  - H2s: {', '.join(comp.page_seo.h2s[:8]) if comp.page_seo.h2s else '(none)'}")
            a(f"  - Word Count: {comp.page_seo.word_count}")
            a(f"  - DR: {comp.ahrefs_metrics.domain_rating}")
            a(f"  - Backlinks: {comp.ahrefs_metrics.backlinks}")
            a("")
    else:
        a("*No competitor data available.*")
        a("")

    a("### Gap Analysis")
    a(f"- **Your Word Count:** {target_seo.word_count} | **Competitor Avg:** {gap_analysis.avg_competitor_word_count}")
    if gap_analysis.missing_topics:
        a(f"- **Missing Topics:** {', '.join(gap_analysis.missing_topics[:10])}")
    if gap_analysis.structure_recommendations:
        a(f"- **Structure Issues:** {'; '.join(gap_analysis.structure_recommendations)}")
    if gap_analysis.content_quality_issues:
        a(f"- **Quality Issues:** {'; '.join(gap_analysis.content_quality_issues)}")
    a("")

    if serp_results:
        a("### SERP Overview (Top 10)")
        for entry in serp_results[:10]:
            a(f"  {entry.position}. {entry.title} — {entry.url} (DR: {entry.domain_rating})")
        a("")

    if notes:
        a("### Additional Notes")
        a(notes)
        a("")

    # --- Workflow Instructions ---
    a("## Execute the 4-Step Reoptimization Workflow")
    a("")
    a("### STEP 0: Viability Check")
    a("Determine if full reoptimization is warranted:")
    a("- Check if the target URL appears in the SERP top 5 for the primary keyword")
    a("- If target is in top 5 with strong organic traffic → limit recommendations to metadata/linking tweaks only")
    a("- If target is NOT in top 5 or has weak metrics → proceed with full reoptimization")
    a("- Note: GSC data (CTR, impressions) is N/A — use Ahrefs organic traffic as engagement proxy")
    a("")

    a("### STEP 1: Current State Analysis")
    a("- Classify the dominant search intent for the primary keyword (informational / commercial / transactional / navigational)")
    a("- Identify the primary underperformance cause from: intent mismatch, content gap, poor structure, weak metadata, insufficient internal linking, or low authority")
    a("- Compare target page content depth and structure against top competitors")
    a("")

    a("### STEP 2: Metadata Update")
    a("Provide optimized metadata:")
    a(f"- **New Title Tag:** Must be ≤60 characters, must include \"{keyword}\", front-loaded preferred")
    a("- **New Meta Description:** Must be ≤160 characters, CTR-optimized with benefit + CTA")
    a("- Show current vs recommended for each")
    a("")

    a("### STEP 3: Content Reoptimization Plan")
    a("Provide 5 sections:")
    a("")
    a("**3.1 Content Structure**")
    a("Create a comparison table with two columns:")
    a("- Column 1: Current H2/H3 headings")
    a("- Column 2: Recommended H2/H3 headings")
    a("Recommend 3-5 heading changes/additions based on competitor analysis and gap data.")
    a("")
    a("**3.2 Visual & Trust Elements**")
    a("Recommend 3 asset types (e.g., comparison table, infographic, case study screenshot) with E-E-A-T justification for each.")
    a("")
    a("**3.3 Internal Linking Opportunities**")
    a("Suggest 3 internal links as: anchor text → target URL path.")
    a("If the target site's internal structure is unclear, flag this as a gap to investigate.")
    a("")
    a("**3.4 FAQs for Schema**")
    a("Write 3-5 Q&A pairs ready for FAQ Schema markup. Questions should reflect real search queries related to the primary and secondary keywords.")
    a("")
    a("**3.5 Key Takeaways**")
    a("Summarize the top 3 actionable priorities from this brief.")
    a("")

    a("### STEP 4: Impact Summary")
    a("- **Expected SEO Impact:** Projected ranking/visibility improvement based on recommendations")
    a("- **Expected Behavioral Impact:** How changes should affect user engagement (time on page, bounce rate)")
    a("- **Follow-up Question:** One strategic question for the client to consider")
    a("")

    a("## Output Rules")
    a("- Output in Markdown format only")
    a("- Be concise, structured, and actionable")
    a("- Do NOT give generic SEO advice — every recommendation must reference specific data from the input")
    a("- GSC data: N/A (not available) — state this explicitly where relevant")
    a("- Do NOT include any preamble or explanation before the brief — start directly with Step 0")

    return "\n".join(lines)


async def call_openrouter(prompt: str, system: str) -> str:
    """Call OpenRouter API with the given prompt and system message."""
    settings = get_settings()

    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY not configured")

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(OPENROUTER_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    return _strip_thinking(content)


async def generate_reoptimization_brief(
    target_seo: PageSEO,
    ahrefs_metrics: AhrefsMetrics,
    keyword_metrics: KeywordMetrics,
    serp_results: list[SerpEntry],
    competitors: list[CompetitorPage],
    gap_analysis: GapAnalysis,
    keyword: str,
    secondary_keywords: list[str],
    notes: str = "",
) -> str:
    """Orchestrate the LLM reoptimization brief generation.

    Returns the AI-generated Markdown string.
    """
    prompt = build_reoptimization_prompt(
        target_seo=target_seo,
        ahrefs_metrics=ahrefs_metrics,
        keyword_metrics=keyword_metrics,
        serp_results=serp_results,
        competitors=competitors,
        gap_analysis=gap_analysis,
        keyword=keyword,
        secondary_keywords=secondary_keywords,
        notes=notes,
    )

    logger.info("Calling OpenRouter (%s) for reoptimization brief...", get_settings().openrouter_model)
    ai_brief = await call_openrouter(prompt, SYSTEM_PROMPT)
    logger.info("Received AI brief (%d chars)", len(ai_brief))

    return ai_brief
