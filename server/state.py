"""Global runtime state — last tick timestamp for market freshness checks."""
# queen/server/state.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

LAST_TICK_IST: Optional[datetime] = None

def set_last_tick(dt):  # dt aware IST
    global LAST_TICK_IST; LAST_TICK_IST = dt

def get_last_tick():    # returns aware IST or None
    return LAST_TICK_IST
