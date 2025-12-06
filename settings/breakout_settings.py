# queen/settings/breakout_settings.py
"""Breakout Detection Settings
===========================
Centralized configuration for all breakout-related modules.

Modules using these settings:
- technicals/microstructure/fvg.py
- technicals/indicators/volume_confirmation.py
- technicals/patterns/false_breakout.py
- technicals/signals/breakout_validator.py
- technicals/microstructure/order_blocks.py
- technicals/microstructure/liquidity.py
- technicals/microstructure/breaker_blocks.py
- technicals/microstructure/wyckoff.py
- helpers/swing_detection.py

Usage:
    from queen.settings.breakout_settings import (
        FVG_SETTINGS,
        VOLUME_SETTINGS,
        ORDER_BLOCK_SETTINGS,
        LIQUIDITY_SETTINGS,
        SWING_SETTINGS,
        WYCKOFF_SETTINGS,
    )
"""

from __future__ import annotations

from typing import Any, Dict

# ===========================================================================
# Swing Detection Settings (shared by multiple modules)
# ===========================================================================
SWING_SETTINGS: Dict[str, Any] = {
    "default_max_points": 5,
    "min_bars_required": 3,
    "fractal_window": 1,          # 1 = 3-bar fractal, 2 = 5-bar fractal
    "equal_level_tolerance": 0.003,  # Tolerance for equal highs/lows
}

# ===========================================================================
# FVG (Fair Value Gap) Settings
# ===========================================================================
FVG_SETTINGS: Dict[str, Any] = {
    # Minimum gap size as ratio of ATR to be considered significant
    "min_gap_atr_ratio": 0.3,

    # Maximum bars back to look for unfilled FVGs
    "max_age_bars": 50,

    # Gap considered filled if this percentage is filled (90% = 0.1 tolerance)
    "fill_tolerance_pct": 0.1,

    # FVG larger than this (ATR ratio) is "significant"
    "significance_atr_ratio": 0.5,

    # Default lookback period for FVG detection
    "lookback_default": 50,

    # How close price must be to FVG to consider it "nearby" (as % of price)
    "nearby_threshold_pct": 0.01,  # 1%
}

# ===========================================================================
# Volume Confirmation Settings
# ===========================================================================
VOLUME_SETTINGS: Dict[str, Any] = {
    # === RVOL (Relative Volume) ===
    "rvol_period": 20,               # Lookback for average volume calculation
    "rvol_high_threshold": 1.5,      # RVOL >= 1.5x = "high" volume
    "rvol_very_high_threshold": 2.5, # RVOL >= 2.5x = "very high"
    "rvol_extreme_threshold": 4.0,   # RVOL >= 4x = "extreme"
    "rvol_low_threshold": 0.7,       # RVOL < 0.7x = "low" volume
    "rvol_very_low_threshold": 0.5,  # RVOL < 0.5x = "very low"

    # === Volume Spike Detection ===
    "spike_threshold": 2.0,          # Volume > 2x average = spike
    "spike_lookback": 20,            # Bars to check for recent spikes
    "spike_confirmation_bars": 1,    # Bars after spike to confirm direction

    # === Volume Trend ===
    "trend_period": 10,              # Bars for volume trend analysis
    "trend_increasing_threshold": 5,  # % slope for "increasing"
    "trend_decreasing_threshold": -5, # % slope for "decreasing"

    # === Accumulation/Distribution ===
    "accumulation_threshold": 1.2,   # Volume ratio for accumulation signal
    "distribution_threshold": 0.8,   # Volume ratio for distribution signal

    # === Breakout Confirmation ===
    "breakout_min_rvol": 1.5,        # Minimum RVOL for valid breakout
    "breakout_ideal_rvol": 2.0,      # Ideal RVOL for strong breakout

    # === Scoring Adjustments ===
    "excellent_volume_bonus": 2,
    "good_volume_bonus": 1,
    "weak_volume_penalty": -1,
    "low_volume_penalty": -2,
}

# ===========================================================================
# False Breakout Pattern Settings
# ===========================================================================
FALSE_BREAKOUT_SETTINGS: Dict[str, Any] = {
    # === Swing Failure Pattern (SFP) ===
    "sfp_lookback": 20,              # Bars to look for swing points
    "sfp_wick_min_pct": 0.3,         # Min wick beyond level as % of ATR
    "sfp_body_inside_pct": 0.8,      # Body must be X% inside the level
    "sfp_confidence_base": 50,       # Base confidence score
    "sfp_confidence_max": 90,        # Maximum confidence score

    # === Fakeout Candle ===
    "fakeout_wick_ratio": 2.0,       # Wick must be 2x body size
    "fakeout_body_max_pct": 0.3,     # Body max % of total candle range
    "fakeout_confidence_base": 50,
    "fakeout_confidence_max": 85,

    # === Bull/Bear Trap ===
    "trap_reversal_min_pct": 0.5,    # Min reversal as % of ATR
    "trap_lookback": 5,              # Bars to confirm trap pattern
    "trap_confirmation_bars": 2,     # Bars after peak/trough for confirmation
    "trap_confidence_base": 50,
    "trap_confidence_max": 80,

    # === Stop Hunt Reversal ===
    "stop_hunt_wick_atr_ratio": 0.5, # Wick must exceed level by X*ATR
    "stop_hunt_close_inside": True,  # Must close back inside the level
    "stop_hunt_confidence_base": 60,
    "stop_hunt_confidence_max": 85,

    # === General ===
    "level_tolerance_pct": 0.1,      # Tolerance for "at level" (% of price)
}

