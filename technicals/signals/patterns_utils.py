# quant/signals/utils_patterns.py
# ------------------------------------------------------------
# 🧩 Pattern Utilities — integrates patterns.json into cockpit
# ------------------------------------------------------------
import random

from quant import config

FAMILY_ICONS = {
    "japanese": "🕯️",
    "cumulative": "🔁",
    "other": "🧩",
}

def get_patterns_for_timeframe(timeframe: str) -> list[tuple[str, str]]:
    """Return (label, family_icon) tuples of all patterns applicable to a given timeframe key.
    """
    patterns = config.get_section("patterns")
    if not patterns:
        return []

    valid = []
    for family, category in patterns.items():  # e.g. 'japanese', 'cumulative', '_comment'
        if not isinstance(category, dict):
            continue  # skip strings like '_comment'

        icon = FAMILY_ICONS.get(family, FAMILY_ICONS["other"])

        for name, meta in category.items():
            if not isinstance(meta, dict):
                continue
            contexts = meta.get("contexts", {})
            if timeframe in contexts:
                label = name.replace("_", " ").title()
                valid.append((label, icon))

    return valid


def get_random_pattern_label(timeframe: str) -> str:
    """Return a random pattern label (with icon) valid for this timeframe."""
    patterns = get_patterns_for_timeframe(timeframe)
    if not patterns:
        return "—"
    label, icon = random.choice(patterns)
    return f"{icon} {label}"


def get_deterministic_pattern_label(timeframe: str, index: int) -> str:
    """Return a deterministic pattern label for reproducibility."""
    patterns = get_patterns_for_timeframe(timeframe)
    if not patterns:
        return "—"
    label, icon = patterns[index % len(patterns)]
    return f"{icon} {label}"

def get_patterns_grouped_by_family(timeframe: str) -> dict:
    """Return a mapping: { family_name: [(label, icon), ...] }
    containing only patterns valid for the given timeframe.
    """
    patterns = config.get_section("patterns")
    if not patterns:
        return {}

    grouped = {}

    for family, category in patterns.items():
        if not isinstance(category, dict):
            continue

        icon = FAMILY_ICONS.get(family, FAMILY_ICONS["other"])
        valid_patterns = []

        for name, meta in category.items():
            if not isinstance(meta, dict):
                continue
            contexts = meta.get("contexts", {})
            if timeframe in contexts:
                label = name.replace("_", " ").title()
                valid_patterns.append((label, icon))

        if valid_patterns:
            grouped[family] = valid_patterns

    return grouped
