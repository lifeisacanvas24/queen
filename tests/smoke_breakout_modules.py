# queen/tests/smoke_breakout_modules.py
"""
Comprehensive Smoke Tests for All Breakout & SMC Modules
=========================================================
Run: python -m queen.tests.smoke_breakout_modules

Tests:
1. Settings
2. FVG Detection
3. Volume Confirmation
4. Volume Profile
5. Delta Volume
6. VWAP with Bands
7. False Breakout Patterns
8. Order Blocks
9. Liquidity Detection
10. Breaker Blocks
11. BOS/CHoCH
12. Mitigation Blocks
13. Premium/Discount Zones
14. Wyckoff Patterns (9 patterns)
15. Breakout Validator (integration)
16. Shared Helpers (Swing Detection)

Total: 80+ test assertions
"""

import sys
import polars as pl
import numpy as np

# Test counters
_passed = 0
_failed = 0


def _assert(condition: bool, msg: str = ""):
    """Assert with tracking"""
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  ✓ {msg}")
    else:
        _failed += 1
        print(f"  ✗ FAILED: {msg}")


def _make_test_df(n: int = 100, with_gaps: bool = False, with_spikes: bool = False, trend: str = "neutral") -> pl.DataFrame:
    """Create test OHLCV data with configurable patterns"""
    np.random.seed(42)

    base = 100.0
    prices = [base]
    volumes = [10000]

    for i in range(1, n):
        # Add gaps at specific bars
        if with_gaps and i in [25, 50, 75]:
            gap = 2.0 * (1 if np.random.random() > 0.5 else -1)
        else:
            gap = 0

        # Add trend bias
        if trend == "up":
            bias = 0.1
        elif trend == "down":
            bias = -0.1
        else:
            bias = 0

        change = np.random.uniform(-0.5, 0.5) + gap + bias
        prices.append(prices[-1] + change)

        # Add volume spikes
        if with_spikes and i in [30, 60, 90]:
            volumes.append(int(10000 * np.random.uniform(2.5, 4.0)))
        else:
            volumes.append(10000 + np.random.randint(-2000, 2000))

    return pl.DataFrame({
        "timestamp": [f"2025-01-{(i % 28) + 1:02d} 09:{15 + (i % 45):02d}" for i in range(n)],
        "open": prices,
        "high": [p + np.random.uniform(0.3, 1.0) for p in prices],
        "low": [p - np.random.uniform(0.3, 1.0) for p in prices],
        "close": [p + np.random.uniform(-0.2, 0.2) for p in prices],
        "volume": volumes,
    })


# =============================================================================
# TEST 1: Settings
# =============================================================================
def test_settings():
    """Test settings module"""
    print("\n" + "=" * 50)
    print("TEST 1: Settings")
    print("=" * 50)

    from queen.settings.breakout_settings import (
        FVG_SETTINGS,
        VOLUME_SETTINGS,
        FALSE_BREAKOUT_SETTINGS,
        BREAKOUT_VALIDATION_SETTINGS,
        ORDER_BLOCK_SETTINGS,
        LIQUIDITY_SETTINGS,
        BREAKER_BLOCK_SETTINGS,
        BOS_CHOCH_SETTINGS,
        WYCKOFF_SETTINGS,
        SWING_SETTINGS,
        get_quality_label,
        validate_settings,
    )

    _assert(isinstance(FVG_SETTINGS, dict), "FVG_SETTINGS is dict")
    _assert(isinstance(VOLUME_SETTINGS, dict), "VOLUME_SETTINGS is dict")
    _assert(isinstance(FALSE_BREAKOUT_SETTINGS, dict), "FALSE_BREAKOUT_SETTINGS is dict")
    _assert(isinstance(BREAKOUT_VALIDATION_SETTINGS, dict), "BREAKOUT_VALIDATION_SETTINGS is dict")
    _assert(isinstance(ORDER_BLOCK_SETTINGS, dict), "ORDER_BLOCK_SETTINGS is dict")
    _assert(isinstance(LIQUIDITY_SETTINGS, dict), "LIQUIDITY_SETTINGS is dict")
    _assert(isinstance(BREAKER_BLOCK_SETTINGS, dict), "BREAKER_BLOCK_SETTINGS is dict")
    _assert(isinstance(BOS_CHOCH_SETTINGS, dict), "BOS_CHOCH_SETTINGS is dict")
    _assert(isinstance(WYCKOFF_SETTINGS, dict), "WYCKOFF_SETTINGS is dict")
    _assert(isinstance(SWING_SETTINGS, dict), "SWING_SETTINGS is dict")

    label = get_quality_label(9)
    _assert(label["label"] == "Excellent", "score 9 = Excellent")

    is_valid = validate_settings()
    _assert(is_valid, "settings validation passes")


