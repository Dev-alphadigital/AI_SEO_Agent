"""
AI SEO Agent — FastAPI Backend

Exposes webhook endpoints for n8n workflows to trigger SEO tasks:
- /webhooks/generate-brief  — Full SEO brief (scrape + GSC + Ahrefs + Gemini)
- /webhooks/scrape          — Scrape a URL for metadata
- /webhooks/gsc-performance — Fetch GSC performance data
- /webhooks/keyword-volumes — Fetch keyword volumes from Ahrefs
- /health                   — Health check
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import traceback

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Load .env from project root
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from app.gsc_client import get_gsc_performance, format_gsc_for_brief
from app.gemini_client import generate_full_seo_report
from app.page_scraper import scrape_page
from app.ahrefs_client import format_keywords_with_msv, get_competitive_analysis
from app.client_profiles import get_client_profile, list_clients

app = FastAPI(
    title="AI SEO Agent",
    description="Webhook endpoints for n8n SEO workflows",
    version="0.1.0",
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class BriefRequest(BaseModel):
    url: str
    keyword: str
    secondary_keywords: Optional[str] = None
    notes: Optional[str] = None
    heading_casing: Optional[str] = None
    client_name: Optional[str] = None
    country: Optional[str] = "us"
    gsc_property: Optional[str] = None
    days_back: Optional[int] = 90
    skip_gemini: Optional[bool] = False
    skip_scrape: Optional[bool] = False
    skip_competitor: Optional[bool] = False
    force_playwright: Optional[bool] = False


class ScrapeRequest(BaseModel):
    url: str
    force_playwright: Optional[bool] = False
    timeout: Optional[int] = 20


class GSCRequest(BaseModel):
    url: str
    site_property: Optional[str] = None
    days_back: Optional[int] = 90


class KeywordRequest(BaseModel):
    keywords: list[str]
    country: Optional[str] = "us"


class CompetitorRequest(BaseModel):
    keyword: str
    target_url: str
    country: Optional[str] = "us"
    limit: Optional[int] = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Strip zero-width spaces and other invisible Unicode from user input."""
    if not text:
        return text
    import unicodedata
    return "".join(
        ch for ch in text
        if unicodedata.category(ch) not in ("Cf", "Cc") or ch in ("\n", "\r", "\t")
    ).strip()


def _safe_header(value: str) -> str:
    """Make a string safe for HTTP headers (Latin-1 only)."""
    return value.encode("latin-1", errors="ignore").decode("latin-1")


def _normalize_url(url: str) -> str:
    url = url.strip()  # Remove leading/trailing whitespace
    url = url.split("?")[0].rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url


def _url_to_slug(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "").replace(".", "_")
    path = parsed.path.strip("/").replace("/", "_") or "home"
    return f"{domain}_{path}"[:50]


