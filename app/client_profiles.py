"""
Client profiles for client-specific SEO report tailoring.

When --client is provided, the report is tailored to the client's target audience,
brand values, tone, and value proposition. Profiles are stored in client_profiles.json.
"""

import json
from pathlib import Path
from typing import Optional

_PROFILES_PATH = Path(__file__).parent / "client_profiles.json"
_CACHE: Optional[dict] = None


def _load_profiles() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not _PROFILES_PATH.exists():
        _CACHE = {}
        return _CACHE
    try:
        with open(_PROFILES_PATH, encoding="utf-8") as f:
            _CACHE = json.load(f)
        return _CACHE
    except Exception:
        _CACHE = {}
        return _CACHE


def get_client_profile(client_name: str) -> Optional[dict]:
    """
    Get client profile by name. Case-insensitive match.
    If not found in saved profiles, returns a minimal auto-generated profile
    so reports always include a client section when --client is used.
    """
    profiles = _load_profiles()
    name_lower = client_name.strip().lower()
    for key, value in profiles.items():
        if key.lower() == name_lower:
            return value
    # Auto-generate minimal profile for unknown clients so the report
    # still includes a client profile section (Gemini will infer details
    # from the scraped page content and SERP data).
    return {
        "target_audience": "(infer from page content and SERP data)",
        "about_the_brand": "(infer from page content and SERP data)",
        "values": "(infer from page content and SERP data)",
        "value_proposition": "(infer from page content and SERP data)",
        "brand_positioning": "(infer from page content and SERP data)",
    }


def format_client_profile_for_prompt(profile: dict) -> str:
    """Format client profile as text for Gemini prompt."""
    parts = []
    if profile.get("target_audience"):
        parts.append(f"- **Target audience:** {profile['target_audience']}")
    if profile.get("about_the_brand"):
        parts.append(f"- **About the brand:** {profile['about_the_brand']}")
    if profile.get("values"):
        parts.append(f"- **Values:** {profile['values']}")
    if profile.get("value_proposition"):
        parts.append(f"- **Value proposition:** {profile['value_proposition']}")
    if profile.get("brand_positioning"):
        parts.append(f"- **Brand positioning:** {profile['brand_positioning']}")
    if profile.get("specific_instructions"):
        parts.append(f"- **Specific content instructions (MUST FOLLOW):** {profile['specific_instructions']}")
    return "\n".join(parts) if parts else ""


def list_clients() -> list[str]:
    """Return list of available client names."""
    return list(_load_profiles().keys())