# =============================================================================
# TEST 2: Shared Swing Detection Helper
# =============================================================================
def test_swing_detection():
    """Test shared swing detection helper"""
    print("\n" + "=" * 50)
    print("TEST 2: Swing Detection Helper")
    print("=" * 50)

    from queen.helpers.swing_detection import (
        find_swing_points,
        find_swing_prices,
        find_swing_highs,
        find_swing_lows,
        SwingPoint,
        SwingType,
    )

    df = _make_test_df(50)

    points = find_swing_points(df, max_points=5)
    _assert(isinstance(points, list), "find_swing_points returns list")
    if points:
        _assert(isinstance(points[0], SwingPoint), "returns SwingPoint objects")
        _assert(hasattr(points[0], "type"), "SwingPoint has type")
        _assert(hasattr(points[0], "price"), "SwingPoint has price")
        _assert(hasattr(points[0], "bar_index"), "SwingPoint has bar_index")

    highs, lows = find_swing_prices(df, max_points=3)
    _assert(isinstance(highs, list), "find_swing_prices returns highs list")
    _assert(isinstance(lows, list), "find_swing_prices returns lows list")

    swing_highs = find_swing_highs(df, max_points=3)
    swing_lows = find_swing_lows(df, max_points=3)
    _assert(all(s.type == SwingType.HIGH for s in swing_highs), "find_swing_highs returns only highs")
    _assert(all(s.type == SwingType.LOW for s in swing_lows), "find_swing_lows returns only lows")


# =============================================================================
# TEST 3: FVG Detection
# =============================================================================
def test_fvg_detection():
    """Test FVG detection module"""
    print("\n" + "=" * 50)
    print("TEST 3: FVG Detection")
    print("=" * 50)

    from queen.technicals.microstructure.fvg import (
        detect_fvg,
        summarize_fvg,
        attach_fvg_signals,
        FVGResult,
    )

    df = _make_test_df(100, with_gaps=True)

    result = detect_fvg(df, lookback=50)
    _assert(isinstance(result, FVGResult), "detect_fvg returns FVGResult")
    _assert(isinstance(result.bullish_zones, list), "bullish_zones is list")
    _assert(isinstance(result.bearish_zones, list), "bearish_zones is list")
    _assert(result.bias in ["bullish", "bearish", "neutral"], f"bias is valid: {result.bias}")

    summary = summarize_fvg(df)
    _assert(isinstance(summary, dict), "summarize_fvg returns dict")
    _assert("fvg_bias" in summary, "summary has fvg_bias")

    df_with_fvg = attach_fvg_signals(df)
    _assert("fvg_bias" in df_with_fvg.columns, "attach adds fvg_bias column")


# =============================================================================
# TEST 4: Volume Confirmation
# =============================================================================
def test_volume_confirmation():
    """Test Volume Confirmation module"""
    print("\n" + "=" * 50)
    print("TEST 4: Volume Confirmation")
    print("=" * 50)

    from queen.technicals.indicators.volume_confirmation import (
        compute_rvol,
        detect_volume_spike,
        summarize_volume_confirmation,
        validate_breakout_volume,
    )

    df = _make_test_df(100, with_spikes=True)

    df_rvol = compute_rvol(df)
    _assert("rvol" in df_rvol.columns, "compute_rvol adds rvol column")
    _assert("rvol_label" in df_rvol.columns, "compute_rvol adds rvol_label column")

    spikes = detect_volume_spike(df_rvol, threshold=2.0)
    _assert(isinstance(spikes, list), "detect_volume_spike returns list")

    summary = summarize_volume_confirmation(df)
    _assert(isinstance(summary, dict), "summarize returns dict")
    _assert("current_rvol" in summary, "summary has current_rvol")

    validation = validate_breakout_volume(df_rvol)
    _assert(isinstance(validation, dict), "validate_breakout_volume returns dict")


