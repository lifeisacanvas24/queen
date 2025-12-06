"""Queen Cockpit - Signal Pipeline
Integrates all technical modules to generate trading signals

This is the core engine that:
1. Receives market data (ticks/candles)
2. Runs technical analysis modules
3. Generates trading signals
4. Stores signals in database
5. Pushes updates to dashboard

Version: 1.0
"""

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False
    pl = None

from database.models import (
    Direction,
    QueenDatabase,
    Signal,
    SignalStatus,
    Timeframe,
    get_db,
)

logger = logging.getLogger("queen.pipeline")


# ============================================
# Module Imports (with fallbacks)
# ============================================

# Try importing Queen technical modules
HAS_FVG = False
HAS_ORDER_BLOCKS = False
HAS_WYCKOFF = False
HAS_BOS_CHOCH = False
HAS_LIQUIDITY = False
HAS_VOLUME = False
HAS_BREAKOUT = False
HAS_CORE = False
HAS_MACD = False
HAS_ATR = False

detect_fvg_zones = None
detect_order_blocks = None
detect_wyckoff_events = None
identify_wyckoff_phase = None
detect_structure_breaks = None
detect_liquidity_sweeps = None
compute_rvol = None
detect_volume_spike = None
detect_accumulation_distribution = None
validate_breakout = None
compute_rsi = None
compute_ema = None
compute_macd = None
compute_atr = None

try:
    from queen.technicals.microstructure.fvg import detect_fvg_zones
    HAS_FVG = True
except ImportError:
    pass

try:
    from queen.technicals.microstructure.order_blocks import detect_order_blocks
    HAS_ORDER_BLOCKS = True
except ImportError:
    pass

try:
    from queen.technicals.microstructure.wyckoff import (
        detect_wyckoff_events,
        identify_wyckoff_phase,
    )
    HAS_WYCKOFF = True
except ImportError:
    pass

try:
    from queen.technicals.microstructure.bos_choch import detect_structure_breaks
    HAS_BOS_CHOCH = True
except ImportError:
    pass

try:
    from queen.technicals.microstructure.liquidity import detect_liquidity_sweeps
    HAS_LIQUIDITY = True
except ImportError:
    pass

try:
    from queen.technicals.indicators.volume_confirmation import (
        compute_rvol,
        detect_accumulation_distribution,
        detect_volume_spike,
    )
    HAS_VOLUME = True
except ImportError:
    pass

try:
    from queen.technicals.signals.breakout_validator import validate_breakout
    HAS_BREAKOUT = True
except ImportError:
    pass

try:
    from queen.technicals.indicators.core import compute_ema, compute_rsi
    HAS_CORE = True
except ImportError:
    pass

try:
    from queen.technicals.indicators.momentum_macd import compute_macd
    HAS_MACD = True
except ImportError:
    pass

try:
    from queen.technicals.indicators.advanced import compute_atr
    HAS_ATR = True
except ImportError:
    pass


# ============================================
# Signal Generation Settings
# ============================================

@dataclass
class PipelineSettings:
    """Pipeline configuration"""

    # Score thresholds
    min_score_scalp: float = 6.0
    min_score_intraday: float = 6.5
    min_score_btst: float = 7.0
    min_score_swing: float = 7.0
    min_score_positional: float = 7.5
    min_score_investment: float = 8.0

    # Signal expiry (hours)
    expiry_scalp: int = 1
    expiry_intraday: int = 4
    expiry_btst: int = 24
    expiry_swing: int = 72
    expiry_positional: int = 168  # 1 week
    expiry_investment: int = 720  # 1 month

    # R:R requirements
    min_rr_scalp: float = 1.5
    min_rr_intraday: float = 2.0
    min_rr_swing: float = 2.5

    # Volume requirements
    min_rvol: float = 1.5

    # Update intervals (seconds)
    scan_interval: int = 60  # How often to scan for new signals


# ============================================
# Analysis Result Classes
# ============================================

@dataclass
class TechnicalAnalysis:
    """Technical analysis results"""

    # Core indicators
    rsi: Optional[float] = None
    rsi_status: str = "neutral"
    macd_signal: str = "neutral"  # bullish/bearish/neutral
    macd_histogram: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None
    above_ema_20: bool = False
    above_ema_50: bool = False
    atr: Optional[float] = None
    atr_pct: Optional[float] = None

    # Volume
    rvol: Optional[float] = None
    volume_spike: bool = False
    accumulation: bool = False
    distribution: bool = False

    # SMC
    fvg_above: Optional[str] = None
    fvg_below: Optional[str] = None
    order_block: Optional[Dict] = None
    bos: bool = False
    choch: bool = False
    liquidity_sweep: bool = False
    premium_zone: bool = False
    discount_zone: bool = False

    # Wyckoff
    wyckoff_phase: Optional[str] = None
    wyckoff_event: Optional[str] = None  # spring, upthrust, etc.

    # Breakout
    breakout_score: Optional[float] = None
    breakout_quality: Optional[str] = None


