"""Competitor analysis — combines Ahrefs SERP data with page scraping."""
import asyncio
import logging

from app.models.schemas import (
    CompetitorPage,
    GapAnalysis,
    PageSEO,
    SerpEntry,
)
from app.services.ahrefs import get_domain_metrics, get_serp_overview
from app.services.page_scraper import scrape_page

logger = logging.getLogger(__name__)


async def analyze_competitors(
    keyword: str, target_url: str
) -> tuple[list[SerpEntry], list[CompetitorPage]]:
    """Get SERP results and scrape/enrich each competitor page.

    Returns (serp_entries, competitor_pages).
    """
    serp_entries = await get_serp_overview(keyword)
    if not serp_entries:
        return [], []

    # Filter out the target URL from competitors
    competitor_urls = [
        entry for entry in serp_entries if entry.url != target_url
    ][:10]

    async def _build_competitor(entry: SerpEntry) -> CompetitorPage:
        page_seo, metrics = await asyncio.gather(
            scrape_page(entry.url),
            get_domain_metrics(entry.url),
        )
        return CompetitorPage(
            url=entry.url,
            page_seo=page_seo,
            ahrefs_metrics=metrics,
        )

    competitors = await asyncio.gather(
        *[_build_competitor(entry) for entry in competitor_urls],
        return_exceptions=True,
    )

    # Filter out any that failed
    valid: list[CompetitorPage] = []
    for i, c in enumerate(competitors):
        if isinstance(c, CompetitorPage):
            valid.append(c)
        else:
            failed_url = competitor_urls[i].url if i < len(competitor_urls) else "unknown"
            logger.warning("Competitor analysis failed for %s: %s", failed_url, c)

    return serp_entries, valid


def identify_gaps(
    target_seo: PageSEO, competitors: list[CompetitorPage]
) -> GapAnalysis:
    """Compare target page against competitors to find content gaps."""
    if not competitors:
        return GapAnalysis()

    # Collect competitor heading topics (lowercased for comparison)
    target_h2_lower = {h.lower() for h in target_seo.h2s}
    target_h3_lower = {h.lower() for h in target_seo.h3s}
    target_topics = target_h2_lower | target_h3_lower

    # Count how often each heading topic appears across competitors
    topic_counts: dict[str, int] = {}
    for comp in competitors:
        comp_topics = set()
        for h in comp.page_seo.h2s + comp.page_seo.h3s:
            comp_topics.add(h.lower())
        for t in comp_topics:
            topic_counts[t] = topic_counts.get(t, 0) + 1

    # Topics covered by 3+ competitors that target is missing
    min_coverage = min(3, max(2, len(competitors) // 2))
    missing_topics = [
        topic for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1])
        if count >= min_coverage and topic not in target_topics
    ]

    # Word count analysis
    comp_word_counts = [c.page_seo.word_count for c in competitors if c.page_seo.word_count > 0]
    avg_wc = int(sum(comp_word_counts) / len(comp_word_counts)) if comp_word_counts else 0

    # Word count target: only set a gap target if we're below average
    if target_seo.word_count < avg_wc:
        word_count_target = avg_wc
    else:
        word_count_target = target_seo.word_count

    # Structure recommendations
    structure_recs: list[str] = []
    if target_seo.word_count < avg_wc and avg_wc > 0:
        structure_recs.append(
            f"Content is {avg_wc - target_seo.word_count} words shorter than "
            f"the competitor average ({avg_wc} words). Consider expanding."
        )
    if not target_seo.h1:
        structure_recs.append("Missing H1 tag — add a primary heading.")
    if len(target_seo.h2s) < 3:
        avg_h2 = int(sum(len(c.page_seo.h2s) for c in competitors) / len(competitors))
        if avg_h2 > len(target_seo.h2s):
            structure_recs.append(
                f"Only {len(target_seo.h2s)} H2 headings vs competitor average of {avg_h2}. "
                "Add more section headings."
            )
    if not target_seo.meta_description:
        structure_recs.append("Missing meta description.")

    # Content quality issues (per audit: on-page SEO checklist items)
    quality_issues: list[str] = []

    # Title checks
    if not target_seo.title:
        quality_issues.append("Missing title tag.")
    elif target_seo.title_length > 60:
        quality_issues.append(
            f"Title tag is {target_seo.title_length} characters (recommended: 50-60). "
            "May be truncated in search results."
        )
    elif target_seo.title_length < 30:
        quality_issues.append(
            f"Title tag is only {target_seo.title_length} characters. "
            "Consider expanding for better SERP visibility."
        )

    # Meta description checks
    if target_seo.meta_description:
        if target_seo.meta_description_length > 160:
            quality_issues.append(
                f"Meta description is {target_seo.meta_description_length} characters "
                "(recommended: 150-160). May be truncated."
            )
        elif target_seo.meta_description_length < 120:
            quality_issues.append(
                f"Meta description is only {target_seo.meta_description_length} characters. "
                "Consider expanding to use full SERP real estate."
            )

    # Open Graph checks
    if not target_seo.og_title:
        quality_issues.append("Missing Open Graph title (og:title) — social shares will use page title.")
    if not target_seo.og_description:
        quality_issues.append("Missing Open Graph description (og:description) — social shares may show no preview.")
    if not target_seo.og_image:
        quality_issues.append(
            "Missing Open Graph image (og:image) — social shares will have no image preview. "
            "Recommended size: 1200x630px."
        )

    # Technical checks
    if target_seo.robots and "noindex" in target_seo.robots.lower():
        quality_issues.append("CRITICAL: robots meta tag contains 'noindex' — page will NOT appear in search results.")
    if not target_seo.has_viewport:
        quality_issues.append("Missing viewport meta tag — page may not be mobile-friendly.")
    if not target_seo.lang:
        quality_issues.append("Missing lang attribute on <html> — helps search engines with language detection.")
    if not target_seo.has_schema_markup:
        quality_issues.append("No structured data (JSON-LD) detected. Consider adding schema markup.")

    # Image checks
    if target_seo.image_count > 0 and target_seo.images_with_alt < target_seo.image_count:
        missing_alt = target_seo.image_count - target_seo.images_with_alt
        quality_issues.append(
            f"{missing_alt} of {target_seo.image_count} images missing alt text. "
            "Add descriptive alt text for accessibility and image SEO."
        )

    return GapAnalysis(
        missing_topics=missing_topics,
        missing_keywords=[],
        structure_recommendations=structure_recs,
        word_count_target=word_count_target,
        avg_competitor_word_count=avg_wc,
        content_quality_issues=quality_issues,
    )
