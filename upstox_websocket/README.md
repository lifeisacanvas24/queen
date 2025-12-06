# Queen Cockpit - Integration Package

Complete WebSocket, Database, and Signal Pipeline integration for the Queen Trading Cockpit.

## 📁 Directory Structure

```
queen_integration/
├── main.py                    # FastAPI application entry point
├── requirements.txt           # Python dependencies
├── .env.example              # Configuration template
├── upstox_auth.py            # OAuth helper for Upstox tokens
│
├── services/
│   ├── __init__.py
│   ├── upstox_websocket.py   # Upstox WebSocket V3 client
│   └── signal_pipeline.py    # Signal generation pipeline
│
├── database/
│   ├── __init__.py
│   └── models.py             # SQLite models and queries
│
├── templates/                 # Jinja2 templates (copy from queen_templates)
│   ├── base.html
│   ├── dashboard.html
│   └── ...
│
└── static/                    # CSS/JS (copy from queen_templates)
    ├── css/queen.css
    └── js/queen.js
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Upstox Access Token

```bash
# Register app at https://account.upstox.com/developer/apps
# Then run:
python upstox_auth.py --api-key YOUR_KEY --api-secret YOUR_SECRET
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your UPSTOX_ACCESS_TOKEN
```

### 4. Copy Templates

Copy the `templates/` and `static/` directories from the `queen_templates` package.

### 5. Run the Application

```bash
python main.py
```

Open http://localhost:8000 in your browser.

---

## 🔌 Components

### 1. Upstox WebSocket Client (`services/upstox_websocket.py`)

Real-time market data from Upstox using WebSocket V3 API.

**Features:**

- Auto-reconnection with exponential backoff
- Subscription management (LTPC, Full, Option Greeks modes)
- Tick data parsing and normalization
- Callback-based event handling

**Usage:**

```python
from services.upstox_websocket import UpstoxWebSocketClient, SubscriptionMode

client = UpstoxWebSocketClient(access_token="your_token")

@client.on_tick
def handle_tick(tick):
    print(f"{tick.symbol}: ₹{tick.ltp:.2f}")

await client.connect()
await client.subscribe(
    ["NSE_EQ|INE002A01018"],  # RELIANCE
    mode=SubscriptionMode.FULL
)
```

**Subscription Modes:**
| Mode | Data Included | Limit |
|------|--------------|-------|
| `ltpc` | LTP, Close Price | 5000 instruments |
| `option_greeks` | Greeks (delta, theta, etc.) | 3000 instruments |
| `full` | OHLC, 5-level depth, volume | 2000 instruments |

### 2. Signal Pipeline (`services/signal_pipeline.py`)

Generates trading signals from technical analysis.

**Features:**

- Integrates with all Queen technical modules
- Score-based signal ranking (0-10)
- Timeframe-specific thresholds
- Automatic R:R calculation
- Database persistence

**Usage:**

```python
from services.signal_pipeline import SignalPipeline
import polars as pl

pipeline = SignalPipeline()

# Analyze a symbol
signals = await pipeline.analyze_symbol(
    symbol="RELIANCE",
    instrument_key="NSE_EQ|INE002A01018",
    candles=df,  # Polars DataFrame
    timeframe="intraday"
)

for signal in signals:
    print(f"{signal.action}: Score {signal.score}")
    pipeline.save_signal(signal)
```

**Signal Scoring:**
| Component | Max Contribution |
|-----------|-----------------|
| RSI | ±1.0 |
| MACD | ±0.8 |
| EMA Alignment | ±0.6 |
| Volume (RVOL) | +0.8 |
| SMC (FVG, OB, BOS) | +1.5 |
| Wyckoff | +1.0 |
| Breakout | +0.5 |

**Timeframe Thresholds:**
| Timeframe | Min Score | Min R:R |
|-----------|----------|---------|
| Scalp | 6.0 | 1.5 |
| Intraday | 6.5 | 2.0 |
| BTST | 7.0 | — |
| Swing | 7.0 | 2.5 |
| Positional | 7.5 | — |
| Investment | 8.0 | — |

### 3. Database (`database/models.py`)

SQLite database for signals, trades, and positions.

**Tables:**

- `signals` - Trading signals with technical data
- `trades` - Trade records with P&L
- `positions` - Portfolio positions
- `watchlist` - Watchlist items
- `trade_stats` - Aggregated statistics
- `settings` - Application settings

**Usage:**

```python
from database.models import QueenDatabase, Signal, Trade, Position

db = QueenDatabase("queen.db")
db.init()

# Add signal
signal = Signal(
    symbol="RELIANCE",
    timeframe="intraday",
    direction="long",
    action="INTRADAY_LONG",
    score=7.5,
    entry_price=2845,
    target_price=2890,
    stop_loss=2820,
)
signal_id = db.add_signal(signal)

# Get active signals
signals = db.get_active_signals(timeframe="intraday")

# Add trade
trade = Trade(
    symbol="RELIANCE",
    direction="long",
    entry_price=2845,
    quantity=10,
    signal_id=signal_id,
)
trade_id = db.add_trade(trade)

# Close trade
db.close_trade(trade_id, exit_price=2890, charges=50)

