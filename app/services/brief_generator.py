"""Brief generator — compiles all analysis data into a Markdown SEO brief."""
import os
from datetime import datetime

from app.models.schemas import (
    AhrefsMetrics,
    CompetitorPage,
    GapAnalysis,
    KeywordMetrics,
    PageSEO,
    SEOBrief,
    SerpEntry,
)

OUTPUT_DIR = "output"


def _ensure_output_dir() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _title_status(length: int) -> str:
    if length == 0:
        return "MISSING"
    if length <= 60:
        return f"{length} chars OK"
    return f"{length} chars TRUNCATED"


def _desc_status(length: int) -> str:
    if length == 0:
        return "MISSING"
    if length <= 160:
        return f"{length} chars OK"
    return f"{length} chars TRUNCATED"


def _check(condition: bool) -> str:
    return "PASS" if condition else "FAIL"


def _build_markdown(brief: SEOBrief) -> str:
    """Render the brief as a Markdown document."""
    lines: list[str] = []
    a = lines.append

    a("# SEO Reoptimization Brief")
    a(f"## Target: {brief.target_url} | Keyword: {brief.keyword}")
    a(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    a("")

    # Warnings
    if brief.warnings:
        a("### Warnings")
        for w in brief.warnings:
            a(f"- {w}")
        a("")

    # ---- Current State ----
    seo = brief.target_page_seo
    met = brief.ahrefs_metrics
    kw = brief.keyword_metrics
    a("### Current State")
    a(f"- **Title:** {seo.title or '(none)'} [{_title_status(seo.title_length)}]")
    a(f"- **Meta Description:** {seo.meta_description[:100] + '...' if len(seo.meta_description) > 100 else seo.meta_description or '(none)'} [{_desc_status(seo.meta_description_length)}]")
    a(f"- **H1:** {seo.h1 or '(none)'}")
    a(f"- **Word Count:** {seo.word_count}")
    a(f"- **H2 Count:** {len(seo.h2s)} | **H3 Count:** {len(seo.h3s)}")
    a(f"- **Internal Links:** {seo.internal_links} | **External Links:** {seo.external_links}")
    a(f"- **Images:** {seo.image_count} ({seo.images_with_alt} with alt text)")
    a(f"- **Domain Rating:** {met.domain_rating} | **URL Rating:** {met.url_rating}")
    a(f"- **Backlinks:** {met.backlinks} | **Referring Domains:** {met.referring_domains}")
    a(f"- **Organic Keywords:** {met.organic_keywords} | **Organic Traffic:** {met.organic_traffic}")
    a("")

    # ---- Social Media Tags ----
    a("### Social Media Tags")
    a(f"- **og:title:** {seo.og_title or 'MISSING'}")
    a(f"- **og:description:** {seo.og_description or 'MISSING'}")
    a(f"- **og:image:** {seo.og_image or 'MISSING'}")
    a(f"- **og:type:** {seo.og_type or 'MISSING'}")
    a(f"- **twitter:card:** {seo.twitter_card or 'MISSING'}")
    a("")

    # ---- Technical Tags ----
    a("### Technical Tags")
    a(f"- **Canonical:** {seo.canonical_url or 'MISSING'}")
    a(f"- **Robots:** {seo.robots or '(not set — defaults to index, follow)'}")
    a(f"- **Viewport:** {'Present' if seo.has_viewport else 'MISSING'}")
    a(f"- **Lang:** {seo.lang or 'MISSING'}")
    a(f"- **Schema Markup:** {', '.join(seo.schema_types) if seo.schema_types else 'None detected'}")
    a("")

    # ---- Keyword Data ----
    a("### Keyword Data")
    a(f"- **Keyword:** {kw.keyword}")
    a(f"- **Volume:** {kw.volume}")
    a(f"- **Difficulty:** {kw.difficulty}")
    a(f"- **CPC:** ${kw.cpc:.2f}")
    a(f"- **Traffic Potential:** {kw.traffic_potential}")
    if kw.intent:
        a(f"- **Search Intent:** {kw.intent}")
    a("")

    # ---- On-Page SEO Checklist ----
    a("### On-Page SEO Checklist")
    kw_lower = brief.keyword.lower()
    title_has_kw = kw_lower in seo.title.lower() if seo.title else False
    h1_has_kw = kw_lower in seo.h1.lower() if seo.h1 else False
    desc_has_kw = kw_lower in seo.meta_description.lower() if seo.meta_description else False
    a(f"| Check | Status |")
    a(f"|-------|--------|")
    a(f"| Title tag present | {_check(bool(seo.title))} |")
    a(f"| Title length 50-60 chars | {_check(30 <= seo.title_length <= 60)} |")
    a(f"| Keyword in title | {_check(title_has_kw)} |")
    a(f"| Meta description present | {_check(bool(seo.meta_description))} |")
    a(f"| Description length 150-160 chars | {_check(120 <= seo.meta_description_length <= 160)} |")
    a(f"| Keyword in description | {_check(desc_has_kw)} |")
    a(f"| H1 tag present | {_check(bool(seo.h1))} |")
    a(f"| Keyword in H1 | {_check(h1_has_kw)} |")
    a(f"| Open Graph tags | {_check(bool(seo.og_title and seo.og_image))} |")
    a(f"| Schema markup | {_check(seo.has_schema_markup)} |")
    a(f"| Mobile viewport | {_check(seo.has_viewport)} |")
    a(f"| Images have alt text | {_check(seo.images_with_alt == seo.image_count or seo.image_count == 0)} |")
    a(f"| Internal links (2+) | {_check(seo.internal_links >= 2)} |")
    a(f"| External links (1+) | {_check(seo.external_links >= 1)} |")
    a("")

    # ---- Content Quality Issues ----
    gap = brief.gap_analysis
    if gap.content_quality_issues:
        a("### Content Quality Issues")
        for issue in gap.content_quality_issues:
            a(f"- {issue}")
        a("")

    # ---- Competitor Landscape ----
    a("### Competitor Landscape")
    if brief.competitors:
        a("| # | URL | DR | Word Count | Backlinks | H2s |")
        a("|---|-----|---:|----------:|---------:|----:|")
        for i, comp in enumerate(brief.competitors, 1):
            a(
                f"| {i} | {comp.url} | {comp.ahrefs_metrics.domain_rating} "
                f"| {comp.page_seo.word_count} | {comp.ahrefs_metrics.backlinks} "
                f"| {len(comp.page_seo.h2s)} |"
            )
    else:
        a("*No competitor data available.*")
    a("")

    # ---- SERP Overview ----
    if brief.serp_results:
        a("### SERP Overview")
        a("| Pos | Title | URL | DR |")
        a("|----:|-------|-----|---:|")
        for entry in brief.serp_results:
            a(f"| {entry.position} | {entry.title} | {entry.url} | {entry.domain_rating} |")
        a("")

    # ---- Gap Analysis ----
    a("### Gap Analysis")
    a(f"- **Your Word Count:** {seo.word_count} | **Competitor Avg:** {gap.avg_competitor_word_count}")
    if gap.word_count_target > seo.word_count:
        a(f"- **Word Count Gap:** Expand by ~{gap.word_count_target - seo.word_count} words to match competitors")
    else:
        a(f"- **Word Count:** Meets or exceeds competitor average")
    a("")
    if gap.missing_topics:
        a("**Missing Topics** (covered by multiple competitors):")
        for topic in gap.missing_topics:
            a(f"- {topic}")
        a("")
    if gap.structure_recommendations:
        a("**Structure Recommendations:**")
        for rec in gap.structure_recommendations:
            a(f"- {rec}")
        a("")

    # ---- Recommendations ----
    a("### Recommendations")
    a("")

    # Title recommendations with formulas from skill docs
    a("#### Title Tag")
    current_title = seo.title or "(none)"
    a(f"- **Current:** {current_title} [{seo.title_length} chars]")
    a(f"- **Target:** Include \"{brief.keyword}\" near the front, keep under 60 characters")
    a("- **Proven title formulas for this keyword:**")
    a(f'  - How-To: "How to {brief.keyword.title()} (2026 Guide)"')
    a(f'  - Complete Guide: "{brief.keyword.title()}: The Complete Guide (2026)"')
    a(f'  - Listicle: "N Best {brief.keyword.title()} Tips That Actually Work"')
    a("- **CTR boosters:** Add numbers (+20-30% CTR), brackets (+38%), current year (+10-15%)")
    a("")

    # Meta description recommendations
    a("#### Meta Description")
    if seo.meta_description:
        a(f"- **Current:** {seo.meta_description[:160]} [{seo.meta_description_length} chars]")
    else:
        a("- **Current:** (none)")
    a("- **Target:** 150-160 characters with keyword + benefit + CTA")
    a("- **Formula:** [What the page offers] + [Benefit to user] + [Call-to-action]")
    a(f'- **Example:** "Learn {brief.keyword} with our complete guide. Covers [key points]. Get actionable tips now."')
    a("")

    # Social tags
    if not seo.og_title or not seo.og_image:
        a("#### Social Media Tags")
        if not seo.og_title:
            a("- Add `og:title` — can differ from title tag, optimize for social sharing")
        if not seo.og_description:
            a("- Add `og:description` — up to 200 characters, focus on shareability")
        if not seo.og_image:
            a("- Add `og:image` — 1200x630px recommended for Facebook/LinkedIn")
        if not seo.twitter_card:
            a("- Add `twitter:card` — use `summary_large_image` for articles")
        a("")

    # Topics to add
    if gap.missing_topics:
        a("#### Topics to Add")
        a("Add these as H2/H3 sections (covered by competitors but missing from your page):")
        for topic in gap.missing_topics[:10]:
            a(f"- {topic}")
        a("")

    # Word count
    if gap.word_count_target > seo.word_count:
        a(f"#### Content Length")
        a(f"- Expand content to ~{gap.word_count_target} words (currently {seo.word_count})")
        a("")

    # Schema
    if not seo.has_schema_markup:
        a("#### Structured Data")
        a("- Add JSON-LD schema markup (Article, FAQ, or HowTo depending on content type)")
        a("- Schema can unlock rich results in Google SERPs")
        a("")

    return "\n".join(lines)


def generate_brief(
    target_url: str,
    keyword: str,
    target_seo: PageSEO,
    ahrefs_data: AhrefsMetrics,
    keyword_data: KeywordMetrics,
    serp_results: list[SerpEntry],
    competitors: list[CompetitorPage],
    gaps: GapAnalysis,
    warnings: list[str] | None = None,
) -> SEOBrief:
    """Assemble the full SEO brief, save Markdown to output/, return the model."""
    _ensure_output_dir()

    brief = SEOBrief(
        target_url=target_url,
        keyword=keyword,
        target_page_seo=target_seo,
        ahrefs_metrics=ahrefs_data,
        keyword_metrics=keyword_data,
        serp_results=serp_results,
        competitors=competitors,
        gap_analysis=gaps,
        warnings=warnings or [],
    )

    # Generate and save Markdown
    md_content = _build_markdown(brief)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = keyword.replace(" ", "_")[:50]
    filename = f"brief_{safe_keyword}_{timestamp}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    brief.markdown_path = filepath
    return brief
