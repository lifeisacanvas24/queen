#!/usr/bin/env python3
# ============================================================
# queen/helpers/guardrail_debug.py — v1.0
# ------------------------------------------------------------
# Formatting helpers for guardrail debugging:
#   • Pretty-print sim_guardrails list
#   • Used by debug_decisions, scan_signals --inspect, replay, etc.
# ============================================================

from __future__ import annotations

from typing import List


def format_guardrails(guardrails: List[str] | None) -> str:
    """Turn a list of guardrail reasons into a single compact string.

    Examples
    --------
    ["heat_stop: open_R=-3.20 <= -3.00 → EXIT"]
      → "[heat_stop] open_R=-3.20 <= -3.00 → EXIT"

    [
      "ladder_cap: ladder_adds=1 >= max_adds=1 → HOLD",
      "no_proof_of_edge: qty=2 >= proof_qty=2, but peak_R=0.10 < min_proof_R=1.00 → HOLD"
    ]
      → "[ladder_cap] ladder_adds=1 >= max_adds=1 → HOLD | [no_proof_of_edge] qty=2 >= proof_qty=2, but peak_R=0.10 < min_proof_R=1.00 → HOLD"

    """
    if not guardrails:
        return ""

    parts: list[str] = []
    for g in guardrails:
        if not g:
            continue

        # Each guardrail string starts like "tag: message"
        if ":" in g:
            tag, msg = g.split(":", 1)
            parts.append(f"[{tag.strip()}] {msg.strip()}")
        else:
            parts.append(g.strip())

    return " | ".join(parts)