def _url_to_website_name(url: str) -> str:
    """Extract clean website domain from URL (e.g. 'inktel.com')."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split("/")[0]
    domain = domain.replace("www.", "")
    return domain


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "service": "AI SEO Agent",
        "docs": "/docs",
        "health": "/health",
        "webhooks": [
            "/webhooks/generate-brief",
            "/webhooks/scrape",
            "/webhooks/gsc-performance",
            "/webhooks/keyword-volumes",
            "/webhooks/competitive-analysis",
        ],
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ai-seo-agent",
        "gsc_configured": bool(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            or os.environ.get("GSC_CREDENTIALS_PATH")
        ),
        "gemini_configured": bool(os.environ.get("GEMINI_API_KEY")),
        "ahrefs_configured": bool(os.environ.get("AHREFS_API_KEY")),
        "clients_available": list_clients(),
    }


@app.post("/webhooks/scrape")
async def webhook_scrape(req: ScrapeRequest):
    """Scrape a URL and return metadata, headings, issues."""
    url = _normalize_url(req.url)
    result = scrape_page(url, timeout=req.timeout, force_playwright=req.force_playwright)
    return result


@app.post("/webhooks/gsc-performance")
async def webhook_gsc(req: GSCRequest):
    """Fetch Google Search Console performance data for a URL."""
    url = _normalize_url(req.url)
    result = get_gsc_performance(
        url,
        site_property=req.site_property,
        days_back=req.days_back,
    )
    return result


@app.post("/webhooks/keyword-volumes")
async def webhook_keywords(req: KeywordRequest):
    """Fetch keyword search volumes from Ahrefs."""
    from app.ahrefs_client import get_keyword_volumes
    volumes = get_keyword_volumes(req.keywords, country=req.country)
    return {"keywords": volumes}


@app.post("/webhooks/competitive-analysis")
async def webhook_competitor_analysis(req: CompetitorRequest):
    """Fetch competitive analysis data (SERP overview + domain rating) from Ahrefs."""
    url = _normalize_url(req.target_url)
    try:
        data, context = get_competitive_analysis(
            req.keyword, url, country=req.country, limit=req.limit
        )
        return {"success": bool(context), "data": data, "context": context}
    except Exception as e:
        return {"success": False, "error": str(e), "data": {}, "context": ""}


@app.post("/webhooks/generate-brief")
async def webhook_generate_brief(req: BriefRequest):
    """
    Full SEO brief generation pipeline.

    Steps: scrape page → GSC data → Ahrefs MSV → Gemini report → save to output/
    Returns the report markdown and file path.
    """
    try:
        url = _normalize_url(req.url)
        req.keyword = _clean_text(req.keyword).strip()
        if req.secondary_keywords:
            req.secondary_keywords = _clean_text(req.secondary_keywords).strip()
        if req.notes:
            req.notes = _clean_text(req.notes).strip()
        if req.client_name:
            req.client_name = req.client_name.strip()

        # 1. Scrape
        scrape_result = None
        if not req.skip_scrape:
            try:
                scrape_result = scrape_page(url, force_playwright=req.force_playwright)
            except Exception:
                scrape_result = {"success": False, "error": "Scraper unavailable"}

        # 2. GSC performance (graceful if google libs missing)
        try:
            gsc_result = get_gsc_performance(
                url,
                site_property=req.gsc_property,
                days_back=req.days_back,
            )
        except ImportError:
            gsc_result = {"success": False, "error": "GSC dependencies not installed", "data": None}
        except Exception as e:
            gsc_result = {"success": False, "error": str(e), "data": None}

        # 3. Client profile
        client_profile = None
        if req.client_name:
            client_profile = get_client_profile(req.client_name)

        # 4. Ahrefs keyword volumes
        keyword_msv_context = ""
        keyword_volumes = {}
        try:
            keyword_volumes, keyword_msv_context = format_keywords_with_msv(
                req.keyword,
                req.secondary_keywords,
                country=req.country,
            )
        except Exception:
            pass

        # 5. Ahrefs competitive analysis
        competitor_context = ""
        if not req.skip_competitor:
            try:
                target_wc = scrape_result.get("word_count") if scrape_result else None
                _, competitor_context = get_competitive_analysis(
                    req.keyword, url, country=req.country,
                    secondary_keywords=req.secondary_keywords,
                    target_word_count=target_wc,
                )
            except Exception:
                pass

        # 6. Generate report via Gemini (or template fallback)
        report = None
        gemini_used = False
        if not req.skip_gemini:
            try:
                gemini_result = generate_full_seo_report(
                    url=url,
                    primary_keyword=req.keyword,
                    secondary_keywords=req.secondary_keywords,
                    notes=req.notes,
                    scrape_result=scrape_result,
                    gsc_result=gsc_result,
                    heading_casing=req.heading_casing,
                    client_profile=client_profile,
                    client_name=req.client_name,
                    keyword_msv_context=keyword_msv_context,
                    competitor_context=competitor_context,
                )
                if gemini_result.get("success") and gemini_result.get("report"):
                    report = gemini_result["report"]
                    gemini_used = True
            except Exception:
                pass

        # 6. Template fallback if Gemini unavailable
        if report is None:
            from create_brief import build_brief, _derive_gsc_property
            report = build_brief(
                url,
                req.keyword,
                gsc_result,
                gemini_result=None,
                property_used=req.gsc_property or _derive_gsc_property(url),
                secondary_keywords=req.secondary_keywords,
                scrape_result=scrape_result,
                notes=req.notes,
                casing_style=req.heading_casing,
                keyword_volumes=keyword_volumes,
            )

        # 7. Save MD + DOCX report
        website_name = _url_to_website_name(url)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        base_name = f"SEO Report of {website_name}_{ts}"

        md_path = OUTPUT_DIR / f"{base_name}.md"
        md_path.write_text(report, encoding="utf-8")

        docx_path = str(OUTPUT_DIR / f"{base_name}.docx")
        try:
            from app.docx_generator import generate_docx
            docx_result = generate_docx(report, docx_path)
            if not docx_result["success"]:
                raise Exception(docx_result.get("error", "DOCX generation failed"))
        except Exception as docx_err:
            return {
                "success": False,
                "error": f"DOCX generation failed: {docx_err}",
                "file": str(md_path),
                "report": report,
            }

        return FileResponse(
            path=docx_path,
            filename=f"{base_name}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "X-SEO-URL": _safe_header(url),
                "X-SEO-Keyword": _safe_header(req.keyword),
                "X-SEO-GSC-Available": str(gsc_result.get("success", False)),
                "X-SEO-Gemini-Used": str(gemini_used),
                "X-SEO-MD-File": _safe_header(str(md_path)),
            },
        )

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "detail": traceback.format_exc(),
        }
