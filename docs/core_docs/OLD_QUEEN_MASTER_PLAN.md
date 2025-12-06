# Queen Trading Cockpit - Master Implementation Plan

> **SINGLE SOURCE OF TRUTH** - All project requirements, architecture, and implementation details in one document.
>
> Last Updated: December 3, 2025

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Current State Analysis](#2-current-state-analysis)
3. [Target Dashboard Analysis](#3-target-dashboard-analysis)
4. [Gap Analysis & Priority Tasks](#4-gap-analysis--priority-tasks)
5. [Revised Implementation Roadmap](#5-revised-implementation-roadmap)
6. [Project Structure](#6-project-structure-current--target-hybrid)
7. [Core Architecture](#7-core-architecture)
8. [Feature Specifications](#8-feature-specifications)
9. [Database Design](#9-database-design)
10. [API Endpoints](#10-api-endpoints)
11. [Frontend Integration](#11-frontend-integration)
12. [Legacy Implementation Roadmap](#12-legacy-implementation-roadmap) _(superseded by section 5)_
13. [Technical Standards](#13-technical-standards)
14. [Open Questions](#14-open-questions)
15. [Changelog](#15-changelog)

---

## 1. Project Overview

### 1.1 Vision

A **layman-friendly Trading Cockpit** that cuts noise and doesn't miss real trading breakouts across all timeframes.

### 1.2 Core Principles

| Principle                   | Description                                                                 |
| --------------------------- | --------------------------------------------------------------------------- |
| **100% DRY**                | No code duplication - abstract base classes, factories, reusable components |
| **100% Polars**             | No pandas anywhere - all DataFrame operations use Polars                    |
| **100% Forward Compatible** | Type hints, Pydantic models, async/await, modern Python 3.11+               |

### 1.3 Tech Stack

- **Backend**: Python 3.11+, FastAPI, Polars
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Data Source**: Upstox API (REST + WebSocket)
- **Frontend**: HTML/CSS/JS (Bulma framework), Jinja2 templates

### 1.4 Timeframes Covered

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

Based on your codebase analysis, you have an **extensive system** already:

#### Data Layer

| Component      | Location                     | Status      | Notes                       |
| -------------- | ---------------------------- | ----------- | --------------------------- |
| Upstox Fetcher | `fetchers/upstox_fetcher.py` | ✅ Complete | Historical candles, caching |
| NSE Fetcher    | `fetchers/nse_fetcher.py`    | ✅ Complete | Quotes, corporate data      |
| Options Chain  | `fetchers/options_chain.py`  | ✅ Complete | F&O data                    |
| Schema Adapter | `helpers/schema_adapter.py`  | ✅ Complete | Polars-native               |
| Candle Adapter | `helpers/candle_adapter.py`  | ✅ Complete | Broker normalization        |

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
| Breadth Indicators             | `technicals/indicators/breadth_*.py`         | ✅ Complete |

#### Pattern Detection

| Type               | Location                           | Status      |
| ------------------ | ---------------------------------- | ----------- |
| Core Patterns      | `technicals/patterns/core.py`      | ✅ Complete |
| Composite Patterns | `technicals/patterns/composite.py` | ✅ Complete |
| Pattern Runner     | `technicals/patterns/runner.py`    | ✅ Complete |

#### Smart Money / Microstructure

| Component       | Location                                 | Status      |
| --------------- | ---------------------------------------- | ----------- |
| CPR             | `technicals/microstructure/cpr.py`       | ✅ Complete |
| VWAP            | `technicals/microstructure/vwap.py`      | ✅ Complete |
| Volume Analysis | `technicals/microstructure/volume.py`    | ✅ Complete |
| Structure       | `technicals/microstructure/structure.py` | ✅ Complete |
| Phases          | `technicals/microstructure/phases.py`    | ✅ Complete |
| Risk            | `technicals/microstructure/risk.py`      | ✅ Complete |

#### Signal Generation

| Component      | Location                                                 | Status      |
| -------------- | -------------------------------------------------------- | ----------- |
| Tactical Core  | `technicals/signals/tactical/core.py`                    | ✅ Complete |
| Bias Regime    | `technicals/signals/tactical/bias_regime.py`             | ✅ Complete |
| Divergence     | `technicals/signals/tactical/divergence.py`              | ✅ Complete |
| Exhaustion     | `technicals/signals/tactical/exhaustion.py`              | ✅ Complete |
| Reversal Stack | `technicals/signals/tactical/reversal_stack.py`          | ✅ Complete |
| Squeeze Pulse  | `technicals/signals/tactical/squeeze_pulse.py`           | ✅ Complete |
| Liquidity Trap | `technicals/signals/tactical/tactical_liquidity_trap.py` | ✅ Complete |
| Pattern Fusion | `technicals/signals/pattern_fusion.py`                   | ✅ Complete |
| Pre-Breakout   | `technicals/signals/pre_breakout.py`                     | ✅ Complete |
| CMV Fusion     | `technicals/signals/fusion/cmv.py`                       | ✅ Complete |
| Market Regime  | `technicals/signals/fusion/market_regime.py`             | ✅ Complete |

#### Services Layer

| Service           | Location                        | Status      |
| ----------------- | ------------------------------- | ----------- |
| Scoring Engine    | `services/scoring.py`           | ✅ Complete |
| Bible Engine      | `services/bible_engine.py`      | ✅ Complete |
| Tactical Pipeline | `services/tactical_pipeline.py` | ✅ Complete |
| Actionable Row    | `services/actionable_row.py`    | ✅ Complete |
| Cockpit Row       | `services/cockpit_row.py`       | ✅ Complete |
| Live Service      | `services/live.py`              | ✅ Complete |
| Morning Intel     | `services/morning.py`           | ✅ Complete |
| Forecast          | `services/forecast.py`          | ✅ Complete |
| History           | `services/history.py`           | ✅ Complete |
| Ladder State      | `services/ladder_state.py`      | ✅ Complete |

#### Strategy Layer

| Component           | Location                            | Status      |
| ------------------- | ----------------------------------- | ----------- |
| Decision Engine     | `strategies/decision_engine.py`     | ✅ Complete |
| Fusion Strategy     | `strategies/fusion.py`              | ✅ Complete |
| Playbook            | `strategies/playbook.py`            | ✅ Complete |
| TV Fusion           | `strategies/tv_fusion.py`           | ✅ Complete |
| Meta Strategy Cycle | `strategies/meta_strategy_cycle.py` | ✅ Complete |

#### Server/API

| Component        | Location                         | Status      |
| ---------------- | -------------------------------- | ----------- |
| FastAPI Main     | `server/main.py`                 | ✅ Complete |
| Cockpit Router   | `server/routers/cockpit.py`      | ✅ Complete |
| Portfolio Router | `server/routers/portfolio.py`    | ✅ Exists   |
| PnL Router       | `server/routers/pnl.py`          | ✅ Exists   |
| Alerts Router    | `server/routers/alerts.py`       | ✅ Exists   |
| Market State     | `server/routers/market_state.py` | ✅ Complete |

#### Settings & Configuration

| Config       | Location                   | Status      |
| ------------ | -------------------------- | ----------- |
| Timeframes   | `settings/timeframes.py`   | ✅ Complete |
| Indicators   | `settings/indicators.py`   | ✅ Complete |
| Patterns     | `settings/patterns.py`     | ✅ Complete |
| Weights      | `settings/weights.py`      | ✅ Complete |
| Regimes      | `settings/regimes.py`      | ✅ Complete |
| Universe     | `settings/universe.py`     | ✅ Complete |
| F&O Universe | `settings/fno_universe.py` | ✅ Complete |

#### Helpers & Utilities

| Helper       | Status      | Notes                               |
| ------------ | ----------- | ----------------------------------- |
| Market Time  | ✅ Complete | Holiday calendar, session detection |
| IO           | ✅ Complete | Atomic writes, Parquet, JSONL       |
| Rate Limiter | ✅ Complete | Token bucket, pool                  |
| Logger       | ✅ Complete | JSONL formatter                     |
| Portfolio    | ✅ Complete | Position loading                    |
| Path Manager | ✅ Complete | Centralized paths                   |

### 2.2 What's Missing or Needs Enhancement (🔴 GAPS)

| Feature                               | Current State                            | Gap                                       |
| ------------------------------------- | ---------------------------------------- | ----------------------------------------- |
| **Portfolio Position DB**             | File-based JSON                          | Need SQLite/PostgreSQL with proper models |
| **Trade History Tracking**            | `services/history.py` exists but limited | Need comprehensive trade recording        |
| **Dashboard Card Generation**         | `cockpit_row.py` exists                  | Need to map to new HTML card format       |
| **Timeframe Tabs (Scalp→Investment)** | Logic exists in `playbook.py`            | Need tab-specific filtering               |
| **Portfolio Tab**                     | Basic `portfolio.py` router              | Need full CRUD + live P&L                 |
| **History Tab**                       | Basic `history.py`                       | Need analytics dashboard                  |
| **F&O Sentiment Display**             | `options_sentiment.py` exists            | Need to integrate into cards              |
| **Wyckoff Phase Visualization**       | `phases.py` exists                       | Need phase bar mapping                    |
| **FVG Detection**                     | Not explicit                             | Need `smart_money/fvg.py`                 |
| **Signal Scoring (1-10)**             | `scoring.py` exists                      | Need to normalize to 1-10 scale           |

### 2.3 Architecture Alignment

Your current architecture is **already very close** to the target:

```
CURRENT STRUCTURE:              TARGET STRUCTURE:
queen/                          queen/server/
├── technicals/                 ├── core/
│   ├── indicators/        →        ├── indicators/     ✅ SAME
│   ├── signals/           →        ├── signals/        ✅ SAME
│   ├── patterns/          →        ├── patterns/       ✅ SAME (move to indicators)
│   └── microstructure/    →        └── smart_money/    ✅ RENAME
├── services/              →    ├── services/           ✅ SAME
├── strategies/            →    (merge into signals/)
├── settings/              →    ├── settings/           ✅ SAME
├── helpers/               →    ├── helpers/            ✅ SAME
├── fetchers/              →    ├── core/data/          ✅ MOVE
└── server/                →    └── api/                ✅ SAME
```

**Key Insight**: You don't need a major restructure - just targeted additions!

---

## 2.4 DRY Audit & Centralization Review

### What's Already Good (✅ DRY Compliant)

| Area                        | Implementation                            | Status             |
| --------------------------- | ----------------------------------------- | ------------------ |
| **Settings Centralization** | `settings/*.py` for all constants         | ✅ Excellent       |
| **Timeframe Config**        | `settings/timeframes.py`                  | ✅ Single source   |
| **Indicator Params**        | `settings/indicator_policy.py`            | ✅ Centralized     |
| **Weights & Thresholds**    | `settings/weights.py`                     | ✅ Configurable    |
| **Regime Detection**        | `settings/regimes.py`                     | ✅ Settings-driven |
| **Pattern Config**          | `settings/patterns.py`                    | ✅ Centralized     |
| **Universe/FnO**            | `settings/universe.py`, `fno_universe.py` | ✅ Complete        |
| **Helper Functions**        | `helpers/*.py`                            | ✅ Well organized  |
| **Registry Pattern**        | `technicals/registry.py`                  | ✅ Auto-scanning   |

### Areas Needing DRY Improvement (🔶 Review Needed)

| Area                 | Issue                                   | Recommendation                           |
| -------------------- | --------------------------------------- | ---------------------------------------- |
| **Duplicate Files**  | `evaluator copy.py`, `alert_v2 copy.py` | Remove duplicates                        |
| **Action Types**     | Scattered across files                  | Create `settings/action_types.py`        |
| **Card Schema**      | New HTML requires mapping               | Create `settings/card_schema.py`         |
| **Score Thresholds** | Some hardcoded in `scoring.py`          | Move to `settings/scoring_thresholds.py` |
| **Timeframe Labels** | "5-15 MIN", "2-7 DAYS" etc.             | Add to `settings/timeframes.py`          |

### Recommended New Settings Files

```python
# settings/action_types.py
from enum import Enum

class ActionType(str, Enum):
    """Central definition of all action types"""
    SCALP_LONG = "SCALP_LONG"
    SCALP_SHORT = "SCALP_SHORT"
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    BREAKOUT = "BREAKOUT"
    # ... all 17 action types

ACTION_COLORS = {
    ActionType.SCALP_LONG: "#26a69a",
    ActionType.SCALP_SHORT: "#ef5350",
    # ... map to CSS classes
}

ACTION_ICONS = {
    ActionType.SCALP_LONG: "fa-arrow-up",
    ActionType.SCALP_SHORT: "fa-arrow-down",
    # ...
}
```

```python
# settings/card_schema.py
"""Signal card display configuration"""

TIMEFRAME_LABELS = {
    "scalp": {"display": "5-15 MIN", "icon": "fa-bolt"},
    "intraday": {"display": "1-4 HR", "icon": "fa-sun"},
    "btst": {"display": "OVERNIGHT", "icon": "fa-moon"},
    "swing": {"display": "2-7 DAYS", "icon": "fa-wave-square"},
    "positional": {"display": "WEEKS", "icon": "fa-calendar-alt"},
    "investment": {"display": "LONG TERM", "icon": "fa-piggy-bank"},
}

TAG_STYLES = {
    "urgent": {"bg": "#ff5722", "icon": "fa-bolt"},
    "bullish": {"bg": "rgba(0,200,83,0.15)", "border": "rgba(0,200,83,0.3)"},
    # ...
}

CONFIDENCE_LEVELS = {
    "high": {"min": 75, "color": "#00c853"},
    "medium": {"min": 50, "color": "#ffc107"},
    "low": {"min": 0, "color": "#ff5252"},
}
```

---

## 2.5 Missing Indicators for Breakout Detection & False Breakout Filtering

Based on research into professional breakout strategies, here are **critical indicators NOT yet implemented** that would significantly improve signal quality:

### 2.5.1 Smart Money Concepts (SMC) - HIGH PRIORITY 🔴

| Indicator                       | Purpose                                | Status                         | Priority |
| ------------------------------- | -------------------------------------- | ------------------------------ | -------- |
| **Fair Value Gap (FVG)**        | Identifies institutional imbalances    | 🔲 Missing                     | **P1**   |
| **Order Blocks**                | Institutional entry zones              | 🔲 Missing                     | **P1**   |
| **Breaker Blocks**              | Failed order blocks (trend reversal)   | 🔲 Missing                     | **P2**   |
| **Liquidity Sweep Detection**   | Identifies stop hunts / fake breakouts | 🔲 Missing                     | **P1**   |
| **Break of Structure (BOS)**    | Confirms trend continuation            | 🔲 Partial (in `structure.py`) | **P2**   |
| **Change of Character (CHoCH)** | First sign of reversal                 | 🔲 Missing                     | **P2**   |

**Why Critical**: These detect where institutions are placing orders and hunting retail stops - the #1 cause of false breakouts.

### 2.5.2 Volume Confirmation Indicators - HIGH PRIORITY 🔴

| Indicator                   | Purpose                        | Status     | Priority |
| --------------------------- | ------------------------------ | ---------- | -------- |
| **Volume Spike Detection**  | Confirms breakout validity     | 🔲 Missing | **P1**   |
| **Relative Volume (RVOL)**  | Volume vs average (e.g., 2.3x) | 🔲 Missing | **P1**   |
| **Volume Profile / POC**    | Point of Control, Value Area   | 🔲 Missing | **P2**   |
| **Cumulative Volume Delta** | Buy vs Sell pressure           | 🔲 Missing | **P2**   |

**Why Critical**: "A breakout without volume is a fake breakout" - most reliable filter.

### 2.5.3 Breakout Confirmation Indicators - MEDIUM PRIORITY 🟡

| Indicator                        | Purpose                               | Status              | Priority |
| -------------------------------- | ------------------------------------- | ------------------- | -------- |
| **Multi-Timeframe Confirmation** | HTF alignment check                   | ✅ Exists (partial) | Enhance  |
| **Consecutive Close Filter**     | 2+ closes beyond level                | 🔲 Missing          | **P2**   |
| **Retest Detection**             | Price returns to test breakout level  | 🔲 Missing          | **P2**   |
| **Displacement Candle**          | Strong momentum candle after breakout | 🔲 Missing          | **P2**   |
| **ATR Breakout Filter**          | Breakout must exceed 1-2x ATR         | 🔲 Missing          | **P2**   |

### 2.5.4 Market Context Indicators - MEDIUM PRIORITY 🟡

| Indicator                | Purpose                                 | Status     | Priority |
| ------------------------ | --------------------------------------- | ---------- | -------- |
| **Market Regime Filter** | Don't trade breakouts in ranging market | ✅ Exists  | ✅       |
| **Sector Strength**      | Confirm sector supports direction       | ✅ Exists  | ✅       |
| **Index Correlation**    | Breakout aligns with Nifty/BankNifty    | 🔲 Missing | **P3**   |
| **VIX / India VIX**      | High VIX = more false breakouts         | 🔲 Missing | **P3**   |

### 2.5.5 False Breakout Detection Patterns - HIGH PRIORITY 🔴

| Pattern                         | Description                           | Status     | Priority |
| ------------------------------- | ------------------------------------- | ---------- | -------- |
| **Swing Failure Pattern (SFP)** | Price exceeds level but closes inside | 🔲 Missing | **P1**   |
| **Fakeout Candle**              | Long wick beyond level, body inside   | 🔲 Missing | **P1**   |
| **Stop Hunt Reversal**          | Sweep + immediate reversal            | 🔲 Missing | **P1**   |
| **Failed Auction**              | Price rejected from new territory     | 🔲 Missing | **P2**   |
| **Trap Pattern**                | Bull/Bear trap detection              | 🔲 Missing | **P1**   |

### 2.5.6 F&O Based Confirmation (India Specific) - HIGH PRIORITY 🔴

| Indicator                       | Purpose                                 | Status     | Priority |
| ------------------------------- | --------------------------------------- | ---------- | -------- |
| **PCR at Breakout Level**       | High PCR at resistance = real breakout  | ✅ Exists  | Enhance  |
| **OI Build-up Direction**       | Long/Short build-up confirmation        | ✅ Exists  | Enhance  |
| **Max Pain Movement**           | Breakout towards max pain = sustainable | ✅ Exists  | ✅       |
| **IV Crush Detection**          | Low IV breakout more reliable           | 🔲 Missing | **P2**   |
| **OI-based Support/Resistance** | Highest OI strikes as S/R               | 🔲 Missing | **P2**   |

---

## 2.6 Indicator Implementation Priority Matrix

### Tier 1: Must Have for Real Breakouts (Week 1-3)

```
┌─────────────────────────────────────────────────────────────┐
│  BREAKOUT VALIDITY CHECKLIST                                │
├─────────────────────────────────────────────────────────────┤
│  ✓ Volume Spike (RVOL > 1.5x)                              │
│  ✓ FVG Present (institutional imbalance)                   │
│  ✓ No Liquidity Sweep in opposite direction                │
│  ✓ Order Block support in breakout direction               │
│  ✓ HTF trend alignment                                     │
│  ✓ ATR confirms volatility (breakout > 1x ATR)             │
└─────────────────────────────────────────────────────────────┘
```

**Files to Create**:

- `technicals/microstructure/fvg.py` - Fair Value Gaps
- `technicals/microstructure/order_blocks.py` - Order Blocks
- `technicals/microstructure/liquidity.py` - Liquidity Sweeps
- `technicals/indicators/volume_confirmation.py` - RVOL, Volume Spike
- `technicals/signals/breakout_validator.py` - Combines all checks

### Tier 2: False Breakout Filters (Week 4-5)

```
┌─────────────────────────────────────────────────────────────┐
│  FALSE BREAKOUT DETECTION                                   │
├─────────────────────────────────────────────────────────────┤
│  ⚠ Swing Failure Pattern detected                          │
│  ⚠ Stop Hunt Reversal pattern                              │
│  ⚠ Low volume on breakout attempt                          │
│  ⚠ Immediate rejection candle                              │
│  ⚠ CHoCH signal after breakout                             │
│  ⚠ Divergence on RSI/MACD at breakout                      │
└─────────────────────────────────────────────────────────────┘
```

**Files to Create**:

- `technicals/patterns/false_breakout.py` - SFP, Fakeout, Trap patterns
- `technicals/signals/breakout_quality.py` - Scoring real vs fake

### Tier 3: Enhanced Context (Week 6+)

- Index correlation
- VIX integration
- OI-based S/R levels
- Volume Profile / POC

---

## 3. Target Dashboard Analysis

### 3.1 Main Tabs

Based on `index.html`, the dashboard has these primary tabs:

```
[Scalp] [Intraday] [BTST] [Swing] [Positional] [Investment] [Portfolio*] [History*]
                                                            ↑ NEW        ↑ NEW
```

### 3.2 Signal Card Structure

Each signal card contains these sections:

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER: [ACTION TYPE + ICON]                    [TIMEFRAME] │
├─────────────────────────────────────────────────────────────┤
│ SYMBOL ROW:                                                 │
│   RELIANCE                              ₹2,847.50           │
│   Reliance Industries                   +1.25% ↑            │
├─────────────────────────────────────────────────────────────┤
│ TAGS: [ACT NOW] [Bullish] [Vol 2.3x] [9/10]                │
├─────────────────────────────────────────────────────────────┤
│ R:R BOX:  Risk: -0.8%  |  Reward: +1.2%  |  R:R: 1:1.5     │
├─────────────────────────────────────────────────────────────┤
│ TECHNICALS:  RSI: 62 ▲  |  MACD: + Cross  |  EMA: Above    │
├─────────────────────────────────────────────────────────────┤
│ F&O SENTIMENT:  PCR: 1.25  |  OI: +2.5L  |  MaxPain: ₹2850 │
├─────────────────────────────────────────────────────────────┤
│ FVG ZONES:  Above: ₹2,865-2,880  |  Below: ₹2,820-2,835    │
├─────────────────────────────────────────────────────────────┤
│ WYCKOFF PHASE: [===ACCUMULATION===|------|------|------]   │
├─────────────────────────────────────────────────────────────┤
│ TRADE DETAILS:                                              │
│   Entry: ₹2,840 - ₹2,850                                   │
│   Target: ₹2,880 (+1.2%)                                   │
│   Stop Loss: ₹2,825 (-0.8%)                                │
├─────────────────────────────────────────────────────────────┤
│ CONFIDENCE: [████████████████░░░░] 90%                      │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Action Types

| Action      | Color        | Use Case            |
| ----------- | ------------ | ------------------- |
| SCALP_LONG  | Teal         | Quick long scalp    |
| SCALP_SHORT | Red          | Quick short scalp   |
| STRONG_BUY  | Bright Green | High conviction buy |
| BUY         | Green        | Standard buy signal |
| BREAKOUT    | Cyan         | Breakout trade      |
| REVERSAL    | Purple       | Reversal setup      |
| SHORT       | Red          | Short position      |
| SELL        | Red          | Exit signal         |
| HOLD        | Yellow       | Continue holding    |
| WATCH       | Orange       | On watchlist        |
| BOOK_PROFIT | Light Green  | Take profits        |
| TRAIL       | Blue         | Trail stop loss     |
| ACCUMULATE  | Purple       | Add to position     |
| BTST_BUY    | Dark Blue    | BTST entry          |
| REDUCE      | Orange       | Reduce position     |
| CORE_HOLD   | Indigo       | Never sell          |
| EXIT        | Red          | Exit immediately    |

---

## 4. Gap Analysis & Priority Tasks

### 13.1 Priority 1: Signal Card Adapter (Bridge Existing → New UI)

**Goal**: Create an adapter that transforms your existing `cockpit_row` / `actionable_row` output into the new `SignalCard` format.

**File to Create**: `services/card_adapter.py`

```python
# Map existing cockpit_row fields to SignalCard structure
def cockpit_row_to_signal_card(row: dict, interval: str) -> SignalCard:
    """Transform existing cockpit_row to new SignalCard format"""

    # Map action from decision_engine to ActionType
    action = map_action_type(row.get('action_tag'), row.get('decision'))

    # Map timeframe
    timeframe_cat = interval_to_category(interval)

    # Extract technicals from existing indicators
    technicals = extract_technicals(row)

    # Map Wyckoff phase from microstructure
    wyckoff = map_wyckoff_phase(row.get('phase'), row.get('structure'))

    return SignalCard(
        symbol=row['symbol'],
        current_price=row.get('cmp') or row.get('last_close'),
        action_type=action,
        timeframe_category=timeframe_cat,
        technicals=technicals,
        wyckoff_phase=wyckoff,
        # ... rest of mapping
    )
```

### 13.2 Priority 2: Database for Positions & Trades

**Goal**: Replace file-based position storage with SQLite

**Files to Create**:

- `db/database.py` - Connection management
- `db/models.py` - SQLAlchemy models (Position, Trade, Signal)
- `db/migrations/` - Alembic migrations

**Why SQLite First**:

- Your `helpers/portfolio.py` already loads from JSON files
- SQLite gives you ACID transactions, queries, and future PostgreSQL migration path
- Can keep JSON as fallback/backup

### 13.3 Priority 3: FVG Detection Module

**Goal**: Add Fair Value Gap detection (missing from microstructure)

**File to Create**: `technicals/microstructure/fvg.py`

```python
def detect_fvg(df: pl.DataFrame, lookback: int = 50) -> dict:
    """Detect bullish and bearish Fair Value Gaps"""
    # Bullish FVG: current_low > prev_prev_high (gap up)
    # Bearish FVG: current_high < prev_prev_low (gap down)
    return {
        'fvg_above': {'start': price1, 'end': price2, 'type': 'resistance'},
        'fvg_below': {'start': price1, 'end': price2, 'type': 'support'},
    }
```

### 7.4 Priority 4: Timeframe Tab Filtering

**Goal**: Route signals to correct tabs based on `playbook.py` classification

**Your `playbook.py` already has**:

- `_classify_intraday_playbook()`
- `_classify_btst_swing_playbook()`
- `assign_playbook()` with `horizon` parameter

**Enhancement Needed**: Add explicit timeframe category output:

```python
def classify_timeframe_tab(row: dict, interval: str) -> str:
    """Return: 'scalp' | 'intraday' | 'btst' | 'swing' | 'positional' | 'investment'"""
    playbook = assign_playbook(row, interval=interval)
    # Map playbook to tab
```

### 4.5 Priority 5: Portfolio Tab Enhancement

**Your `server/routers/portfolio.py` exists** - enhance it with:

- Live P&L calculation using `helpers/portfolio.py` + live prices
- Action suggestions using existing `decision_engine.py`
- CRUD endpoints for position management

### 4.6 Priority 6: History Tab Analytics

**Your `services/history.py` exists** - enhance it with:

- Trade recording on position close
- Win rate, profit factor calculations
- Monthly P&L aggregation
- Performance by timeframe breakdown

---

## 5. Revised Implementation Roadmap

### Phase 1: Smart Money & Volume Indicators (Week 1-2) - CRITICAL FOR BREAKOUTS

| Task                      | File                                           | Status      | Impact |
| ------------------------- | ---------------------------------------------- | ----------- | ------ |
| Fair Value Gap Detection  | `technicals/microstructure/fvg.py`             | ✅ **DONE** | High   |
| Order Block Detection     | `technicals/microstructure/order_blocks.py`    | 🔲 TODO     | High   |
| Liquidity Sweep Detection | `technicals/microstructure/liquidity.py`       | 🔲 TODO     | High   |
| Relative Volume (RVOL)    | `technicals/indicators/volume_confirmation.py` | ✅ **DONE** | High   |
| Volume Spike Detection    | `technicals/indicators/volume_confirmation.py` | ✅ **DONE** | High   |

### Phase 2: False Breakout Filters (Week 3-4) - AVOID FAKE SIGNALS

| Task                        | File                                       | Status      | Impact |
| --------------------------- | ------------------------------------------ | ----------- | ------ |
| Swing Failure Pattern (SFP) | `technicals/patterns/false_breakout.py`    | ✅ **DONE** | High   |
| Stop Hunt Reversal          | `technicals/patterns/false_breakout.py`    | ✅ **DONE** | High   |
| Bull/Bear Trap Detection    | `technicals/patterns/false_breakout.py`    | ✅ **DONE** | High   |
| Fakeout Candle Pattern      | `technicals/patterns/false_breakout.py`    | ✅ **DONE** | High   |
| Breakout Quality Scorer     | `technicals/signals/breakout_validator.py` | ✅ **DONE** | High   |
| Centralized Settings        | `settings/breakout_settings.py`            | ✅ **DONE** | High   |
| Smoke Tests                 | `tests/smoke_breakout_modules.py`          | ✅ **DONE** | Medium |

### Phase 3: Signal Card Bridge (Week 5-6) - UI INTEGRATION

| Task                                | File                        | Status  |
| ----------------------------------- | --------------------------- | ------- |
| Create SignalCard Pydantic model    | `models/card.py`            | 🔲 TODO |
| Create card_adapter.py              | `services/card_adapter.py`  | 🔲 TODO |
| Map cockpit_row → SignalCard        | `services/card_adapter.py`  | 🔲 TODO |
| Integrate new indicators into cards | `services/card_adapter.py`  | 🔲 TODO |
| Update cockpit router               | `server/routers/cockpit.py` | 🔲 TODO |

### Phase 4: DRY Cleanup & Settings Centralization (Week 7)

| Task                        | File                             | Status  |
| --------------------------- | -------------------------------- | ------- |
| Create action_types.py      | `settings/action_types.py`       | 🔲 TODO |
| Create card_schema.py       | `settings/card_schema.py`        | 🔲 TODO |
| Remove duplicate files      | Various                          | 🔲 TODO |
| Centralize score thresholds | `settings/scoring_thresholds.py` | 🔲 TODO |

### Phase 5: Database Layer (Week 8-9)

| Task                       | File                           | Status  |
| -------------------------- | ------------------------------ | ------- |
| SQLite setup               | `db/database.py`               | 🔲 TODO |
| Position model             | `db/models.py`                 | 🔲 TODO |
| Trade model                | `db/models.py`                 | 🔲 TODO |
| Migrate from JSON → SQLite | `scripts/migrate_positions.py` | 🔲 TODO |

### Phase 6: Portfolio & History Tabs (Week 10-11)

| Task                            | File                            | Status  |
| ------------------------------- | ------------------------------- | ------- |
| Portfolio tracker with live P&L | `services/portfolio_tracker.py` | 🔲 TODO |
| Action suggestions for holdings | `services/portfolio_tracker.py` | 🔲 TODO |
| Trade history recorder          | `services/trade_recorder.py`    | 🔲 TODO |
| Analytics calculations          | `services/trade_analytics.py`   | 🔲 TODO |
| Portfolio API endpoints         | `server/routers/portfolio.py`   | 🔲 TODO |
| History API endpoints           | `server/routers/history.py`     | 🔲 TODO |

### Phase 7: Frontend Integration (Week 12)

| Task                             | File                                     | Status  |
| -------------------------------- | ---------------------------------------- | ------- |
| Update index.html with API calls | `server/templates/new-design/index.html` | 🔲 TODO |
| Add Portfolio tab HTML           | `server/templates/new-design/index.html` | 🔲 TODO |
| Add History tab HTML             | `server/templates/new-design/index.html` | 🔲 TODO |
| JavaScript for dynamic cards     | `server/static/js/cockpit_cards.js`      | 🔲 TODO |

### Phase 8: Testing & Polish (Week 13-14)

| Task                           | Status  |
| ------------------------------ | ------- |
| Smoke tests for new indicators | 🔲 TODO |
| Backtest breakout validator    | 🔲 TODO |
| End-to-end testing             | 🔲 TODO |
| Performance optimization       | 🔲 TODO |
| Documentation update           | 🔲 TODO |

---

## 6. Project Structure (Current → Target Hybrid)

```
queen/
├── server/
│   ├── __init__.py
│   ├── main.py                      # FastAPI entry point
│   ├── config.py                    # Environment & settings
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py          # Shared dependencies (DB, fetcher)
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── signals.py           # GET /api/signals/{timeframe}
│   │       ├── portfolio.py         # Portfolio management
│   │       ├── history.py           # Trade history
│   │       ├── market.py            # Market status, indices
│   │       └── websocket.py         # Real-time updates
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   │
│   │   ├── data/                    # Data Layer (100% Polars)
│   │   │   ├── __init__.py
│   │   │   ├── fetcher.py           # Upstox API wrapper
│   │   │   ├── transformer.py       # Data normalization
│   │   │   ├── cache.py             # Caching layer
│   │   │   └── models.py            # Data models
│   │   │
│   │   ├── indicators/              # Technical Indicators (DRY)
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Abstract BaseIndicator
│   │   │   ├── registry.py          # Indicator factory/registry
│   │   │   │
│   │   │   ├── western/             # Western Indicators
│   │   │   │   ├── __init__.py
│   │   │   │   ├── momentum.py      # RSI, Stochastic, CCI, Williams %R
│   │   │   │   ├── trend.py         # MACD, EMA, SMA, ADX, Supertrend
│   │   │   │   ├── volatility.py    # ATR, Bollinger, Keltner
│   │   │   │   └── volume.py        # OBV, VWAP, Volume Profile
│   │   │   │
│   │   │   ├── japanese/            # Candlestick Patterns
│   │   │   │   ├── __init__.py
│   │   │   │   ├── single.py        # Doji, Hammer, Shooting Star
│   │   │   │   ├── double.py        # Engulfing, Harami, Tweezer
│   │   │   │   └── triple.py        # Morning/Evening Star, 3 Soldiers
│   │   │   │
│   │   │   ├── wyckoff/             # Wyckoff Analysis
│   │   │   │   ├── __init__.py
│   │   │   │   ├── phases.py        # Phase detection
│   │   │   │   ├── events.py        # PS, SC, AR, ST, Spring, UTAD
│   │   │   │   └── composite.py     # Composite operator
│   │   │   │
│   │   │   ├── smart_money/         # Smart Money Concepts
│   │   │   │   ├── __init__.py
│   │   │   │   ├── fvg.py           # Fair Value Gaps
│   │   │   │   ├── order_blocks.py  # Order blocks
│   │   │   │   ├── liquidity.py     # Liquidity pools
│   │   │   │   └── structure.py     # BOS, CHoCH
│   │   │   │
│   │   │   └── price_action/        # Price Action
│   │   │       ├── __init__.py
│   │   │       ├── support_resistance.py
│   │   │       ├── trendlines.py
│   │   │       ├── patterns.py      # Chart patterns
│   │   │       └── pivots.py        # Pivot points
│   │   │
│   │   ├── signals/                 # Signal Generation
│   │   │   ├── __init__.py
│   │   │   ├── generator.py         # Main signal engine
│   │   │   ├── scorer.py            # Signal scoring (1-10)
│   │   │   ├── filters.py           # Noise filtering
│   │   │   ├── classifier.py        # Timeframe classification
│   │   │   └── risk_reward.py       # R:R calculation
│   │   │
│   │   ├── fo/                      # F&O Analysis
│   │   │   ├── __init__.py
│   │   │   ├── oi_analysis.py       # Open Interest
│   │   │   ├── pcr.py               # Put-Call Ratio
│   │   │   ├── max_pain.py          # Max Pain
│   │   │   └── iv_analysis.py       # Implied Volatility
│   │   │
│   │   ├── portfolio/               # Portfolio Management
│   │   │   ├── __init__.py
│   │   │   ├── tracker.py           # Position tracking
│   │   │   ├── pnl.py               # P&L calculations
│   │   │   └── alerts.py            # Exit/trail alerts
│   │   │
│   │   ├── history/                 # Trade History
│   │   │   ├── __init__.py
│   │   │   ├── recorder.py          # Trade recording
│   │   │   └── analytics.py         # Performance analytics
│   │   │
│   │   └── timeframes/              # Multi-Timeframe
│   │       ├── __init__.py
│   │       ├── manager.py           # MTF coordination
│   │       └── confluence.py        # Cross-TF confluence
│   │
│   ├── models/                      # Pydantic Models
│   │   ├── __init__.py
│   │   ├── signal.py                # Signal schemas
│   │   ├── indicator.py             # Indicator results
│   │   ├── card.py                  # SignalCard for frontend
│   │   ├── portfolio.py             # Position schemas
│   │   └── trade.py                 # Trade history schemas
│   │
│   ├── db/                          # Database Layer
│   │   ├── __init__.py
│   │   ├── database.py              # Connection management
│   │   ├── models.py                # SQLAlchemy ORM models
│   │   └── migrations/              # Alembic migrations
│   │
│   ├── templates/
│   │   └── new-design/
│   │       └── index.html           # Main dashboard
│   │
│   └── static/
│       ├── css/
│       └── js/
│
├── tests/
│   ├── unit/
│   │   ├── test_indicators/
│   │   ├── test_signals/
│   │   └── test_data/
│   └── integration/
│
├── scripts/
│   ├── backtest.py
│   └── data_loader.py
│
├── docs/
│   └── MASTER_PLAN.md               # THIS FILE
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 7. Core Architecture

### 13.1 Base Indicator Class (DRY Foundation)

```python
# server/core/indicators/base.py
from abc import ABC, abstractmethod
from typing import Literal
import polars as pl
from pydantic import BaseModel

class IndicatorResult(BaseModel):
    """Standardized indicator output"""
    name: str
    value: float | str | None
    signal: Literal["BULLISH", "BEARISH", "NEUTRAL", "OVERBOUGHT", "OVERSOLD"]
    strength: float  # 0-100
    description: str

class BaseIndicator(ABC):
    """Abstract base class - ALL indicators inherit from this"""

    def __init__(self, df: pl.DataFrame):
        self._validate_ohlcv(df)
        self.df = df

    @staticmethod
    def _validate_ohlcv(df: pl.DataFrame) -> None:
        required = {"open", "high", "low", "close", "volume", "timestamp"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")

    @property
    @abstractmethod
    def name(self) -> str:
        """Indicator name"""
        pass

    @abstractmethod
    def calculate(self) -> pl.DataFrame:
        """Calculate indicator, return DataFrame with new columns"""
        pass

    @abstractmethod
    def generate_signal(self) -> IndicatorResult:
        """Generate trading signal from latest values"""
        pass
```

### 13.2 Indicator Registry (Factory Pattern)

```python
# server/core/indicators/registry.py
from typing import Type
import polars as pl
from .base import BaseIndicator

class IndicatorRegistry:
    """Central registry for all indicators - ensures DRY"""

    _indicators: dict[str, Type[BaseIndicator]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register indicators"""
        def decorator(indicator_class: Type[BaseIndicator]):
            cls._indicators[name] = indicator_class
            return indicator_class
        return decorator

    @classmethod
    def create(cls, name: str, df: pl.DataFrame, **kwargs) -> BaseIndicator:
        """Factory method to create indicator instances"""
        if name not in cls._indicators:
            raise ValueError(f"Unknown indicator: {name}")
        return cls._indicators[name](df, **kwargs)

    @classmethod
    def calculate_multiple(cls, df: pl.DataFrame, indicators: list[str]) -> dict:
        """Calculate multiple indicators at once"""
        return {name: cls.create(name, df).generate_signal() for name in indicators}

# Usage in indicator files:
@IndicatorRegistry.register("rsi")
class RSI(BaseIndicator):
    ...
```

### 13.3 Data Fetcher (100% Polars)

```python
# server/core/data/fetcher.py
import polars as pl
import httpx
from datetime import datetime, timedelta

class UpstoxFetcher:
    """Upstox API - returns Polars DataFrames only"""

    BASE_URL = "https://api.upstox.com/v2"

    def __init__(self, access_token: str):
        self.token = access_token
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {access_token}"}
        )

    async def get_ohlcv(
        self,
        symbol: str,
        interval: str,
        days_back: int = 100
    ) -> pl.DataFrame:
        """Fetch OHLCV as Polars DataFrame"""

        instrument_key = await self._get_instrument_key(symbol)
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days_back)

        response = await self.client.get(
            f"{self.BASE_URL}/historical-candle/{instrument_key}/{interval}",
            params={
                "from_date": from_date.strftime("%Y-%m-%d"),
                "to_date": to_date.strftime("%Y-%m-%d"),
            }
        )
        response.raise_for_status()
        candles = response.json()["data"]["candles"]

        # Upstox returns [timestamp, open, high, low, close, volume, oi]
        return pl.DataFrame({
            "timestamp": [row[0] for row in candles],
            "open": [float(row[1]) for row in candles],
            "high": [float(row[2]) for row in candles],
            "low": [float(row[3]) for row in candles],
            "close": [float(row[4]) for row in candles],
            "volume": [int(row[5]) for row in candles],
            "oi": [int(row[6]) if len(row) > 6 else 0 for row in candles],
        }).with_columns([
            pl.col("timestamp").str.to_datetime()
        ]).sort("timestamp")
```

### 7.4 Signal Card Model

```python
# server/models/card.py
from pydantic import BaseModel
from typing import Optional
from enum import Enum

class ActionType(str, Enum):
    SCALP_LONG = "SCALP_LONG"
    SCALP_SHORT = "SCALP_SHORT"
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    BREAKOUT = "BREAKOUT"
    REVERSAL = "REVERSAL"
    SHORT = "SHORT"
    SELL = "SELL"
    HOLD = "HOLD"
    WATCH = "WATCH"
    BOOK_PROFIT = "BOOK_PROFIT"
    TRAIL = "TRAIL"
    ACCUMULATE = "ACCUMULATE"
    BTST_BUY = "BTST_BUY"
    REDUCE = "REDUCE"
    CORE_HOLD = "CORE_HOLD"
    EXIT = "EXIT"

class SignalCard(BaseModel):
    """Complete signal card - matches HTML structure exactly"""

    # Core Info
    symbol: str
    company_name: str
    current_price: float
    price_change_pct: float

    # Action
    action_type: ActionType
    timeframe_label: str          # "5-15 MIN", "2-7 DAYS", etc.
    timeframe_category: str       # scalp, intraday, btst, swing, positional, investment

    # Tags
    tags: list[dict]              # [{type, value, color}]

    # Risk/Reward
    risk_pct: float
    reward_pct: float
    rr_ratio: float

    # Technicals
    technicals: dict              # RSI, MACD, EMA, ATR

    # Candlestick Pattern
    candlestick_pattern: Optional[dict]

    # Wyckoff
    wyckoff_phase: str
    wyckoff_progress: float       # 0-100

    # Smart Money
    fvg_above: Optional[dict]     # {start, end, type}
    fvg_below: Optional[dict]

    # F&O (optional)
    fo_sentiment: Optional[dict]  # PCR, OI, Max Pain, IV

    # Trade Levels
    entry_range: tuple[float, float]
    target: float
    stoploss: float
    special_instructions: Optional[str]

    # Score & Confidence
    score: int                    # 1-10
    confidence: float             # 0-100

    # Metadata
    is_urgent: bool = False
    is_new: bool = False
    is_holding: bool = False
```

---

## 8. Feature Specifications

### 11.1 Signal Generation (Existing Tabs)

**Scalp Tab**

- Sub-filters: Long, Short, Breakout
- Indicators: RSI, MACD, EMA(9,21), ATR, Volume
- Timeframe: 1m, 5m candles
- Special: Quick momentum, tight stops

**Intraday Tab**

- Sub-filters: Fresh Entry, Holding, Exit
- Indicators: All Western + Candlestick patterns
- Timeframe: 15m, 1h candles
- Special: VWAP levels, market internals

**BTST Tab**

- Sub-filters: BTST Long, Momentum
- Indicators: EOD analysis + global cues
- Timeframe: 1h, 4h candles
- Special: Gap up probability, FII/DII data

**Swing Tab**

- Sub-filters: Fresh, Holding
- Indicators: Full technical suite + Wyckoff
- Timeframe: 4h, 1d candles
- Special: Sector rotation, relative strength

**Positional Tab**

- Sub-filters: Fresh, Trailing, Exit
- Indicators: Weekly trends, Wyckoff phases
- Timeframe: 1d, 1w candles
- Special: Fundamental confluence

**Investment Tab**

- Sub-filters: Accumulate, Core Hold
- Indicators: Long-term trends, valuation
- Timeframe: 1w, 1M candles
- Special: Dividend yield, quality score

### 11.2 Portfolio Tracking (NEW)

**Purpose**: Track actual holdings, provide HOLD/EXIT signals

**Features**:

- Add positions manually (or auto-sync from broker - TBD)
- Live P&L with real-time prices
- Suggested actions based on technical analysis:
  - HOLD: Position on track
  - BOOK_PROFIT: Target near or overbought
  - TRAIL: Update trailing stop
  - EXIT: Stop loss hit or reversal signals
  - ADD: Good entry for averaging
  - REVIEW: Position underwater

**Position Card Display**:

- Same card format as signals
- Shows: Avg cost, current price, P&L, holding days
- Target/SL distances
- Action suggestion with reason

**Sub-filters**: All, Scalp, Intraday, Swing, Positional, Investment, ⚠️ Action Needed

### 11.3 Trade History (NEW)

**Purpose**: Complete record of all trades for performance analysis

**Features**:

- Trade log with entry/exit details
- Performance analytics:
  - Win rate
  - Profit factor
  - Average profit/loss
  - Best/worst trades
- Monthly P&L breakdown
- Performance by timeframe
- Export to CSV

**Filters**: All Time, Last 7/30/90 Days, Winners Only, Losers Only

---

## 9. Database Design

### 9.1 ORM Models

```python
# server/db/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

class TradeStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PARTIAL = "PARTIAL"

class TradeType(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class TimeframeCategory(str, enum.Enum):
    SCALP = "scalp"
    INTRADAY = "intraday"
    BTST = "btst"
    SWING = "swing"
    POSITIONAL = "positional"
    INVESTMENT = "investment"


class Position(Base):
    """Active portfolio positions"""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    company_name = Column(String(100))

    trade_type = Column(Enum(TradeType), default=TradeType.LONG)
    quantity = Column(Integer, nullable=False)
    avg_buy_price = Column(Float, nullable=False)

    entry_date = Column(DateTime, default=datetime.utcnow)
    timeframe = Column(Enum(TimeframeCategory), nullable=False)

    target_price = Column(Float)
    stoploss_price = Column(Float)
    trailing_sl = Column(Float)

    status = Column(Enum(TradeStatus), default=TradeStatus.OPEN)
    notes = Column(String(500))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    trades = relationship("Trade", back_populates="position")


class Trade(Base):
    """Trade transactions (for history)"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    position_id = Column(Integer, ForeignKey("positions.id"))

    symbol = Column(String(20), nullable=False, index=True)
    trade_type = Column(Enum(TradeType), nullable=False)
    action = Column(String(20))  # BUY, SELL, PARTIAL_EXIT

    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    executed_at = Column(DateTime, default=datetime.utcnow)
    timeframe = Column(Enum(TimeframeCategory))

    # For closed trades
    exit_price = Column(Float)
    exit_date = Column(DateTime)
    pnl_amount = Column(Float)
    pnl_percentage = Column(Float)
    holding_days = Column(Integer)
    exit_reason = Column(String(100))

    signal_score = Column(Integer)
    notes = Column(String(500))

    position = relationship("Position", back_populates="trades")


class Signal(Base):
    """Signal history (for backtesting)"""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)

    action_type = Column(String(30))
    timeframe = Column(Enum(TimeframeCategory))

    price_at_signal = Column(Float)
    entry_suggested = Column(Float)
    target_suggested = Column(Float)
    stoploss_suggested = Column(Float)

    score = Column(Integer)
    confidence = Column(Float)

    # Technical snapshot
    rsi = Column(Float)
    macd_signal = Column(String(20))
    wyckoff_phase = Column(String(20))

    # Outcome tracking
    was_successful = Column(Boolean)
    actual_return = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## 10. API Endpoints

### 13.1 Signal Endpoints

| Method | Endpoint                   | Description               |
| ------ | -------------------------- | ------------------------- |
| GET    | `/api/signals/{timeframe}` | Get signals for timeframe |
| GET    | `/api/signals/stats`       | Get overall signal stats  |
| GET    | `/api/market/status`       | Market open/close status  |

### 13.2 Portfolio Endpoints

| Method | Endpoint                              | Description                 |
| ------ | ------------------------------------- | --------------------------- |
| GET    | `/api/portfolio/positions`            | Get all open positions      |
| GET    | `/api/portfolio/summary`              | Portfolio summary stats     |
| POST   | `/api/portfolio/positions`            | Add new position            |
| PUT    | `/api/portfolio/positions/{id}`       | Update position (SL/target) |
| POST   | `/api/portfolio/positions/{id}/close` | Close position              |

### 13.3 History Endpoints

| Method | Endpoint                             | Description              |
| ------ | ------------------------------------ | ------------------------ |
| GET    | `/api/history/trades`                | Get trade history        |
| GET    | `/api/history/performance/timeframe` | Performance by timeframe |
| GET    | `/api/history/performance/monthly`   | Monthly P&L              |
| GET    | `/api/history/export`                | Export to CSV            |

---

## 11. Frontend Integration

### 11.1 Updated Tab Structure

```html
<nav class="main-tabs">
  <ul>
    <li class="is-active" data-tab="scalp">
      <a><i class="fas fa-bolt"></i> Scalp</a>
    </li>
    <li data-tab="intraday">
      <a><i class="fas fa-sun"></i> Intraday</a>
    </li>
    <li data-tab="btst">
      <a><i class="fas fa-moon"></i> BTST</a>
    </li>
    <li data-tab="swing">
      <a><i class="fas fa-wave-square"></i> Swing</a>
    </li>
    <li data-tab="positional">
      <a><i class="fas fa-calendar-alt"></i> Positional</a>
    </li>
    <li data-tab="investment">
      <a><i class="fas fa-piggy-bank"></i> Investment</a>
    </li>
    <!-- NEW TABS -->
    <li data-tab="portfolio">
      <a><i class="fas fa-wallet"></i> Portfolio</a>
    </li>
    <li data-tab="history">
      <a><i class="fas fa-history"></i> History</a>
    </li>
  </ul>
</nav>
```

### 11.2 API Integration (JavaScript)

```javascript
const API_BASE = "/api";

// Load signals for a timeframe
async function loadSignals(timeframe) {
  const response = await fetch(`${API_BASE}/signals/${timeframe}`);
  const data = await response.json();
  renderSignalCards(data.signals);
}

// Load portfolio positions
async function loadPortfolio() {
  const positions = await fetch(`${API_BASE}/portfolio/positions`).then((r) =>
    r.json(),
  );
  const summary = await fetch(`${API_BASE}/portfolio/summary`).then((r) =>
    r.json(),
  );
  renderPortfolio(positions, summary);
}

// Load trade history
async function loadHistory(days = null) {
  const url = days
    ? `${API_BASE}/history/trades?days=${days}`
    : `${API_BASE}/history/trades`;
  const data = await fetch(url).then((r) => r.json());
  renderHistory(data);
}
```

---

## 12. Legacy Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

- [ ] Set up project structure
- [ ] Database setup (SQLite + SQLAlchemy)
- [ ] Base indicator class
- [ ] Upstox data fetcher (Polars)
- [ ] Core Western indicators (RSI, MACD, EMA, ATR)
- [ ] Basic FastAPI setup

### Phase 2: Indicators (Week 3-4)

- [ ] Complete Western indicators
- [ ] Japanese candlestick patterns
- [ ] Wyckoff phase detection
- [ ] FVG/Smart Money modules
- [ ] Indicator registry/factory

### Phase 3: Signal Engine (Week 5-6)

- [ ] Signal generator with confluence
- [ ] Scoring system (1-10)
- [ ] Timeframe classifier
- [ ] Risk/Reward calculator
- [ ] Noise filtering

### Phase 4: Portfolio & History (Week 7-8)

- [ ] Position tracker
- [ ] P&L calculations
- [ ] Action suggestions (HOLD/EXIT/etc.)
- [ ] Trade recorder
- [ ] Performance analytics

### Phase 5: F&O Integration (Week 9)

- [ ] PCR analysis
- [ ] OI interpretation
- [ ] Max Pain calculation
- [ ] IV analysis

### Phase 6: Frontend (Week 10)

- [ ] API → Template integration
- [ ] Portfolio tab UI
- [ ] History tab UI
- [ ] Real-time updates (WebSocket)

### Phase 7: Testing & Polish (Week 11-12)

- [ ] Unit tests
- [ ] Integration tests
- [ ] Backtesting framework
- [ ] Performance optimization
- [ ] Documentation

---

## 13. Technical Standards

### 13.1 Code Standards

- Python 3.11+ with type hints everywhere
- Pydantic for all data validation
- Polars for all DataFrame operations (NO pandas)
- Async/await for all I/O operations
- Abstract base classes for extensibility

### 13.2 DRY Checklist

- [ ] All indicators inherit from BaseIndicator
- [ ] Use IndicatorRegistry for creation
- [ ] Shared signal scoring logic
- [ ] Reusable R:R calculation
- [ ] Common data validation

### 13.3 File Naming

- snake_case for all Python files
- Descriptive names (e.g., `support_resistance.py` not `sr.py`)
- One class per file for large classes
- Group related small classes

---

## 14. Open Questions

| #   | Question         | Options                                    | Decision |
| --- | ---------------- | ------------------------------------------ | -------- |
| 1   | Database         | SQLite vs PostgreSQL                       | TBD      |
| 2   | Position Entry   | Manual only vs Auto-sync from broker       | TBD      |
| 3   | Auto-suggestions | Should signals create suggested positions? | TBD      |
| 4   | Multi-user       | Single user vs user accounts               | TBD      |
| 5   | Upstox Data      | REST polling vs WebSocket                  | TBD      |
| 6   | Stock Universe   | Nifty 50, F&O stocks, custom list?         | TBD      |
| 7   | Alerts           | Push notifications for urgent signals?     | TBD      |

---

## 15. Changelog

| Date       | Version | Changes                                                         |
| ---------- | ------- | --------------------------------------------------------------- |
| 2025-12-03 | 1.0     | Initial master plan created                                     |
| 2025-12-03 | 1.1     | Added Portfolio Tracking feature                                |
| 2025-12-03 | 1.1     | Added Trade History feature                                     |
| 2025-12-03 | 1.2     | Consolidated into single document                               |
| 2025-12-03 | **2.0** | **Major Update**: Analyzed actual codebase from GitHub          |
| 2025-12-03 | 2.0     | Added Section 2: Current State Analysis (what exists)           |
| 2025-12-03 | 2.0     | Added Section 4: Gap Analysis & Priority Tasks                  |
| 2025-12-03 | 2.0     | Added Section 5: Revised Implementation Roadmap (12 weeks)      |
| 2025-12-03 | 2.0     | Updated Appendix A: Indicators marked as ✅ COMPLETE            |
| 2025-12-03 | **2.1** | **DRY Audit**: Added Section 2.4 - DRY compliance review        |
| 2025-12-03 | 2.1     | Added Section 2.5 - Missing indicators for breakout detection   |
| 2025-12-03 | 2.1     | Added Section 2.6 - Indicator implementation priority matrix    |
| 2025-12-03 | 2.1     | Added Appendix B - New indicators to implement                  |
| 2025-12-03 | 2.1     | Updated roadmap: Prioritized SMC & Volume indicators (Week 1-4) |
| 2025-12-03 | 2.1     | Added Breakout Quality Score formula                            |

---

## Appendix A: Indicator Status (Based on Actual Codebase)

### Western Indicators

| Indicator         | Location                                     | Status      |
| ----------------- | -------------------------------------------- | ----------- |
| RSI               | `technicals/indicators/core.py`              | ✅ Complete |
| Stochastic        | `technicals/indicators/core.py`              | ✅ Complete |
| CCI               | `technicals/indicators/core.py`              | ✅ Complete |
| Williams %R       | `technicals/indicators/core.py`              | ✅ Complete |
| MACD              | `technicals/indicators/momentum_macd.py`     | ✅ Complete |
| EMA (9,21,50,200) | `technicals/indicators/core.py`              | ✅ Complete |
| SMA               | `technicals/indicators/core.py`              | ✅ Complete |
| ADX/DMI           | `technicals/indicators/adx_dmi.py`           | ✅ Complete |
| Supertrend        | `technicals/indicators/advanced.py`          | ✅ Complete |
| ATR               | `technicals/indicators/core.py`              | ✅ Complete |
| Bollinger Bands   | `technicals/indicators/advanced.py`          | ✅ Complete |
| Keltner Channels  | `technicals/indicators/keltner.py`           | ✅ Complete |
| OBV               | `technicals/indicators/state.py`             | ✅ Complete |
| VWAP              | `technicals/microstructure/vwap.py`          | ✅ Complete |
| Volume Profile    | `technicals/indicators/volume_*.py`          | ✅ Complete |
| Chaikin           | `technicals/indicators/volume_chaikin.py`    | ✅ Complete |
| MFI               | `technicals/indicators/volume_mfi.py`        | ✅ Complete |
| Volatility Fusion | `technicals/indicators/volatility_fusion.py` | ✅ Complete |
| Breadth           | `technicals/indicators/breadth_*.py`         | ✅ Complete |

### Pattern Detection

| Pattern            | Location                               | Status      |
| ------------------ | -------------------------------------- | ----------- |
| Core Patterns      | `technicals/patterns/core.py`          | ✅ Complete |
| Composite Patterns | `technicals/patterns/composite.py`     | ✅ Complete |
| Pattern Fusion     | `technicals/signals/pattern_fusion.py` | ✅ Complete |

### Microstructure / Smart Money

| Component                 | Location                                      | Status      |
| ------------------------- | --------------------------------------------- | ----------- |
| CPR                       | `technicals/microstructure/cpr.py`            | ✅ Complete |
| VWAP Zones                | `technicals/microstructure/vwap.py`           | ✅ Complete |
| Structure (HH/HL/LH/LL)   | `technicals/microstructure/structure.py`      | ✅ Complete |
| Volume Analysis           | `technicals/microstructure/volume.py`         | ✅ Complete |
| Phases (Wyckoff-like)     | `technicals/microstructure/phases.py`         | ✅ Complete |
| Risk Detection            | `technicals/microstructure/risk.py`           | ✅ Complete |
| **FVG (Fair Value Gaps)** | `technicals/microstructure/fvg.py`            | 🔲 **TODO** |
| **Order Blocks**          | `technicals/microstructure/order_blocks.py`   | 🔲 **TODO** |
| **Liquidity Sweeps**      | `technicals/microstructure/liquidity.py`      | 🔲 **TODO** |
| **Breaker Blocks**        | `technicals/microstructure/breaker_blocks.py` | 🔲 **TODO** |

### Tactical Signals

| Signal         | Location                                                 | Status      |
| -------------- | -------------------------------------------------------- | ----------- |
| Tactical Core  | `technicals/signals/tactical/core.py`                    | ✅ Complete |
| Bias Regime    | `technicals/signals/tactical/bias_regime.py`             | ✅ Complete |
| Divergence     | `technicals/signals/tactical/divergence.py`              | ✅ Complete |
| Exhaustion     | `technicals/signals/tactical/exhaustion.py`              | ✅ Complete |
| Reversal Stack | `technicals/signals/tactical/reversal_stack.py`          | ✅ Complete |
| Squeeze Pulse  | `technicals/signals/tactical/squeeze_pulse.py`           | ✅ Complete |
| Liquidity Trap | `technicals/signals/tactical/tactical_liquidity_trap.py` | ✅ Complete |
| Pre-Breakout   | `technicals/signals/pre_breakout.py`                     | ✅ Complete |
| CMV Fusion     | `technicals/signals/fusion/cmv.py`                       | ✅ Complete |
| Market Regime  | `technicals/signals/fusion/market_regime.py`             | ✅ Complete |

---

## Appendix B: NEW Indicators Implementation Status

### B.1 Smart Money Concepts (SMC) - Priority 1

| Indicator                   | File                               | Purpose                           | Status      |
| --------------------------- | ---------------------------------- | --------------------------------- | ----------- |
| Fair Value Gap (FVG)        | `microstructure/fvg.py`            | Identify institutional imbalances | ✅ **DONE** |
| Order Blocks                | `microstructure/order_blocks.py`   | Institutional entry zones         | 🔲 TODO     |
| Liquidity Sweep             | `microstructure/liquidity.py`      | Detect stop hunts                 | 🔲 TODO     |
| Break of Structure (BOS)    | `microstructure/structure.py`      | Enhance existing                  | 🔲 TODO     |
| Change of Character (CHoCH) | `microstructure/structure.py`      | Add to existing                   | 🔲 TODO     |
| Breaker Blocks              | `microstructure/breaker_blocks.py` | Failed OB = reversal              | 🔲 TODO     |

### B.2 Volume Confirmation - Priority 1

| Indicator                 | File                                | Purpose              | Status      |
| ------------------------- | ----------------------------------- | -------------------- | ----------- |
| Relative Volume (RVOL)    | `indicators/volume_confirmation.py` | Volume vs 20-day avg | ✅ **DONE** |
| Volume Spike              | `indicators/volume_confirmation.py` | Sudden volume surge  | ✅ **DONE** |
| Volume Trend              | `indicators/volume_confirmation.py` | Inc/Dec/Stable       | ✅ **DONE** |
| Accumulation/Distribution | `indicators/volume_confirmation.py` | Smart money flow     | ✅ **DONE** |
| Volume Profile / POC      | `indicators/volume_profile.py`      | Point of Control     | 🔲 TODO     |

### B.3 False Breakout Patterns - Priority 1

| Pattern               | File                         | Purpose             | Status      |
| --------------------- | ---------------------------- | ------------------- | ----------- |
| Swing Failure Pattern | `patterns/false_breakout.py` | Classic SFP         | ✅ **DONE** |
| Fakeout Candle        | `patterns/false_breakout.py` | Long wick rejection | ✅ **DONE** |
| Bull/Bear Trap        | `patterns/false_breakout.py` | Trap pattern        | ✅ **DONE** |
| Stop Hunt Reversal    | `patterns/false_breakout.py` | Sweep + reverse     | ✅ **DONE** |
| False Breakout Risk   | `patterns/false_breakout.py` | Combined assessment | ✅ **DONE** |

### B.4 Breakout Validation - Priority 2

| Indicator             | File                            | Purpose           | Status      |
| --------------------- | ------------------------------- | ----------------- | ----------- |
| ATR Breakout Filter   | `signals/breakout_validator.py` | Breakout > 1x ATR | ✅ **DONE** |
| Consecutive Close     | `signals/breakout_validator.py` | 2+ closes beyond  | ✅ **DONE** |
| Breakout Score (1-10) | `signals/breakout_validator.py` | Combined scoring  | ✅ **DONE** |
| Retest Detection      | `signals/breakout_validator.py` | Pullback to level | 🔲 TODO     |
| MTF Confirmation      | `signals/breakout_validator.py` | HTF alignment     | ✅ **DONE** |

### B.5 Settings

| File                            | Purpose                   | Status      |
| ------------------------------- | ------------------------- | ----------- |
| `settings/breakout_settings.py` | Centralized configuration | ✅ **DONE** |

### B.6 Summary Statistics

| Category                | Total Items | Done         | TODO        |
| ----------------------- | ----------- | ------------ | ----------- |
| SMC Indicators          | 6           | 1            | 5           |
| Volume Confirmation     | 5           | 4            | 1           |
| False Breakout Patterns | 5           | 5            | 0           |
| Breakout Validation     | 5           | 4            | 1           |
| **TOTAL**               | **21**      | **14 (67%)** | **7 (33%)** |

---

## Appendix C: Complete Existing Indicator Inventory

> See [QUEEN_INVENTORY.md](QUEEN_INVENTORY.md) for full details

### C.1 Summary of Existing Modules

| Category           | Module Count            | Key Functions                     |
| ------------------ | ----------------------- | --------------------------------- |
| Core Indicators    | `core.py`               | SMA, EMA, RSI, Slope              |
| Advanced           | `advanced.py`           | BB, Supertrend, ATR Channels      |
| ADX/DMI            | `adx_dmi.py`            | ADX, DMI, LBX                     |
| MACD               | `momentum_macd.py`      | MACD, Signal, Histogram           |
| Keltner            | `keltner.py`            | Keltner Channels, Vol Index       |
| Volume             | `volume_*.py`           | Chaikin, MFI, OBV                 |
| Volatility         | `volatility_fusion.py`  | Combined volatility               |
| Breadth            | `breadth_*.py`          | Market breadth                    |
| Patterns Core      | `patterns/core.py`      | Japanese candlesticks             |
| Patterns Composite | `patterns/composite.py` | Multi-candle patterns             |
| Tactical Signals   | `signals/tactical/`     | 10+ signal modules                |
| Fusion Signals     | `signals/fusion/`       | CMV, LBX, Market Regime           |
| Microstructure     | `microstructure/`       | CPR, VWAP, Structure, Phases      |
| Strategies         | `strategies/`           | Decision Engine, Playbook, Fusion |
| Services           | `services/`             | Scoring, Bible Engine, Cockpit    |

### C.2 No Duplicates Found

The new modules do NOT duplicate existing functionality:

- **FVG**: New concept, not in existing codebase
- **Volume Confirmation**: Complements (not duplicates) existing volume modules
- **False Breakout**: New patterns not in `patterns/core.py`
- **Breakout Validator**: New integration layer

### C.3 Recommended DRY Improvement

The new modules include local `_calculate_atr()` functions. These should ideally use:

```python
from queen.helpers.ta_math import atr_wilder
```

The code includes fallback to local implementation if import fails.

---

_End of Master Plan_
