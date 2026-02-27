#!/usr/bin/env python3
"""
Check GSC setup and test API connection.

Run: python check_gsc.py [url]

If url not provided, only checks credentials and API access.
"""

import os
import sys
from pathlib import Path

_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sys.path.insert(0, str(Path(__file__).parent))

def main():
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or os.environ.get("GSC_CREDENTIALS_PATH")
    
    print("GSC Setup Check")
    print("=" * 50)
    
    if not creds_path:
        print("[FAIL] GOOGLE_APPLICATION_CREDENTIALS or GSC_CREDENTIALS_PATH not set in .env")
        print("  Add: GOOGLE_APPLICATION_CREDENTIALS=f:\\AI_SEO_Agent\\credentials\\gsc-service-account.json")
        return 1
    
    if not Path(creds_path).exists():
        print(f"[FAIL] Credentials file not found: {creds_path}")
        print("  1. Download service account JSON from Google Cloud Console")
        print("  2. Save as: credentials/gsc-service-account.json")
        print("  3. See .planning/GSC_SETUP.md")
        return 1
    
    print(f"[OK] Credentials file exists: {creds_path}")
    
    # Test API
    from app.gsc_client import get_gsc_performance, format_gsc_for_brief
    
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com/"
    if not url.startswith("http"):
        url = "https://" + url
    
    print(f"\nTesting GSC pull for: {url}")
    result = get_gsc_performance(url)
    
    if result.get("success"):
        print("\n[OK] GSC API working. Performance data:")
        print(format_gsc_for_brief(result))
        return 0
    
    print(f"\n[FAIL] GSC API error: {result.get('error', 'Unknown')}")
    print("\nCommon fixes:")
    print("  - 403: Add service account email to Search Console (Settings > Users)")
    print("  - 404: Use correct property (https://example.com/ or sc-domain:example.com)")
    print("  - Property: Use --property when property differs from URL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
