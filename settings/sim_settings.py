# queen/settings/sim_settings.py
"""Simulation configuration for Queen of Quant.

Central place for tunable knobs used by the synthetic simulator.
Edit these to tune behavior across the system.
"""

# Notional exposure to aim for per synthetic 'unit'.
# Lower value -> larger unit counts for the same price (more conservative).
NOTIONAL_PER_UNIT_DEFAULT: float = 3_000.0

# Maximum number of unit-chunks the sim will pyramid into:
# e.g. MAX_PYRAMID_UNITS = 3.0 -> max position = 3 * unit_size
MAX_PYRAMID_UNITS: float = 3.0

# Trailing stop percent (e.g. 0.04 -> 4% trailing stop below sim_peak).
TRAIL_PCT: float = 0.04

# Enable ADD-only-when-green guard (do not average down).
ADD_ONLY_WHEN_GREEN: bool = True

# Minimum unrealised PnL percent required to permit ADD (if enabled).
# e.g. 1.0 -> require +1% unreal before honoring ADD; 0.0 -> any positive PnL.
ADD_MIN_UNREAL_PCT: float = 1.0

# Minimum and maximum integer-like units per symbol
MIN_UNITS: float = 1.0
MAX_UNITS: float = 50.0
