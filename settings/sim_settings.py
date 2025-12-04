# queen/settings/sim_settings.py
"""Simulation configuration for Queen of Quant.

Centralized simulation knobs.
Change values here to tune simulator behaviour globally.
"""

# Notional exposure to aim for per synthetic 'unit'.
NOTIONAL_PER_UNIT_DEFAULT: float = 3_000.0

# Maximum number of unit-chunks the sim will pyramid into:
# e.g. MAX_PYRAMID_UNITS = 3.0 → max position = 3 * unit_size
MAX_PYRAMID_UNITS: float = 3.0

# Trailing stop percent (e.g. 0.04 → 4% trailing stop below sim_peak).
TRAIL_PCT: float = 0.04

# ADD-only-when-green behaviour
ADD_ONLY_WHEN_GREEN: bool = True

# Minimum unrealised PnL percent required to allow ADD (e.g. 1.0 = +1%)
# If 0.0 then any positive (+eps) unreal will allow an ADD.
ADD_MIN_UNREAL_PCT: float = 0.0

# Minimum / maximum units per symbol (for sizing)
SIM_MIN_UNITS: float = 1.0
SIM_MAX_UNITS: float = 50.0
