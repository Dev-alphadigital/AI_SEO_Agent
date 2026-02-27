"""
Google Search Console (GSC) API Client

Pulls performance data (clicks, impressions, avg position, top queries) for SEO briefs.
Required for Priority 1 validation — GSC data must be present when available.

Setup:
1. Create a Google Cloud project and enable Search Console API
2. Create a Service Account, download JSON key
3. Add service account email as user in GSC property (with "Full" access)
4. Set GOOGLE_APPLICATION_CREDENTIALS or path in .env
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Lazy imports to avoid hard dependency at import time
def _get_client():
    """Lazy load Google API client."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        return service_account, build, HttpError
    except ImportError as e:
        raise ImportError(
            "GSC client requires: pip install google-auth google-auth-oauthlib google-api-python-client"
        ) from e


def _load_credentials(credentials_path: Optional[str] = None):
    """Load service account credentials."""
    service_account_module, build_module, HttpError = _get_client()

    path = (
        credentials_path
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or os.environ.get("GSC_CREDENTIALS_PATH")
    )

    if not path or not Path(path).exists():
        return None, "GSC credentials not found. Set GOOGLE_APPLICATION_CREDENTIALS or GSC_CREDENTIALS_PATH to service account JSON path."

    try:
        scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
        credentials = service_account_module.Credentials.from_service_account_file(
            path, scopes=scopes
        )
        return credentials, None
    except Exception as e:
        return None, f"Failed to load GSC credentials: {e}"


def _normalize_url_for_property(url: str) -> str:
    """Convert URL to GSC property format (URL prefix)."""
    url = url.rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    if url.count("/") == 2:  # https://example.com
        url += "/"
    return url


def get_gsc_performance(
    url: str,
    site_property: Optional[str] = None,
    days_back: int = 90,
    credentials_path: Optional[str] = None,
) -> dict:
    """
    Fetch GSC performance data for a URL.

    Returns:
        {
            "success": bool,
            "error": str | None,
            "data": {
                "clicks": int,
                "impressions": int,
                "avg_position": float,
                "ctr": float,
                "top_queries": [{"query": str, "clicks": int, "impressions": int, "position": float}],
                "date_range": {"start": str, "end": str}
            }
        }
    """
    credentials, err = _load_credentials(credentials_path)
    if err:
        return {"success": False, "error": err, "data": None}

    service_account_module, build_module, HttpError = _get_client()

    try:
        service = build_module(
            "searchconsole", "v1", credentials=credentials, cache_discovery=False
        )

        # Determine property: use provided or derive from URL
        property_url = site_property or _normalize_url_for_property(url)

        end_date = datetime.utcnow().date() - timedelta(days=3)  # GSC data lag
        start_date = end_date - timedelta(days=days_back)

        # Query 1: Get page-level data (filtered by URL)
        request_body = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["page"],
            "dimensionFilterGroups": [
                {
                    "filters": [
                        {
                            "dimension": "page",
                            "operator": "contains",
                            "expression": url.split("?")[0].rstrip("/"),
                        }
                    ]
                }
            ],
            "rowLimit": 100,
        }

        response = service.searchanalytics().query(
            siteUrl=property_url, body=request_body
        ).execute()

        rows = response.get("rows", [])
        total_clicks = sum(r.get("clicks", 0) for r in rows)
        total_impressions = sum(r.get("impressions", 0) for r in rows)

        # Calculate weighted average position
        pos_sum = 0
        imp_sum = 0
        for r in rows:
            imp = r.get("impressions", 0)
            pos_sum += r.get("position", 0) * imp
            imp_sum += imp
        avg_position = pos_sum / imp_sum if imp_sum else 0
        ctr = total_clicks / total_impressions if total_impressions else 0

        # Query 2: Top queries for this page
        query_request = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["page", "query"],
            "dimensionFilterGroups": [
                {
                    "filters": [
                        {
                            "dimension": "page",
                            "operator": "contains",
                            "expression": url.split("?")[0].rstrip("/"),
                        }
                    ]
                }
            ],
            "rowLimit": 10,
        }

        query_response = service.searchanalytics().query(
            siteUrl=property_url, body=query_request
        ).execute()

        top_queries = []
        for row in query_response.get("rows", []):
            keys = row.get("keys", [])
            query_text = keys[1] if len(keys) > 1 else keys[0] if keys else ""
            top_queries.append({
                "query": query_text,
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "position": round(row.get("position", 0), 1),
                "ctr": round(row.get("ctr", 0) * 100, 2),
            })

        return {
            "success": True,
            "error": None,
            "data": {
                "clicks": int(total_clicks),
                "impressions": int(total_impressions),
                "avg_position": round(avg_position, 1),
                "ctr": round(ctr * 100, 2),
                "top_queries": top_queries,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
            },
        }

    except HttpError as e:
        err_msg = e.content.decode() if hasattr(e, "content") else str(e)
        if "403" in str(e) or "forbidden" in err_msg.lower():
            return {
                "success": False,
                "error": "GSC access denied. Add service account email to Search Console property with Full access.",
                "data": None,
            }
        if "404" in str(e) or "not found" in err_msg.lower():
            return {
                "success": False,
                "error": f"Property not found: {property_url}. Use URL prefix (e.g. https://example.com/) or domain (sc-domain:example.com).",
                "data": None,
            }
        return {
            "success": False,
            "error": f"GSC API error: {err_msg[:200]}",
            "data": None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None,
        }


def format_gsc_for_brief(gsc_result: dict) -> str:
    """Format GSC result as markdown for SEO brief. Uses 'Current top queries (GSC)' label (Priority 2)."""
    if not gsc_result.get("success") or not gsc_result.get("data"):
        return (
            "**GSC data not available** — " + (gsc_result.get("error") or "Unknown error") + "\n\n"
            "**Current top queries (GSC):** Not available.\n\n"
            "Recommendations based on keyword research only."
        )

    d = gsc_result["data"]
    lines = [
        "### GSC Performance Data (Priority 1)",
        "",
        f"- **Clicks:** {d['clicks']:,}",
        f"- **Impressions:** {d['impressions']:,}",
        f"- **Average Position:** {d['avg_position']}",
        f"- **CTR:** {d['ctr']}%",
        f"- **Date Range:** {d['date_range']['start']} to {d['date_range']['end']}",
        "",
        "**Current top queries (GSC):**",
        "| Query | Clicks | Impressions | Position |",
        "|-------|--------|-------------|----------|",
    ]

    for q in d.get("top_queries", [])[:10]:
        lines.append(f"| {q['query'][:50]} | {q['clicks']} | {q['impressions']} | {q['position']} |")

    return "\n".join(lines)
