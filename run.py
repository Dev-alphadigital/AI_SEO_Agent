#!/usr/bin/env python3
"""
AI SEO Agent — Project Entry Point

This project runs as an AI agent in Cursor. Use Cursor chat to trigger SEO workflows.
This script validates your setup and confirms the agent is ready.
"""

import os
from pathlib import Path

def load_env():
    """Load .env file if present."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

def main():
    load_env()
    
    print("=" * 50)
    print("  AI SEO Agent — Ready")
    print("=" * 50)
    print()
    
    # Validate key env vars
    gsc_creds = bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")) or bool(os.environ.get("GSC_CREDENTIALS_PATH"))
    gsc_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or os.environ.get("GSC_CREDENTIALS_PATH")
    gsc_exists = gsc_path and Path(gsc_path).exists() if gsc_path else False
    ahrefs = bool(os.environ.get("AHREFS_API_KEY"))
    gemini = bool(os.environ.get("GEMINI_API_KEY"))
    
    print("Environment:")
    print(f"  GSC (Priority 1):    {'[OK]' if gsc_exists else '[--]'} (see .planning/GSC_SETUP.md)")
    print(f"  AHREFS_API_KEY:      {'[OK]' if ahrefs else '[--]'}")
    print(f"  GEMINI_API_KEY:      {'[OK]' if gemini else '[--]'} (AI recommendations)")
    print()
    
    skills_dir = Path(__file__).parent / ".agents" / "skills"
    skills = list(skills_dir.glob("*/SKILL.md")) if skills_dir.exists() else []
    print(f"Skills loaded: {len(skills)}")
    print()
    print("GSC (must have):")
    print("  python create_brief.py <url> <keyword>  -- full brief with GSC data")
    if not gsc_exists:
        print("  Configure: .planning/GSC_SETUP.md")
    print()
    print("How to run:")
    print("  1. Open this project in Cursor")
    print("  2. Start a chat and ask, e.g.:")
    print('     - "Create an SEO brief for [URL] targeting [keyword]"')
    print('     - "Research keywords for BPO services"')
    print('     - "Find content gaps between my site and competitors"')
    print("  3. Outputs go to the output/ folder")
    print()
    print("=" * 50)

if __name__ == "__main__":
    main()