# =============================================================================
# TEST 5: Volume Profile
# =============================================================================
def test_volume_profile():
    """Test Volume Profile module"""
    print("\n" + "=" * 50)
    print("TEST 5: Volume Profile")
    print("=" * 50)

    from queen.technicals.indicators.volume_profile import (
        calculate_volume_profile,
        get_poc,
        get_value_area,
        summarize_volume_profile,
        VolumeProfileResult,
    )

    df = _make_test_df(60)

    result = calculate_volume_profile(df, num_bins=30)
    _assert(isinstance(result, VolumeProfileResult), "returns VolumeProfileResult")
    _assert(result.poc > 0, f"POC is positive: {result.poc:.2f}")
    _assert(result.vah >= result.val, "VAH >= VAL")
    _assert(isinstance(result.bins, list), "bins is list")

    poc = get_poc(df)
    _assert(poc > 0, f"get_poc returns positive: {poc:.2f}")

    val, vah = get_value_area(df)
    _assert(vah >= val, "value area valid")

    summary = summarize_volume_profile(df)
    _assert("poc" in summary, "summary has poc")
    _assert("vah" in summary, "summary has vah")


# =============================================================================
# TEST 6: Delta Volume
# =============================================================================
def test_delta_volume():
    """Test Delta Volume module"""
    print("\n" + "=" * 50)
    print("TEST 6: Delta Volume")
    print("=" * 50)

    from queen.technicals.indicators.delta_volume import (
        calculate_delta,
        calculate_cumulative_delta,
        detect_delta_divergence,
        summarize_delta,
        DeltaResult,
    )

    df = _make_test_df(50, trend="up")

    result = calculate_delta(df)
    _assert(isinstance(result, DeltaResult), "returns DeltaResult")
    _assert(isinstance(result.bars, list), "bars is list")
    _assert(result.delta_trend in ["rising", "falling", "flat"], f"trend valid: {result.delta_trend}")
    _assert(isinstance(result.buyers_in_control, bool), "buyers_in_control is bool")

    cum_delta = calculate_cumulative_delta(df)
    _assert(isinstance(cum_delta, float), "cumulative delta is float")

    div, div_type = detect_delta_divergence(df)
    _assert(isinstance(div, bool), "divergence is bool")

    summary = summarize_delta(df)
    _assert("cumulative_delta" in summary, "summary has cumulative_delta")


# =============================================================================
# TEST 7: VWAP with Bands
# =============================================================================
def test_vwap():
    """Test VWAP with Standard Deviation Bands"""
    print("\n" + "=" * 50)
    print("TEST 7: VWAP with Bands")
    print("=" * 50)

    from queen.technicals.microstructure.vwap import (
        detect_vwap,
        detect_vwap_bands,
        analyze_vwap,
        summarize_vwap,
        VWAPState,
        VWAPBands,
        VWAPResult,
    )

    df = _make_test_df(50)

    state = detect_vwap(df)
    _assert(isinstance(state, VWAPState), "detect_vwap returns VWAPState")
    _assert(state.vwap > 0, f"VWAP positive: {state.vwap:.2f}")
    _assert(state.zone in ["above", "at", "below"], f"zone valid: {state.zone}")

    bands = detect_vwap_bands(df)
    _assert(isinstance(bands, VWAPBands), "detect_vwap_bands returns VWAPBands")
    _assert(bands.upper_1 > bands.vwap, "upper_1 > vwap")
    _assert(bands.lower_1 < bands.vwap, "lower_1 < vwap")
    _assert(bands.upper_2 > bands.upper_1, "upper_2 > upper_1")
    _assert(bands.std_dev > 0, f"std_dev positive: {bands.std_dev:.2f}")

    result = analyze_vwap(df)
    _assert(isinstance(result, VWAPResult), "analyze_vwap returns VWAPResult")
    _assert(isinstance(result.is_overbought, bool), "is_overbought is bool")

    summary = summarize_vwap(df)
    _assert("std_dev" in summary, "summary has std_dev")


