#!/usr/bin/env python3
# ============================================================
# queen/settings/profiles.py — Historical Profiles Config (v8.0)
# ============================================================
"""Profile Configuration for Data Lookback Windows
---------------------------------------------------
📅 Purpose:
    Defines default lookback duration and history depth
    for intraday, daily, weekly, and monthly profiles.

💡 Usage:
    from queen.settings import profiles
    lookback = profiles.PROFILES["intraday"]["lookback_days"]
"""

from __future__ import annotations

from typing import Any, Dict

# ------------------------------------------------------------
# 🧩 Profile Settings
# ------------------------------------------------------------
PROFILES: Dict[str, Dict[str, int]] = {
    "intraday": {"default_weeks": 4, "lookback_days": 30},
    "daily": {"default_weeks": 12, "lookback_days": 90},
    "weekly": {"default_weeks": 26, "lookback_days": 365},
    "monthly": {"default_weeks": 60, "lookback_days": 1825},
}


# ------------------------------------------------------------
# 🧠 Helper Functions
# ------------------------------------------------------------
def get_profile(name: str) -> Dict[str, Any]:
    """Retrieve profile configuration by name."""
    return PROFILES.get(name.lower(), {})


def all_profiles() -> list[str]:
    """List all available profile keys."""
    return list(PROFILES.keys())


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧩 Queen Profiles Configuration")
    pprint(all_profiles())
    pprint(get_profile("daily"))
