"""
Queen Cockpit - Card Generator Service
Maps trading signals to card template data structures

Version 3.0
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class ActionType(Enum):
    """Card action types with styling info"""
    SCALP_LONG = ("long", "fa-arrow-trend-up", "SCALP LONG")
    SCALP_SHORT = ("short", "fa-arrow-trend-down", "SCALP SHORT")
    INTRADAY_LONG = ("long", "fa-arrow-up", "INTRADAY LONG")
    INTRADAY_SHORT = ("short", "fa-arrow-down", "INTRADAY SHORT")
    BREAKOUT = ("breakout", "fa-rocket", "BREAKOUT")
    REVERSAL = ("reversal", "fa-rotate", "REVERSAL")
    BTST_BUY = ("btst", "fa-moon", "BTST BUY")
    SWING_BUY = ("long", "fa-wave-square", "SWING BUY")
    HOLD = ("hold", "fa-hand", "HOLD")
    REDUCE = ("reduce", "fa-arrow-down", "REDUCE")
    ACCUMULATE = ("accumulate", "fa-coins", "ACCUMULATE")
    CORE_HOLD = ("core", "fa-shield-halved", "CORE HOLD")
    
    @property
    def css_class(self) -> str:
        return self.value[0]
    
    @property
    def icon(self) -> str:
        return self.value[1]
    
    @property
    def label(self) -> str:
        return self.value[2]


class TagType(Enum):
    """Tag types with styling"""
    NEW = ("new", "fa-star")
    URGENT = ("urgent", "fa-bolt")
    HOLDING = ("holding", "fa-wallet")
    BULLISH = ("bullish", "fa-arrow-up")
    BEARISH = ("bearish", "fa-arrow-down")
    NEUTRAL = ("neutral", None)
    SMC = ("smc", "fa-check")
    VOLUME = ("volume", "fa-chart-bar")
    PHASE = ("phase", None)
    SECTOR = ("sector", None)
    SCORE = ("score", None)


@dataclass
class Tag:
    """Tag data structure"""
    type: str
    label: str
    icon: Optional[str] = None


@dataclass
class Technicals:
    """Technical indicators data"""
    rsi: Dict[str, Any] = field(default_factory=dict)
    macd: Dict[str, Any] = field(default_factory=dict)
    ema: Dict[str, Any] = field(default_factory=dict)
    atr: Dict[str, Any] = field(default_factory=dict)
    rs: Optional[Dict[str, Any]] = None  # Relative Strength for Swing


@dataclass
class FOSentiment:
    """F&O Sentiment data"""
    pcr: Dict[str, Any] = field(default_factory=dict)
    oi: Dict[str, Any] = field(default_factory=dict)
    max_pain: Dict[str, Any] = field(default_factory=dict)
    iv: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FVGZones:
    """Fair Value Gap zones"""
    above: Optional[Dict[str, str]] = None
    below: Optional[Dict[str, str]] = None


@dataclass
class GlobalCues:
    """Global market cues for BTST"""
    sgx: Dict[str, str] = field(default_factory=dict)
    us: Dict[str, str] = field(default_factory=dict)
    fii: Dict[str, str] = field(default_factory=dict)


@dataclass
class Holding:
    """Holding data for positional/investment"""
    entry_price: float = 0.0
    avg_cost: float = 0.0
    pnl_pct: float = 0.0
    profit: float = 0.0
    weight: float = 0.0


@dataclass
class ContextItem:
    """Context box item"""
    text: str
    sentiment: str = "neutral"  # positive, negative, neutral
    icon: Optional[str] = None


@dataclass
class Indicator:
    """Indicator bar data"""
    label: str
    value: str
    percent: int
    strength: str = "neutral"  # strong, weak, neutral


class CardGenerator:
    """
    Generates card data structures from trading signals
    """
    
    @staticmethod
    def format_price(price: float) -> str:
        """Format price with Indian number system"""
        if price >= 10000:
            return f"{price:,.2f}"
        return f"{price:.2f}"
    
    @staticmethod
    def get_score_class(score: float) -> str:
        """Get CSS class for score"""
        if score >= 8:
            return "high"
        elif score >= 6:
            return "medium"
        return "low"
    
    @staticmethod
    def get_rsi_status(rsi: float) -> tuple:
        """Get RSI status and label"""
        if rsi >= 70:
            return ("overbought", "Overbought")
        elif rsi >= 60:
            return ("bullish", "Bullish")
        elif rsi <= 30:
            return ("oversold", "Oversold")
        elif rsi <= 40:
            return ("bearish", "Bearish")
        return ("neutral", "Neutral")
    
    @staticmethod
    def get_pcr_signal(pcr: float) -> tuple:
        """Get PCR signal"""
        if pcr >= 1.3:
            return ("bullish", "V.Bullish")
        elif pcr >= 1.0:
            return ("bullish", "Bullish")
        elif pcr <= 0.7:
            return ("bearish", "V.Bearish")
        elif pcr <= 0.9:
            return ("bearish", "Bearish")
        return ("neutral", "Neutral")
    
    def generate_scalp_card(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Generate scalp card data"""
        direction = signal.get("direction", "long")
        is_breakout = signal.get("type") == "breakout"
        
        # Determine action type
        if is_breakout:
            action = ActionType.BREAKOUT
        elif direction == "short":
            action = ActionType.SCALP_SHORT
        else:
            action = ActionType.SCALP_LONG
        
        # Build tags
        tags = []
        if signal.get("is_new"):
            tags.append(Tag("new", "NEW", "fa-star"))
        if signal.get("is_urgent"):
            tags.append(Tag("urgent", "ACT NOW", "fa-bolt"))
        if signal.get("fvg"):
            tags.append(Tag("smc", "FVG", "fa-check"))
        if signal.get("order_block"):
            tags.append(Tag("smc", "Order Block", None))
        if signal.get("rvol"):
            tags.append(Tag("volume", f"RVOL {signal['rvol']}x", "fa-chart-bar"))
        if signal.get("wyckoff_event"):
            tags.append(Tag("phase", signal["wyckoff_event"], None))
        tags.append(Tag("score", f"{signal.get('score', 0)}/10", None))
        
        card_data = {
            "symbol": signal["symbol"],
            "company_name": signal.get("company_name", ""),
            "current_price": signal["price"],
            "price_change": signal.get("change_pct", 0),
            "action_class": action.css_class,
            "action_icon": action.icon,
            "action_label": action.label,
            "timeframe_label": "5M",
            "category": f"scalp-{direction}",
            "is_urgent": signal.get("is_urgent", False),
            "tags": [{"type": t.type, "label": t.label, "icon": t.icon} for t in tags],
            "score": signal.get("score", 0),
            "score_label": "Breakout Strength" if is_breakout else "Signal Strength",
            "risk_pct": signal.get("risk_pct", "-1.0%"),
            "reward_pct": signal.get("reward_pct", "+2.0%"),
            "rr_ratio": signal.get("rr_ratio", "1:2"),
            "entry": signal.get("entry"),
            "target": signal.get("target"),
            "stop_loss": signal.get("stop_loss"),
        }
        
        # Add Wyckoff phase if available
        if signal.get("wyckoff_phase"):
            card_data["wyckoff_phase"] = signal["wyckoff_phase"]
        
        # Add FVG zones if available
        if signal.get("fvg_above") or signal.get("fvg_below"):
            card_data["fvg_zones"] = {
                "above": {"range": signal.get("fvg_above"), "type": "Target Zone"} if signal.get("fvg_above") else None,
                "below": {"range": signal.get("fvg_below"), "type": "Support Zone"} if signal.get("fvg_below") else None,
            }
        
        # Add indicators
        if signal.get("vwap_sigma") or signal.get("delta"):
            card_data["indicators"] = []
            if signal.get("vwap_sigma"):
                card_data["indicators"].append({
                    "label": "VWAP",
                    "value": f"{signal['vwap_sigma']:+.1f}σ",
                    "percent": min(abs(signal["vwap_sigma"]) * 30, 100),
                    "strength": "strong" if signal["vwap_sigma"] > 0 else "weak"
                })
            if signal.get("delta"):
                card_data["indicators"].append({
                    "label": "Delta",
                    "value": signal["delta"],
                    "percent": 70,
                    "strength": "strong" if signal["delta"] == "Bullish" else "weak"
                })
        
        # Add confidence for breakouts
        if is_breakout and signal.get("confidence"):
            card_data["confidence"] = signal["confidence"]
        
        return card_data
    
    def generate_intraday_card(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Generate intraday card data with technicals and F&O"""
        direction = signal.get("direction", "long")
        is_breakout = signal.get("type") == "breakout"
        
        # Determine action type
        if is_breakout:
            action = ActionType.BREAKOUT
        elif direction == "short":
            action = ActionType.INTRADAY_SHORT
        else:
            action = ActionType.INTRADAY_LONG
        
        card_data = self._generate_base_card(signal, action, "intraday", "2-4 HRS")
        
        # Add technicals
        if signal.get("technicals"):
            t = signal["technicals"]
            rsi_status = self.get_rsi_status(t.get("rsi", 50))
            card_data["technicals"] = {
                "rsi": {"value": t.get("rsi", 50), "status": rsi_status[0], "label": rsi_status[1]},
                "macd": {"value": "+" if t.get("macd_bullish") else "-", "status": "bullish" if t.get("macd_bullish") else "bearish", "label": "▲ Cross" if t.get("macd_bullish") else "▼ Cross"},
                "ema": {"value": "Above" if t.get("above_ema") else "Below", "status": "bullish" if t.get("above_ema") else "bearish", "label": t.get("ema_detail", "20/50")},
                "atr": {"value": f"{t.get('atr', 1.5):.1f}%", "status": "overbought" if t.get("atr", 1.5) > 2 else "neutral", "label": "High" if t.get("atr", 1.5) > 2 else "Normal"}
            }
        
        # Add F&O sentiment
        if signal.get("fo"):
            f = signal["fo"]
            pcr_signal = self.get_pcr_signal(f.get("pcr", 1.0))
            card_data["fo_sentiment"] = {
                "pcr": {"value": f.get("pcr", 1.0), "signal": pcr_signal[0], "label": pcr_signal[1]},
                "oi": {"value": f.get("oi", "+0L"), "signal": "bullish" if "+" in str(f.get("oi", "")) else "bearish", "label": f.get("oi_type", "Long Build")},
                "max_pain": {"value": f.get("max_pain", 0), "signal": "bullish" if signal["price"] > f.get("max_pain", 0) else "bearish", "label": "Above" if signal["price"] > f.get("max_pain", 0) else "Below"},
                "iv": {"value": f.get("iv", 20), "signal": "neutral", "label": "High" if f.get("iv", 20) > 25 else "Normal"}
            }
        
        # Add exit time
        card_data["exit_time"] = signal.get("exit_time", "3:15 PM")
        card_data["entry_range"] = signal.get("entry_range", f"{signal.get('entry', 0)}")
        card_data["target_pct"] = signal.get("target_pct", "+2.0%")
        card_data["stop_pct"] = signal.get("stop_pct", "-1.0%")
        
        return card_data
    
    def generate_btst_card(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Generate BTST card data with global cues"""
        action = ActionType.BTST_BUY
        card_data = self._generate_base_card(signal, action, "btst", "BUY TODAY")
        
        # Add technicals (same as intraday)
        if signal.get("technicals"):
            t = signal["technicals"]
            rsi_status = self.get_rsi_status(t.get("rsi", 50))
            card_data["technicals"] = {
                "rsi": {"value": t.get("rsi", 50), "status": rsi_status[0], "label": rsi_status[1]},
                "macd": {"value": "+" if t.get("macd_bullish") else "-", "status": "bullish" if t.get("macd_bullish") else "bearish", "label": "▲ Cross" if t.get("macd_bullish") else "▼ Cross"},
                "ema": {"value": "Above" if t.get("above_ema") else "Below", "status": "bullish" if t.get("above_ema") else "bearish", "label": t.get("ema_detail", "20/50")},
                "atr": {"value": f"{t.get('atr', 1.5):.1f}%", "status": "neutral", "label": "Normal"}
            }
        
        # Add F&O sentiment
        if signal.get("fo"):
            f = signal["fo"]
            pcr_signal = self.get_pcr_signal(f.get("pcr", 1.0))
            card_data["fo_sentiment"] = {
                "pcr": {"value": f.get("pcr", 1.0), "signal": pcr_signal[0], "label": pcr_signal[1]},
                "oi": {"value": f.get("oi", "+0L"), "signal": "bullish" if "+" in str(f.get("oi", "")) else "bearish", "label": f.get("oi_type", "Long Build")},
                "max_pain": {"value": f.get("max_pain", 0), "signal": "bullish", "label": "Above"},
                "iv": {"value": f.get("iv", 20), "signal": "neutral", "label": "Normal"}
            }
        
        # Add global cues
        if signal.get("global_cues"):
            gc = signal["global_cues"]
            card_data["global_cues"] = {
                "sgx": {"value": gc.get("sgx", "+0.0%"), "sentiment": "positive" if "+" in gc.get("sgx", "") else "negative"},
                "us": {"value": gc.get("us", "Flat"), "sentiment": "positive" if gc.get("us") == "Green" else "negative" if gc.get("us") == "Red" else "neutral"},
                "fii": {"value": gc.get("fii", "Neutral"), "sentiment": "positive" if "Buyer" in gc.get("fii", "") else "negative" if "Seller" in gc.get("fii", "") else "neutral"}
            }
        
        # Add BTST-specific fields
        card_data["gap_probability"] = signal.get("gap_probability", 70)
        card_data["buy_before"] = signal.get("buy_before", "3:20 PM")
        card_data["sell_time"] = signal.get("sell_time", "Tomorrow 9:30-10:00 AM")
        card_data["entry_range"] = signal.get("entry_range", f"{signal.get('entry', 0)}")
        
        return card_data
    
    def generate_swing_card(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Generate swing card data with weekly technicals"""
        action = ActionType.SWING_BUY
        card_data = self._generate_base_card(signal, action, "swing", "2-5 DAYS")
        card_data["status"] = signal.get("status", "fresh")
        card_data["category"] = f"swing-{signal.get('status', 'fresh')}"
        
        # Add weekly technicals with RS
        if signal.get("technicals"):
            t = signal["technicals"]
            rsi_status = self.get_rsi_status(t.get("rsi", 50))
            card_data["technicals"] = {
                "rsi": {"value": t.get("rsi", 50), "status": rsi_status[0], "label": rsi_status[1]},
                "macd": {"value": "+" if t.get("macd_bullish") else "-", "status": "bullish" if t.get("macd_bullish") else "bearish", "label": "▲ Cross" if t.get("macd_bullish") else "▼ Cross"},
                "ema": {"value": "Above" if t.get("above_ema") else "Below", "status": "bullish" if t.get("above_ema") else "bearish", "label": "50/200"},
                "rs": {"value": f"{t.get('rs', 1.0):.2f}", "status": "bullish" if t.get("rs", 1.0) > 1 else "bearish", "label": "Strong" if t.get("rs", 1.0) > 1 else "Weak"}
            }
        
        # Add context
        card_data["context"] = signal.get("context", [])
        
        # Add swing-specific fields
        card_data["entry_zone"] = signal.get("entry_zone", "")
        card_data["target1"] = signal.get("target1", signal.get("target", 0))
        card_data["target1_pct"] = signal.get("target1_pct", "+6%")
        card_data["target2"] = signal.get("target2")
        card_data["target2_pct"] = signal.get("target2_pct", "+8%")
        card_data["stop_pct"] = signal.get("stop_pct", "-3.5%")
        card_data["position_build"] = signal.get("position_build", "2 Tranches (50% each)")
        
        return card_data
    
    def generate_positional_card(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Generate positional card data with P&L tracking"""
        action_type = signal.get("action", "HOLD")
        if action_type == "HOLD":
            action = ActionType.HOLD
        elif action_type == "REDUCE":
            action = ActionType.REDUCE
        else:
            action = ActionType.SWING_BUY  # Fresh entry
        
        card_data = self._generate_base_card(signal, action, "positional", 
                                             "MAINTAIN" if action_type == "HOLD" else "BOOK PARTIAL" if action_type == "REDUCE" else "WEEKS")
        card_data["action"] = action_type
        card_data["category"] = f"positional-{action_type.lower()}"
        card_data["status"] = signal.get("status", "fresh")
        
        # Add holding data if available
        if signal.get("holding"):
            h = signal["holding"]
            card_data["holding"] = {
                "entry_price": h.get("entry_price", 0),
                "pnl_pct": h.get("pnl_pct", 0),
                "profit": h.get("profit", 0)
            }
        
        # Add context
        card_data["context"] = signal.get("context", [])
        
        # Action-specific fields
        if action_type == "HOLD":
            card_data["trail_sl"] = signal.get("trail_sl", 0)
            card_data["target"] = signal.get("target", 0)
            card_data["target_pct"] = signal.get("target_pct", "+9%")
        elif action_type == "REDUCE":
            card_data["book_pct"] = signal.get("book_pct", "50%")
            card_data["tight_sl"] = signal.get("tight_sl", 0)
            card_data["reduce_reason"] = signal.get("reduce_reason", "Distribution Phase")
        else:
            card_data["entry_zone"] = signal.get("entry_zone", "")
            card_data["target"] = signal.get("target", 0)
            card_data["target_pct"] = signal.get("target_pct", "+8%")
            card_data["stop_pct"] = signal.get("stop_pct", "-3%")
        
        return card_data
    
    def generate_investment_card(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Generate investment card data with thesis and valuation"""
        action_type = signal.get("action", "ACCUMULATE")
        if action_type == "CORE":
            action = ActionType.CORE_HOLD
        else:
            action = ActionType.ACCUMULATE
        
        card_data = self._generate_base_card(signal, action, "investment",
                                             "NEVER SELL" if action_type == "CORE" else "LONG TERM")
        card_data["action"] = action_type
        card_data["category"] = f"invest-{action_type.lower()}"
        
        # Investment grade
        card_data["investment_grade"] = signal.get("investment_grade", "A")
        card_data["investment_grade_pct"] = {"AAA": 100, "AA": 95, "A+": 90, "A": 85, "B+": 75, "B": 65}.get(signal.get("investment_grade", "A"), 80)
        
        # Add holding data if available
        if signal.get("holding"):
            h = signal["holding"]
            card_data["holding"] = {
                "avg_cost": h.get("avg_cost", 0),
                "pnl_pct": h.get("pnl_pct", 0),
                "weight": h.get("weight", 0)
            }
        
        # Investment thesis
        card_data["investment_thesis"] = signal.get("investment_thesis", [])
        
        # Valuation and quality
        if signal.get("valuation"):
            card_data["valuation"] = {
                "label": signal["valuation"].get("label", "Fair Value"),
                "pct": signal["valuation"].get("pct", 70),
                "strength": signal["valuation"].get("strength", "strong")
            }
        
        if signal.get("quality_score"):
            card_data["quality_score"] = {
                "label": signal["quality_score"].get("label", "A"),
                "pct": signal["quality_score"].get("pct", 85),
                "strength": "strong"
            }
        
        # Action-specific fields
        if action_type == "CORE":
            card_data["add_below"] = signal.get("add_below", 0)
            card_data["long_term_target"] = signal.get("long_term_target", 0)
            card_data["target_horizon"] = signal.get("target_horizon", "10Y")
            card_data["target_multiple"] = signal.get("target_multiple", "3x")
        else:
            card_data["buy_zone"] = signal.get("buy_zone", "")
            card_data["target_12m"] = signal.get("target_12m", 0)
            card_data["target_12m_pct"] = signal.get("target_12m_pct", "+18%")
            card_data["dividend_yield"] = signal.get("dividend_yield")
            card_data["recommended_weight"] = signal.get("recommended_weight", "5-8%")
        
        # Quality confidence
        card_data["quality_confidence"] = signal.get("quality_confidence", "90%")
        card_data["quality_confidence_pct"] = int(signal.get("quality_confidence", "90%").replace("%", ""))
        
        return card_data
    
    def _generate_base_card(self, signal: Dict[str, Any], action: ActionType, 
                           timeframe: str, timeframe_label: str) -> Dict[str, Any]:
        """Generate base card data common to all cards"""
        # Build tags
        tags = []
        if signal.get("is_new"):
            tags.append(Tag("new", "NEW" if timeframe != "swing" else "FRESH", "fa-star"))
        if signal.get("is_urgent"):
            tags.append(Tag("urgent", "ACT NOW", "fa-bolt"))
        if signal.get("is_holding"):
            tags.append(Tag("holding", "HOLDING", "fa-wallet"))
        if signal.get("sentiment") == "bullish":
            tags.append(Tag("bullish", signal.get("sentiment_label", "Bullish"), "fa-arrow-up"))
        elif signal.get("sentiment") == "bearish":
            tags.append(Tag("bearish", signal.get("sentiment_label", "Bearish"), "fa-arrow-down"))
        if signal.get("wyckoff_phase"):
            tags.append(Tag("phase", signal["wyckoff_phase"].title(), None))
        if signal.get("sector"):
            tags.append(Tag("sector", signal["sector"], signal.get("sector_icon")))
        tags.append(Tag("score", f"{signal.get('score', 0)}/10", None))
        
        return {
            "symbol": signal["symbol"],
            "company_name": signal.get("company_name", ""),
            "current_price": signal["price"],
            "price_change": signal.get("change_pct", 0),
            "action_class": action.css_class,
            "action_icon": action.icon,
            "action_label": action.label,
            "timeframe_label": timeframe_label,
            "category": timeframe,
            "is_urgent": signal.get("is_urgent", False),
            "tags": [{"type": t.type, "label": t.label, "icon": t.icon} for t in tags],
            "score": signal.get("score", 0),
            "score_label": "Signal Strength",
            "risk_pct": signal.get("risk_pct", "-1.0%"),
            "reward_pct": signal.get("reward_pct", "+2.0%"),
            "rr_ratio": signal.get("rr_ratio", "1:2"),
            "entry": signal.get("entry"),
            "target": signal.get("target"),
            "stop_loss": signal.get("stop_loss"),
            "wyckoff_phase": signal.get("wyckoff_phase"),
            "confidence": signal.get("confidence"),
        }


# Singleton instance
card_generator = CardGenerator()


def generate_card(signal: Dict[str, Any], timeframe: str) -> Dict[str, Any]:
    """
    Generate card data for a signal
    
    Args:
        signal: Trading signal data
        timeframe: One of 'scalp', 'intraday', 'btst', 'swing', 'positional', 'investment'
    
    Returns:
        Card data dictionary for Jinja2 template
    """
    generators = {
        "scalp": card_generator.generate_scalp_card,
        "intraday": card_generator.generate_intraday_card,
        "btst": card_generator.generate_btst_card,
        "swing": card_generator.generate_swing_card,
        "positional": card_generator.generate_positional_card,
        "investment": card_generator.generate_investment_card,
    }
    
    generator = generators.get(timeframe)
    if generator:
        return generator(signal)
    raise ValueError(f"Unknown timeframe: {timeframe}")