# ===========================================================================
# Order Block Settings
# ===========================================================================
ORDER_BLOCK_SETTINGS: Dict[str, Any] = {
    # Impulse move requirements
    "min_impulse_atr_ratio": 1.5,    # Impulse must be > 1.5x ATR
    "impulse_bars": 3,                # Bars to confirm impulse

    # OB candle requirements
    "min_ob_body_ratio": 0.5,         # Body must be > 50% of range

    # Tracking
    "max_age_bars": 50,               # How far back to look
    "max_obs_to_track": 10,           # Max OBs to return
    "lookback_default": 50,

    # Mitigation
    "mitigation_tolerance": 0.1,      # 10% into zone = mitigated

    # Strength scoring
    "strong_impulse_ratio": 3.0,      # 3x ATR = strong
    "medium_impulse_ratio": 2.0,      # 2x ATR = medium
}

# ===========================================================================
# Liquidity Settings
# ===========================================================================
LIQUIDITY_SETTINGS: Dict[str, Any] = {
    # Sweep detection
    "sweep_min_wick_atr": 0.3,        # Min wick beyond level (ATR ratio)
    "sweep_max_close_beyond": 0.1,    # Max close beyond level (ATR ratio)

    # Pool detection
    "pool_min_touches": 2,            # Min times level tested
    "pool_tolerance_pct": 0.002,      # Price tolerance for "same level"
    "equal_level_tolerance": 0.003,   # Tolerance for equal highs/lows

    # Tracking
    "lookback_default": 50,
    "max_sweeps_to_track": 10,

    # Strength scoring
    "sweep_strength_multiplier": 30,  # Strength = (sweep_size/ATR) * this
    "pool_strength_per_touch": 25,    # Each touch adds this much strength
}

# ===========================================================================
# Breaker Block Settings
# ===========================================================================
BREAKER_BLOCK_SETTINGS: Dict[str, Any] = {
    # When does an OB become a breaker?
    "mitigation_threshold": 0.5,      # OB 50% mitigated = breaker candidate
    "confirmation_bars": 2,           # Bars needed to confirm break

    # Tracking
    "max_age_bars": 100,              # Look further back for breakers
    "max_breakers_to_track": 5,
    "lookback_default": 100,

    # Strength
    "strong_breaker_impulse": 2.0,    # Original impulse was > 2x ATR
}

# ===========================================================================
# BOS / CHoCH Settings (Break of Structure / Change of Character)
# ===========================================================================
BOS_CHOCH_SETTINGS: Dict[str, Any] = {
    # BOS (Break of Structure) - continuation
    "bos_min_break_pct": 0.001,       # Min break beyond swing (0.1%)
    "bos_confirmation_close": True,   # Must close beyond level

    # CHoCH (Change of Character) - reversal
    "choch_requires_impulse": True,   # Must have impulse after break
    "choch_min_impulse_atr": 1.0,     # Impulse must be > 1x ATR

    # Lookback
    "structure_lookback": 50,
    "swing_lookback": 20,
}

# ===========================================================================
# Wyckoff Settings
# ===========================================================================
WYCKOFF_SETTINGS: Dict[str, Any] = {
    # Spring / Upthrust detection (similar to liquidity sweep)
    "spring_wick_min_atr": 0.3,       # Wick below support must be > 0.3 ATR
    "spring_close_above": True,       # Must close back above support
    "upthrust_wick_min_atr": 0.3,     # Wick above resistance
    "upthrust_close_below": True,     # Must close back below resistance

    # Climax detection
    "climax_volume_multiple": 2.5,    # Volume must be > 2.5x average
    "climax_range_atr_ratio": 1.5,    # Wide range bar > 1.5x ATR
    "climax_close_off_extreme": 0.3,  # Close must be 30% off high/low

    # Phase identification
    "accumulation_min_bars": 20,      # Minimum bars for accumulation phase
    "distribution_min_bars": 20,

    # SOS/SOW
    "sos_volume_increase": 1.5,       # Volume must increase by 50%
    "sow_volume_increase": 1.5,
}

