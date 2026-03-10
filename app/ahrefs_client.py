"""
Ahrefs API client — keyword MSV + competitive analysis for SEO reports.

Uses Ahrefs API v3 (Keywords Explorer, SERP Overview, Site Explorer).
Requires AHREFS_API_KEY in .env.
If the API fails or key is missing, returns empty/placeholder so the brief still generates.
"""

import os
from typing import Optional
from urllib.parse import urlparse

# Try official Ahrefs SDK (Python 3.11+)
try:
    from ahrefs import AhrefsClient
    HAS_AHREFS_SDK = True
except ImportError:
    HAS_AHREFS_SDK = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def get_keyword_volumes(
    keywords: list[str],
    country: str = "us",
) -> dict[str, Optional[int]]:
    """
    Fetch MSV (Monthly Search Volume) for each keyword from Ahrefs.

    Args:
        keywords: List of keyword strings (primary + secondary from form).
        country: Country code for search volume (default: us).

    Returns:
        Dict mapping keyword -> volume (int) or None if not found/failed.
        Empty dict if API unavailable or no keywords.
    """
    if not keywords:
        return {}

    api_key = os.environ.get("AHREFS_API_KEY") or os.environ.get("AHREFS_API_TOKEN")
    if not api_key or not api_key.strip():
        return {k: None for k in keywords}

    # Deduplicate preserving order
    seen = set()
    unique = []
    for k in keywords:
        k = (k or "").strip()
        if k and k.lower() not in seen:
            seen.add(k.lower())
            unique.append(k)

    if not unique:
        return {}

    result: dict[str, Optional[int]] = {k: None for k in unique}

    if HAS_AHREFS_SDK:
        try:
            with AhrefsClient(api_key=api_key) as client:
                # keywords_explorer_overview accepts comma-separated string
                kw_str = ",".join(unique[:10])  # API may limit batch size
                items = client.keywords_explorer_overview(
                    keywords=kw_str,
                    country=country,
                    select="keyword,volume",
                )
                if items is not None:
                    iterable = items if isinstance(items, (list, tuple)) else [items]
                    api_by_lower = {}
                    for item in iterable:
                        kw = getattr(item, "keyword", None) or getattr(item, "query", None)
                        vol = getattr(item, "volume", None)
                        if kw is not None:
                            api_by_lower[str(kw).lower()] = int(vol) if vol is not None else None
                    for user_kw in unique:
                        result[user_kw] = api_by_lower.get(user_kw.lower())
        except Exception:
            pass
        return result

    # Fallback: direct HTTP to Ahrefs API v3 (GET, not POST)
    if HAS_REQUESTS:
        try:
            kw_str = ",".join(unique[:10])
            resp = requests.get(
                "https://api.ahrefs.com/v3/keywords-explorer/overview",
                params={
                    "keywords": kw_str,
                    "country": country,
                    "select": "keyword,volume",
                },
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("keywords", data if isinstance(data, list) else [])
                api_by_lower = {}
                for item in (items if isinstance(items, list) else [items]):
                    kw = item.get("keyword") or item.get("query")
                    vol = item.get("volume")
                    if kw is not None:
                        api_by_lower[str(kw).lower()] = int(vol) if vol is not None else None
                for user_kw in unique:
                    result[user_kw] = api_by_lower.get(user_kw.lower())
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Competitive analysis — Keywords Explorer + Domain Rating
# ---------------------------------------------------------------------------

def _get_api_key() -> Optional[str]:
    """Return Ahrefs API key or None."""
    key = os.environ.get("AHREFS_API_KEY") or os.environ.get("AHREFS_API_TOKEN")
    return key if key and key.strip() else None


def get_keyword_competition(
    keywords: list[str],
    country: str = "us",
) -> dict:
    """
    Fetch keyword competition data from Ahrefs Keywords Explorer.
    Returns difficulty, CPC, traffic potential, global volume per keyword.

    Returns:
        {"success": bool, "error": str|None, "keywords": [
            {"keyword": str, "volume": int, "difficulty": int,
             "cpc": int, "traffic_potential": int, "global_volume": int}
        ]}
    """
    api_key = _get_api_key()
    if not api_key:
        return {"success": False, "error": "AHREFS_API_KEY not set", "keywords": []}

    if not HAS_REQUESTS:
        return {"success": False, "error": "requests library not installed", "keywords": []}

    if not keywords:
        return {"success": True, "error": None, "keywords": []}

    try:
        kw_str = ",".join(k.strip() for k in keywords[:10] if k.strip())
        resp = requests.get(
            "https://api.ahrefs.com/v3/keywords-explorer/overview",
            params={
                "keywords": kw_str,
                "country": country,
                "select": "keyword,volume,difficulty,cpc,traffic_potential,global_volume",
            },
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=20,
        )
        if resp.status_code != 200:
            return {"success": False, "error": f"Ahrefs Keywords API {resp.status_code}: {resp.text[:200]}", "keywords": []}

        data = resp.json()
        raw = data.get("keywords", data if isinstance(data, list) else [])
        result = []
        for item in (raw if isinstance(raw, list) else []):
            result.append({
                "keyword": item.get("keyword", ""),
                "volume": item.get("volume"),
                "difficulty": item.get("difficulty"),
                "cpc": item.get("cpc"),
                "traffic_potential": item.get("traffic_potential"),
                "global_volume": item.get("global_volume"),
            })
        return {"success": True, "error": None, "keywords": result}
    except Exception as e:
        return {"success": False, "error": str(e), "keywords": []}


def get_domain_rating(
    domain: str,
    mode: str = "domain",
) -> dict:
    """
    Fetch Domain Rating (DR) for a domain from Ahrefs Site Explorer.

    Returns:
        {"success": bool, "error": str|None, "domain_rating": float|None, "ahrefs_rank": int|None}
    """
    api_key = _get_api_key()
    if not api_key:
        return {"success": False, "error": "AHREFS_API_KEY not set", "domain_rating": None, "ahrefs_rank": None}

    if not HAS_REQUESTS:
        return {"success": False, "error": "requests library not installed", "domain_rating": None, "ahrefs_rank": None}

    try:
        from datetime import datetime, timedelta
        recent = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

        resp = requests.get(
            "https://api.ahrefs.com/v3/site-explorer/domain-rating",
            params={"target": domain, "mode": mode, "date": recent},
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=20,
        )
        if resp.status_code != 200:
            return {"success": False, "error": f"Ahrefs DR API {resp.status_code}", "domain_rating": None, "ahrefs_rank": None}

        data = resp.json()
        # Response is nested: {"domain_rating": {"domain_rating": 90.0, "ahrefs_rank": 1163}}
        inner = data.get("domain_rating", data)
        return {
            "success": True,
            "error": None,
            "domain_rating": inner.get("domain_rating"),
            "ahrefs_rank": inner.get("ahrefs_rank"),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "domain_rating": None, "ahrefs_rank": None}


def _get_backlinks_stats(domain: str, api_key: str) -> dict:
    """Fetch live backlinks + referring domains for a domain.

    Returns dict with 'backlinks', 'referring_domains', and '_api_exhausted' flag.
    """
    from datetime import datetime, timedelta
    recent = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    try:
        resp = requests.get(
            "https://api.ahrefs.com/v3/site-explorer/backlinks-stats",
            params={"target": domain, "mode": "domain", "date": recent},
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            m = data.get("metrics") if "metrics" in data else data
            # Use 'is not None' checks (not 'or') to preserve valid 0 values
            bl = m.get("live")
            if bl is None:
                bl = m.get("backlinks")
            rd = m.get("live_refdomains")
            if rd is None:
                rd = m.get("refdomains")
            if bl is not None or rd is not None:
                return {"backlinks": int(bl) if bl is not None else 0, "referring_domains": int(rd) if rd is not None else 0}
            print(f"  [backlinks-stats] {domain}: unexpected response keys: {list(m.keys())[:10]}")
            return {"backlinks": None, "referring_domains": None}
        elif resp.status_code == 403:
            print(f"  [backlinks-stats] {domain}: API units exhausted")
            return {"backlinks": None, "referring_domains": None, "_api_exhausted": True}
        else:
            print(f"  [backlinks-stats] {domain}: HTTP {resp.status_code} — {resp.text[:200]}")
    except Exception as e:
        print(f"  [backlinks-stats] {domain}: {e}")
    return {"backlinks": None, "referring_domains": None}


def _get_organic_traffic(domain: str, api_key: str) -> dict:
    """Fetch organic traffic + organic keywords for a domain via site-explorer/metrics.

    Returns dict with 'organic_traffic', 'organic_keywords', and '_api_exhausted' flag.
    """
    from datetime import datetime, timedelta
    recent = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    try:
        resp = requests.get(
            "https://api.ahrefs.com/v3/site-explorer/metrics",
            params={
                "target": domain, "mode": "domain", "date": recent,
                "select": "org_traffic,org_keywords",
            },
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            m = data.get("metrics") if "metrics" in data else data
            # Use 'is not None' checks (not 'or') to preserve valid 0 values
            traffic = m.get("org_traffic")
            if traffic is None:
                traffic = m.get("organic_traffic")
            keywords = m.get("org_keywords")
            if keywords is None:
                keywords = m.get("organic_keywords")
            if traffic is not None or keywords is not None:
                return {
                    "organic_traffic": int(traffic) if traffic is not None else None,
                    "organic_keywords": int(keywords) if keywords is not None else None,
                }
            print(f"  [metrics] {domain}: unexpected response keys: {list(m.keys())[:10]}")
            return {"organic_traffic": None, "organic_keywords": None}
        elif resp.status_code == 403:
            print(f"  [metrics] {domain}: API units exhausted")
            return {"organic_traffic": None, "organic_keywords": None, "_api_exhausted": True}
        else:
            print(f"  [metrics] {domain}: HTTP {resp.status_code} — {resp.text[:200]}")
    except Exception as e:
        print(f"  [metrics] {domain}: {e}")
    return {"organic_traffic": None, "organic_keywords": None}


def get_top_pages(domain: str, country: str = "us", limit: int = 30) -> list:
    """Fetch top organic pages on a domain from Ahrefs site-explorer/top-pages.

    Returns list of dicts with 'url', 'traffic', 'title' for each page.
    Used to provide real domain URLs for inbound internal linking recommendations.
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    from datetime import datetime, timedelta
    recent = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

    try:
        resp = requests.get(
            "https://api.ahrefs.com/v3/site-explorer/top-pages",
            params={
                "target": domain,
                "mode": "domain",
                "date": recent,
                "country": country,
                "limit": limit,
                "select": "raw_url,top_keyword_best_position_title,keywords,top_keyword_volume",
                "order_by": "top_keyword_volume:desc",
            },
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            pages = data.get("pages", data.get("top_pages", []))
            if isinstance(pages, list):
                return [
                    {
                        "url": p.get("raw_url", p.get("url", "")),
                        "traffic": p.get("top_keyword_volume", 0),
                        "title": p.get("top_keyword_best_position_title", ""),
                        "keywords": p.get("keywords", 0),
                    }
                    for p in pages
                    if p.get("raw_url") or p.get("url")
                ]
            return []
        elif resp.status_code == 403:
            print(f"  [top-pages] {domain}: API units exhausted")
            return []
        else:
            print(f"  [top-pages] {domain}: HTTP {resp.status_code} — {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"  [top-pages] {domain}: {e}")
        return []


def _enrich_serp_with_backlinks(serp_results: list, api_key: str, skip_dr: bool = False) -> list:
    """Enrich SERP results with domain-level backlinks, referring domains, DR, and organic traffic.

    The SERP endpoint returns page-level backlinks/refdomains/traffic.
    This function fetches domain-level data which is more useful for competitive analysis.

    Args:
        serp_results: List of SERP result dicts.
        api_key: Ahrefs API key.
        skip_dr: If True, skip the DR API call (use when SERP already provides DR).
    """
    # Collect unique domains
    seen_domains = {}
    for entry in serp_results:
        dom = _extract_root_domain(entry.get("url", ""))
        if dom and dom not in seen_domains:
            # Track whether DR is already available for this domain
            seen_domains[dom] = {"has_dr": entry.get("domain_rating") is not None}

    print(f"Ahrefs: Enriching {len(seen_domains)} domains with backlinks/traffic data...")

    # Fetch domain-level data for each unique domain; stop early if API units exhausted
    api_exhausted = False
    for dom, info in list(seen_domains.items()):
        if api_exhausted:
            # Still need DR for remaining domains (cheaper call), skip expensive enrichment
            domain_data = {"backlinks": None, "referring_domains": None, "organic_traffic": None, "organic_keywords": None}
            if not skip_dr or not info["has_dr"]:
                dr_data = get_domain_rating(dom)
                if dr_data.get("domain_rating") is not None:
                    domain_data["domain_rating"] = dr_data["domain_rating"]
                else:
                    domain_data["domain_rating"] = None
            else:
                domain_data["domain_rating"] = None
            seen_domains[dom] = domain_data
            continue

        bl_stats = _get_backlinks_stats(dom, api_key)
        if bl_stats.get("_api_exhausted"):
            api_exhausted = True
            print(f"Ahrefs: API units exhausted — skipping enrichment for remaining domains")
            domain_data = {"backlinks": None, "referring_domains": None, "organic_traffic": None, "organic_keywords": None}
        else:
            traffic_data = _get_organic_traffic(dom, api_key)
            if traffic_data.get("_api_exhausted"):
                api_exhausted = True
                print(f"Ahrefs: API units exhausted — skipping enrichment for remaining domains")
            domain_data = {
                "backlinks": bl_stats.get("backlinks"),
                "referring_domains": bl_stats.get("referring_domains"),
                "organic_traffic": traffic_data.get("organic_traffic"),
                "organic_keywords": traffic_data.get("organic_keywords"),
            }

        # Only fetch DR if not already present from SERP
        if not skip_dr or not info["has_dr"]:
            dr_data = get_domain_rating(dom)
            domain_data["domain_rating"] = dr_data.get("domain_rating")
        else:
            domain_data["domain_rating"] = None  # Keep existing SERP DR

        seen_domains[dom] = domain_data

    # Log enrichment summary
    enriched = sum(1 for d in seen_domains.values() if isinstance(d, dict) and d.get("backlinks") is not None)
    print(f"Ahrefs: Enrichment complete — {enriched}/{len(seen_domains)} domains have backlink data")

    # Merge domain-level data into each SERP entry
    for entry in serp_results:
        dom = _extract_root_domain(entry.get("url", ""))
        stats = seen_domains.get(dom, {})
        # Override with domain-level backlinks and traffic
        entry["backlinks"] = stats.get("backlinks")
        entry["referring_domains"] = stats.get("referring_domains")
        entry["organic_traffic"] = stats.get("organic_traffic")
        entry["organic_keywords"] = stats.get("organic_keywords")
        # Only override DR if it was fetched and current value is missing
        if stats.get("domain_rating") is not None:
            entry["domain_rating"] = stats["domain_rating"]

    return serp_results


def _fetch_serp_for_keyword(
    keyword: str,
    country: str,
    api_key: str,
    limit: int = 10,
) -> dict:
    """
    Fetch actual Google organic SERP results from Ahrefs.
    Filters to type=organic only (excludes AI Overview, PAA, sitelinks, etc.).
    Requests minimal fields to reduce API unit cost; domain-level enrichment
    (backlinks, refdomains, traffic) is done separately by _enrich_serp_with_backlinks.
    """
    from datetime import datetime, timedelta
    recent_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

    resp = requests.get(
        "https://api.ahrefs.com/v3/serp-overview/serp-overview",
        params={
            "keyword": keyword.strip(),
            "country": country,
            "date": recent_date,
            "output": "json",
            "select": "position,url,title,domain_rating,type",
        },
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=20,
    )
    if resp.status_code != 200:
        return {
            "success": False,
            "error": f"Ahrefs SERP Overview API {resp.status_code}: {resp.text[:300]}",
            "serp_results": [],
            "keyword_used": keyword,
        }

    data = resp.json()
    raw_items = data.get("positions", data.get("serp_overview", data.get("items", [])))
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    # Separate organic results, PAA questions, AI overview, and featured snippets
    results = []
    paa_questions = []
    serp_features = []  # AI overview, featured snippets, etc.
    seen_domains = set()
    for item in raw_items:
        url = item.get("url")
        item_type = item.get("type", [])
        type_list = item_type if isinstance(item_type, list) else [item_type]

        # Extract People Also Ask questions
        if "question" in type_list:
            q_title = (item.get("title") or "").strip()
            if q_title:
                paa_questions.append(q_title)
            continue

        # Capture AI overview and featured snippet data for AEO/GEO analysis
        if "ai_overview" in type_list:
            serp_features.append({
                "type": "ai_overview",
                "title": (item.get("title") or "").strip(),
                "url": url or "",
            })
            continue

        if "featured_snippet" in type_list:
            serp_features.append({
                "type": "featured_snippet",
                "title": (item.get("title") or "").strip(),
                "url": url or "",
            })
            continue

        if not url:
            continue

        # Only include organic results
        if isinstance(item_type, list):
            if "organic" not in item_type:
                continue
        elif item_type != "organic":
            continue

        parsed = urlparse(url)
        domain = (parsed.netloc or "").replace("www.", "")

        # Deduplicate: keep only the first (highest-ranked) entry per domain
        root_domain = _extract_root_domain(url)
        if root_domain in seen_domains:
            continue
        seen_domains.add(root_domain)

        dr = item.get("domain_rating")
        # Use sequential ranking (1, 2, 3...) for organic results instead of
        # raw Ahrefs positions which have gaps from AI Overview/PAA/sitelinks
        results.append({
            "position": len(results) + 1,
            "url": url,
            "title": item.get("title") or "",
            "domain": domain,
            "domain_rating": dr if dr else None,
            # backlinks, referring_domains, organic_traffic filled by enrichment
        })
        if len(results) >= limit:
            break

    return {"success": True, "error": None, "serp_results": results, "paa_questions": paa_questions, "serp_features": serp_features, "keyword_used": keyword}


def _broaden_keyword(keyword: str) -> Optional[str]:
    """
    Strip location modifiers to create a broader keyword for SERP fallback.
    E.g. "bpo services in florida" -> "bpo services"
    """
    import re
    # Strip trailing location phrases: "in <place>", "near <place>", "for <place>"
    broader = re.sub(r'\s+(?:in|near|for|around|at)\s+\S+(?:\s+\S+)?$', '', keyword.strip(), flags=re.IGNORECASE)
    broader = broader.strip()
    return broader if broader and broader.lower() != keyword.strip().lower() else None


def _search_google_serper(keyword: str, country: str = "us", limit: int = 10) -> list:
    """
    Fetch actual Google SERP results via Serper.dev API.
    Requires SERPER_API_KEY in .env (free: 2,500 queries at serper.dev).
    Returns list of dicts with url, title, domain, snippet.
    """
    serper_key = os.environ.get("SERPER_API_KEY")
    if not serper_key or not serper_key.strip():
        return [], []

    if not HAS_REQUESTS:
        return [], []

    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            json={"q": keyword.strip(), "gl": country, "hl": "en", "num": limit},
            headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
            timeout=20,
        )
        if resp.status_code != 200:
            return [], []

        data = resp.json()
        organic = data.get("organic", [])
        serp = []
        for i, item in enumerate(organic[:limit], 1):
            url = item.get("link", "")
            if not url:
                continue
            parsed = urlparse(url)
            domain = (parsed.netloc or "").replace("www.", "")
            serp.append({
                "position": item.get("position", i),
                "url": url,
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "domain": domain,
                "domain_rating": None,
            })

        # Extract People Also Ask from Serper response
        paa_questions = []
        for paa_item in data.get("peopleAlsoAsk", []):
            q = paa_item.get("question", "").strip()
            if q:
                paa_questions.append(q)

        return serp, paa_questions
    except Exception:
        return [], []


def _search_serp_via_ddgs(keyword: str, limit: int = 10) -> list:
    """
    Fallback: Use DuckDuckGo to get search results for the exact keyword.
    Returns list of dicts with url, title, domain (no DR/backlinks — enriched later).
    """
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []

    try:
        results = DDGS().text(keyword, max_results=limit)
        serp = []
        for i, r in enumerate(results or [], 1):
            url = r.get("href", "")
            if not url:
                continue
            parsed = urlparse(url)
            domain = (parsed.netloc or "").replace("www.", "")
            serp.append({
                "position": i,
                "url": url,
                "title": r.get("title", ""),
                "domain": domain,
                "domain_rating": None,
            })
        return serp
    except Exception:
        return []


def get_serp_overview(
    keyword: str,
    country: str = "us",
    limit: int = 10,
) -> dict:
    """
    Fetch SERP overview for a keyword — actual top-ranking pages on Google.

    Strategy (in order):
    1. Serper.dev — live Google SERP results (best, requires SERPER_API_KEY)
    2. Ahrefs SERP Overview — tracked Google SERP data
    3. DuckDuckGo — live search fallback
    4. Ahrefs broadened keyword — last resort

    Returns:
        {"success": bool, "error": str|None, "serp_results": [...],
         "keyword_used": str, "broadened": bool, "source": "google"|"ahrefs"|"ddgs"}
    """
    api_key = _get_api_key()

    if not HAS_REQUESTS:
        return {"success": False, "error": "requests library not installed", "serp_results": [], "keyword_used": keyword, "broadened": False, "source": None}

    if not keyword or not keyword.strip():
        return {"success": True, "error": None, "serp_results": [], "keyword_used": keyword, "broadened": False, "source": None}

    try:
        all_paa = []

        # 1. Serper.dev — actual live Google results (best source)
        google_results, serper_paa = _search_google_serper(keyword, country, limit)
        if serper_paa:
            all_paa.extend(serper_paa)
        if google_results:
            return {
                "success": True,
                "error": None,
                "serp_results": google_results,
                "paa_questions": all_paa,
                "keyword_used": keyword,
                "broadened": False,
                "source": "google",
            }

        # 2. Ahrefs SERP for exact keyword
        if api_key:
            result = _fetch_serp_for_keyword(keyword, country, api_key, limit)
            if result.get("serp_results"):
                result["broadened"] = False
                result["source"] = "ahrefs"
                # Merge any PAA from Ahrefs
                all_paa.extend(result.get("paa_questions", []))
                result["paa_questions"] = all_paa
                return result

        # 3. DuckDuckGo for exact keyword
        ddgs_results = _search_serp_via_ddgs(keyword, limit)
        if ddgs_results:
            return {
                "success": True,
                "error": None,
                "serp_results": ddgs_results,
                "paa_questions": all_paa,
                "keyword_used": keyword,
                "broadened": False,
                "source": "ddgs",
            }

        # 4. Last resort: Ahrefs with broadened keyword
        if api_key:
            broader = _broaden_keyword(keyword)
            if broader:
                result2 = _fetch_serp_for_keyword(broader, country, api_key, limit)
                if result2.get("serp_results"):
                    result2["broadened"] = True
                    result2["original_keyword"] = keyword
                    result2["source"] = "ahrefs"
                    all_paa.extend(result2.get("paa_questions", []))
                    result2["paa_questions"] = all_paa
                    return result2

        # Nothing worked
        return {"success": False, "error": "No SERP data available", "serp_results": [], "paa_questions": all_paa, "keyword_used": keyword, "broadened": False, "source": None}
    except Exception as e:
        return {"success": False, "error": str(e), "serp_results": [], "paa_questions": [], "keyword_used": keyword, "broadened": False, "source": None}


def get_organic_competitors(
    domain: str,
    country: str = "us",
    limit: int = 10,
) -> dict:
    """
    Fetch organic competitors for a domain from Ahrefs Site Explorer.

    Returns domains that share the most organic keywords with the target.

    Returns:
        {"success": bool, "error": str|None, "competitors": [
            {"domain": str, "common_keywords": int, "domain_rating": float,
             "traffic": int, "keyword_overlap_pct": float}
        ]}
    """
    api_key = _get_api_key()
    if not api_key:
        return {"success": False, "error": "AHREFS_API_KEY not set", "competitors": []}

    if not HAS_REQUESTS:
        return {"success": False, "error": "requests library not installed", "competitors": []}

    if not domain or not domain.strip():
        return {"success": True, "error": None, "competitors": []}

    try:
        from datetime import datetime, timedelta
        recent = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

        resp = requests.get(
            "https://api.ahrefs.com/v3/site-explorer/organic-competitors",
            params={
                "target": domain.strip(),
                "country": country,
                "mode": "domain",
                "date": recent,
                "select": "competitor_domain,keywords_common,keywords_competitor,domain_rating,share,traffic",
                "limit": limit,
                "order_by": "keywords_common:desc",
            },
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=20,
        )
        if resp.status_code != 200:
            return {
                "success": False,
                "error": f"Ahrefs Organic Competitors API {resp.status_code}: {resp.text[:300]}",
                "competitors": [],
            }

        data = resp.json()
        raw = data.get("competitors", [])
        results = []
        for item in (raw if isinstance(raw, list) else []):
            results.append({
                "domain": item.get("competitor_domain", ""),
                "common_keywords": item.get("keywords_common"),
                "domain_rating": item.get("domain_rating"),
                "traffic": item.get("traffic"),
                "keyword_overlap_pct": item.get("share"),
            })
        return {"success": True, "error": None, "competitors": results}
    except Exception as e:
        return {"success": False, "error": str(e), "competitors": []}


def _format_competitive_context(data: dict) -> str:
    """Format competitive analysis data as markdown context for Gemini."""
    kw_data = data.get("keyword_competition", [])
    serp_competitors = data.get("serp_competitors", [])
    target_dr = data.get("target_dr")
    target_domain = data.get("target_domain", "")
    target_url = data.get("target_url", "")
    target_word_count = data.get("target_word_count")

    if not kw_data and target_dr is None and not serp_competitors:
        return "**Competitive Analysis Data (Ahrefs):** Not available for this keyword. Analysis should be based on scraped page content only."

    lines = ["**Competitive Analysis Data (from Ahrefs):**"]

    # Target domain DR
    if target_dr is not None:
        lines.append(f"- **Target domain:** {target_domain} | DR: {target_dr} | Ahrefs Rank: {data.get('target_ahrefs_rank', 'N/A')}")
    else:
        lines.append(f"- **Target domain:** {target_domain} | DR: (not available)")

    # --- SERP Competitors ---
    serp_keyword_used = data.get("keyword_used", data.get("keyword", ""))
    is_broadened = data.get("serp_broadened", False)

    if serp_competitors:
        lines.append("")
        serp_source = data.get("serp_source", "ahrefs")
        if is_broadened:
            lines.append(f"**IMPORTANT: Ahrefs has no SERP data for the exact keyword \"{data.get('keyword', '')}\". The SERP data below is for the broader keyword \"{serp_keyword_used}\" and may not perfectly reflect the local/specific competitive landscape. Adjust your analysis accordingly.**")
            lines.append("")
        if serp_source == "google":
            lines.append(f"**SERP Competitors — Top {len(serp_competitors)} Google results for \"{serp_keyword_used}\" (live Google SERP, enriched with Ahrefs data):**")
        elif serp_source == "ddgs":
            lines.append(f"**SERP Competitors — Top {len(serp_competitors)} search results for \"{serp_keyword_used}\" (DuckDuckGo, enriched with Ahrefs data):**")
        else:
            lines.append(f"**SERP Competitors — Top {len(serp_competitors)} pages ranking for \"{serp_keyword_used}\" (Ahrefs SERP tracking):**")
        lines.append("")
        lines.append("| Pos | Title | URL | DR | Backlinks | Ref Domains | Organic Traffic | Word Count |")
        lines.append("|----:|-------|-----|---:|----------:|------------:|----------------:|-----------:|")

        target_root = _extract_root_domain(target_url) if target_url else ""
        target_in_serp = False

        for comp in serp_competitors:
            pos = comp.get("position", "?")
            title = comp.get("title", "")[:65]
            dr = comp.get("domain_rating")
            dr_str = f"{dr:.1f}" if dr is not None else "—"
            url = comp.get("url", "")

            # Mark target domain if it appears in SERP
            marker = ""
            comp_root = _extract_root_domain(url) if url else ""
            if target_root and comp_root == target_root:
                marker = " **(YOU)**"
                target_in_serp = True

            backlinks = comp.get("backlinks")
            backlinks_str = f"{backlinks:,}" if backlinks is not None else "—"
            ref_domains = comp.get("referring_domains")
            ref_domains_str = f"{ref_domains:,}" if ref_domains is not None else "—"
            # Treat 0 traffic + 0 keywords as "not available" (Ahrefs plan limitation)
            traffic = comp.get("organic_traffic")
            org_kw = comp.get("organic_keywords")
            if traffic is not None and (traffic > 0 or (org_kw is not None and org_kw > 0)):
                traffic_str = f"{traffic:,}"
            else:
                traffic_str = "—"

            wc = comp.get("word_count")
            wc_str = f"{wc:,}" if wc is not None else "—"

            lines.append(f"| {pos} | {title} | {url}{marker} | {dr_str} | {backlinks_str} | {ref_domains_str} | {traffic_str} | {wc_str} |")

        # Competitive gap summary
        lines.append("")
        if not target_in_serp:
            lines.append(f"- **Target domain ({target_domain}) is NOT currently in the top {len(serp_competitors)} for this keyword.**")
        else:
            lines.append(f"- **Target domain ({target_domain}) IS ranking in the top {len(serp_competitors)} for this keyword.**")

        # DR comparison
        competitor_drs = [c["domain_rating"] for c in serp_competitors if c.get("domain_rating") is not None]
        if competitor_drs:
            avg_dr = sum(competitor_drs) / len(competitor_drs)
            min_dr = min(competitor_drs)
            max_dr = max(competitor_drs)
            lines.append(f"- **SERP DR range:** {min_dr:.0f} – {max_dr:.0f} (avg: {avg_dr:.0f})")
            if target_dr is not None:
                dr_gap = avg_dr - target_dr
                if dr_gap > 0:
                    lines.append(f"- **DR gap:** Your DR ({target_dr:.0f}) is {dr_gap:.0f} points below the SERP average ({avg_dr:.0f}). You need stronger domain authority to compete.")
                else:
                    lines.append(f"- **DR advantage:** Your DR ({target_dr:.0f}) is {abs(dr_gap):.0f} points above the SERP average ({avg_dr:.0f}).")

        # Top 3 strongest competitors
        sorted_by_dr = sorted(
            [c for c in serp_competitors if c.get("domain_rating") is not None],
            key=lambda x: x["domain_rating"], reverse=True,
        )[:3]
        if sorted_by_dr:
            lines.append("")
            lines.append("**Top 3 strongest competitors (by DR):**")
            for c in sorted_by_dr:
                lines.append(
                    f"- #{c.get('position','?')} {c['domain']} (DR {c['domain_rating']:.0f})"
                )

        # Weakest competitor = realistic target
        sorted_by_dr_asc = sorted(
            [c for c in serp_competitors if c.get("domain_rating") is not None],
            key=lambda x: x["domain_rating"],
        )[:3]
        if sorted_by_dr_asc:
            lines.append("")
            lines.append("**Weakest competitors in SERP (realistic targets to outrank):**")
            for c in sorted_by_dr_asc:
                lines.append(
                    f"- #{c.get('position','?')} {c['domain']} (DR {c['domain_rating']:.0f})"
                )

        # Word count comparison
        comp_word_counts = [c["word_count"] for c in serp_competitors if c.get("word_count")]
        if comp_word_counts:
            avg_wc = int(sum(comp_word_counts) / len(comp_word_counts))
            min_wc = min(comp_word_counts)
            max_wc = max(comp_word_counts)
            lines.append("")
            lines.append("**Content Length Comparison (Word Count):**")
            if target_word_count is not None:
                lines.append(f"- **Your page:** {target_word_count:,} words")
            lines.append(f"- **SERP average:** {avg_wc:,} words (range: {min_wc:,} – {max_wc:,})")
            if target_word_count is not None:
                wc_gap = avg_wc - target_word_count
                if wc_gap > 0:
                    lines.append(f"- **Content gap:** Your page is {wc_gap:,} words shorter than the SERP average. Consider expanding content to be more competitive.")
                else:
                    lines.append(f"- **Content advantage:** Your page is {abs(wc_gap):,} words longer than the SERP average.")
            # Show top 3 longest competitor pages
            sorted_by_wc = sorted(
                [c for c in serp_competitors if c.get("word_count")],
                key=lambda x: x["word_count"], reverse=True,
            )[:3]
            if sorted_by_wc:
                lines.append("- **Longest competitor pages:**")
                for c in sorted_by_wc:
                    lines.append(f"  - #{c.get('position','?')} {c['domain']}: {c['word_count']:,} words")

        # --- Competitor Heading Gap Analysis ---
        all_comp_headings = []
        for comp in serp_competitors:
            for h in comp.get("competitor_headings", []):
                all_comp_headings.append(h)
        if all_comp_headings:
            lines.append("")
            lines.append("**Competitor Headings (for gap analysis — compare against target page headings):**")
            # Deduplicate by normalized text, keep heading level
            seen_normalized = set()
            unique_headings = []
            for h in all_comp_headings:
                norm = h.lower().strip()
                if norm not in seen_normalized:
                    seen_normalized.add(norm)
                    unique_headings.append(h)
            for h in unique_headings[:60]:
                lines.append(f"- {h}")

        # --- Rich Content on Competitor Pages ---
        comp_rich = {}
        for comp in serp_competitors:
            rc = comp.get("rich_content", {})
            for key, count in rc.items():
                if count and count > 0:
                    comp_rich[key] = comp_rich.get(key, 0) + 1  # Number of competitors with this element
        if comp_rich:
            lines.append("")
            lines.append("**Rich Content Found on Competitor Pages:**")
            labels = {"tables": "Tables", "figures": "Figures", "images": "Images",
                      "iframes": "Embedded content (iframes)", "canvas": "Canvas charts",
                      "svg": "SVG graphics", "videos": "Videos"}
            for key, num_comps in sorted(comp_rich.items(), key=lambda x: x[1], reverse=True):
                label = labels.get(key, key)
                lines.append(f"- **{label}:** found on {num_comps}/{len(serp_competitors)} competitor pages")

        # --- People Also Ask ---
        paa_questions = data.get("paa_questions", [])
        if paa_questions:
            lines.append("")
            lines.append("**People Also Ask (from SERP):**")
            for q in paa_questions[:10]:
                lines.append(f"- {q}")

        # --- SERP Features (AI Overview, Featured Snippets) — for AEO/GEO analysis ---
        serp_features = data.get("serp_features", [])
        if serp_features:
            lines.append("")
            lines.append("**SERP Features Detected (real data for AEO/GEO analysis):**")
            for feat in serp_features:
                feat_type = feat.get("type", "unknown").replace("_", " ").title()
                feat_title = feat.get("title", "")
                feat_url = feat.get("url", "")
                if feat_title and feat_url:
                    lines.append(f"- **{feat_type}:** \"{feat_title}\" (source: {feat_url})")
                elif feat_title:
                    lines.append(f"- **{feat_type}:** \"{feat_title}\"")
                else:
                    lines.append(f"- **{feat_type}** detected for this keyword")

    elif data.get("serp_success") is False:
        lines.append("")
        lines.append("**SERP Competitors:** Data not available for this keyword. Base competitive analysis on scraped page content only.")
    else:
        # SERP succeeded but returned empty — explicitly tell Gemini
        lines.append("")
        lines.append(f"**SERP Competitors:** Ahrefs has no SERP tracking data for \"{data.get('keyword', '')}\" (keyword too niche or low-volume). No SERP competitor data is available — DO NOT fabricate or invent competitor data. Only use data provided here.")

    # --- Organic Competitors (Site Explorer) ---
    organic_competitors = data.get("organic_competitors", [])
    if organic_competitors:
        lines.append("")
        lines.append(f"**Organic Competitors (domains sharing keywords with {target_domain}):**")
        lines.append("")
        lines.append("| Domain | Common Keywords | DR | Traffic | Keyword Overlap % |")
        lines.append("|--------|----------------:|---:|--------:|------------------:|")
        for oc in organic_competitors:
            dom = oc.get("domain", "?")
            ck = f"{oc['common_keywords']:,}" if oc.get("common_keywords") is not None else "—"
            dr = f"{oc['domain_rating']:.0f}" if oc.get("domain_rating") is not None else "—"
            tr = f"{oc['traffic']:,}" if oc.get("traffic") is not None else "—"
            ov = f"{oc['keyword_overlap_pct']:.1f}%" if oc.get("keyword_overlap_pct") is not None else "—"
            lines.append(f"| {dom} | {ck} | {dr} | {tr} | {ov} |")

        # DR comparison against organic competitors
        oc_drs = [c["domain_rating"] for c in organic_competitors if c.get("domain_rating") is not None]
        if oc_drs and target_dr is not None:
            avg_oc_dr = sum(oc_drs) / len(oc_drs)
            lines.append("")
            lines.append(f"- **Avg organic competitor DR:** {avg_oc_dr:.0f}")
            dr_gap = avg_oc_dr - target_dr
            if dr_gap > 0:
                lines.append(f"- **DR gap vs organic competitors:** Your DR ({target_dr:.0f}) is {dr_gap:.0f} points below the average ({avg_oc_dr:.0f}).")
            else:
                lines.append(f"- **DR advantage vs organic competitors:** Your DR ({target_dr:.0f}) is {abs(dr_gap):.0f} points above the average ({avg_oc_dr:.0f}).")
    elif not serp_competitors and data.get("organic_competitors_success") is not False:
        # Neither SERP nor organic competitors available
        lines.append("")
        lines.append("**Organic Competitors:** No organic competitor data available from Ahrefs for this domain.")

    # SERP broadening reminder (also shown at top of SERP section)
    if data.get("serp_broadened") and serp_competitors:
        lines.append("")
        lines.append(f"**REMINDER:** SERP competitors above are for the broader keyword \"{data.get('keyword_used', '')}\" — NOT for \"{data.get('original_keyword', '')}\". The actual competitors for the location-specific keyword may differ. Clearly state this in the report.")

    # Keyword competition table (existing)
    if kw_data:
        lines.append("")
        lines.append("**Keyword competitive landscape:**")
        lines.append("")
        lines.append("| Keyword | Search Volume | Difficulty | CPC (cents) | Traffic Potential | Global Volume |")
        lines.append("|---------|---------------|------------|-------------|-------------------|---------------|")
        for kw in kw_data:
            name = kw.get("keyword", "?")
            vol = kw.get("volume")
            vol_str = f"{vol:,}" if vol is not None else "—"
            # For very low-volume keywords, Ahrefs often lacks difficulty/CPC/TP data
            is_low_vol = vol is not None and vol <= 50
            na_label = "n/a (low vol)" if is_low_vol else "—"
            diff = kw.get("difficulty")
            diff_str = f"{diff}/100" if diff is not None else na_label
            cpc = f"${kw['cpc'] / 100:.2f}" if kw.get("cpc") is not None else na_label
            tp = f"{kw['traffic_potential']:,}" if kw.get("traffic_potential") is not None else na_label
            gv = f"{kw['global_volume']:,}" if kw.get("global_volume") is not None else "—"
            lines.append(f"| {name} | {vol_str} | {diff_str} | {cpc} | {tp} | {gv} |")

        # Difficulty summary
        diffs = [kw["difficulty"] for kw in kw_data if kw.get("difficulty") is not None]
        if diffs:
            avg_diff = sum(diffs) / len(diffs)
            easy = [kw["keyword"] for kw in kw_data if kw.get("difficulty") is not None and kw["difficulty"] <= 30]
            hard = [kw["keyword"] for kw in kw_data if kw.get("difficulty") is not None and kw["difficulty"] >= 70]
            lines.append("")
            lines.append(f"- **Avg keyword difficulty:** {avg_diff:.0f}/100")
            if easy:
                lines.append(f"- **Low-competition keywords (KD <= 30):** {', '.join(easy)}")
            if hard:
                lines.append(f"- **High-competition keywords (KD >= 70):** {', '.join(hard)}")

        # Traffic potential summary
        tp_vals = [kw["traffic_potential"] for kw in kw_data if kw.get("traffic_potential") is not None]
        if tp_vals:
            total_tp = sum(tp_vals)
            lines.append(f"- **Total traffic potential (all keywords):** {total_tp:,}")

    return "\n".join(lines)


def _scrape_competitor_content(url: str, timeout: int = 15) -> dict:
    """Scrape competitor page for word count, headings, and rich content detection."""
    try:
        from app.page_scraper import scrape_page
        result = scrape_page(url, timeout=timeout)
        if result.get("success"):
            return {
                "word_count": result.get("word_count", 0) or None,
                "headings": result.get("headings", []),
                "rich_content": result.get("rich_content", {}),
            }
    except Exception:
        pass
    return {"word_count": None, "headings": [], "rich_content": {}}


def _enrich_serp_with_content(serp_results: list) -> list:
    """Enrich SERP results with word counts, headings, and rich content from each competitor."""
    for entry in serp_results:
        url = entry.get("url", "")
        if url:
            data = _scrape_competitor_content(url)
            entry["word_count"] = data["word_count"]
            entry["competitor_headings"] = data["headings"]
            entry["rich_content"] = data["rich_content"]
        else:
            entry["word_count"] = None
            entry["competitor_headings"] = []
            entry["rich_content"] = {}
    return serp_results


def _extract_root_domain(url: str) -> str:
    """Extract root domain from URL (e.g., about.nike.com -> nike.com)."""
    parsed = urlparse(url)
    host = (parsed.netloc or "").replace("www.", "")
    parts = host.split(".")
    # Handle common TLDs: foo.co.uk -> foo.co.uk, about.nike.com -> nike.com
    if len(parts) > 2 and parts[-2] in ("co", "com", "org", "net", "gov", "edu"):
        return ".".join(parts[-3:])
    if len(parts) > 2:
        return ".".join(parts[-2:])
    return host


def get_competitive_analysis(
    keyword: str,
    target_url: str,
    country: str = "us",
    secondary_keywords: Optional[str] = None,
    limit: int = 10,
    target_word_count: Optional[int] = None,
) -> tuple[dict, str]:
    """
    Orchestrate competitive analysis:
    1. SERP Overview — fetch top ranking pages for the keyword (with broadened fallback)
    2. Domain Rating — your domain's DR
    3. Keyword competition — difficulty, CPC, traffic potential
    4. Organic competitors — domains sharing keywords (fallback if SERP empty)

    Returns:
        (raw_data_dict, formatted_context_string)
        On failure returns ({}, "") so the brief still generates.
    """
    domain = _extract_root_domain(target_url)
    if not domain:
        return {}, ""

    # Build keyword list from primary + secondary
    all_kw = [keyword]
    if secondary_keywords:
        all_kw.extend(k.strip() for k in secondary_keywords.split(",") if k.strip())

    # Fetch all data sources
    dr_result = get_domain_rating(domain)
    kw_result = get_keyword_competition(all_kw, country=country)
    serp_result = get_serp_overview(keyword, country=country, limit=limit)

    # Enrich SERP results with domain-level backlinks, referring domains, and traffic.
    # When source is Ahrefs, DR is already present from the SERP endpoint — skip redundant DR calls.
    api_key = _get_api_key()
    if serp_result.get("serp_results") and api_key:
        skip_dr = serp_result.get("source") == "ahrefs"
        serp_result["serp_results"] = _enrich_serp_with_backlinks(
            serp_result["serp_results"], api_key, skip_dr=skip_dr
        )

    # Enrich SERP results with word counts, headings, and rich content from competitor pages
    if serp_result.get("serp_results"):
        serp_result["serp_results"] = _enrich_serp_with_content(
            serp_result["serp_results"]
        )

    # If SERP is empty, also fetch organic competitors as fallback
    organic_result = {"success": False, "competitors": []}
    if not serp_result.get("serp_results"):
        organic_result = get_organic_competitors(domain, country=country, limit=limit)

    raw_data = {
        "target_domain": domain,
        "target_url": target_url,
        "target_dr": dr_result.get("domain_rating"),
        "target_ahrefs_rank": dr_result.get("ahrefs_rank"),
        "keyword_competition": kw_result.get("keywords", []),
        "serp_competitors": serp_result.get("serp_results", []),
        "serp_success": serp_result.get("success", False),
        "serp_broadened": serp_result.get("broadened", False),
        "serp_source": serp_result.get("source", "ahrefs"),
        "keyword_used": serp_result.get("keyword_used", keyword),
        "original_keyword": serp_result.get("original_keyword", keyword),
        "paa_questions": serp_result.get("paa_questions", []),
        "serp_features": serp_result.get("serp_features", []),
        "organic_competitors": organic_result.get("competitors", []),
        "organic_competitors_success": organic_result.get("success", False),
        "keyword": keyword,
        "country": country,
        "target_word_count": target_word_count,
    }

    context = _format_competitive_context(raw_data)
    return raw_data, context


def format_keywords_with_msv(
    primary_keyword: str,
    secondary_keywords: Optional[str] = None,
    country: str = "us",
) -> tuple[dict[str, Optional[int]], str]:
    """
    Fetch MSV for primary + secondary keywords and build a context string for Gemini.

    Returns:
        (keyword_volume_map, context_string)
        context_string is ready to append to report context.
    """
    all_kw = [primary_keyword]
    if secondary_keywords:
        all_kw.extend(k.strip() for k in secondary_keywords.split(",") if k.strip())

    volumes = get_keyword_volumes(all_kw, country=country)
    lines = ["**Keyword targets (with MSV from Ahrefs):**"]
    for kw in all_kw:
        vol = volumes.get(kw)
        if vol is not None:
            lines.append(f"- {kw}: {vol:,} MSV")
        else:
            lines.append(f"- {kw}: (MSV not available)")
    return volumes, "\n".join(lines)