# =============================================================================
# TEST 8: False Breakout Patterns
# =============================================================================
def test_false_breakout():
    """Test False Breakout Pattern Detection"""
    print("\n" + "=" * 50)
    print("TEST 8: False Breakout Patterns")
    print("=" * 50)

    from queen.technicals.patterns.false_breakout import (
        detect_swing_failure,
        detect_trap_pattern,
        summarize_false_breakout_risk,
        FalseBreakoutRisk,
    )

    df = _make_test_df(50)

    sfp = detect_swing_failure(df)
    _assert(sfp is None or hasattr(sfp, "pattern_type"), "SFP returns None or signal")

    trap = detect_trap_pattern(df)
    _assert(trap is None or hasattr(trap, "pattern_type"), "Trap returns None or signal")

    risk = summarize_false_breakout_risk(df)
    _assert(isinstance(risk, FalseBreakoutRisk), "risk is FalseBreakoutRisk")
    _assert(risk.risk_level in ["low", "medium", "high", "very_high"], f"risk_level valid: {risk.risk_level}")
    _assert(0 <= risk.risk_score <= 100, f"risk_score valid: {risk.risk_score}")


# =============================================================================
# TEST 9: Order Blocks
# =============================================================================
def test_order_blocks():
    """Test Order Blocks detection"""
    print("\n" + "=" * 50)
    print("TEST 9: Order Blocks")
    print("=" * 50)

    from queen.technicals.microstructure.order_blocks import (
        detect_order_blocks,
        summarize_order_blocks,
        OrderBlockResult,
    )

    df = _make_test_df(80, trend="up")

    result = detect_order_blocks(df, lookback=50)
    _assert(isinstance(result, OrderBlockResult), "returns OrderBlockResult")
    _assert(isinstance(result.bullish_obs, list), "bullish_obs is list")
    _assert(isinstance(result.bearish_obs, list), "bearish_obs is list")
    _assert(result.bias in ["bullish", "bearish", "neutral"], f"bias valid: {result.bias}")

    summary = summarize_order_blocks(df)
    _assert(isinstance(summary, dict), "summarize returns dict")


# =============================================================================
# TEST 10: Liquidity Detection
# =============================================================================
def test_liquidity():
    """Test Liquidity Sweeps and Pools"""
    print("\n" + "=" * 50)
    print("TEST 10: Liquidity Detection")
    print("=" * 50)

    from queen.technicals.microstructure.liquidity import (
        detect_liquidity_sweeps,
        detect_liquidity_pools,
        summarize_liquidity,
        LiquidityResult,
    )

    df = _make_test_df(60)

    sweeps = detect_liquidity_sweeps(df)
    _assert(isinstance(sweeps, LiquidityResult), "returns LiquidityResult")
    _assert(isinstance(sweeps.sweeps, list), "sweeps is list")

    # detect_liquidity_pools returns tuple (buy_side, sell_side)
    buy_pools, sell_pools = detect_liquidity_pools(df)
    _assert(isinstance(buy_pools, list), "buy_pools is list")
    _assert(isinstance(sell_pools, list), "sell_pools is list")

    summary = summarize_liquidity(df)
    _assert(isinstance(summary, dict), "summarize returns dict")


# =============================================================================
# TEST 11: Breaker Blocks
# =============================================================================
def test_breaker_blocks():
    """Test Breaker Blocks detection"""
    print("\n" + "=" * 50)
    print("TEST 11: Breaker Blocks")
    print("=" * 50)

    from queen.technicals.microstructure.breaker_blocks import (
        detect_breaker_blocks,
        summarize_breaker_blocks,
        BreakerBlockResult,
    )

    df = _make_test_df(80)

    result = detect_breaker_blocks(df, lookback=50)
    _assert(isinstance(result, BreakerBlockResult), "returns BreakerBlockResult")
    _assert(isinstance(result.bullish_breakers, list), "bullish_breakers is list")
    _assert(isinstance(result.bearish_breakers, list), "bearish_breakers is list")

    summary = summarize_breaker_blocks(df)
    _assert(isinstance(summary, dict), "summarize returns dict")


# =============================================================================
# TEST 12: BOS/CHoCH
# =============================================================================
def test_bos_choch():
    """Test Break of Structure and Change of Character"""
    print("\n" + "=" * 50)
    print("TEST 12: BOS/CHoCH")
    print("=" * 50)

    from queen.technicals.microstructure.bos_choch import (
        detect_bos,
        detect_choch,
        analyze_market_structure,
        summarize_bos_choch,
        MarketStructureResult,
        TrendDirection,
    )

    df = _make_test_df(60, trend="up")

    bos_signals = detect_bos(df)
    _assert(isinstance(bos_signals, list), "detect_bos returns list")

    choch_signals = detect_choch(df)
    _assert(isinstance(choch_signals, list), "detect_choch returns list")

    result = analyze_market_structure(df)
    _assert(isinstance(result, MarketStructureResult), "returns MarketStructureResult")
    _assert(result.structure_bias in ["bullish", "bearish", "neutral"], f"bias valid: {result.structure_bias}")

    summary = summarize_bos_choch(df)
    _assert("current_trend" in summary, "summary has current_trend")


