"""
Test each Ahrefs API endpoint individually to diagnose issues.
"""
import os
import json
import requests
from datetime import datetime, timedelta
from urllib.parse import urlparse
from pathlib import Path

# Load .env
_env = Path(__file__).resolve().parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

API_KEY = os.environ.get("AHREFS_API_KEY", "")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}

TARGET_URL = "https://inktel.com/florida"
TARGET_DOMAIN = "inktel.com"
KEYWORD = "pizza"  # Changed from "bpo services"
COUNTRY = "us"

recent_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
today = datetime.now().strftime("%Y-%m-%d")


def test_serp_no_select():
    """Test SERP overview WITHOUT select param to see all available fields."""
    print("\n" + "="*60)
    print("TEST A: SERP Overview — NO select (discover all fields)")
    print("="*60)
    resp = requests.get(
        "https://api.ahrefs.com/v3/serp-overview/serp-overview",
        params={
            "keyword": KEYWORD,
            "country": COUNTRY,
            "date": recent_date,
            "output": "json",
        },
        headers=HEADERS,
        timeout=20,
    )
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Top-level keys: {list(data.keys())}")

    positions = data.get("positions", [])
    print(f"Number of results: {len(positions)}")

    if positions:
        print(f"\nALL fields in first result:")
        print(json.dumps(positions[0], indent=2))
        print(f"\nALL fields in second result:")
        if len(positions) > 1:
            print(json.dumps(positions[1], indent=2))

        # Show first 5 results summary
        print(f"\nFirst 5 results:")
        for i, item in enumerate(positions[:5]):
            print(f"  #{i+1}: {json.dumps(item)}")
    return data


def test_serp_with_select():
    """Test SERP overview WITH select param (current code)."""
    print("\n" + "="*60)
    print("TEST B: SERP Overview — WITH select (current code uses this)")
    print("="*60)
    resp = requests.get(
        "https://api.ahrefs.com/v3/serp-overview/serp-overview",
        params={
            "keyword": KEYWORD,
            "country": COUNTRY,
            "output": "json",
            "select": "position,title",
        },
        headers=HEADERS,
        timeout=20,
    )
    print(f"Status: {resp.status_code}")
    data = resp.json()

    positions = data.get("positions", [])
    print(f"Number of results: {len(positions)}")
    if positions:
        print(f"First result: {json.dumps(positions[0], indent=2)}")
        non_null = {k: v for k, v in positions[0].items() if v is not None}
        null_fields = {k: v for k, v in positions[0].items() if v is None}
        print(f"  Non-null fields: {non_null}")
        print(f"  NULL fields: {list(null_fields.keys())}")
        print(f"  All keys: {list(positions[0].keys())}")
        # Check if there are nested objects
        for k, v in positions[0].items():
            if isinstance(v, dict):
                print(f"  {k} is dict with keys: {list(v.keys())}")
            elif isinstance(v, list):
                print(f"  {k} is list with {len(v)} items")
    return data


def test_backlinks_stats():
    """Test backlinks stats endpoint."""
    print("\n" + "="*60)
    print("TEST C: Backlinks Stats")
    print("="*60)
    resp = requests.get(
        "https://api.ahrefs.com/v3/site-explorer/backlinks-stats",
        params={"target": TARGET_DOMAIN, "mode": "domain", "date": recent_date},
        headers=HEADERS,
        timeout=15,
    )
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Full response: {json.dumps(data, indent=2)}")
    return data


def test_backlinks_stats_no_select():
    """Test backlinks stats without date to see what we get."""
    print("\n" + "="*60)
    print("TEST D: Backlinks Stats — different date formats")
    print("="*60)

    # Try with today's date
    resp1 = requests.get(
        "https://api.ahrefs.com/v3/site-explorer/backlinks-stats",
        params={"target": TARGET_DOMAIN, "mode": "domain", "date": today},
        headers=HEADERS,
        timeout=15,
    )
    print(f"With today ({today}): Status {resp1.status_code}")
    print(f"  Response: {json.dumps(resp1.json(), indent=2)}")

    # Try with subdomains mode
    resp2 = requests.get(
        "https://api.ahrefs.com/v3/site-explorer/backlinks-stats",
        params={"target": TARGET_DOMAIN, "mode": "subdomains", "date": recent_date},
        headers=HEADERS,
        timeout=15,
    )
    print(f"\nWith mode=subdomains: Status {resp2.status_code}")
    print(f"  Response: {json.dumps(resp2.json(), indent=2)}")


def test_organic_metrics():
    """Test site-explorer/metrics endpoint (organic traffic + keywords)."""
    print("\n" + "="*60)
    print("TEST E: Organic Metrics (site-explorer/metrics)")
    print("="*60)
    resp = requests.get(
        "https://api.ahrefs.com/v3/site-explorer/metrics",
        params={
            "target": TARGET_DOMAIN, "mode": "domain", "date": recent_date,
            "select": "org_traffic,org_keywords",
        },
        headers=HEADERS,
        timeout=15,
    )
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Full response: {json.dumps(data, indent=2)}")
    return data


def test_organic_competitors():
    """Test organic competitors endpoint."""
    print("\n" + "="*60)
    print("TEST F: Organic Competitors")
    print("="*60)
    resp = requests.get(
        "https://api.ahrefs.com/v3/site-explorer/organic-competitors",
        params={
            "target": TARGET_DOMAIN,
            "country": COUNTRY,
            "mode": "domain",
            "date": today,
            "select": "competitor_domain,keywords_common,keywords_competitor,domain_rating,share,traffic",
            "limit": 10,
            "order_by": "keywords_common:desc",
        },
        headers=HEADERS,
        timeout=20,
    )
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Top-level keys: {list(data.keys())}")
    print(f"Full response (first 2000 chars): {json.dumps(data, indent=2)[:2000]}")
    return data


def test_organic_competitors_no_select():
    """Test organic competitors WITHOUT select to see all fields."""
    print("\n" + "="*60)
    print("TEST F: Organic Competitors — NO select (discover fields)")
    print("="*60)
    resp = requests.get(
        "https://api.ahrefs.com/v3/site-explorer/organic-competitors",
        params={
            "target": TARGET_DOMAIN,
            "country": COUNTRY,
            "mode": "domain",
            "date": today,
            "limit": 5,
            "order_by": "keywords_common:desc",
        },
        headers=HEADERS,
        timeout=20,
    )
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Full response: {json.dumps(data, indent=2)[:3000]}")
    return data


if __name__ == "__main__":
    print(f"API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
    print(f"Target: {TARGET_URL} ({TARGET_DOMAIN})")
    print(f"Keyword: {KEYWORD}")
    print(f"Date (recent): {recent_date}, Date (today): {today}")

    test_serp_no_select()
    test_serp_with_select()
    test_backlinks_stats()
    test_backlinks_stats_no_select()
    test_organic_metrics()
    test_organic_competitors()
    test_organic_competitors_no_select()

    print("\n" + "="*60)
    print("DONE — check which endpoints return data vs errors.")
    print("If backlinks-stats or metrics return non-200, that explains N/A in reports.")
