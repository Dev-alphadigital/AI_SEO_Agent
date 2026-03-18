#!/usr/bin/env python3
"""
Create SEO brief — Gemini-driven analysis and optimization strategy.

Uses Gemini as the SEO agent: gathers data (GSC, scrape), passes to Gemini,
and outputs the full analysis report. All thinking and optimization strategy
is done by Gemini.

Fallback: --no-gemini produces a template-based brief without AI analysis.

Usage:
  python create_brief.py <url> <keyword> [--client NAME] [--property GSC_PROPERTY] [--output PATH]
  python create_brief.py <url> <keyword> --client "Goldman Sachs"  # report tailored to client profile

Example:
  python create_brief.py https://sesky.pk/ "perfume Pakistan"
  python create_brief.py https://goldmansachs.com/... "India Economy 2026" --client "Goldman Sachs"
  python create_brief.py https://example.com/ "keyword" --notes "Focus on X" --casing title --no-gemini
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Load .env
_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sys.path.insert(0, str(Path(__file__).parent))

from app.gsc_client import get_gsc_performance, format_gsc_for_brief
from app.gemini_client import generate_full_seo_report
from app.page_scraper import scrape_page
from app.client_profiles import get_client_profile, list_clients
from app.ahrefs_client import format_keywords_with_msv, get_competitive_analysis, get_top_pages


def _clean_text(text: str) -> str:
    """Strip zero-width spaces and other invisible Unicode from user input."""
    if not text:
        return text
    import unicodedata
    return "".join(
        ch for ch in text
        if unicodedata.category(ch) not in ("Cf", "Cc") or ch in ("\n", "\r", "\t")
    ).strip()


def _normalize_url(url: str) -> str:
    """Clean URL for brief."""
    url = url.split("?")[0].rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url


def _url_to_slug(url: str) -> str:
    """Extract domain slug for filename."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "").replace(".", "_")
    path = parsed.path.strip("/").replace("/", "_") or "home"
    return f"{domain}_{path}"[:50]


def _url_to_website_name(url: str) -> str:
    """Extract clean website domain from URL (e.g. 'inktel.com')."""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split("/")[0]
    domain = domain.replace("www.", "")
    return domain


