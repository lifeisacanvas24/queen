"""
Queen Cockpit - Main FastAPI Application
Integrates WebSocket, Database, Signal Pipeline, and Dashboard

Version: 1.0
"""

import asyncio
import os
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Local imports
from services.upstox_websocket import (
    UpstoxWebSocketClient, DashboardBroadcaster, TickData,
    SubscriptionMode, init_market_feed, get_market_feed, get_broadcaster
)
from services.signal_pipeline import (
    SignalPipeline, PipelineSettings, init_pipeline, get_pipeline
)
from database.models import (
    QueenDatabase, Signal, Trade, Position, Timeframe,
    init_db, get_db
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("queen")

# ============================================
# Configuration
# ============================================

class Config:
    """Application configuration"""
    # API
    UPSTOX_ACCESS_TOKEN: str = os.environ.get("UPSTOX_ACCESS_TOKEN", "")

    # Database
    DB_PATH: str = os.environ.get("QUEEN_DB_PATH", "queen.db")

    # Paths
    BASE_DIR: Path = Path(__file__).parent
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    STATIC_DIR: Path = BASE_DIR / "static"

    # Server
    HOST: str = os.environ.get("QUEEN_HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("QUEEN_PORT", "8000"))
    DEBUG: bool = os.environ.get("QUEEN_DEBUG", "false").lower() == "true"

    # Market hours (IST)
    MARKET_OPEN_HOUR: int = 9
    MARKET_OPEN_MINUTE: int = 15
    MARKET_CLOSE_HOUR: int = 15
    MARKET_CLOSE_MINUTE: int = 30


config = Config()


# ============================================
# Global State
# ============================================

class AppState:
    """Application state container"""
    db: Optional[QueenDatabase] = None
    upstox_client: Optional[UpstoxWebSocketClient] = None
    broadcaster: Optional[DashboardBroadcaster] = None
    pipeline: Optional[SignalPipeline] = None
    connected_clients: set = set()


state = AppState()


# ============================================
# Lifespan Management
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown"""
    logger.info("Starting Queen Cockpit...")

    # Initialize database
    state.db = init_db(config.DB_PATH)
    logger.info(f"Database initialized: {config.DB_PATH}")

    # Initialize signal pipeline
    state.pipeline = init_pipeline(
        db=state.db,
        on_signal=on_new_signal
    )
    logger.info("Signal pipeline initialized")

    # Initialize dashboard broadcaster
    state.broadcaster = DashboardBroadcaster()
    await state.broadcaster.start()
    logger.info("Dashboard broadcaster started")

    # Initialize Upstox WebSocket if token available
    if config.UPSTOX_ACCESS_TOKEN:
        try:
            state.upstox_client = UpstoxWebSocketClient(
                access_token=config.UPSTOX_ACCESS_TOKEN,
                on_tick=on_market_tick,
                on_connect=on_upstox_connect,
                on_disconnect=on_upstox_disconnect,
            )
            await state.upstox_client.connect()
            logger.info("Upstox WebSocket connected")
        except Exception as e:
            logger.error(f"Failed to connect Upstox WebSocket: {e}")
    else:
        logger.warning("UPSTOX_ACCESS_TOKEN not set - running without live data")

    yield

    # Shutdown
    logger.info("Shutting down Queen Cockpit...")

    if state.upstox_client:
        await state.upstox_client.disconnect()

    if state.broadcaster:
        await state.broadcaster.stop()

    if state.pipeline:
        await state.pipeline.stop_scanner()

    if state.db:
        state.db.close()

    logger.info("Shutdown complete")


# ============================================
# Callbacks
# ============================================

def on_market_tick(tick: TickData):
    """Handle incoming market tick"""
    if state.broadcaster:
        state.broadcaster.update_tick(tick)


def on_new_signal(signal: Signal):
    """Handle new signal generated"""
    logger.info(f"New signal: {signal.symbol} {signal.action} @ {signal.entry_price}")
    # Could push to broadcaster here for real-time signal updates


def on_upstox_connect():
    """Handle Upstox WebSocket connection"""
    logger.info("Upstox WebSocket connected")


def on_upstox_disconnect(reason: str):
    """Handle Upstox WebSocket disconnection"""
    logger.warning(f"Upstox WebSocket disconnected: {reason}")


# ============================================
# FastAPI Application
# ============================================

app = FastAPI(
    title="Queen Cockpit",
    description="Professional Trading Signal Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
if config.STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

# Templates
templates = None
if config.TEMPLATES_DIR.exists():
    templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))

    # Custom filters
    def format_price(value):
        """Format price with Indian notation"""
        if value is None:
            return "—"
        if value >= 10000000:
            return f"₹{value/10000000:.2f}Cr"
        elif value >= 100000:
            return f"₹{value/100000:.2f}L"
        elif value >= 1000:
            return f"₹{value:,.2f}"
        return f"₹{value:.2f}"

    templates.env.filters["format_price"] = format_price


# ============================================
# Helper Functions
# ============================================

def is_market_open() -> bool:
    """Check if Indian market is open"""
    now = datetime.now()

    # Weekend check
    if now.weekday() >= 5:
        return False

    # Time check (IST)
    market_open = now.replace(
        hour=config.MARKET_OPEN_HOUR,
        minute=config.MARKET_OPEN_MINUTE,
        second=0
    )
    market_close = now.replace(
        hour=config.MARKET_CLOSE_HOUR,
        minute=config.MARKET_CLOSE_MINUTE,
        second=0
    )

    return market_open <= now <= market_close


def get_dashboard_stats() -> Dict[str, int]:
    """Get signal counts for dashboard stats bar"""
    if not state.db:
        return {"buy": 0, "sell": 0, "hold": 0, "urgent": 0}

    signals = state.db.get_active_signals(limit=500)

    buy = sum(1 for s in signals if s.direction == "long")
    sell = sum(1 for s in signals if s.direction == "short")
    hold = sum(1 for s in signals if s.action in ["HOLD", "CORE_HOLD"])
    urgent = sum(1 for s in signals if s.score >= 8.0)

    return {
        "buy": buy,
        "sell": sell,
        "hold": hold,
        "urgent": urgent,
    }


def get_tab_counts() -> Dict[str, int]:
    """Get signal counts per timeframe tab"""
    if not state.db:
        return {tf.value: 0 for tf in Timeframe}

    counts = {}
    for tf in Timeframe:
        signals = state.db.get_active_signals(timeframe=tf.value)
        counts[tf.value] = len(signals)

    return counts


def signal_to_card_data(signal: Signal) -> Dict[str, Any]:
    """Convert Signal object to card template data"""

    # Action type mapping
    action_classes = {
        "SCALP_LONG": "long",
        "SCALP_SHORT": "short",
        "INTRADAY_LONG": "long",
        "INTRADAY_SHORT": "short",
        "BTST_BUY": "btst",
        "SWING_BUY": "swing",
        "ACCUMULATE": "accumulate",
        "REDUCE": "reduce",
        "HOLD": "hold",
        "CORE_HOLD": "core",
    }

    action_icons = {
        "SCALP_LONG": "⚡",
        "SCALP_SHORT": "⚡",
        "INTRADAY_LONG": "📈",
        "INTRADAY_SHORT": "📉",
        "BTST_BUY": "🌙",
        "SWING_BUY": "🔄",
        "ACCUMULATE": "➕",
        "REDUCE": "➖",
        "HOLD": "⏸",
        "CORE_HOLD": "💎",
    }

    timeframe_labels = {
        "scalp": "5M",
        "intraday": "2-4H",
        "btst": "O/N",
        "swing": "2-5D",
        "positional": "Weeks",
        "investment": "Long",
    }

    # Build tags
    tags = []
    for tag in signal.tags[:5]:
        tag_type = "neutral"
        if tag.lower() in ["new", "urgent"]:
            tag_type = tag.lower()
        elif "bullish" in tag.lower() or "▲" in tag:
            tag_type = "bullish"
        elif "bearish" in tag.lower() or "▼" in tag:
            tag_type = "bearish"
        elif "smc" in tag.lower() or "fvg" in tag.lower() or "block" in tag.lower():
            tag_type = "smc"
        elif "volume" in tag.lower() or "rvol" in tag.lower():
            tag_type = "volume"

        tags.append({
            "type": tag_type,
            "label": tag,
        })

    # Score class
    score_class = "high" if signal.score >= 7.5 else "medium" if signal.score >= 6.0 else "low"

    return {
        # Identity
        "symbol": signal.symbol,
        "company_name": signal.symbol,  # TODO: lookup company name
        "current_price": signal.entry_price,
        "price_change": 0,  # TODO: calculate from live data

        # Action
        "action_class": action_classes.get(signal.action, "neutral"),
        "action_icon": action_icons.get(signal.action, "📊"),
        "action_label": signal.action.replace("_", " ").title(),
        "timeframe_label": timeframe_labels.get(signal.timeframe, ""),
        "category": signal.direction,
        "is_urgent": signal.score >= 8.0,

        # Score
        "score": signal.score,
        "score_class": score_class,

        # Tags
        "tags": tags,

        # R:R
        "risk_pct": signal.risk_pct,
        "reward_pct": signal.reward_pct,
        "rr_ratio": signal.rr_ratio,

        # Levels
        "entry": signal.entry_price,
        "target": signal.target_price,
        "target2": signal.target2_price,
        "stop_loss": signal.stop_loss,

        # Technicals (from stored data)
        "technicals": signal.technicals,

        # Wyckoff
        "wyckoff_phase": signal.wyckoff_phase,

        # Context
        "context": signal.context or [],

        # Confidence
        "confidence": signal.confidence,

        # Metadata
        "created_at": signal.created_at.isoformat() if signal.created_at else None,
        "expires_at": signal.expires_at.isoformat() if signal.expires_at else None,
    }


# ============================================
# Dashboard Routes
# ============================================

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    tab: str = Query("scalp", description="Active tab"),
    portfolio: str = Query("all", description="Portfolio filter"),
):
    """Main dashboard page"""
    if not templates:
        return HTMLResponse("<h1>Templates not configured</h1>")

    # Get signals for each timeframe
    signals_by_tf = {}
    for tf in Timeframe:
        signals = state.db.get_active_signals(timeframe=tf.value) if state.db else []
        signals_by_tf[tf.value] = [signal_to_card_data(s) for s in signals]

    # Get stats
    stats = get_dashboard_stats()
    tab_counts = get_tab_counts()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active_tab": tab,
            "active_portfolio": portfolio,

            # Signals by timeframe
            "scalp_signals": signals_by_tf.get("scalp", []),
            "intraday_signals": signals_by_tf.get("intraday", []),
            "btst_signals": signals_by_tf.get("btst", []),
            "swing_signals": signals_by_tf.get("swing", []),
            "positional_signals": signals_by_tf.get("positional", []),
            "investment_signals": signals_by_tf.get("investment", []),

            # Stats
            "stats": stats,
            "tab_counts": tab_counts,

            # Status
            "is_market_open": is_market_open(),
            "is_connected": state.upstox_client.is_connected if state.upstox_client else False,
            "current_time": datetime.now().strftime("%H:%M:%S"),
        }
    )


# ============================================
# API Routes
# ============================================

@app.get("/api/signals")
async def get_signals(
    timeframe: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """Get active signals"""
    if not state.db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    signals = state.db.get_active_signals(timeframe=timeframe, limit=limit)

    return {
        "count": len(signals),
        "signals": [signal_to_card_data(s) for s in signals],
    }


@app.get("/api/signals/{timeframe}")
async def get_signals_by_timeframe(timeframe: str):
    """Get signals for specific timeframe"""
    if timeframe not in [tf.value for tf in Timeframe]:
        raise HTTPException(status_code=400, detail="Invalid timeframe")

    if not state.db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    signals = state.db.get_active_signals(timeframe=timeframe)

    return {
        "timeframe": timeframe,
        "count": len(signals),
        "signals": [signal_to_card_data(s) for s in signals],
    }


@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics"""
    return {
        "stats": get_dashboard_stats(),
        "tab_counts": get_tab_counts(),
        "market_status": {
            "is_open": is_market_open(),
            "is_connected": state.upstox_client.is_connected if state.upstox_client else False,
        },
    }


@app.get("/api/positions")
async def get_positions(category: Optional[str] = None):
    """Get portfolio positions"""
    if not state.db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    positions = state.db.get_positions(category=category)

    return {
        "count": len(positions),
        "positions": [
            {
                "symbol": p.symbol,
                "avg_cost": p.avg_cost,
                "quantity": p.quantity,
                "current_price": p.current_price,
                "pnl": p.pnl,
                "pnl_pct": p.pnl_pct,
                "weight_pct": p.weight_pct,
                "category": p.category,
            }
            for p in positions
        ],
    }


@app.get("/api/trades")
async def get_trades(
    status: str = Query("all", description="Filter by status: all, open, closed"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get trades"""
    if not state.db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if status == "open":
        trades = state.db.get_open_trades()
    elif status == "closed":
        trades = state.db.get_trade_history(limit=limit)
    else:
        open_trades = state.db.get_open_trades()
        closed_trades = state.db.get_trade_history(limit=limit)
        trades = open_trades + closed_trades

    return {
        "count": len(trades),
        "trades": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "direction": t.direction,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "quantity": t.quantity,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "status": t.status,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            }
            for t in trades
        ],
    }


@app.get("/api/trade-stats")
async def get_trade_stats():
    """Get trade statistics"""
    if not state.db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    return state.db.get_trade_stats()


# ============================================
# WebSocket Routes
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Dashboard WebSocket for real-time updates"""
    await websocket.accept()
    state.connected_clients.add(websocket)

    if state.broadcaster:
        await state.broadcaster.add_client(websocket)

    logger.info(f"Dashboard client connected. Total: {len(state.connected_clients)}")

    try:
        while True:
            # Receive messages from client (for subscriptions, etc.)
            data = await websocket.receive_json()

            msg_type = data.get("type")

            if msg_type == "subscribe":
                # Handle subscription request
                instruments = data.get("instruments", [])
                if state.upstox_client and instruments:
                    await state.upstox_client.subscribe(
                        instruments,
                        mode=SubscriptionMode.FULL
                    )

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        state.connected_clients.discard(websocket)
        if state.broadcaster:
            await state.broadcaster.remove_client(websocket)
        logger.info(f"Dashboard client disconnected. Total: {len(state.connected_clients)}")


# ============================================
# Market Data Subscription
# ============================================

@app.post("/api/subscribe")
async def subscribe_instruments(instruments: List[str]):
    """Subscribe to market data for instruments"""
    if not state.upstox_client:
        raise HTTPException(status_code=503, detail="Market feed not connected")

    if not state.upstox_client.is_connected:
        raise HTTPException(status_code=503, detail="Market feed disconnected")

    await state.upstox_client.subscribe(instruments, mode=SubscriptionMode.FULL)

    return {"status": "subscribed", "instruments": instruments}


@app.post("/api/unsubscribe")
async def unsubscribe_instruments(instruments: List[str]):
    """Unsubscribe from market data"""
    if not state.upstox_client:
        raise HTTPException(status_code=503, detail="Market feed not connected")

    await state.upstox_client.unsubscribe(instruments)

    return {"status": "unsubscribed", "instruments": instruments}


# ============================================
# Health Check
# ============================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": state.db is not None,
        "market_feed": state.upstox_client.is_connected if state.upstox_client else False,
        "pipeline": state.pipeline is not None,
        "connected_clients": len(state.connected_clients),
        "market_open": is_market_open(),
    }


# ============================================
# Entry Point
# ============================================

def main():
    """Run the application"""
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info",
    )


if __name__ == "__main__":
    main()
