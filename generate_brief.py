#!/usr/bin/env python3
"""
Generate SEO brief with GSC data (Priority 1).

Fetches GSC performance data and outputs the GSC section for inclusion in briefs.
All Priority 1 requirements — GSC must be run for every brief.

Usage:
  python generate_brief.py <url> <keyword> [--property PROPERTY]

Example:
  python generate_brief.py https://sesky.pk/ "perfume Pakistan"
"""

import argparse
import os
import sys
from pathlib import Path

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


def main():
    parser = argparse.ArgumentParser(description="Generate SEO brief with GSC data (Priority 1)")
    parser.add_argument("url", help="Target URL")
    parser.add_argument("keyword", help="Target keyword")
    parser.add_argument("--property", "-p", help="GSC property (optional)")
    args = parser.parse_args()

    url = args.url.split("?")[0].rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url

    print(f"# SEO Brief — GSC Section (Priority 1)")
    print(f"## Target: {url} | Keyword: {args.keyword}")
    print()

    result = get_gsc_performance(url, site_property=args.property)
    print(format_gsc_for_brief(result))

    if not result.get("success"):
        print()
        print("**Action required:** Configure GSC per .planning/GSC_SETUP.md")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