@dataclass
class SignalCandidate:
    """A potential trading signal before scoring"""

    symbol: str
    instrument_key: str
    timeframe: str
    direction: str
    action: str
    current_price: float
    entry_price: float
    target_price: float
    target2_price: Optional[float] = None
    stop_loss: float = 0
    analysis: TechnicalAnalysis = field(default_factory=TechnicalAnalysis)
    tags: List[str] = field(default_factory=list)
    context: List[Dict] = field(default_factory=list)
    raw_score: float = 0
    confidence: float = 0


# ============================================
# Signal Pipeline
# ============================================

class SignalPipeline:
    """Main signal generation pipeline.

    Usage:
        pipeline = SignalPipeline()

        # Process candle data for a symbol
        signals = await pipeline.analyze_symbol(
            symbol="RELIANCE",
            instrument_key="NSE_EQ|INE002A01018",
            candles=df,  # Polars DataFrame with OHLCV
            timeframe="scalp"
        )

        # Or run full scan
        await pipeline.run_scan(symbols_df)
    """

    def __init__(
        self,
        db: Optional[QueenDatabase] = None,
        settings: Optional[PipelineSettings] = None,
        on_signal: Optional[Callable[[Signal], None]] = None,
    ):
        """Initialize pipeline.

        Args:
            db: Database instance (uses global if None)
            settings: Pipeline settings
            on_signal: Callback when new signal is generated

        """
        self.db = db or get_db()
        self.settings = settings or PipelineSettings()
        self._on_signal_callback = on_signal
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None

        # Log available modules
        self._log_module_status()

    def _log_module_status(self):
        """Log which modules are available"""
        modules = {
            "FVG": HAS_FVG,
            "Order Blocks": HAS_ORDER_BLOCKS,
            "Wyckoff": HAS_WYCKOFF,
            "BOS/CHoCH": HAS_BOS_CHOCH,
            "Liquidity": HAS_LIQUIDITY,
            "Volume": HAS_VOLUME,
            "Breakout": HAS_BREAKOUT,
            "Core (RSI/EMA)": HAS_CORE,
            "MACD": HAS_MACD,
            "ATR": HAS_ATR,
        }

        available = [k for k, v in modules.items() if v]
        missing = [k for k, v in modules.items() if not v]

        if available:
            logger.info(f"Available modules: {', '.join(available)}")
        if missing:
            logger.warning(f"Missing modules: {', '.join(missing)}")

    # ==================== Analysis ====================

    def _run_technical_analysis(
        self,
        df: "pl.DataFrame",
        current_price: float
    ) -> TechnicalAnalysis:
        """Run all technical analysis on candle data.

        Args:
            df: Polars DataFrame with columns: datetime, open, high, low, close, volume
            current_price: Current market price

        Returns:
            TechnicalAnalysis object with all results

        """
        analysis = TechnicalAnalysis()

        if not HAS_POLARS or df is None or len(df) < 20:
            return analysis

        close = df["close"].to_numpy()
        high = df["high"].to_numpy()
        low = df["low"].to_numpy()
        volume = df["volume"].to_numpy() if "volume" in df.columns else None

        # Core indicators
        if HAS_CORE and compute_rsi:
            try:
                rsi_series = compute_rsi(df, period=14)
                analysis.rsi = float(rsi_series[-1]) if len(rsi_series) > 0 else None
                if analysis.rsi:
                    if analysis.rsi >= 70:
                        analysis.rsi_status = "overbought"
                    elif analysis.rsi >= 60:
                        analysis.rsi_status = "bullish"
                    elif analysis.rsi <= 30:
                        analysis.rsi_status = "oversold"
                    elif analysis.rsi <= 40:
                        analysis.rsi_status = "bearish"
            except Exception as e:
                logger.debug(f"RSI error: {e}")

        if HAS_CORE and compute_ema:
            try:
                ema_20 = compute_ema(df, period=20)
                ema_50 = compute_ema(df, period=50)

                analysis.ema_20 = float(ema_20[-1]) if len(ema_20) > 0 else None
                analysis.ema_50 = float(ema_50[-1]) if len(ema_50) > 0 else None

                if analysis.ema_20:
                    analysis.above_ema_20 = current_price > analysis.ema_20
                if analysis.ema_50:
                    analysis.above_ema_50 = current_price > analysis.ema_50

                if len(df) >= 200:
                    ema_200 = compute_ema(df, period=200)
                    analysis.ema_200 = float(ema_200[-1]) if len(ema_200) > 0 else None
            except Exception as e:
                logger.debug(f"EMA error: {e}")

        # MACD
        if HAS_MACD and compute_macd:
            try:
                macd_result = compute_macd(df)
                if macd_result is not None:
                    macd_line = macd_result.get("macd", [])
                    signal_line = macd_result.get("signal", [])
                    histogram = macd_result.get("histogram", [])

                    if len(histogram) > 0:
                        analysis.macd_histogram = float(histogram[-1])
                        if len(histogram) > 1:
                            if histogram[-1] > 0 and histogram[-1] > histogram[-2]:
                                analysis.macd_signal = "bullish"
                            elif histogram[-1] < 0 and histogram[-1] < histogram[-2]:
                                analysis.macd_signal = "bearish"
            except Exception as e:
                logger.debug(f"MACD error: {e}")

        # ATR
        if HAS_ATR and compute_atr:
            try:
                atr_series = compute_atr(df, period=14)
                if len(atr_series) > 0:
                    analysis.atr = float(atr_series[-1])
                    analysis.atr_pct = (analysis.atr / current_price) * 100 if current_price else None
            except Exception as e:
                logger.debug(f"ATR error: {e}")

        # Volume analysis
        if HAS_VOLUME and volume is not None:
            try:
                if compute_rvol:
                    rvol_series = compute_rvol(df)
                    analysis.rvol = float(rvol_series[-1]) if len(rvol_series) > 0 else None

                if detect_volume_spike:
                    spikes = detect_volume_spike(df)
                    analysis.volume_spike = bool(spikes[-1]) if len(spikes) > 0 else False

                if detect_accumulation_distribution:
                    ad_result = detect_accumulation_distribution(df)
                    if ad_result:
                        analysis.accumulation = ad_result.get("accumulation", False)
                        analysis.distribution = ad_result.get("distribution", False)
            except Exception as e:
                logger.debug(f"Volume error: {e}")

        # SMC - FVG
        if HAS_FVG and detect_fvg_zones:
            try:
                fvg_result = detect_fvg_zones(df)
                if fvg_result:
                    bullish_fvgs = fvg_result.get("bullish", [])
                    bearish_fvgs = fvg_result.get("bearish", [])

                    # Find nearest FVG zones
                    for fvg in bearish_fvgs:  # Above current price
                        if fvg.get("low", 0) > current_price:
                            analysis.fvg_above = f"{fvg.get('low'):.2f} - {fvg.get('high'):.2f}"
                            break

                    for fvg in reversed(bullish_fvgs):  # Below current price
                        if fvg.get("high", float("inf")) < current_price:
                            analysis.fvg_below = f"{fvg.get('low'):.2f} - {fvg.get('high'):.2f}"
                            break
            except Exception as e:
                logger.debug(f"FVG error: {e}")

        # SMC - Order Blocks
        if HAS_ORDER_BLOCKS and detect_order_blocks:
            try:
                ob_result = detect_order_blocks(df)
                if ob_result:
                    # Get nearest unmitigated order block
                    blocks = ob_result.get("blocks", [])
                    for block in blocks:
                        if not block.get("mitigated", True):
                            analysis.order_block = block
                            break
            except Exception as e:
                logger.debug(f"Order Block error: {e}")

        # SMC - BOS/CHoCH
        if HAS_BOS_CHOCH and detect_structure_breaks:
            try:
                structure = detect_structure_breaks(df)
                if structure:
                    analysis.bos = structure.get("bos", False)
                    analysis.choch = structure.get("choch", False)
            except Exception as e:
                logger.debug(f"BOS/CHoCH error: {e}")

        # SMC - Liquidity
        if HAS_LIQUIDITY and detect_liquidity_sweeps:
            try:
                sweeps = detect_liquidity_sweeps(df)
                if sweeps and len(sweeps) > 0:
                    analysis.liquidity_sweep = True
            except Exception as e:
                logger.debug(f"Liquidity error: {e}")

        # Wyckoff
        if HAS_WYCKOFF:
            try:
                if identify_wyckoff_phase:
                    phase = identify_wyckoff_phase(df)
                    analysis.wyckoff_phase = phase

                if detect_wyckoff_events:
                    events = detect_wyckoff_events(df)
                    if events and len(events) > 0:
                        analysis.wyckoff_event = events[-1].get("event")
            except Exception as e:
                logger.debug(f"Wyckoff error: {e}")

        # Breakout validation
        if HAS_BREAKOUT and validate_breakout:
            try:
                breakout = validate_breakout(df)
                if breakout:
                    analysis.breakout_score = breakout.get("score")
                    analysis.breakout_quality = breakout.get("quality")
            except Exception as e:
                logger.debug(f"Breakout error: {e}")

        return analysis

    def _calculate_signal_score(
        self,
        analysis: TechnicalAnalysis,
        timeframe: str,
        direction: str
    ) -> float:
        """Calculate signal score (0-10) based on analysis results.

        Scoring weights vary by timeframe.
        """
        score = 5.0  # Base score

        is_long = direction == Direction.LONG.value

        # RSI contribution (+/- 1.0)
        if analysis.rsi:
            if is_long:
                if analysis.rsi < 40:  # Oversold = bullish
                    score += 0.8
                elif analysis.rsi > 70:  # Overbought = bearish for long
                    score -= 0.5
            else:
                if analysis.rsi > 60:  # Overbought = bearish
                    score += 0.8
                elif analysis.rsi < 30:
                    score -= 0.5

        # MACD contribution (+/- 0.8)
        if analysis.macd_signal == "bullish" and is_long or analysis.macd_signal == "bearish" and not is_long:
            score += 0.8
        elif analysis.macd_signal == "bullish" and not is_long or analysis.macd_signal == "bearish" and is_long:
            score -= 0.5

        # EMA alignment (+/- 0.6)
        if is_long:
            if analysis.above_ema_20 and analysis.above_ema_50:
                score += 0.6
            elif not analysis.above_ema_20 and not analysis.above_ema_50:
                score -= 0.4
        else:
            if not analysis.above_ema_20 and not analysis.above_ema_50:
                score += 0.6
            elif analysis.above_ema_20 and analysis.above_ema_50:
                score -= 0.4

        # Volume contribution (+0.8)
        if analysis.rvol and analysis.rvol >= self.settings.min_rvol:
            score += 0.5
            if analysis.volume_spike:
                score += 0.3

        if is_long and analysis.accumulation or not is_long and analysis.distribution:
            score += 0.5

        # SMC contribution (+1.5)
        if analysis.fvg_below and is_long:
            score += 0.4  # Support from FVG
        if analysis.fvg_above and not is_long:
            score += 0.4  # Resistance from FVG

        if analysis.order_block:
            ob_type = analysis.order_block.get("type", "")
            if (ob_type == "bullish" and is_long) or (ob_type == "bearish" and not is_long):
                score += 0.5

        if analysis.bos:
            score += 0.3
        if analysis.choch:
            score += 0.3  # Reversal signal

        if analysis.liquidity_sweep:
            score += 0.4  # Potential reversal after sweep

        # Wyckoff contribution (+1.0)
        if analysis.wyckoff_phase:
            if analysis.wyckoff_phase == "accumulation" and is_long or analysis.wyckoff_phase == "distribution" and not is_long:
                score += 0.5
            elif analysis.wyckoff_phase == "markup" and is_long or analysis.wyckoff_phase == "markdown" and not is_long:
                score += 0.3

        if analysis.wyckoff_event:
            event = analysis.wyckoff_event.lower()
            if event == "spring" and is_long or event == "upthrust" and not is_long:
                score += 0.5

        # Breakout contribution (+0.5)
        if analysis.breakout_score:
            score += min(analysis.breakout_score / 20, 0.5)  # Max 0.5 from breakout

        # Clamp score
        return max(0, min(10, score))

    def _build_tags(self, analysis: TechnicalAnalysis, direction: str) -> List[str]:
        """Build display tags from analysis"""
        tags = []

        is_long = direction == Direction.LONG.value

        # Volume tags
        if analysis.rvol and analysis.rvol >= 2.0:
            tags.append(f"RVOL {analysis.rvol:.1f}x")
        if analysis.volume_spike:
            tags.append("Vol Spike")

        # SMC tags
        if analysis.fvg_below and is_long:
            tags.append("FVG Support")
        if analysis.fvg_above and not is_long:
            tags.append("FVG Resistance")
        if analysis.order_block:
            tags.append("Order Block")
        if analysis.bos:
            tags.append("BOS")
        if analysis.choch:
            tags.append("CHoCH")
        if analysis.liquidity_sweep:
            tags.append("Sweep")

        # Wyckoff tags
        if analysis.wyckoff_event:
            tags.append(analysis.wyckoff_event.title())
        if analysis.wyckoff_phase:
            tags.append(analysis.wyckoff_phase.title())

        # Technical tags
        if analysis.rsi_status in ["overbought", "oversold"]:
            tags.append(analysis.rsi_status.title())
        if analysis.macd_signal == "bullish":
            tags.append("MACD ▲")
        elif analysis.macd_signal == "bearish":
            tags.append("MACD ▼")

        # Breakout tag
        if analysis.breakout_quality in ["excellent", "good"]:
            tags.append(f"Breakout ({analysis.breakout_quality})")

        return tags[:6]  # Limit to 6 tags

    def _build_context(self, analysis: TechnicalAnalysis, direction: str) -> List[Dict]:
        """Build context items from analysis"""
        context = []

        is_long = direction == Direction.LONG.value

        # EMA context
        if analysis.above_ema_20:
            context.append({
                "text": "Above 20 EMA",
                "sentiment": "positive" if is_long else "negative"
            })
        else:
            context.append({
                "text": "Below 20 EMA",
                "sentiment": "negative" if is_long else "positive"
            })

        # Volume context
        if analysis.rvol:
            sentiment = "positive" if analysis.rvol >= 1.5 else "neutral"
            context.append({
                "text": f"RVOL: {analysis.rvol:.1f}x",
                "sentiment": sentiment
            })

        # Wyckoff phase context
        if analysis.wyckoff_phase:
            phase = analysis.wyckoff_phase.lower()
            if phase == "accumulation":
                sentiment = "positive" if is_long else "neutral"
            elif phase == "distribution":
                sentiment = "positive" if not is_long else "neutral"
            elif phase == "markup":
                sentiment = "positive" if is_long else "negative"
            elif phase == "markdown":
                sentiment = "positive" if not is_long else "negative"
            else:
                sentiment = "neutral"

            context.append({
                "text": f"Wyckoff: {analysis.wyckoff_phase.title()}",
                "sentiment": sentiment
            })

        # ATR context
        if analysis.atr_pct:
            volatility = "High" if analysis.atr_pct > 2 else "Low" if analysis.atr_pct < 1 else "Normal"
            context.append({
                "text": f"Volatility: {volatility} ({analysis.atr_pct:.1f}%)",
                "sentiment": "neutral"
            })

        return context[:5]  # Limit to 5 context items

    def _calculate_levels(
        self,
        current_price: float,
        analysis: TechnicalAnalysis,
        direction: str,
        timeframe: str
    ) -> Dict[str, float]:
        """Calculate entry, target, and stop loss levels"""
        is_long = direction == Direction.LONG.value

        # Default ATR-based calculation
        atr = analysis.atr or (current_price * 0.01)  # Default 1% if no ATR

        # Multipliers by timeframe
        multipliers = {
            Timeframe.SCALP.value: {"sl": 0.8, "target": 1.5},
            Timeframe.INTRADAY.value: {"sl": 1.2, "target": 2.5},
            Timeframe.BTST.value: {"sl": 1.5, "target": 3.0},
            Timeframe.SWING.value: {"sl": 2.0, "target": 4.0},
            Timeframe.POSITIONAL.value: {"sl": 2.5, "target": 6.0},
            Timeframe.INVESTMENT.value: {"sl": 3.0, "target": 8.0},
        }

        mult = multipliers.get(timeframe, multipliers[Timeframe.INTRADAY.value])

        if is_long:
            entry = current_price
            stop_loss = entry - (atr * mult["sl"])
            target = entry + (atr * mult["target"])
            target2 = entry + (atr * mult["target"] * 1.5)
        else:
            entry = current_price
            stop_loss = entry + (atr * mult["sl"])
            target = entry - (atr * mult["target"])
            target2 = entry - (atr * mult["target"] * 1.5)

        # Adjust based on FVG zones if available
        if analysis.fvg_below and is_long:
            try:
                fvg_low = float(analysis.fvg_below.split(" - ")[0])
                if fvg_low < entry and fvg_low > stop_loss:
                    stop_loss = fvg_low - (atr * 0.2)  # Just below FVG
            except (ValueError, IndexError):
                pass

        if analysis.fvg_above and not is_long:
            try:
                fvg_high = float(analysis.fvg_above.split(" - ")[1])
                if fvg_high > entry and fvg_high < stop_loss:
                    stop_loss = fvg_high + (atr * 0.2)  # Just above FVG
            except (ValueError, IndexError):
                pass

        # Calculate risk/reward
        risk = abs(entry - stop_loss)
        reward = abs(target - entry)
        risk_pct = (risk / entry) * 100 if entry else 0
        reward_pct = (reward / entry) * 100 if entry else 0
        rr_ratio = reward / risk if risk else 0

        return {
            "entry": round(entry, 2),
            "target": round(target, 2),
            "target2": round(target2, 2),
            "stop_loss": round(stop_loss, 2),
            "risk": round(risk, 2),
            "reward": round(reward, 2),
            "risk_pct": round(risk_pct, 2),
            "reward_pct": round(reward_pct, 2),
            "rr_ratio": round(rr_ratio, 2),
        }

    def _determine_action(self, direction: str, timeframe: str, score: float) -> str:
        """Determine the action type for the signal"""
        is_long = direction == Direction.LONG.value

        action_map = {
            Timeframe.SCALP.value: "SCALP_LONG" if is_long else "SCALP_SHORT",
            Timeframe.INTRADAY.value: "INTRADAY_LONG" if is_long else "INTRADAY_SHORT",
            Timeframe.BTST.value: "BTST_BUY" if is_long else "BTST_SELL",
            Timeframe.SWING.value: "SWING_BUY" if is_long else "SWING_SELL",
            Timeframe.POSITIONAL.value: "ACCUMULATE" if is_long else "REDUCE",
            Timeframe.INVESTMENT.value: "CORE_HOLD" if score >= 8.5 else "ACCUMULATE",
        }

        return action_map.get(timeframe, "INTRADAY_LONG" if is_long else "INTRADAY_SHORT")

    def _get_expiry(self, timeframe: str) -> datetime:
        """Get signal expiry time based on timeframe"""
        hours_map = {
            Timeframe.SCALP.value: self.settings.expiry_scalp,
            Timeframe.INTRADAY.value: self.settings.expiry_intraday,
            Timeframe.BTST.value: self.settings.expiry_btst,
            Timeframe.SWING.value: self.settings.expiry_swing,
            Timeframe.POSITIONAL.value: self.settings.expiry_positional,
            Timeframe.INVESTMENT.value: self.settings.expiry_investment,
        }

        hours = hours_map.get(timeframe, 4)
        return datetime.now() + timedelta(hours=hours)

    def _get_min_score(self, timeframe: str) -> float:
        """Get minimum score threshold for timeframe"""
        score_map = {
            Timeframe.SCALP.value: self.settings.min_score_scalp,
            Timeframe.INTRADAY.value: self.settings.min_score_intraday,
            Timeframe.BTST.value: self.settings.min_score_btst,
            Timeframe.SWING.value: self.settings.min_score_swing,
            Timeframe.POSITIONAL.value: self.settings.min_score_positional,
            Timeframe.INVESTMENT.value: self.settings.min_score_investment,
        }

        return score_map.get(timeframe, 6.5)

    # ==================== Main Analysis ====================

    async def analyze_symbol(
        self,
        symbol: str,
        instrument_key: str,
        candles: "pl.DataFrame",
        timeframe: str,
        current_price: Optional[float] = None,
    ) -> List[Signal]:
        """Analyze a symbol and generate signals.

        Args:
            symbol: Trading symbol (e.g., "RELIANCE")
            instrument_key: Upstox instrument key
            candles: Polars DataFrame with OHLCV data
            timeframe: Signal timeframe
            current_price: Current price (uses last close if None)

        Returns:
            List of generated Signal objects

        """
        if not HAS_POLARS or candles is None or len(candles) < 20:
            logger.warning(f"Insufficient data for {symbol}")
            return []

        # Get current price from last candle if not provided
        if current_price is None:
            current_price = float(candles["close"][-1])

        signals = []

        # Run technical analysis
        analysis = self._run_technical_analysis(candles, current_price)

        # Check for long signal
        long_score = self._calculate_signal_score(analysis, timeframe, Direction.LONG.value)
        if long_score >= self._get_min_score(timeframe):
            signal = self._create_signal(
                symbol=symbol,
                instrument_key=instrument_key,
                timeframe=timeframe,
                direction=Direction.LONG.value,
                current_price=current_price,
                analysis=analysis,
                score=long_score
            )
            if signal:
                signals.append(signal)

        # Check for short signal
        short_score = self._calculate_signal_score(analysis, timeframe, Direction.SHORT.value)
        if short_score >= self._get_min_score(timeframe):
            signal = self._create_signal(
                symbol=symbol,
                instrument_key=instrument_key,
                timeframe=timeframe,
                direction=Direction.SHORT.value,
                current_price=current_price,
                analysis=analysis,
                score=short_score
            )
            if signal:
                signals.append(signal)

        return signals

    def _create_signal(
        self,
        symbol: str,
        instrument_key: str,
        timeframe: str,
        direction: str,
        current_price: float,
        analysis: TechnicalAnalysis,
        score: float
    ) -> Optional[Signal]:
        """Create a Signal object from analysis results"""
        # Calculate levels
        levels = self._calculate_levels(current_price, analysis, direction, timeframe)

        # Check R:R requirement
        min_rr_map = {
            Timeframe.SCALP.value: self.settings.min_rr_scalp,
            Timeframe.INTRADAY.value: self.settings.min_rr_intraday,
            Timeframe.SWING.value: self.settings.min_rr_swing,
        }
        min_rr = min_rr_map.get(timeframe, 1.5)

        if levels["rr_ratio"] < min_rr:
            logger.debug(f"{symbol} {direction}: R:R {levels['rr_ratio']:.2f} below minimum {min_rr}")
            return None

        # Build tags and context
        tags = self._build_tags(analysis, direction)
        context = self._build_context(analysis, direction)

        # Build technicals dict for storage
        technicals = {
            "rsi": analysis.rsi,
            "rsi_status": analysis.rsi_status,
            "macd_signal": analysis.macd_signal,
            "ema_20": analysis.ema_20,
            "ema_50": analysis.ema_50,
            "atr": analysis.atr,
            "atr_pct": analysis.atr_pct,
            "rvol": analysis.rvol,
        }

        # Confidence based on score and volume
        confidence = min(100, int(score * 10 + (10 if analysis.rvol and analysis.rvol >= 2 else 0)))

        signal = Signal(
            symbol=symbol,
            instrument_key=instrument_key,
            timeframe=timeframe,
            direction=direction,
            action=self._determine_action(direction, timeframe, score),
            score=round(score, 1),
            entry_price=levels["entry"],
            target_price=levels["target"],
            target2_price=levels["target2"],
            stop_loss=levels["stop_loss"],
            risk_pct=levels["risk_pct"],
            reward_pct=levels["reward_pct"],
            rr_ratio=f"1:{levels['rr_ratio']:.1f}",
            wyckoff_phase=analysis.wyckoff_phase,
            tags=tags,
            technicals=technicals,
            context=context,
            confidence=confidence,
            created_at=datetime.now(),
            expires_at=self._get_expiry(timeframe),
            status=SignalStatus.ACTIVE.value,
        )

        return signal

    # ==================== Signal Storage ====================

    def save_signal(self, signal: Signal) -> int:
        """Save signal to database and notify callback"""
        signal_id = self.db.add_signal(signal)
        signal.id = signal_id

        logger.info(
            f"New signal: {signal.symbol} {signal.action} "
            f"Score: {signal.score} Entry: {signal.entry_price}"
        )

        # Notify callback
        if self._on_signal_callback:
            try:
                self._on_signal_callback(signal)
            except Exception as e:
                logger.error(f"Error in signal callback: {e}")

        return signal_id

    def get_active_signals(self, timeframe: Optional[str] = None) -> List[Signal]:
        """Get active signals from database"""
        # First expire old signals
        self.db.expire_old_signals()

        return self.db.get_active_signals(timeframe=timeframe)

    # ==================== Batch Scanning ====================

    async def scan_universe(
        self,
        universe: List[Dict[str, Any]],
        candle_provider: Callable[[str, str], "pl.DataFrame"],
        timeframes: Optional[List[str]] = None,
    ) -> List[Signal]:
        """Scan multiple symbols for signals.

        Args:
            universe: List of dicts with 'symbol' and 'instrument_key'
            candle_provider: Async function that returns candles for (symbol, timeframe)
            timeframes: List of timeframes to scan (default: all)

        Returns:
            List of generated signals

        """
        if timeframes is None:
            timeframes = [t.value for t in Timeframe]

        all_signals = []

        for item in universe:
            symbol = item["symbol"]
            instrument_key = item["instrument_key"]

            for tf in timeframes:
                try:
                    # Get candles
                    candles = await candle_provider(symbol, tf)

                    if candles is None or len(candles) < 20:
                        continue

                    # Analyze
                    signals = await self.analyze_symbol(
                        symbol=symbol,
                        instrument_key=instrument_key,
                        candles=candles,
                        timeframe=tf
                    )

                    # Save signals
                    for signal in signals:
                        self.save_signal(signal)
                        all_signals.append(signal)

                except Exception as e:
                    logger.error(f"Error scanning {symbol} ({tf}): {e}")

        logger.info(f"Scan complete: {len(all_signals)} signals generated")
        return all_signals

    # ==================== Background Scanner ====================

    async def start_scanner(
        self,
        universe: List[Dict[str, Any]],
        candle_provider: Callable[[str, str], "pl.DataFrame"],
        timeframes: Optional[List[str]] = None,
    ) -> None:
        """Start background scanner loop.

        Args:
            universe: List of symbols to scan
            candle_provider: Function to get candles
            timeframes: Timeframes to scan

        """
        self._running = True

        async def scan_loop():
            while self._running:
                try:
                    await self.scan_universe(universe, candle_provider, timeframes)
                except Exception as e:
                    logger.error(f"Scan error: {e}")

                await asyncio.sleep(self.settings.scan_interval)

        self._scan_task = asyncio.create_task(scan_loop())
        logger.info("Background scanner started")

    async def stop_scanner(self) -> None:
        """Stop background scanner"""
        self._running = False

        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

        logger.info("Background scanner stopped")