def _derive_gsc_property(url: str) -> str:
    """Derive GSC property from URL (URL prefix format)."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}/"
    return base


def _format_keyword_msv(primary: str, secondary: str, volumes: dict) -> str:
    """Format MSV for keywords section. Returns inline text or table."""
    parts = []
    for kw in [primary] + [s.strip() for s in (secondary or "").split(",") if s.strip()]:
        v = volumes.get(kw)
        parts.append(f"{kw}: {v:,}" if v is not None else f"{kw}: (add from Ahrefs)")
    return " | ".join(parts) if parts else "(add from Ahrefs)"


def build_brief(
    url: str,
    keyword: str,
    gsc_result: dict,
    gemini_result: dict = None,
    property_used: str = None,
    secondary_keywords: str = None,
    scrape_result: dict = None,
    notes: str = None,
    casing_style: str = None,
    keyword_volumes: dict = None,
) -> str:
    """Build full SEO brief markdown with GSC section and Priority 3 items."""
    if not property_used:
        property_used = _derive_gsc_property(url)

    warnings = []
    if not gsc_result.get("success"):
        warnings.append(f"GSC: {gsc_result.get('error', 'Unknown error')} — recommendations based on keyword research only.")
    else:
        warnings.append("GSC data included (clicks, impressions, avg position, top queries).")

    # Scraped metadata
    title_str = meta_str = h1_str = "(scrape unavailable)"
    issues = []
    if scrape_result and scrape_result.get("success"):
        title_str = scrape_result.get("title") or "(none)"
        meta_str = scrape_result.get("meta_description") or "(none)"
        h1_str = scrape_result.get("h1") if scrape_result.get("h1") else "(none detected)"
        issues = scrape_result.get("issues", [])

    lines = [
        "# SEO Brief",
        f"## Target: {url} | Keyword: {keyword}",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "### Warnings",
    ]
    for w in warnings:
        lines.append(f"- {w}")
    lines.extend(["", "---", ""])

    # GSC Performance Data — Priority 1, must be present
    lines.append("## GSC Performance Data (Priority 1)")
    lines.append("")
    lines.append(format_gsc_for_brief(gsc_result))
    lines.extend(["", "---", ""])

    # Current State (P1 #3 metadata, P1 #4 headings)
    headings = scrape_result.get("headings", []) if scrape_result else []
    lines.extend([
        "## Current State (Priority 1)",
        "",
        f"- **Title:** {title_str} [{len(title_str)} chars]",
        f"- **Meta Description:** {meta_str} [{len(meta_str)} chars]",
        f"- **H1:** {h1_str}",
    ])
    if headings:
        lines.extend(["", "**Heading hierarchy (H1/H2/H3):**", ""])
        for h in headings[:25]:
            lines.append(f"- {h}")
    lines.extend([
        "",
        "---",
        "",
        "## Target keywords (form) — Priority 1",
        "",
        "*(Keywords from form input — distinct from Current top queries above)*",
        "",
        f"- **Primary Keyword:** {keyword}",
        f"- **Secondary Keywords:** {secondary_keywords or '(add from research)'}",
        f"- **MSV:** {_format_keyword_msv(keyword, secondary_keywords, keyword_volumes or {})}",
        "",
    ])

    # Priority 3: Notes section (incorporated or marked not used)
    lines.append("### Notes (form)")
    if notes and notes.strip():
        lines.append("")
        lines.append(notes.strip())
    else:
        lines.append("")
        lines.append("*(Not provided / not used)*")
    lines.extend(["", "---", ""])

    # Priority 3: Issues to Fix
    lines.append("## Issues to Fix (Priority 3)")
    lines.append("")
    if issues:
        for issue in issues:
            lines.append(f"- {issue}")
    else:
        lines.append("- *(No obvious issues detected from scrape)*")
    lines.extend(["", "---", ""])

    # Recommendations
    lines.extend([
        "## Recommendations",
        "",
    ])

    # Use Gemini recommendations if available
    if gemini_result and gemini_result.get("success"):
        lines.append("### Recommended Title")
        if gemini_result.get("recommended_title"):
            title = gemini_result["recommended_title"]
            lines.append(f"- **{title}** [{len(title)} chars]")
        else:
            lines.append("- **Target:** 50–60 chars, include primary keyword")
        lines.append("")
        lines.append("### Recommended Meta Description")
        if gemini_result.get("recommended_meta"):
            meta = gemini_result["recommended_meta"]
            lines.append(f"- **{meta}** [{len(meta)} chars]")
        else:
            lines.append("- **Target:** 150–160 chars, keyword + CTA")
        lines.append("")
        lines.append("### Heading Structure Comparison")
        if gemini_result.get("heading_suggestions"):
            lines.append("")
            lines.append(gemini_result["heading_suggestions"])
        else:
            lines.append("- Add current vs recommended table")
        # Priority 3: PAA/snippet subtopics (1-3 question-style H2/H3)
        paa = gemini_result.get("paa_subtopics") or []
        if paa:
            lines.append("")
            lines.append("### PAA/Snippet Subtopics (Priority 3)")
            lines.append("")
            lines.append("*(Question-style H2/H3 for broader SERP coverage)*")
            lines.append("")
            for p in paa[:3]:
                lines.append(f"- {p}")
    else:
        lines.extend([
            "### Recommended Title",
            "- **Target:** 50–60 chars, include primary keyword",
            "",
            "### Recommended Meta Description",
            "- **Target:** 150–160 chars, keyword + CTA",
            "",
            "### Heading comparison",
            "- Add current vs recommended table (enable Gemini for AI-generated suggestions)",
        ])

    # Quick Reference (includes casing style — Priority 3)
    quick_ref = [
        "",
        "---",
        "",
        "## Quick Reference",
        "",
        f"| Item | Value |",
        f"|------|-------|",
        f"| **URL** | {url} |",
        f"| **Keyword** | {keyword} |",
        f"| **GSC Property** | {property_used} |",
    ]
    if casing_style:
        quick_ref.append(f"| **Heading casing** | {casing_style.title()} case |")
    quick_ref.extend(["", ""])
    lines.extend(quick_ref)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Create SEO brief with GSC performance data (Priority 1 required)"
    )
    parser.add_argument("url", help="Target URL")
    parser.add_argument("keyword", help="Target keyword")
    parser.add_argument("--property", "-p", help="GSC property URL (e.g. https://example.com/ or sc-domain:example.com)")
    parser.add_argument("--output", "-o", help="Output file path (default: output/brief_<slug>_<timestamp>.md)")
    parser.add_argument("--days", "-d", type=int, default=90, help="GSC data days back (default: 90)")
    parser.add_argument("--secondary", "-s", help="Secondary keywords (comma-separated)")
    parser.add_argument("--notes", "-n", help="Notes from form (incorporated or marked not used)")
    parser.add_argument("--casing", "-c", choices=["title", "sentence"], help="Heading casing: title or sentence")
    parser.add_argument("--client", help="Client name (e.g. Markup AI, Goldman Sachs). Report tailored to client profile.")
    parser.add_argument("--country", default="us", help="Country code for Ahrefs MSV (default: us)")
    parser.add_argument("--no-competitor", action="store_true", help="Skip Ahrefs competitive analysis (saves API units)")
    parser.add_argument("--no-gemini", action="store_true", help="Skip Gemini AI recommendations")
    parser.add_argument("--no-scrape", action="store_true", help="Skip page scraping (use placeholders)")
    parser.add_argument("--playwright", action="store_true", help="Force Playwright (for bot-blocked sites: Tesla, Nike, etc.)")
    args = parser.parse_args()

    url = _normalize_url(args.url)
    args.keyword = _clean_text(args.keyword)
    if args.secondary:
        args.secondary = _clean_text(args.secondary)
    if args.notes:
        args.notes = _clean_text(args.notes)
    slug = _url_to_slug(url)
    property_url = args.property or _derive_gsc_property(url)

    # Scrape page (full body, headings H1-H6, internal/external links, rich content)
    scrape_result = None
    if not args.no_scrape:
        scrape_result = scrape_page(url, force_playwright=args.playwright)
        if scrape_result.get("success"):
            m = scrape_result.get("method", "?")
            t = (scrape_result.get("title") or "")[:40]
            h = "yes" if scrape_result.get("h1") else "no"
            n_headings = len(scrape_result.get("headings", []))
            n_int = len(scrape_result.get("internal_links", []))
            body_words = len(scrape_result.get("body_text", "").split())
            print(f"Scrape [{m}]: title={t}..., H1={h}, headings={n_headings}, internal_links={n_int}, body={body_words}w")
        elif scrape_result.get("error"):
            print(f"Scrape: {scrape_result['error']} (using placeholders)")

    # Always fetch GSC — required for every brief
    result = get_gsc_performance(
        url,
        site_property=property_url,
        days_back=args.days,
    )

    # Client profile (for tailored report)
    client_profile = None
    if args.client:
        client_profile = get_client_profile(args.client)
        if client_profile:
            print(f"Client: {args.client} (profile loaded)")
        else:
            print(f"Client: '{args.client}' not found. Available: {', '.join(list_clients())}")

    # Ahrefs keyword MSV (Priority 1 — keyword targets with MSV)
    keyword_msv_context = ""
    keyword_volumes = {}
    try:
        keyword_volumes, keyword_msv_context = format_keywords_with_msv(
            args.keyword,
            args.secondary,
            country=args.country,
        )
        has_msv = any(v is not None for v in keyword_volumes.values())
        print("Ahrefs: Keyword MSV fetched" if has_msv else "Ahrefs: MSV not available (check AHREFS_API_KEY)")
    except Exception as e:
        print(f"Ahrefs: {e} (MSV will show 'not available' in report)")

    # Ahrefs competitive analysis (SERP overview + domain rating)
    competitor_context = ""
    if not args.no_competitor:
        try:
            target_wc = scrape_result.get("word_count") if scrape_result else None
            _, competitor_context = get_competitive_analysis(
                args.keyword, url, country=args.country,
                secondary_keywords=args.secondary,
                target_word_count=target_wc,
            )
            if competitor_context:
                print("Ahrefs: Competitive analysis data fetched")
            else:
                print("Ahrefs: Competitive analysis not available")
        except Exception as e:
            print(f"Ahrefs competitive analysis: {e} (skipping)")

    # Ahrefs top pages on domain (for inbound internal linking with real URLs)
    domain_pages = []
    if not args.no_competitor:
        try:
            domain = urlparse(url).netloc.replace("www.", "")
            domain_pages = get_top_pages(domain, country=args.country, limit=30)
            if domain_pages:
                print(f"Ahrefs: {len(domain_pages)} top pages fetched for inbound linking")
            else:
                print("Ahrefs: Top pages not available (inbound linking will use scraped data only)")
        except Exception as e:
            print(f"Ahrefs top pages: {e} (skipping)")

    brief = None
    if not args.no_gemini:
        report_result = generate_full_seo_report(
            url=url,
            primary_keyword=args.keyword,
            secondary_keywords=args.secondary,
            notes=args.notes,
            scrape_result=scrape_result,
            gsc_result=result,
            heading_casing=args.casing,
            client_profile=client_profile,
            client_name=args.client,
            keyword_msv_context=keyword_msv_context,
            competitor_context=competitor_context,
            domain_pages=domain_pages,
        )
        if report_result.get("success") and report_result.get("report"):
            brief = report_result["report"]
            print("Gemini: Full analysis and optimization strategy generated")
        elif report_result.get("error"):
            print(f"Gemini: {report_result['error']} (falling back to template)")

    if brief is None:
        brief = build_brief(
            url,
            args.keyword,
            result,
            gemini_result=None,
            property_used=property_url,
            secondary_keywords=args.secondary,
            scrape_result=scrape_result,
            notes=args.notes,
            casing_style=args.casing,
            keyword_volumes=keyword_volumes,
        )

    # Output — both MD and DOCX, named "SEO Report of {website}_<ts>"
    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)

    if args.output:
        base_path = Path(args.output).with_suffix("")
    else:
        website_name = _url_to_website_name(url)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        base_path = out_dir / f"SEO Report of {website_name}_{ts}"

    # Save markdown
    md_path = base_path.with_suffix(".md")
    md_path.write_text(brief, encoding="utf-8")
    print(f"MD saved: {md_path}")

    # Save DOCX
    try:
        from app.docx_generator import generate_docx
        docx_result = generate_docx(brief, str(base_path.with_suffix(".docx")))
        if docx_result["success"]:
            print(f"DOCX saved: {docx_result['path']}")
        else:
            print(f"DOCX generation failed: {docx_result['error']}")
    except ImportError as e:
        print(f"DOCX export failed (missing dependency): {e}")
    except Exception as e:
        print(f"DOCX export failed: {e}")

    print()
    print("GSC section:")
    print(format_gsc_for_brief(result))

    if not result.get("success"):
        print()
        print("GSC setup required: .planning/GSC_SETUP.md")
        print("  - Add service account JSON to credentials/")
        print("  - Add service account email to Search Console property")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
