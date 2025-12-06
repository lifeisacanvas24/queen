# Queen Trading Cockpit - Master Implementation Plan

> **SINGLE SOURCE OF TRUTH** - All project requirements, architecture, and implementation details.
>
> **Version**: 8.0 - DASHBOARD COMPLETE
> **Last Updated**: December 5, 2025

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Current State Analysis](#2-current-state-analysis)
3. [New Modules Implementation Status](#3-new-modules-implementation-status)
4. [Dashboard Implementation Status](#4-dashboard-implementation-status) ⭐ NEW
5. [Gap Analysis & Priority Tasks](#5-gap-analysis--priority-tasks)
6. [Indicator Implementation Priority Matrix](#6-indicator-implementation-priority-matrix)
7. [Project Structure](#7-project-structure)
8. [Dashboard Card Mapping](#8-dashboard-card-mapping)
9. [Database Design](#9-database-design)
10. [Technical Standards](#10-technical-standards)
11. [File Installation Guide](#11-file-installation-guide)
12. [Next Steps](#12-next-steps)

---

## 1. Project Overview

### 1.1 Vision

A **layman-friendly Trading Cockpit** that cuts noise and doesn't miss real trading breakouts across all timeframes.

### 1.2 Core Principles

| Principle                   | Description                          | Status      |
| --------------------------- | ------------------------------------ | ----------- |
| **100% DRY**                | No code duplication - shared helpers | ✅ Complete |
| **100% Polars**             | No pandas anywhere                   | ✅ Complete |
| **100% Forward Compatible** | Type hints, modern Python 3.11+      | ✅ Complete |

### 1.3 Tech Stack

- **Backend**: Python 3.11+, FastAPI, Polars
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Data Source**: Upstox API (REST + WebSocket)
- **Frontend**: HTML/CSS/JS (Apple Design System), Jinja2 templates ✅ NEW

### 1.4 Timeframes

| Category   | Holding Period  | Candle Intervals | Use Case                |
| ---------- | --------------- | ---------------- | ----------------------- |
| Scalp      | 5-15 minutes    | 1m, 5m           | Quick momentum trades   |
| Intraday   | 15min - 4 hours | 15m, 1h          | Day trading             |
| BTST       | Overnight       | 1h, 4h           | Buy Today Sell Tomorrow |
| Swing      | 2-7 days        | 4h, 1d           | Short-term trends       |
| Positional | Weeks-Months    | 1d, 1w           | Medium-term holdings    |
| Investment | Long-term       | 1w, 1M           | Core portfolio          |

---

## 2. Current State Analysis

### 2.1 What Already Exists (✅ BUILT)

#### Data Layer

| Component      | Location                     | Status      |
| -------------- | ---------------------------- | ----------- |
| Upstox Fetcher | `fetchers/upstox_fetcher.py` | ✅ Complete |
| NSE Fetcher    | `fetchers/nse_fetcher.py`    | ✅ Complete |
| Options Chain  | `fetchers/options_chain.py`  | ✅ Complete |
| Schema Adapter | `helpers/schema_adapter.py`  | ✅ Complete |
| Candle Adapter | `helpers/candle_adapter.py`  | ✅ Complete |

#### Technical Indicators

| Category                       | Modules                                      | Status      |
| ------------------------------ | -------------------------------------------- | ----------- |
| Core (RSI, EMA, SMA)           | `technicals/indicators/core.py`              | ✅ Complete |
| Advanced (BB, Supertrend, ATR) | `technicals/indicators/advanced.py`          | ✅ Complete |
| ADX/DMI                        | `technicals/indicators/adx_dmi.py`           | ✅ Complete |
| MACD                           | `technicals/indicators/momentum_macd.py`     | ✅ Complete |
| Keltner Channels               | `technicals/indicators/keltner.py`           | ✅ Complete |
| Volume (Chaikin, MFI)          | `technicals/indicators/volume_*.py`          | ✅ Complete |
| Volatility Fusion              | `technicals/indicators/volatility_fusion.py` | ✅ Complete |

#### Pattern Detection

| Type               | Location                           | Status      |
| ------------------ | ---------------------------------- | ----------- |
| Core Patterns      | `technicals/patterns/core.py`      | ✅ Complete |
| Composite Patterns | `technicals/patterns/composite.py` | ✅ Complete |
| Pattern Runner     | `technicals/patterns/runner.py`    | ✅ Complete |

#### Microstructure (Existing)

| Component       | Location                                 | Status      |
| --------------- | ---------------------------------------- | ----------- |
| CPR             | `technicals/microstructure/cpr.py`       | ✅ Complete |
| VWAP            | `technicals/microstructure/vwap.py`      | ✅ ENHANCED |
| Volume Analysis | `technicals/microstructure/volume.py`    | ✅ Complete |
| Structure       | `technicals/microstructure/structure.py` | ✅ ENHANCED |
| Phases          | `technicals/microstructure/phases.py`    | ✅ Complete |
| Risk            | `technicals/microstructure/risk.py`      | ✅ Complete |

#### Services Layer

| Service           | Location                        | Status      |
| ----------------- | ------------------------------- | ----------- |
| Scoring Engine    | `services/scoring.py`           | ✅ Complete |
| Bible Engine      | `services/bible_engine.py`      | ✅ Complete |
| Tactical Pipeline | `services/tactical_pipeline.py` | ✅ Complete |
| Cockpit Row       | `services/cockpit_row.py`       | ✅ Complete |
| Live Service      | `services/live.py`              | ✅ Complete |
| Morning Intel     | `services/morning.py`           | ✅ Complete |

---

## 3. New Modules Implementation Status

### 3.1 Smart Money Concepts (SMC) - 8/8 ✅ 100%

| Indicator                       | File                                  | Purpose                   | Status      |
| ------------------------------- | ------------------------------------- | ------------------------- | ----------- |
| **Fair Value Gap (FVG)**        | `microstructure/fvg.py`               | Institutional imbalances  | ✅ **DONE** |
| **Order Blocks**                | `microstructure/order_blocks.py`      | Institutional entry zones | ✅ **DONE** |
| **Liquidity Sweeps**            | `microstructure/liquidity.py`         | Stop hunt detection       | ✅ **DONE** |
| **Breaker Blocks**              | `microstructure/breaker_blocks.py`    | Failed OB = reversal      | ✅ **DONE** |
| **BOS (Break of Structure)**    | `microstructure/bos_choch.py`         | Trend continuation        | ✅ **DONE** |
| **CHoCH (Change of Character)** | `microstructure/bos_choch.py`         | First reversal sign       | ✅ **DONE** |
| **Mitigation Blocks**           | `microstructure/mitigation_blocks.py` | Track unmitigated OBs     | ✅ **DONE** |
| **Premium/Discount Zones**      | `microstructure/premium_discount.py`  | Price zone analysis       | ✅ **DONE** |

### 3.2 Volume Confirmation - 8/8 ✅ 100%

| Indicator                     | File                                | Purpose              | Status      |
| ----------------------------- | ----------------------------------- | -------------------- | ----------- |
| **RVOL (Relative Volume)**    | `indicators/volume_confirmation.py` | Volume vs 20-day avg | ✅ **DONE** |
| **Volume Spike Detection**    | `indicators/volume_confirmation.py` | Sudden volume surge  | ✅ **DONE** |
| **Volume Trend**              | `indicators/volume_confirmation.py` | Inc/Dec/Stable       | ✅ **DONE** |
| **Accumulation/Distribution** | `indicators/volume_confirmation.py` | Smart money flow     | ✅ **DONE** |
| **Volume Profile / POC**      | `indicators/volume_profile.py`      | Point of Control     | ✅ **DONE** |
| **VAH / VAL**                 | `indicators/volume_profile.py`      | Value Area           | ✅ **DONE** |
| **Delta Volume**              | `indicators/delta_volume.py`        | Buy vs Sell pressure | ✅ **DONE** |
| **VWAP Bands**                | `microstructure/vwap.py`            | 1σ, 2σ, 3σ bands     | ✅ **DONE** |

### 3.3 False Breakout Patterns - 5/5 ✅ 100%

| Pattern                         | File                         | Purpose             | Status      |
| ------------------------------- | ---------------------------- | ------------------- | ----------- |
| **Swing Failure Pattern (SFP)** | `patterns/false_breakout.py` | Classic SFP         | ✅ **DONE** |
| **Fakeout Candle**              | `patterns/false_breakout.py` | Long wick rejection | ✅ **DONE** |
| **Bull/Bear Trap**              | `patterns/false_breakout.py` | Trap detection      | ✅ **DONE** |
| **Stop Hunt Reversal**          | `patterns/false_breakout.py` | Sweep + reverse     | ✅ **DONE** |
| **False Breakout Risk**         | `patterns/false_breakout.py` | Combined assessment | ✅ **DONE** |

### 3.4 Wyckoff Theory - 9/9 ✅ 100%

| Pattern                    | File                        | Purpose                  | Status      |
| -------------------------- | --------------------------- | ------------------------ | ----------- |
| **Spring**                 | `microstructure/wyckoff.py` | False breakdown          | ✅ **DONE** |
| **Upthrust**               | `microstructure/wyckoff.py` | False breakout           | ✅ **DONE** |
| **Selling Climax**         | `microstructure/wyckoff.py` | Exhaustion selling       | ✅ **DONE** |
| **Buying Climax**          | `microstructure/wyckoff.py` | Exhaustion buying        | ✅ **DONE** |
| **Sign of Strength (SOS)** | `microstructure/wyckoff.py` | Bullish confirmation     | ✅ **DONE** |
| **Sign of Weakness (SOW)** | `microstructure/wyckoff.py` | Bearish confirmation     | ✅ **DONE** |
| **Automatic Rally**        | `microstructure/wyckoff.py` | Bounce after SC          | ✅ **DONE** |
| **Secondary Test**         | `microstructure/wyckoff.py` | Retest of SC             | ✅ **DONE** |
| **Phase Identification**   | `microstructure/wyckoff.py` | Acc/Markup/Dist/Markdown | ✅ **DONE** |

### 3.5 Breakout Validation - 5/5 ✅ 100%

| Indicator                 | File                            | Purpose                  | Status      |
| ------------------------- | ------------------------------- | ------------------------ | ----------- |
| **ATR Breakout Filter**   | `signals/breakout_validator.py` | Breakout > 1x ATR        | ✅ **DONE** |
| **Consecutive Close**     | `signals/breakout_validator.py` | 2+ closes beyond         | ✅ **DONE** |
| **Breakout Score (1-10)** | `signals/breakout_validator.py` | Combined scoring         | ✅ **DONE** |
| **MTF Confirmation**      | `signals/breakout_validator.py` | HTF alignment            | ✅ **DONE** |
| **Quality Label**         | `signals/breakout_validator.py` | Excellent/Good/Fair/Weak | ✅ **DONE** |

### 3.6 Shared Helpers - 3/3 ✅ 100%

| Helper              | File                            | Used By     | Status      |
| ------------------- | ------------------------------- | ----------- | ----------- |
| **Swing Detection** | `helpers/swing_detection.py`    | 12+ modules | ✅ **DONE** |
| **ATR Calculation** | `helpers/ta_math.py`            | 15+ modules | ✅ Existing |
| **Settings**        | `settings/breakout_settings.py` | All modules | ✅ **DONE** |

---

## 4. Dashboard Implementation Status ⭐ NEW

### 4.1 Dashboard Components - 100% ✅ COMPLETE

| Component           | File                                     | Purpose                     | Status      |
| ------------------- | ---------------------------------------- | --------------------------- | ----------- |
| **Base Layout**     | `templates/base.html`                    | Main page structure         | ✅ **DONE** |
| **Header**          | `templates/components/header.html`       | Logo, controls, status      | ✅ **DONE** |
| **Stats Bar**       | `templates/components/stats_bar.html`    | Buy/Sell/Hold/Urgent counts | ✅ **DONE** |
| **Tabs Navigation** | `templates/components/tabs_nav.html`     | 7 timeframe tabs            | ✅ **DONE** |
| **Sub Filters**     | `templates/components/sub_filters.html`  | Filter pills                | ✅ **DONE** |
| **Signals Grid**    | `templates/components/signals_grid.html` | Cards container             | ✅ **DONE** |
| **Footer**          | `templates/components/footer.html`       | Status, version             | ✅ **DONE** |

### 4.2 Card Templates - 6/6 ✅ 100%

| Card Type           | File                         | Timeframe | Special Components       |
| ------------------- | ---------------------------- | --------- | ------------------------ |
| **Scalp Card**      | `cards/card_scalp.html`      | 5M        | FVG Zones, VWAP σ, Delta |
| **Intraday Card**   | `cards/card_intraday.html`   | 2-4 hrs   | Technicals Box, F&O Box  |
| **BTST Card**       | `cards/card_btst.html`       | Overnight | Global Cues, Gap Prob%   |
| **Swing Card**      | `cards/card_swing.html`      | 2-5 days  | Weekly Technicals, RS    |
| **Positional Card** | `cards/card_positional.html` | Weeks+    | P&L Box, Trail SL        |
| **Investment Card** | `cards/card_investment.html` | Long-term | Thesis, Valuation        |

### 4.3 Card Partials (Reusable) - 7/7 ✅ 100%

| Partial           | File                          | Used By                  |
| ----------------- | ----------------------------- | ------------------------ |
| **Signal Score**  | `partials/signal_score.html`  | All cards                |
| **R:R Box**       | `partials/rr_box.html`        | All cards                |
| **Wyckoff Phase** | `partials/wyckoff_phase.html` | Scalp, Swing, Positional |
| **FVG Zones**     | `partials/fvg_zones.html`     | Scalp, Intraday          |
| **Trade Levels**  | `partials/trade_levels.html`  | Scalp                    |
| **Context Box**   | `partials/context_box.html`   | All cards                |
| **Confidence**    | `partials/confidence.html`    | All cards                |

### 4.4 Services - 2/2 ✅ 100%

| Service              | File                           | Purpose                   | Status      |
| -------------------- | ------------------------------ | ------------------------- | ----------- |
| **Card Generator**   | `services/card_generator.py`   | Signal → Card data mapper | ✅ **DONE** |
| **Dashboard Router** | `services/dashboard_router.py` | FastAPI endpoints         | ✅ **DONE** |

### 4.5 Static Assets - 2/2 ✅ 100%

| Asset          | File                   | Lines | Status                      |
| -------------- | ---------------------- | ----- | --------------------------- |
| **CSS**        | `static/css/queen.css` | 400+  | ✅ Apple Design System      |
| **JavaScript** | `static/js/queen.js`   | 200+  | ✅ Tab switching, WebSocket |

### 4.6 Dashboard Features Implemented

| Feature               | Description                                                     | Status      |
| --------------------- | --------------------------------------------------------------- | ----------- |
| **7 Timeframe Tabs**  | Scalp, Intraday, BTST, Swing, Positional, Investment, Portfolio | ✅          |
| **Sub-Filter Pills**  | Long/Short/Breakout/All filtering per tab                       | ✅          |
| **Action Badges**     | Long, Short, Breakout, BTST, Hold, Reduce, Accumulate, Core     | ✅          |
| **Technicals Box**    | RSI, MACD, EMA, ATR with status colors                          | ✅          |
| **F&O Sentiment Box** | PCR, OI, Max Pain, IV with signal badges                        | ✅          |
| **Wyckoff Phase Bar** | 4-phase visual bar with active highlight                        | ✅          |
| **FVG Zones**         | Above/Below zones with target/support types                     | ✅          |
| **Global Cues**       | SGX Nifty, US Futures, FII status (BTST)                        | ✅          |
| **Gap Probability**   | Progress bar showing gap up % (BTST)                            | ✅          |
| **P&L Tracking**      | Entry, P&L %, Profit amount (Positional/Investment)             | ✅          |
| **Investment Thesis** | Quality score, Valuation, Dividend yield                        | ✅          |
| **Real-time Clock**   | Updates every second                                            | ✅          |
| **Tab Count Badges**  | Signal count per tab                                            | ✅          |
| **Urgent Cards**      | Orange border for time-sensitive signals                        | ✅          |
| **Responsive Grid**   | 1-3 columns based on screen width                               | ✅          |
| **WebSocket Class**   | Ready for real-time updates                                     | ✅ Skeleton |

---

## 5. Gap Analysis & Priority Tasks

### 5.1 What's Complete ✅

| Feature                  | Status  | Notes                                  |
| ------------------------ | ------- | -------------------------------------- |
| All 38 Technical Modules | ✅ 100% | SMC, Wyckoff, Volume, Breakout         |
| Dashboard Templates      | ✅ 100% | 6 card types, 7 partials, 6 components |
| Card Generator           | ✅ 100% | Maps signals to card data              |
| CSS Design System        | ✅ 100% | Apple-style dark theme                 |
| JavaScript Core          | ✅ 100% | Tabs, filters, clock                   |

### 5.2 What's Remaining 🟡

| Feature                         | Current State              | Priority | Effort  |
| ------------------------------- | -------------------------- | -------- | ------- |
| **WebSocket Integration**       | Skeleton ready             | **P1**   | 2-4 hrs |
| **Database Setup**              | Not started                | **P1**   | 4-6 hrs |
| **Signal Pipeline Integration** | Modules exist, need wiring | **P1**   | 4-6 hrs |
| **Portfolio Tab Backend**       | Template ready             | **P2**   | 4-6 hrs |
| **History Tab**                 | Not started                | **P2**   | 4-6 hrs |
| **F&O Enhancement**             | PCR/OI exists              | **P3**   | 2-4 hrs |

### 5.3 F&O Based Confirmation (India Specific) 🟡

| Indicator                   | Purpose                                 | Status     | Priority |
| --------------------------- | --------------------------------------- | ---------- | -------- |
| PCR at Breakout Level       | High PCR at resistance = real breakout  | ✅ Exists  | Done     |
| OI Build-up Direction       | Long/Short build-up confirmation        | ✅ Exists  | Done     |
| Max Pain Movement           | Breakout towards max pain = sustainable | ✅ Exists  | Done     |
| IV Crush Detection          | Low IV breakout more reliable           | 🔲 Missing | **P3**   |
| OI-based Support/Resistance | Highest OI strikes as S/R               | 🔲 Missing | **P3**   |

---

## 6. Indicator Implementation Priority Matrix

### 6.1 By Timeframe Usage

| Indicator         | Scalp | Intraday | BTST | Swing | Positional | Investment |
| ----------------- | :---: | :------: | :--: | :---: | :--------: | :--------: |
| FVG               |  ✅   |    ✅    |  ✅  |   -   |     -      |     -      |
| Order Blocks      |  ✅   |    ✅    |  ✅  |   -   |     -      |     -      |
| Wyckoff Phase     |  ✅   |    -     |  -   |  ✅   |     ✅     |     ✅     |
| RVOL              |  ✅   |    ✅    |  ✅  |   -   |     -      |     -      |
| VWAP Bands        |  ✅   |    ✅    |  -   |   -   |     -      |     -      |
| PCR               |   -   |    ✅    |  ✅  |   -   |     -      |     -      |
| OI                |   -   |    ✅    |  ✅  |   -   |     -      |     -      |
| Global Cues       |   -   |    -     |  ✅  |   -   |     -      |     -      |
| Weekly RSI        |   -   |    -     |  -   |  ✅   |     ✅     |     -      |
| RS (Rel Strength) |   -   |    -     |  -   |  ✅   |     -      |     -      |
| Quality Score     |   -   |    -     |  -   |   -   |     -      |     ✅     |
| Valuation         |   -   |    -     |  -   |   -   |     -      |     ✅     |

---

## 7. Project Structure

### 7.1 Complete File Tree

```
queen/
├── fetchers/
│   ├── upstox_fetcher.py      ✅
│   ├── nse_fetcher.py         ✅
│   └── options_chain.py       ✅
├── helpers/
│   ├── schema_adapter.py      ✅
│   ├── candle_adapter.py      ✅
│   ├── swing_detection.py     ✅ NEW
│   └── ta_math.py             ✅
├── technicals/
│   ├── indicators/
│   │   ├── core.py            ✅
│   │   ├── advanced.py        ✅
│   │   ├── volume_confirmation.py  ✅ NEW
│   │   ├── volume_profile.py       ✅ NEW
│   │   └── delta_volume.py         ✅ NEW
│   ├── microstructure/
│   │   ├── fvg.py             ✅ NEW
│   │   ├── order_blocks.py    ✅ NEW
│   │   ├── liquidity.py       ✅ NEW
│   │   ├── breaker_blocks.py  ✅ NEW
│   │   ├── bos_choch.py       ✅ NEW
│   │   ├── mitigation_blocks.py ✅ NEW
│   │   ├── premium_discount.py  ✅ NEW
│   │   ├── wyckoff.py         ✅ NEW
│   │   ├── vwap.py            ✅ ENHANCED
│   │   └── structure.py       ✅ ENHANCED
│   ├── patterns/
│   │   ├── core.py            ✅
│   │   ├── composite.py       ✅
│   │   ├── false_breakout.py  ✅ NEW
│   │   └── runner.py          ✅
│   └── signals/
│       └── breakout_validator.py ✅ NEW
├── settings/
│   └── breakout_settings.py   ✅ NEW
├── services/
│   ├── scoring.py             ✅
│   ├── bible_engine.py        ✅
│   ├── tactical_pipeline.py   ✅
│   ├── cockpit_row.py         ✅
│   ├── card_generator.py      ✅ NEW
│   └── dashboard_router.py    ✅ NEW
├── templates/                 ✅ NEW
│   ├── base.html
│   ├── dashboard.html
│   ├── components/
│   │   ├── header.html
│   │   ├── stats_bar.html
│   │   ├── tabs_nav.html
│   │   ├── sub_filters.html
│   │   ├── signals_grid.html
│   │   └── footer.html
│   └── cards/
│       ├── card_base.html
│       ├── card_scalp.html
│       ├── card_intraday.html
│       ├── card_btst.html
│       ├── card_swing.html
│       ├── card_positional.html
│       ├── card_investment.html
│       └── partials/
│           ├── signal_score.html
│           ├── rr_box.html
│           ├── wyckoff_phase.html
│           ├── fvg_zones.html
│           ├── trade_levels.html
│           ├── context_box.html
│           └── confidence.html
├── static/                    ✅ NEW
│   ├── css/queen.css
│   └── js/queen.js
└── tests/
    └── smoke_breakout_modules.py ✅
```

---

## 8. Dashboard Card Mapping

### 8.1 Signal-to-Card Type

| Signal Type           | Card Template          | Tab        |
| --------------------- | ---------------------- | ---------- |
| Scalp Long            | `card_scalp.html`      | Scalp      |
| Scalp Short           | `card_scalp.html`      | Scalp      |
| Breakout (5M)         | `card_scalp.html`      | Scalp      |
| Intraday Long         | `card_intraday.html`   | Intraday   |
| Intraday Short        | `card_intraday.html`   | Intraday   |
| Intraday Breakout     | `card_intraday.html`   | Intraday   |
| BTST Buy              | `card_btst.html`       | BTST       |
| Swing Fresh           | `card_swing.html`      | Swing      |
| Swing Active          | `card_swing.html`      | Swing      |
| Positional Fresh      | `card_positional.html` | Positional |
| Positional Hold       | `card_positional.html` | Positional |
| Positional Reduce     | `card_positional.html` | Positional |
| Investment Accumulate | `card_investment.html` | Investment |
| Investment Core       | `card_investment.html` | Investment |

### 8.2 Card Data Schema

```python
{
    # Identity
    "symbol": "RELIANCE",
    "company_name": "Reliance Industries Ltd",
    "current_price": 2847.50,
    "price_change": 1.25,

    # Action
    "action_class": "long",
    "action_icon": "fa-arrow-trend-up",
    "action_label": "SCALP LONG",
    "timeframe_label": "5M",
    "category": "scalp-long",
    "is_urgent": False,

    # Score & Tags
    "score": 8.5,
    "tags": [{"type": "new", "label": "NEW", "icon": "fa-star"}],

    # Trade Levels
    "risk_pct": "-0.5%",
    "reward_pct": "+1.0%",
    "rr_ratio": "1:2",
    "entry": 2845,
    "target": 2875,
    "stop_loss": 2830,

    # Technicals (Intraday+)
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

    # SMC
    "wyckoff_phase": "accumulation",
    "fvg_zones": {
        "above": {"range": "1720 - 1735", "type": "Target Zone"},
        "below": {"range": "1655 - 1665", "type": "Support Zone"}
    },

    # BTST
    "global_cues": {
        "sgx": {"value": "+0.4%", "sentiment": "positive"},
        "us": {"value": "Green", "sentiment": "positive"},
        "fii": {"value": "Net Buyer", "sentiment": "positive"}
    },
    "gap_probability": 78,

    # Positional/Investment
    "holding": {
        "entry_price": 2680,
        "pnl_pct": 6.2,
        "profit": 1656,
        "weight": 12
    },

    # Context
    "context": [
        {"text": "Trend Intact", "sentiment": "positive", "icon": "fa-check"}
    ],

    # Confidence
    "confidence": 80
}
```

---

## 9. Database Design

### 9.1 Trades Table

```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,  -- 'long' / 'short'
    entry_price REAL,
    exit_price REAL,
    quantity INTEGER,
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    pnl REAL,
    pnl_pct REAL,
    timeframe TEXT,
    strategy TEXT,
    status TEXT  -- 'open' / 'closed'
);
```

### 9.2 Positions Table

```sql
CREATE TABLE positions (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    avg_cost REAL,
    quantity INTEGER,
    current_price REAL,
    pnl REAL,
    pnl_pct REAL,
    weight_pct REAL,
    category TEXT  -- 'core' / 'swing' / 'scalp'
);
```

### 9.3 Signals Table (NEW)

```sql
CREATE TABLE signals (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    direction TEXT,
    action TEXT,
    score REAL,
    entry_price REAL,
    target_price REAL,
    stop_loss REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    status TEXT DEFAULT 'active'  -- 'active' / 'triggered' / 'expired'
);
```

---

## 10. Technical Standards

### 10.1 All Standards Met ✅

- ✅ 100% Polars (no pandas)
- ✅ 100% DRY (shared helpers)
- ✅ 100% Settings-driven
- ✅ Type hints on all functions
- ✅ Docstrings with usage examples
- ✅ Fallback defaults for imports
- ✅ Registry pattern with EXPORTS dict
- ✅ CLI test in `__main__` block
- ✅ Apple Design System CSS
- ✅ Jinja2 template inheritance

### 10.2 DRY Import Pattern

```python
# All modules follow this pattern:
try:
    from queen.helpers.swing_detection import find_swing_points
    _USE_SHARED_SWING = True
except ImportError:
    _USE_SHARED_SWING = False
```

---

## 11. File Installation Guide

### 11.1 Copy Template Files to Project

```bash
# Unzip the templates package
unzip queen_templates_v3.zip

# Copy to your queen project
cp -r queen_templates/templates queen/
cp -r queen_templates/static queen/
cp queen_templates/services/card_generator.py queen/services/
cp queen_templates/services/dashboard_router.py queen/services/
```

### 11.2 Update FastAPI App

```python
# In your main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from services.dashboard_router import router as dashboard_router

app = FastAPI(title="Queen Cockpit")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include dashboard router
app.include_router(dashboard_router)
```

### 11.3 Run Smoke Tests

```bash
cd queen
python -m tests.smoke_breakout_modules
```

---

## 12. Next Steps

### Phase 5: Integration (Priority 1) ⬅️ CURRENT

| Task                 | File                           | Description                    | Est. Time |
| -------------------- | ------------------------------ | ------------------------------ | --------- |
| 1. WebSocket Service | `services/websocket.py`        | Real-time price/signal updates | 2-4 hrs   |
| 2. Signal Pipeline   | `services/signal_pipeline.py`  | Wire modules → card generator  | 4-6 hrs   |
| 3. Database Setup    | `database/models.py`           | SQLite tables + migrations     | 4-6 hrs   |
| 4. API Integration   | `services/dashboard_router.py` | Connect real signal data       | 2-4 hrs   |

### Phase 6: Portfolio & History (Priority 2)

| Task              | Description                 | Est. Time |
| ----------------- | --------------------------- | --------- |
| Portfolio Backend | CRUD + live P&L calculation | 4-6 hrs   |
| History Tab       | Trade history + analytics   | 4-6 hrs   |
| Trade Execution   | Optional order placement    | 8+ hrs    |

### Phase 7: F&O Enhancement (Priority 3)

| Task               | Description                      | Est. Time |
| ------------------ | -------------------------------- | --------- |
| IV Crush detection | Identify low IV breakouts        | 2-4 hrs   |
| OI-based S/R       | Highest OI as support/resistance | 2-4 hrs   |
| VIX integration    | Filter high-VIX conditions       | 2-4 hrs   |

---

## Summary Statistics

| Category                | Done   | Total  | Progress    |
| ----------------------- | ------ | ------ | ----------- |
| SMC Modules             | 8      | 8      | **100%** ✅ |
| Volume Modules          | 8      | 8      | **100%** ✅ |
| False Breakout          | 5      | 5      | **100%** ✅ |
| Wyckoff                 | 9      | 9      | **100%** ✅ |
| Breakout Validation     | 5      | 5      | **100%** ✅ |
| Shared Helpers          | 3      | 3      | **100%** ✅ |
| **Dashboard Templates** | **20** | **20** | **100%** ✅ |
| **Dashboard Services**  | **2**  | **2**  | **100%** ✅ |
| **Static Assets**       | **2**  | **2**  | **100%** ✅ |
| **Total Components**    | **62** | **62** | **100%** ✅ |

### Code Statistics

| Category           | Lines             |
| ------------------ | ----------------- |
| Technical Modules  | ~8,930            |
| Jinja2 Templates   | ~1,200            |
| CSS                | ~400              |
| JavaScript         | ~200              |
| Card Generator     | ~500              |
| **Total New Code** | **~11,230 lines** |

---

## Files Delivered

| File                     | Size      | Contents                          |
| ------------------------ | --------- | --------------------------------- |
| `queen_templates_v3.zip` | 35 KB     | Complete Jinja2 templates package |
| `queen_cockpit_v3.html`  | 77 KB     | Standalone HTML reference         |
| `queen_FINAL_v9.zip`     | 104 KB    | All technical modules             |
| `QUEEN_MASTER_PLAN.md`   | This file | Project documentation             |

---

_End of Master Plan - v8.0 DASHBOARD COMPLETE_
