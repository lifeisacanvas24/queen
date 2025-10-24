#!/usr/bin/env python3
# ============================================================
# queen/alerts/rules.py — v0.6 (DRY path + typed loader)
# ============================================================
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from queen.settings import settings as SETTINGS

DEFAULT_RULES_PATH: Path = SETTINGS.PATHS["CONFIGS"] / "alert_rules.yaml"


@dataclass
class Rule:
    name: str
    symbol: str
    kind: str  # "price" | "pattern" | "indicator"
    timeframe: str  # "1m","5m","1d","1w","1mo", etc.
    op: Optional[str] = None  # lt|gt|eq|crosses_above|crosses_below
    value: Optional[float] = None
    pattern: Optional[str] = None
    indicator: Optional[str] = None
    params: Dict[str, Any] = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> Rule:
        return Rule(
            name=d.get("name") or f"rule_{d.get('symbol','_')}_{d.get('kind','_')}",
            symbol=d["symbol"],
            kind=d["kind"],
            timeframe=str(d.get("timeframe", "1m")),
            op=d.get("op"),
            value=d.get("value"),
            pattern=d.get("pattern"),
            indicator=d.get("indicator"),
            params=d.get("params") or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_rules(path: Optional[Union[str, Path]] = None) -> List[Rule]:
    p = Path(path) if path else DEFAULT_RULES_PATH
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text()) or []
    items = data.get("rules") if isinstance(data, dict) else data
    return [Rule.from_dict(x) for x in (items or [])]
