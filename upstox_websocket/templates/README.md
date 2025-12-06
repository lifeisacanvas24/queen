# Queen Cockpit - Jinja2 Templates

Apple-style trading dashboard with modular Jinja2 templates.

## Directory Structure

```
queen_templates/
├── templates/
│   ├── base.html                 # Main layout template
│   ├── dashboard.html            # Dashboard page
│   ├── components/
│   │   ├── header.html           # Header with logo, controls, status
│   │   ├── stats_bar.html        # Buy/Sell/Hold/Urgent counts
│   │   ├── tabs_nav.html         # Timeframe tabs navigation
│   │   ├── footer.html           # Footer with status
│   │   ├── sub_filters.html      # Filter pills component
│   │   └── signals_grid.html     # Cards grid container
│   └── cards/
│       ├── card_base.html        # Base card template (extended by others)
│       ├── card_scalp.html       # Scalp card (5M)
│       ├── card_intraday.html    # Intraday card with Technicals + F&O
│       ├── card_btst.html        # BTST card with Global Cues
│       ├── card_swing.html       # Swing card with Weekly Technicals
│       ├── card_positional.html  # Positional card with P&L tracking
│       ├── card_investment.html  # Investment card with Thesis
│       └── partials/
│           ├── signal_score.html     # Score bar component
│           ├── rr_box.html           # Risk/Reward box
│           ├── wyckoff_phase.html    # Wyckoff phase bar
│           ├── fvg_zones.html        # FVG zones display
│           ├── trade_levels.html     # Entry/Target/Stop grid
│           ├── context_box.html      # Context items box
│           └── confidence.html       # Confidence bar
├── static/
│   ├── css/
│   │   └── queen.css             # Complete stylesheet
│   └── js/
│       └── queen.js              # Dashboard JavaScript
└── services/
    ├── __init__.py
    ├── card_generator.py         # Signal to card data mapper
    └── dashboard_router.py       # FastAPI router

```

## Usage with FastAPI

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from services.dashboard_router import router as dashboard_router

app = FastAPI(title="Queen Cockpit")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include dashboard router
app.include_router(dashboard_router)
```

## Template Variables

### base.html
- `portfolio`: Selected portfolio filter
- `timeframe`: Selected timeframe
- `is_market_open`: Boolean for market status

### dashboard.html
- `active_tab`: Current active tab (scalp/intraday/btst/swing/positional/investment)
- `stats`: Dict with buy_count, sell_count, hold_count, urgent_count
- `tab_counts`: Dict with signal counts per tab
- `scalp_signals`, `intraday_signals`, etc.: Lists of card data

### Card Data Structure

All cards expect a `signal` object with:

```python
{
    # Common fields
    "symbol": "RELIANCE",
    "company_name": "Reliance Industries Ltd",
    "current_price": 2847.50,
    "price_change": 1.25,  # Percentage
    "action_class": "long",  # CSS class
    "action_icon": "fa-arrow-trend-up",
    "action_label": "SCALP LONG",
    "timeframe_label": "5M",
    "category": "scalp-long",
    "is_urgent": False,
    "tags": [{"type": "new", "label": "NEW", "icon": "fa-star"}],
    "score": 8.5,
    "score_label": "Signal Strength",
    
    # Trade levels
    "risk_pct": "-0.5%",
    "reward_pct": "+1.0%",
    "rr_ratio": "1:2",
    "entry": 2845,
    "target": 2875,
    "stop_loss": 2830,
    
    # Wyckoff (optional)
    "wyckoff_phase": "accumulation",
    
    # Technicals (for intraday+)
    "technicals": {
        "rsi": {"value": 61, "status": "bullish", "label": "Bullish"},
        "macd": {"value": "+", "status": "bullish", "label": "▲ Cross"},
        "ema": {"value": "Above", "status": "bullish", "label": "20/50"},
        "atr": {"value": "1.2%", "status": "neutral", "label": "Normal"}
    },
    
    # F&O Sentiment
    "fo_sentiment": {
        "pcr": {"value": 1.18, "signal": "bullish", "label": "Bullish"},
        "oi": {"value": "+2.1L", "signal": "bullish", "label": "Long Build"},
        "max_pain": {"value": 1120, "signal": "neutral", "label": "Near"},
        "iv": {"value": 15, "signal": "neutral", "label": "Normal"}
    },
    
    # FVG Zones (optional)
    "fvg_zones": {
        "above": {"range": "1720 - 1735", "type": "Target Zone"},
        "below": {"range": "1655 - 1665", "type": "Support Zone"}
    },
    
    # Global Cues (BTST)
    "global_cues": {
        "sgx": {"value": "+0.4%", "sentiment": "positive"},
        "us": {"value": "Green", "sentiment": "positive"},
        "fii": {"value": "Net Buyer", "sentiment": "positive"}
    },
    
    # Holding data (Positional/Investment)
    "holding": {
        "entry_price": 2680,
        "avg_cost": 2680,
        "pnl_pct": 6.2,
        "profit": 1656,
        "weight": 12
    },
    
    # Context
    "context": [
        {"text": "Trend Intact", "sentiment": "positive", "icon": "fa-check"},
        {"text": "Above 50 DMA", "sentiment": "positive"}
    ],
    
    # Confidence
    "confidence": 80
}
```

## Custom Jinja2 Filters

- `format_price`: Formats float to Indian price format (₹1,234.56)

## CSS Classes Reference

### Action Badges
- `.action-badge.long` - Green (Buy/Long)
- `.action-badge.short` - Red (Sell/Short)
- `.action-badge.breakout` - Cyan
- `.action-badge.btst` - Blue
- `.action-badge.hold` - Yellow
- `.action-badge.reduce` - Orange
- `.action-badge.accumulate` - Purple
- `.action-badge.core` - Cyan

### Tags
- `.tag-new` - Green background
- `.tag-urgent` - Orange background
- `.tag-holding` - Blue background
- `.tag-bullish` - Green border
- `.tag-bearish` - Red border
- `.tag-neutral` - Yellow border
- `.tag-smc` - Cyan border
- `.tag-volume` - Purple border
- `.tag-phase` - Orange border
- `.tag-sector` - Teal border
- `.tag-score` - Gray background

### Info Boxes
- `.info-box.tech` - Blue left border (Technicals)
- `.info-box.fo` - Purple left border (F&O)
- `.info-box.fvg` - Cyan left border (FVG)
- `.info-box.context` - Teal left border (Context)
- `.info-box.phase` - Orange left border (Wyckoff)

### Status Classes
- `.bullish` - Green text
- `.bearish` - Red text
- `.neutral` - Yellow text
- `.overbought` - Orange text
- `.oversold` - Cyan text

## WebSocket Integration

The `queen.js` file includes a `QueenWebSocket` class for real-time updates:

```javascript
const ws = new QueenWebSocket('ws://localhost:8000/ws');
ws.connect();
```

Message types:
- `price_update`: Update price on cards
- `new_signal`: Add new signal card
- `signal_update`: Update existing signal
- `remove_signal`: Remove signal card

## Responsive Design

- Desktop: 3-column grid (min-width: 360px per card)
- Tablet: 2-column grid
- Mobile: 1-column grid, stacked FVG zones