# Get stats
stats = db.get_trade_stats()
print(f"Win Rate: {stats['win_rate']:.1f}%")
```

---

## 🌐 API Endpoints

### Dashboard

| Method | Path                   | Description                 |
| ------ | ---------------------- | --------------------------- |
| GET    | `/`                    | Main dashboard              |
| GET    | `/dashboard?tab=scalp` | Dashboard with specific tab |

### Signals API

| Method | Path                       | Description          |
| ------ | -------------------------- | -------------------- |
| GET    | `/api/signals`             | All active signals   |
| GET    | `/api/signals/{timeframe}` | Signals by timeframe |
| GET    | `/api/stats`               | Dashboard statistics |

### Portfolio API

| Method | Path               | Description         |
| ------ | ------------------ | ------------------- |
| GET    | `/api/positions`   | Portfolio positions |
| GET    | `/api/trades`      | Trade history       |
| GET    | `/api/trade-stats` | Trade statistics    |

### Market Data API

| Method | Path               | Description                  |
| ------ | ------------------ | ---------------------------- |
| POST   | `/api/subscribe`   | Subscribe to instruments     |
| POST   | `/api/unsubscribe` | Unsubscribe from instruments |

### WebSocket

| Path  | Description             |
| ----- | ----------------------- |
| `/ws` | Real-time price updates |

**WebSocket Message Types:**

```javascript
// Subscribe to instruments
ws.send(JSON.stringify({
    type: "subscribe",
    instruments: ["NSE_EQ|INE002A01018"]
}));

// Price update (from server)
{
    "updates": [
        {
            "type": "price_update",
            "symbol": "RELIANCE",
            "ltp": 2847.50,
            "change": 12.30,
            "change_pct": 0.43
        }
    ]
}
```

---

## ⚙️ Configuration

### Environment Variables

| Variable              | Default    | Description             |
| --------------------- | ---------- | ----------------------- |
| `UPSTOX_ACCESS_TOKEN` | —          | Upstox API access token |
| `QUEEN_DB_PATH`       | `queen.db` | SQLite database path    |
| `QUEEN_HOST`          | `0.0.0.0`  | Server host             |
| `QUEEN_PORT`          | `8000`     | Server port             |
| `QUEEN_DEBUG`         | `false`    | Enable debug mode       |

### Pipeline Settings

```python
from services.signal_pipeline import PipelineSettings

settings = PipelineSettings(
    # Score thresholds
    min_score_scalp=6.0,
    min_score_intraday=6.5,
    min_score_swing=7.0,

    # R:R requirements
    min_rr_scalp=1.5,
    min_rr_intraday=2.0,

    # Volume
    min_rvol=1.5,

    # Scan interval (seconds)
    scan_interval=60,
)

pipeline = SignalPipeline(settings=settings)
```

---

## 🔧 Integration with Queen Modules

The signal pipeline automatically imports available Queen technical modules:

```python
# Supported modules (auto-detected)
from queen.technicals.microstructure.fvg import detect_fvg_zones
from queen.technicals.microstructure.order_blocks import detect_order_blocks
from queen.technicals.microstructure.wyckoff import detect_wyckoff_events
from queen.technicals.microstructure.bos_choch import detect_structure_breaks
from queen.technicals.microstructure.liquidity import detect_liquidity_sweeps
from queen.technicals.indicators.volume_confirmation import compute_rvol
from queen.technicals.signals.breakout_validator import validate_breakout
from queen.technicals.indicators.core import compute_rsi, compute_ema
from queen.technicals.indicators.momentum_macd import compute_macd
from queen.technicals.indicators.advanced import compute_atr
```

If modules are missing, the pipeline degrades gracefully and uses available modules.

---

## 📊 Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Upstox API     │────▶│  WebSocket Client │────▶│  Dashboard      │
│  (Live Data)    │     │  (upstox_ws.py)   │     │  Broadcaster    │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                        ┌──────────────────┐              │
                        │  Signal Pipeline  │◀────────────┘
                        │  (pipeline.py)    │
                        └────────┬─────────┘
                                 │
                        ┌────────▼─────────┐     ┌─────────────────┐
                        │  SQLite Database  │────▶│  FastAPI        │
                        │  (models.py)      │     │  Dashboard      │
                        └──────────────────┘     └─────────────────┘
```

---

## 🧪 Testing

### Test Database

```bash
python -m database.models
```

### Test WebSocket (requires token)

```bash
export UPSTOX_ACCESS_TOKEN=your_token
python -m services.upstox_websocket
```

### Test Pipeline

```bash
python -m services.signal_pipeline
```

---

## 📝 Notes

1. **Token Expiry**: Upstox tokens expire daily. Use `upstox_auth.py` to refresh.

2. **Rate Limits**: Upstox limits:
   - 2 WebSocket connections per user
   - 5000 LTPC subscriptions
   - 2000 Full mode subscriptions

3. **Market Hours**: Indian market: 9:15 AM - 3:30 PM IST, Mon-Fri

4. **Database**: SQLite is used for simplicity. For production, consider PostgreSQL.

---

## 📄 License

Part of the Queen Trading Cockpit project.
