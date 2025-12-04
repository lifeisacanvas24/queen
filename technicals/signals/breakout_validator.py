#queen/technicals/signals/breakout_validator.py
"""
Breakout Validator Module
=========================
Combines FVG, Volume, and False Breakout patterns into a single
breakout quality score (1-10) that helps filter real vs fake breakouts.

This is the main entry point for breakout validation.

Usage:
    from queen.technicals.signals.breakout_validator import (
        validate_breakout,
        calculate_breakout_score,
        BreakoutValidationResult,
    )

    # Full validation
    result = validate_breakout(df, breakout_level=2850.0, direction="up")
    print(f"Breakout Quality: {result.score}/10 - {result.verdict}")

    # Quick score only
    score = calculate_breakout_score(df, direction="up")
    print(f"Score: {score}")

Integration with existing cockpit_row:
    # In services/cockpit_row.py or scoring.py
    validation = validate_breakout(df, direction="up")
    row["breakout_score"] = validation.score
    row["breakout_valid"] = validation.is_valid
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal, List, Dict, Any
import polars as pl

# Import our new modules
from queen.technicals.microstructure.fvg import detect_fvg, FVGResult
from queen.technicals.indicators.volume_confirmation import (
    compute_rvol,
    summarize_volume_confirmation,
    validate_breakout_volume,
)
from queen.technicals.patterns.false_breakout import (
    summarize_false_breakout_risk,
    FalseBreakoutRisk,
)

# Import settings
try:
    from queen.settings.breakout_settings import (
        BREAKOUT_VALIDATION_SETTINGS as SETTINGS,
        get_quality_label,
    )
except ImportError:
    # Fallback defaults
    SETTINGS = {
        "weight_volume": 2.0,
        "weight_fvg": 2.0,
        "weight_order_block": 1.5,
        "weight_htf_trend": 1.5,
        "weight_atr_confirm": 1.0,
        "weight_consecutive": 1.0,
        "penalty_sfp": -3.0,
        "penalty_fakeout": -2.5,
        "penalty_trap": -2.5,
        "penalty_stop_hunt": -2.0,
        "penalty_low_volume": -2.0,
        "penalty_divergence": -1.5,
        "penalty_against_htf": -2.0,
        "base_score": 5,
        "min_score": 1,
        "max_score": 10,
        "valid_breakout_min_score": 6,
        "strong_breakout_min_score": 8,
        "atr_breakout_min_ratio": 1.0,
        "consecutive_closes_required": 2,
    }

    def get_quality_label(score):
        if score >= 9:
            return {"label": "Excellent", "color": "#00c853"}
        elif score >= 7:
            return {"label": "Good", "color": "#4caf50"}
        elif score >= 5:
            return {"label": "Fair", "color": "#ffc107"}
        elif score >= 3:
            return {"label": "Weak", "color": "#ff9800"}
        else:
            return {"label": "Poor", "color": "#f44336"}


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class ScoreComponent:
    """Individual component of the breakout score"""
    name: str
    value: float                      # Raw value (e.g., RVOL=2.3)
    contribution: float               # Points added/removed
    passed: bool                      # Did this check pass?
    details: str                      # Human-readable explanation


@dataclass
class BreakoutValidationResult:
    """Complete breakout validation result"""
    # Overall score (1-10)
    score: int

    # Classification
    is_valid: bool                    # Score >= valid threshold
    is_strong: bool                   # Score >= strong threshold
    quality_label: str                # "Excellent", "Good", "Fair", "Weak", "Poor"
    quality_color: str                # CSS color code

    # Component breakdown
    components: List[ScoreComponent]

    # Volume analysis
    volume_result: dict
    volume_valid: bool

    # FVG analysis
    fvg_result: dict
    fvg_aligned: bool

    # False breakout risk
    false_breakout_risk: FalseBreakoutRisk

    # Summary
    verdict: str                      # One-line summary
    warnings: List[str]               # List of concerns
    positives: List[str]              # List of positive signals

    # For UI display
    display_dict: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _calculate_atr(df: pl.DataFrame, period: int = 14) -> float:
    """Get latest ATR value"""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    tr = pl.max_horizontal(tr1, tr2, tr3)
    atr = tr.rolling_mean(window_size=period)

    atr_list = atr.to_list()
    for v in reversed(atr_list):
        if v is not None:
            return v
    return 1.0  # Fallback


def _check_atr_breakout(
    df: pl.DataFrame,
    direction: Literal["up", "down"],
    lookback: int = 5,
) -> ScoreComponent:
    """Check if breakout exceeds ATR threshold"""
    atr = _calculate_atr(df)
    closes = df["close"].to_list()

    if len(closes) < lookback + 1:
        return ScoreComponent(
            name="ATR Breakout",
            value=0.0,
            contribution=0.0,
            passed=False,
            details="Insufficient data"
        )

    # Calculate move size
    recent_close = closes[-1]
    lookback_close = closes[-lookback]
    move = recent_close - lookback_close if direction == "up" else lookback_close - recent_close
    move_atr_ratio = move / atr if atr > 0 else 0

    min_ratio = SETTINGS["atr_breakout_min_ratio"]

    if move_atr_ratio >= min_ratio * 1.5:
        return ScoreComponent(
            name="ATR Breakout",
            value=round(move_atr_ratio, 2),
            contribution=SETTINGS["weight_atr_confirm"],
            passed=True,
            details=f"Strong: Move = {move_atr_ratio:.1f}x ATR"
        )
    elif move_atr_ratio >= min_ratio:
        return ScoreComponent(
            name="ATR Breakout",
            value=round(move_atr_ratio, 2),
            contribution=SETTINGS["weight_atr_confirm"] * 0.5,
            passed=True,
            details=f"Adequate: Move = {move_atr_ratio:.1f}x ATR"
        )
    else:
        return ScoreComponent(
            name="ATR Breakout",
            value=round(move_atr_ratio, 2),
            contribution=0.0,
            passed=False,
            details=f"Weak: Move = {move_atr_ratio:.1f}x ATR (need {min_ratio}x)"
        )


def _check_consecutive_closes(
    df: pl.DataFrame,
    level: float,
    direction: Literal["up", "down"],
) -> ScoreComponent:
    """Check for consecutive closes beyond level"""
    closes = df["close"].to_list()
    required = SETTINGS["consecutive_closes_required"]

    if len(closes) < required:
        return ScoreComponent(
            name="Consecutive Closes",
            value=0,
            contribution=0.0,
            passed=False,
            details="Insufficient data"
        )

    recent = closes[-required:]

    if direction == "up":
        count = sum(1 for c in recent if c > level)
    else:
        count = sum(1 for c in recent if c < level)

    passed = count >= required

    return ScoreComponent(
        name="Consecutive Closes",
        value=count,
        contribution=SETTINGS["weight_consecutive"] if passed else 0.0,
        passed=passed,
        details=f"{count}/{required} closes beyond level" + (" ✓" if passed else "")
    )


# ---------------------------------------------------------------------------
# Main Validation Function
# ---------------------------------------------------------------------------
def validate_breakout(
    df: pl.DataFrame,
    breakout_level: Optional[float] = None,
    direction: Literal["up", "down"] = "up",
    htf_trend: Optional[Literal["bullish", "bearish", "neutral"]] = None,
    has_divergence: bool = False,
) -> BreakoutValidationResult:
    """
    Comprehensive breakout validation.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    breakout_level : float, optional
        The level being broken. If None, uses recent high/low.
    direction : str
        "up" (bullish breakout) or "down" (bearish breakout)
    htf_trend : str, optional
        Higher timeframe trend for alignment check
    has_divergence : bool
        Whether RSI/MACD divergence is present

    Returns
    -------
    BreakoutValidationResult
        Complete validation with score and analysis
    """
    components: List[ScoreComponent] = []
    warnings: List[str] = []
    positives: List[str] = []

    # Start with base score
    score = float(SETTINGS["base_score"])

    # =========================================================================
    # 1. VOLUME CONFIRMATION
    # =========================================================================
    if "rvol" not in df.columns:
        df = compute_rvol(df)

    volume_result = summarize_volume_confirmation(df)
    volume_validation = validate_breakout_volume(df)

    volume_component = ScoreComponent(
        name="Volume Confirmation",
        value=volume_result["current_rvol"] or 0,
        contribution=0.0,
        passed=volume_validation["is_valid"],
        details=volume_validation["verdict"]
    )

    if volume_validation["is_valid"]:
        volume_component.contribution = SETTINGS["weight_volume"]
        if volume_result["current_rvol"] and volume_result["current_rvol"] >= 2.5:
            positives.append(f"Strong volume: {volume_result['display_value']}")
        else:
            positives.append(f"Good volume: {volume_result['display_value']}")
    else:
        volume_component.contribution = SETTINGS["penalty_low_volume"]
        warnings.append(f"Weak volume: {volume_result['display_value']}")

    score += volume_component.contribution
    components.append(volume_component)

    # =========================================================================
    # 2. FVG ANALYSIS
    # =========================================================================
    fvg_result = detect_fvg(df)
    fvg_summary = {
        "total_unfilled": fvg_result.total_unfilled,
        "bullish_count": len(fvg_result.bullish_zones),
        "bearish_count": len(fvg_result.bearish_zones),
        "bias": fvg_result.bias,
        "in_fvg": fvg_result.in_fvg,
    }

    # Check FVG alignment with breakout direction
    fvg_aligned = False
    if direction == "up" and fvg_result.nearest_below:
        fvg_aligned = True  # Support FVG exists
        positives.append("FVG support below")
    elif direction == "down" and fvg_result.nearest_above:
        fvg_aligned = True  # Resistance FVG exists
        positives.append("FVG resistance above")

    fvg_component = ScoreComponent(
        name="FVG Alignment",
        value=fvg_result.total_unfilled,
        contribution=SETTINGS["weight_fvg"] if fvg_aligned else 0.0,
        passed=fvg_aligned,
        details=f"Bias: {fvg_result.bias}, {fvg_result.total_unfilled} unfilled FVGs"
    )

    score += fvg_component.contribution
    components.append(fvg_component)

    # =========================================================================
    # 3. FALSE BREAKOUT RISK
    # =========================================================================
    fb_direction = "up" if direction == "up" else "down"
    false_breakout_risk = summarize_false_breakout_risk(
        df,
        breakout_level=breakout_level,
        direction=fb_direction
    )

    fb_penalty = 0.0
    if false_breakout_risk.signals_detected:
        for signal in false_breakout_risk.signals_detected:
            if signal.pattern_type == "sfp":
                fb_penalty += SETTINGS["penalty_sfp"]
                warnings.append(f"⚠ SFP detected: {signal.confidence:.0f}% confidence")
            elif signal.pattern_type == "fakeout":
                fb_penalty += SETTINGS["penalty_fakeout"]
                warnings.append("⚠ Fakeout candle pattern")
            elif signal.pattern_type in ["bull_trap", "bear_trap"]:
                fb_penalty += SETTINGS["penalty_trap"]
                warnings.append(f"⚠ {signal.pattern_type.replace('_', ' ').title()}")
            elif signal.pattern_type == "stop_hunt":
                fb_penalty += SETTINGS["penalty_stop_hunt"]
                warnings.append("⚠ Stop hunt reversal detected")

    fb_component = ScoreComponent(
        name="False Breakout Check",
        value=false_breakout_risk.risk_score,
        contribution=fb_penalty,
        passed=len(false_breakout_risk.signals_detected) == 0,
        details=false_breakout_risk.verdict if false_breakout_risk.signals_detected else "No warning patterns"
    )

    score += fb_component.contribution
    components.append(fb_component)

    # =========================================================================
    # 4. ATR BREAKOUT CONFIRMATION
    # =========================================================================
    atr_component = _check_atr_breakout(df, direction)
    score += atr_component.contribution
    components.append(atr_component)

    if atr_component.passed:
        positives.append(atr_component.details)

    # =========================================================================
    # 5. CONSECUTIVE CLOSES (if level provided)
    # =========================================================================
    if breakout_level:
        consec_component = _check_consecutive_closes(df, breakout_level, direction)
        score += consec_component.contribution
        components.append(consec_component)

        if consec_component.passed:
            positives.append(consec_component.details)

    # =========================================================================
    # 6. HIGHER TIMEFRAME ALIGNMENT
    # =========================================================================
    if htf_trend:
        aligned = (
            (direction == "up" and htf_trend == "bullish") or
            (direction == "down" and htf_trend == "bearish")
        )

        htf_component = ScoreComponent(
            name="HTF Alignment",
            value=htf_trend,
            contribution=SETTINGS["weight_htf_trend"] if aligned else SETTINGS["penalty_against_htf"],
            passed=aligned,
            details=f"HTF: {htf_trend}, Direction: {direction}"
        )

        score += htf_component.contribution
        components.append(htf_component)

        if aligned:
            positives.append(f"Aligned with {htf_trend} HTF trend")
        else:
            warnings.append(f"Against {htf_trend} HTF trend")

    # =========================================================================
    # 7. DIVERGENCE CHECK
    # =========================================================================
    if has_divergence:
        div_component = ScoreComponent(
            name="Divergence",
            value="detected",
            contribution=SETTINGS["penalty_divergence"],
            passed=False,
            details="RSI/MACD divergence present"
        )
        score += div_component.contribution
        components.append(div_component)
        warnings.append("RSI/MACD divergence detected")

    # =========================================================================
    # FINAL SCORE CALCULATION
    # =========================================================================
    final_score = int(round(max(SETTINGS["min_score"], min(SETTINGS["max_score"], score))))

    is_valid = final_score >= SETTINGS["valid_breakout_min_score"]
    is_strong = final_score >= SETTINGS["strong_breakout_min_score"]

    quality = get_quality_label(final_score)

    # Generate verdict
    if is_strong:
        verdict = f"Strong breakout signal: {final_score}/10"
    elif is_valid:
        verdict = f"Valid breakout signal: {final_score}/10"
    elif final_score >= 4:
        verdict = f"Weak breakout - proceed with caution: {final_score}/10"
    else:
        verdict = f"Likely false breakout - avoid: {final_score}/10"

    # Build display dict for UI
    display_dict = {
        "score": final_score,
        "score_display": f"{final_score}/10",
        "quality_label": quality["label"],
        "quality_color": quality["color"],
        "is_valid": is_valid,
        "is_strong": is_strong,
        "volume_display": volume_result["display_value"],
        "fvg_count": fvg_result.total_unfilled,
        "warning_count": len(warnings),
        "positive_count": len(positives),
    }

    return BreakoutValidationResult(
        score=final_score,
        is_valid=is_valid,
        is_strong=is_strong,
        quality_label=quality["label"],
        quality_color=quality["color"],
        components=components,
        volume_result=volume_result,
        volume_valid=volume_validation["is_valid"],
        fvg_result=fvg_summary,
        fvg_aligned=fvg_aligned,
        false_breakout_risk=false_breakout_risk,
        verdict=verdict,
        warnings=warnings,
        positives=positives,
        display_dict=display_dict,
    )


def calculate_breakout_score(
    df: pl.DataFrame,
    direction: Literal["up", "down"] = "up",
    **kwargs,
) -> int:
    """
    Quick breakout score calculation.

    Returns score 1-10 without full analysis details.
    """
    result = validate_breakout(df, direction=direction, **kwargs)
    return result.score


def attach_breakout_validation(
    df: pl.DataFrame,
    direction: Literal["up", "down"] = "up",
) -> pl.DataFrame:
    """
    Attach breakout validation columns to DataFrame.

    Adds columns:
        - breakout_score: int (1-10)
        - breakout_valid: bool
        - breakout_quality: str
    """
    result = validate_breakout(df, direction=direction)

    return df.with_columns([
        pl.lit(result.score).alias("breakout_score"),
        pl.lit(result.is_valid).alias("breakout_valid"),
        pl.lit(result.quality_label).alias("breakout_quality"),
    ])


# ---------------------------------------------------------------------------
# Registry Export (for auto-discovery)
# ---------------------------------------------------------------------------
EXPORTS = {
    "breakout_validate": validate_breakout,
    "breakout_score": calculate_breakout_score,
    "breakout_attach": attach_breakout_validation,
}

NAME = "breakout_validator"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("BREAKOUT VALIDATOR TEST")
    print("=" * 60)

    # Create sample data
    np.random.seed(42)
    n = 60

    # Simulate a breakout scenario
    base = 100.0
    prices = [base]
    volumes = [10000]

    for i in range(1, n):
        # Normal movement until bar 45, then breakout
        if i < 45:
            change = np.random.uniform(-0.3, 0.3)
            vol = 10000 + np.random.randint(-2000, 2000)
        else:
            # Breakout phase
            change = np.random.uniform(0.3, 0.8)  # Upward bias
            vol = 10000 * np.random.uniform(1.5, 3.0)  # High volume

        prices.append(prices[-1] + change)
        volumes.append(vol)

    df = pl.DataFrame({
        "timestamp": list(range(n)),
        "open": prices,
        "high": [p + np.random.uniform(0.2, 0.8) for p in prices],
        "low": [p - np.random.uniform(0.2, 0.8) for p in prices],
        "close": [p + np.random.uniform(-0.2, 0.2) for p in prices],
        "volume": volumes,
    })

    # Test validation
    result = validate_breakout(
        df,
        breakout_level=prices[44],  # Pre-breakout price
        direction="up",
        htf_trend="bullish",
    )

    print(f"\n📊 BREAKOUT SCORE: {result.score}/10")
    print(f"   Quality: {result.quality_label}")
    print(f"   Valid: {result.is_valid}")
    print(f"   Strong: {result.is_strong}")
    print(f"\n📝 VERDICT: {result.verdict}")

    print("\n✅ POSITIVES:")
    for p in result.positives:
        print(f"   • {p}")

    print("\n⚠️ WARNINGS:")
    for w in result.warnings:
        print(f"   • {w}")

    print("\n📈 COMPONENT BREAKDOWN:")
    for comp in result.components:
        status = "✓" if comp.passed else "✗"
        print(f"   {status} {comp.name}: {comp.contribution:+.1f} pts")
        print(f"      {comp.details}")

    print("\n" + "=" * 60)
