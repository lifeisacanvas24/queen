"""
Queen Cockpit - Dashboard Router
FastAPI router for serving the trading dashboard

Version 3.0
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List, Dict, Any
from datetime import datetime
import pytz

from services.card_generator import generate_card


router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Setup templates
templates = Jinja2Templates(directory="templates")


# Custom Jinja2 filters
def format_price(value: float) -> str:
    """Format price with Indian number system"""
    if value is None:
        return "0.00"
    if value >= 10000:
        return f"{value:,.2f}"
    return f"{value:.2f}"


def add_custom_filters(templates: Jinja2Templates):
    """Add custom filters to Jinja2 environment"""
    templates.env.filters["format_price"] = format_price


add_custom_filters(templates)


def is_market_open() -> bool:
    """Check if Indian market is open"""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    # Market closed on weekends
    if now.weekday() >= 5:
        return False
    
    # Market hours: 9:15 AM to 3:30 PM
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    return market_open <= now <= market_close


def get_stats(signals: Dict[str, List]) -> Dict[str, int]:
    """Calculate stats from signals"""
    buy_count = 0
    sell_count = 0
    hold_count = 0
    urgent_count = 0
    
    for timeframe, signal_list in signals.items():
        for signal in signal_list:
            direction = signal.get("direction", "long")
            action = signal.get("action", "")
            
            if direction == "long" or action in ["ACCUMULATE", "BTST_BUY"]:
                buy_count += 1
            elif direction == "short" or action == "REDUCE":
                sell_count += 1
            elif action in ["HOLD", "CORE"]:
                hold_count += 1
            
            if signal.get("is_urgent"):
                urgent_count += 1
    
    return {
        "buy_count": buy_count,
        "sell_count": sell_count,
        "hold_count": hold_count,
        "urgent_count": urgent_count
    }


def get_tab_counts(signals: Dict[str, List]) -> Dict[str, int]:
    """Get signal counts per tab"""
    return {
        "scalp": len(signals.get("scalp", [])),
        "intraday": len(signals.get("intraday", [])),
        "btst": len(signals.get("btst", [])),
        "swing": len(signals.get("swing", [])),
        "positional": len(signals.get("positional", [])),
        "investment": len(signals.get("investment", [])),
    }


async def get_signals_by_timeframe(
    portfolio: str = "all",
    timeframe_filter: str = "15m"
) -> Dict[str, List[Dict]]:
    """
    Fetch signals from your signal generation service
    This should be replaced with actual signal fetching logic
    """
    # TODO: Replace with actual signal fetching from your Queen modules
    # Example structure:
    return {
        "scalp": [],
        "intraday": [],
        "btst": [],
        "swing": [],
        "positional": [],
        "investment": [],
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    portfolio: str = "all",
    timeframe: str = "15m",
    tab: str = "scalp"
):
    """Render main dashboard"""
    
    # Fetch signals
    raw_signals = await get_signals_by_timeframe(portfolio, timeframe)
    
    # Generate card data for each timeframe
    signals = {}
    for tf, signal_list in raw_signals.items():
        signals[tf] = [generate_card(s, tf) for s in signal_list]
    
    # Calculate stats and counts
    stats = get_stats(raw_signals)
    tab_counts = get_tab_counts(raw_signals)
    
    # Check market status
    market_open = is_market_open()
    
    # Get current time
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    last_update = now.strftime("%H:%M")
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "portfolio": portfolio,
            "timeframe": timeframe,
            "active_tab": tab,
            "is_market_open": market_open,
            "stats": stats,
            "tab_counts": tab_counts,
            "last_update": last_update,
            "scalp_signals": signals.get("scalp", []),
            "intraday_signals": signals.get("intraday", []),
            "btst_signals": signals.get("btst", []),
            "swing_signals": signals.get("swing", []),
            "positional_signals": signals.get("positional", []),
            "investment_signals": signals.get("investment", []),
            "portfolio_connected": False,
            "portfolio_holdings": [],
        }
    )


@router.get("/api/signals/{timeframe}")
async def get_signals_api(
    timeframe: str,
    portfolio: str = "all",
):
    """API endpoint to fetch signals for a specific timeframe"""
    raw_signals = await get_signals_by_timeframe(portfolio, "15m")
    
    if timeframe not in raw_signals:
        return {"error": f"Unknown timeframe: {timeframe}"}
    
    signals = [generate_card(s, timeframe) for s in raw_signals[timeframe]]
    return {"signals": signals, "count": len(signals)}


@router.get("/api/stats")
async def get_stats_api(portfolio: str = "all"):
    """API endpoint to fetch dashboard stats"""
    raw_signals = await get_signals_by_timeframe(portfolio, "15m")
    
    return {
        "stats": get_stats(raw_signals),
        "tab_counts": get_tab_counts(raw_signals),
        "is_market_open": is_market_open()
    }
