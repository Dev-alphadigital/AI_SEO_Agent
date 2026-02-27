#!/usr/bin/env python3
"""
Fetch GSC performance data for a URL.

Usage:
  python fetch_gsc.py <url> [--property PROPERTY] [--days 90]

Example:
  python fetch_gsc.py https://sesky.pk/
  python fetch_gsc.py https://sesky.pk/ --property https://sesky.pk/ --days 90
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Load .env if present
_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.gsc_client import get_gsc_performance, format_gsc_for_brief


def main():
    parser = argparse.ArgumentParser(description="Fetch GSC performance data for SEO brief")
    parser.add_argument("url", help="Target URL (e.g. https://sesky.pk/)")
    parser.add_argument("--property", "-p", help="GSC property URL (optional, derived from url if not set)")
    parser.add_argument("--days", "-d", type=int, default=90, help="Days of data (default: 90)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--credentials", "-c", help="Path to service account JSON (overrides env)")
    args = parser.parse_args()

    result = get_gsc_performance(
        url=args.url,
        site_property=args.property,
        days_back=args.days,
        credentials_path=args.credentials,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if result.get("success") else 1

    print(format_gsc_for_brief(result))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