# =============================================================================
# TEST 13: Mitigation Blocks
# =============================================================================
def test_mitigation_blocks():
    """Test Mitigation Block tracking"""
    print("\n" + "=" * 50)
    print("TEST 13: Mitigation Blocks")
    print("=" * 50)

    from queen.technicals.microstructure.mitigation_blocks import (
        track_mitigation_status,
        get_unmitigated_obs,
        summarize_mitigation,
        MitigationResult,
    )

    df = _make_test_df(80)

    result = track_mitigation_status(df, lookback=60)
    _assert(isinstance(result, MitigationResult), "returns MitigationResult")
    _assert(isinstance(result.all_blocks, list), "all_blocks is list")
    _assert(isinstance(result.unmitigated, list), "unmitigated is list")

    unmitigated = get_unmitigated_obs(df)
    _assert(isinstance(unmitigated, list), "get_unmitigated_obs returns list")

    summary = summarize_mitigation(df)
    _assert(isinstance(summary, dict), "summarize returns dict")


# =============================================================================
# TEST 14: Premium/Discount Zones
# =============================================================================
def test_premium_discount():
    """Test Premium/Discount Zone analysis"""
    print("\n" + "=" * 50)
    print("TEST 14: Premium/Discount Zones")
    print("=" * 50)

    from queen.technicals.microstructure.premium_discount import (
        analyze_premium_discount,
        get_zone_for_price,
        is_discount_zone,
        is_premium_zone,
        summarize_premium_discount,
        PremiumDiscountResult,
        PriceZone,
    )

    df = _make_test_df(60)

    result = analyze_premium_discount(df, lookback=50)
    _assert(isinstance(result, PremiumDiscountResult), "returns PremiumDiscountResult")
    _assert(result.range_high >= result.range_low, "range_high >= range_low")
    _assert(result.equilibrium > 0, f"equilibrium positive: {result.equilibrium:.2f}")
    _assert(isinstance(result.current_zone, PriceZone), "current_zone is PriceZone")
    _assert(result.bias in ["bullish", "bearish", "neutral"], f"bias valid: {result.bias}")

    zone = get_zone_for_price(100.0, df)
    _assert(isinstance(zone, PriceZone), "get_zone_for_price returns PriceZone")

    is_disc = is_discount_zone(df)
    is_prem = is_premium_zone(df)
    _assert(isinstance(is_disc, bool), "is_discount_zone returns bool")
    _assert(isinstance(is_prem, bool), "is_premium_zone returns bool")

    summary = summarize_premium_discount(df)
    _assert("current_zone" in summary, "summary has current_zone")


# =============================================================================
# TEST 15: Wyckoff Patterns (9 patterns)
# =============================================================================
def test_wyckoff():
    """Test all Wyckoff patterns"""
    print("\n" + "=" * 50)
    print("TEST 15: Wyckoff Patterns (9 patterns)")
    print("=" * 50)

    from queen.technicals.microstructure.wyckoff import (
        detect_spring,
        detect_upthrust,
        detect_selling_climax,
        detect_buying_climax,
        detect_sos,
        detect_sow,
        detect_automatic_rally,
        detect_secondary_test,
        identify_wyckoff_phase,
        analyze_wyckoff,
        summarize_wyckoff,
        WyckoffResult,
        WyckoffPhase,
    )

    df = _make_test_df(80, with_spikes=True)

    spring = detect_spring(df)
    _assert(spring is None or hasattr(spring, "signal_type"), "spring returns None or signal")

    upthrust = detect_upthrust(df)
    _assert(upthrust is None or hasattr(upthrust, "signal_type"), "upthrust returns None or signal")

    sc = detect_selling_climax(df)
    _assert(sc is None or hasattr(sc, "signal_type"), "selling_climax returns None or signal")

    bc = detect_buying_climax(df)
    _assert(bc is None or hasattr(bc, "signal_type"), "buying_climax returns None or signal")

    sos = detect_sos(df)
    _assert(sos is None or hasattr(sos, "signal_type"), "SOS returns None or signal")

    sow = detect_sow(df)
    _assert(sow is None or hasattr(sow, "signal_type"), "SOW returns None or signal")

    ar = detect_automatic_rally(df)
    _assert(ar is None or hasattr(ar, "signal_type"), "automatic_rally returns None or signal")

    st = detect_secondary_test(df)
    _assert(st is None or hasattr(st, "signal_type"), "secondary_test returns None or signal")

    phase = identify_wyckoff_phase(df)
    _assert(isinstance(phase, WyckoffPhase), f"phase is WyckoffPhase: {phase}")

    result = analyze_wyckoff(df)
    _assert(isinstance(result, WyckoffResult), "analyze_wyckoff returns WyckoffResult")
    _assert(isinstance(result.signals, list), "signals is list")
    _assert(isinstance(result.estimated_phase, WyckoffPhase), "estimated_phase is WyckoffPhase")
    _assert(result.bias in ["bullish", "bearish", "neutral"], f"bias valid: {result.bias}")

    summary = summarize_wyckoff(df)
    _assert("wyckoff_phase" in summary, "summary has wyckoff_phase")
    _assert("sos_detected" in summary, "summary has sos_detected")