# ============================================
# Global Instance
# ============================================

_pipeline: Optional[SignalPipeline] = None


def get_pipeline() -> SignalPipeline:
    """Get global pipeline instance"""
    global _pipeline
    if _pipeline is None:
        _pipeline = SignalPipeline()
    return _pipeline


def init_pipeline(
    db: Optional[QueenDatabase] = None,
    settings: Optional[PipelineSettings] = None,
    on_signal: Optional[Callable[[Signal], None]] = None,
) -> SignalPipeline:
    """Initialize global pipeline"""
    global _pipeline
    _pipeline = SignalPipeline(db=db, settings=settings, on_signal=on_signal)
    return _pipeline


# ============================================
# Module Exports
# ============================================

EXPORTS = {
    "SignalPipeline": SignalPipeline,
    "PipelineSettings": PipelineSettings,
    "TechnicalAnalysis": TechnicalAnalysis,
    "SignalCandidate": SignalCandidate,
    "get_pipeline": get_pipeline,
    "init_pipeline": init_pipeline,
}


# ============================================
# CLI Test
# ============================================

if __name__ == "__main__":
    import numpy as np

    # Test with mock data
    async def test():
        if not HAS_POLARS:
            print("Polars not available, skipping test")
            return

        # Create mock candle data
        dates = pl.datetime_range(
            datetime(2024, 1, 1),
            datetime(2024, 1, 31),
            interval="1h",
            eager=True
        )

        n = len(dates)
        np.random.seed(42)

        # Generate realistic OHLCV
        base_price = 2800
        returns = np.random.randn(n) * 0.005
        closes = base_price * np.cumprod(1 + returns)

        candles = pl.DataFrame({
            "datetime": dates,
            "open": closes * (1 + np.random.randn(n) * 0.002),
            "high": closes * (1 + np.abs(np.random.randn(n) * 0.005)),
            "low": closes * (1 - np.abs(np.random.randn(n) * 0.005)),
            "close": closes,
            "volume": np.random.randint(100000, 1000000, n),
        })

        print(f"Test candles: {len(candles)} rows")
        print(candles.head())

        # Initialize pipeline with in-memory db
        from database.models import QueenDatabase
        db = QueenDatabase(":memory:")
        db.init()

        pipeline = SignalPipeline(db=db)

        # Analyze
        signals = await pipeline.analyze_symbol(
            symbol="RELIANCE",
            instrument_key="NSE_EQ|INE002A01018",
            candles=candles,
            timeframe="intraday"
        )

        print(f"\nGenerated {len(signals)} signals:")
        for sig in signals:
            print(f"  {sig.action} Score: {sig.score} Entry: {sig.entry_price} "
                  f"Target: {sig.target_price} SL: {sig.stop_loss} R:R: {sig.rr_ratio}")
            print(f"    Tags: {sig.tags}")

        db.close()

    asyncio.run(test())
