from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

# Simple JSONL or JSON file reader; point to your alerts archive
DEFAULT_PATHS = [
    Path("data/archives/alerts_log.jsonl"),
    Path("data/archives/alerts_log.json"),
]

def load_history(max_items:int=500) -> List[Dict]:
    for p in DEFAULT_PATHS:
        if p.exists():
            try:
                if p.suffix == '.jsonl':
                    rows = []
                    for line in p.read_text().splitlines():
                        try: rows.append(json.loads(line))
                        except: pass
                    return rows[-max_items:]
                j=json.loads(p.read_text())
                if isinstance(j, list): return j[-max_items:]
                if isinstance(j, dict) and 'items' in j: return j['items'][-max_items:]
            except Exception:
                continue
    return []
