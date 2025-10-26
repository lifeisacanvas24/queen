#!/usr/bin/env python3
# ============================================================
# queen/settings/profiles.py — Historical Profiles Config (v9.1)
# Forward-only, DRY, delegates window calc to timeframes
# ============================================================
from __future__ import annotations

from typing import Any, Dict

from queen.settings import timeframes as TF  # single owner of TF math ✅

# ------------------------------------------------------------
# 🧩 Profile Settings (human-facing presets)
# ------------------------------------------------------------
PROFILES: Dict[str, Dict[str, int]] = {
    "intraday": {"default_weeks": 4, "lookback_days": 30},
    "daily": {"default_weeks": 12, "lookback_days": 90},
    "weekly": {"default_weeks": 26, "lookback_days": 365},
    "monthly": {"default_weeks": 60, "lookback_days": 1825},
}


# ------------------------------------------------------------
# 🧠 Helpers
# ------------------------------------------------------------
def get_profile(name: str) -> Dict[str, Any]:
    """Retrieve profile configuration by name (case-insensitive)."""
    return PROFILES.get((name or "").lower(), {})


def all_profiles() -> list[str]:
    """List all available profile keys."""
    return list(PROFILES.keys())


def window_days(profile_key: str, bars: int, token: str | None = None) -> int:
    """Return approximate calendar-days window for `bars` of a given timeframe.

    Delegates to timeframes.window_days_for_tf(); `profile_key` is only used
    to pick a sensible default token when one isn't provided.

    Examples:
        window_days('weekly', 52)            -> uses '1w' unless token is passed
        window_days('intraday', 200, '5m')   -> uses '5m'

    """
    pk = (profile_key or "").lower()
    tf_token = token or {
        "intraday": "15m",
        "daily": "1d",
        "weekly": "1w",
        "monthly": "1mo",
    }.get(pk, "1d")
    return TF.window_days_for_tf(tf_token, int(bars))


def validate() -> dict:
    """Light schema check: keys, types, positive values."""
    errs: list[str] = []
    for k, v in PROFILES.items():
        if not isinstance(v, dict):
            errs.append(f"{k}: value must be dict")
            continue
        for req in ("default_weeks", "lookback_days"):
            if req not in v:
                errs.append(f"{k}: missing '{req}'")
                continue
            val = v[req]
            if not isinstance(val, int) or val <= 0:
                errs.append(f"{k}: '{req}' must be positive int")
    return {"ok": len(errs) == 0, "errors": errs, "count": len(PROFILES)}


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧩 Queen Profiles Configuration")
    pprint(all_profiles())
    pprint(get_profile("daily"))
    print("weekly, 60 bars →", window_days("weekly", 60))
    print("intraday(5m), 200 bars →", window_days("intraday", 200, "5m"))
    pprint(validate())