# =============================================================================
# TEST 16: Breakout Validator (Integration)
# =============================================================================
def test_breakout_validator():
    """Test integrated Breakout Validator"""
    print("\n" + "=" * 50)
    print("TEST 16: Breakout Validator (Integration)")
    print("=" * 50)

    from queen.technicals.signals.breakout_validator import (
        validate_breakout,
        calculate_breakout_score,
        attach_breakout_validation,
        BreakoutValidationResult,
    )

    df = _make_test_df(60, with_spikes=True, trend="up")

    result = validate_breakout(
        df,
        breakout_level=100.0,
        direction="up",
        htf_trend="bullish",
    )

    _assert(isinstance(result, BreakoutValidationResult), "returns BreakoutValidationResult")
    _assert(1 <= result.score <= 10, f"score in range 1-10: {result.score}")
    _assert(isinstance(result.is_valid, bool), "is_valid is bool")
    _assert(isinstance(result.is_strong, bool), "is_strong is bool")
    _assert(result.quality_label in ["Excellent", "Good", "Fair", "Weak", "Poor"],
            f"quality_label valid: {result.quality_label}")
    _assert(isinstance(result.components, list), "components is list")
    _assert(isinstance(result.verdict, str), "verdict is string")

    score = calculate_breakout_score(df, direction="up")
    _assert(1 <= score <= 10, f"quick score in range: {score}")

    df_attached = attach_breakout_validation(df)
    _assert("breakout_score" in df_attached.columns, "attach adds breakout_score")
    _assert("breakout_valid" in df_attached.columns, "attach adds breakout_valid")


# =============================================================================
# MAIN RUNNER
# =============================================================================
def run_all():
    """Run all tests"""
    global _passed, _failed
    _passed = 0
    _failed = 0

    print("\n" + "=" * 60)
    print("COMPREHENSIVE BREAKOUT & SMC MODULES SMOKE TESTS")
    print("=" * 60)

    tests = [
        ("Settings", test_settings),
        ("Swing Detection Helper", test_swing_detection),
        ("FVG Detection", test_fvg_detection),
        ("Volume Confirmation", test_volume_confirmation),
        ("Volume Profile", test_volume_profile),
        ("Delta Volume", test_delta_volume),
        ("VWAP with Bands", test_vwap),
        ("False Breakout Patterns", test_false_breakout),
        ("Order Blocks", test_order_blocks),
        ("Liquidity Detection", test_liquidity),
        ("Breaker Blocks", test_breaker_blocks),
        ("BOS/CHoCH", test_bos_choch),
        ("Mitigation Blocks", test_mitigation_blocks),
        ("Premium/Discount Zones", test_premium_discount),
        ("Wyckoff Patterns", test_wyckoff),
        ("Breakout Validator", test_breakout_validator),
    ]

    for name, test_fn in tests:
        try:
            test_fn()
        except ImportError as e:
            print(f"\n⚠ SKIPPED {name}: Module not found - {e}")
        except Exception as e:
            print(f"\n❌ ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            _failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {_passed} passed, {_failed} failed")
    print(f"TOTAL TESTS: {_passed + _failed}")
    print("=" * 60)

    return _failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