# ===========================================================================
# Breakout Validation Settings (Combined Scoring)
# ===========================================================================
BREAKOUT_VALIDATION_SETTINGS: Dict[str, Any] = {
    # === Scoring Weights (Positives) ===
    "weight_volume": 2.0,             # Volume confirmation weight
    "weight_fvg": 2.0,                # FVG alignment weight
    "weight_order_block": 1.5,        # Order block support weight
    "weight_htf_trend": 1.5,          # Higher timeframe alignment
    "weight_atr_confirm": 1.0,        # ATR breakout confirmation
    "weight_consecutive": 1.0,        # Consecutive closes weight
    "weight_no_liquidity_against": 1.0,  # No sweep against direction

    # === Penalty Weights ===
    "penalty_sfp": -3.0,              # Swing Failure Pattern detected
    "penalty_fakeout": -2.5,          # Fakeout candle detected
    "penalty_trap": -2.5,             # Bull/Bear trap detected
    "penalty_stop_hunt": -2.0,        # Stop hunt reversal detected
    "penalty_low_volume": -2.0,       # Low volume on breakout
    "penalty_divergence": -1.5,       # RSI/MACD divergence
    "penalty_against_htf": -2.0,      # Against higher timeframe trend
    "penalty_liquidity_sweep_against": -1.5,  # Swept in wrong direction

    # === Thresholds ===
    "base_score": 5,                  # Starting score (1-10 scale)
    "min_score": 1,                   # Minimum possible score
    "max_score": 10,                  # Maximum possible score
    "valid_breakout_min_score": 6,    # Minimum score for "valid" breakout
    "strong_breakout_min_score": 8,   # Minimum score for "strong" breakout

    # === ATR Breakout Filter ===
    "atr_breakout_min_ratio": 1.0,    # Breakout must exceed 1x ATR
    "atr_breakout_strong_ratio": 1.5, # Strong breakout exceeds 1.5x ATR

    # === Consecutive Close Filter ===
    "consecutive_closes_required": 2, # Bars closing beyond level

    # === Multi-Timeframe ===
    "mtf_alignment_bonus": 1.0,       # Bonus if HTF aligned
    "mtf_misalignment_penalty": -1.5, # Penalty if HTF opposed
}

# ===========================================================================
# Quality Labels (for UI display)
# ===========================================================================
BREAKOUT_QUALITY_LABELS: Dict[tuple, Dict[str, Any]] = {
    (9, 10): {"label": "Excellent", "color": "#00c853", "icon": "fa-star"},
    (7, 8): {"label": "Good", "color": "#4caf50", "icon": "fa-check-circle"},
    (5, 6): {"label": "Fair", "color": "#ffc107", "icon": "fa-exclamation-circle"},
    (3, 4): {"label": "Weak", "color": "#ff9800", "icon": "fa-exclamation-triangle"},
    (1, 2): {"label": "Poor", "color": "#f44336", "icon": "fa-times-circle"},
}


# ===========================================================================
# Helper Functions
# ===========================================================================
def get_quality_label(score: int) -> Dict[str, Any]:
    """Get UI label for breakout quality score."""
    for (low, high), label_info in BREAKOUT_QUALITY_LABELS.items():
        if low <= score <= high:
            return label_info
    return {"label": "Unknown", "color": "#9e9e9e", "icon": "fa-question"}


def validate_settings() -> bool:
    """Validate all settings are properly configured."""
    errors = []

    # FVG validations
    if FVG_SETTINGS["min_gap_atr_ratio"] <= 0:
        errors.append("FVG min_gap_atr_ratio must be positive")

    # Volume validations
    if VOLUME_SETTINGS["breakout_min_rvol"] < 1.0:
        errors.append("Volume breakout_min_rvol should be >= 1.0")

    # Breakout validation
    if BREAKOUT_VALIDATION_SETTINGS["base_score"] < 1:
        errors.append("Breakout base_score must be >= 1")

    # Order Block validations
    if ORDER_BLOCK_SETTINGS["min_impulse_atr_ratio"] <= 0:
        errors.append("Order Block min_impulse_atr_ratio must be positive")

    # Liquidity validations
    if LIQUIDITY_SETTINGS["sweep_min_wick_atr"] <= 0:
        errors.append("Liquidity sweep_min_wick_atr must be positive")

    if errors:
        for e in errors:
            print(f"⚠️ Settings Error: {e}")
        return False

    return True


# ===========================================================================
# Export all settings
# ===========================================================================
__all__ = [
    # Settings dictionaries
    "SWING_SETTINGS",
    "FVG_SETTINGS",
    "VOLUME_SETTINGS",
    "FALSE_BREAKOUT_SETTINGS",
    "ORDER_BLOCK_SETTINGS",
    "LIQUIDITY_SETTINGS",
    "BREAKER_BLOCK_SETTINGS",
    "BOS_CHOCH_SETTINGS",
    "WYCKOFF_SETTINGS",
    "BREAKOUT_VALIDATION_SETTINGS",
    "BREAKOUT_QUALITY_LABELS",
    # Helper functions
    "get_quality_label",
    "validate_settings",
]
