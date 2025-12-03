
Thought for 12 seconds
The user wants me to proceed with Step 2: Creating specific rules for each timeframe (scalp vs swing). I need to build comprehensive rules for:
SCALP (5-30 minutes)
INTRADAY (1-6 hours)
BTST (Overnight)
SWING (3-15 days)
POSITIONAL (2-8 weeks)
For each timeframe, I need to define:
Entry criteria
Exit criteria
Indicator settings (different periods for different timeframes)
Stop loss rules
Target rules
Volume requirements
Time-of-day considerations
Risk management
Specific patterns that work best
Multi-timeframe alignment requirements
This should be comprehensive and practical for the user's trading engine.
STEP 2: Timeframe-Specific Rules
Complete Implementation for Scalp, Intraday, BTST, Swing, and Positional Trading

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           TIMEFRAME HIERARCHY                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  TIMEFRAME    │ HOLD TIME      │ CHART TF      │ CONFIRMATION TF │ RISK/TRADE      │
│  ─────────────┼────────────────┼───────────────┼─────────────────┼─────────────────│
│  SCALP        │ 5-30 min       │ 1min, 3min    │ 5min, 15min     │ 0.25-0.5%       │
│  INTRADAY     │ 30min - 6hrs   │ 5min, 15min   │ 1hr, Daily      │ 0.5-1%          │
│  BTST         │ Overnight      │ 15min, 1hr    │ Daily           │ 1-1.5%          │
│  SWING        │ 3-15 days      │ Daily         │ Weekly          │ 1.5-3%          │
│  POSITIONAL   │ 2-8 weeks      │ Daily, Weekly │ Monthly         │ 3-5%            │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘


# 🔴 YOU ARE ABSOLUTELY RIGHT -

WHAT YOU MEANT (CORRECT PERSPECTIVE):
═════════════════════════════════════
At 09:15-09:30, this WAS a valid INTRADAY LONG/SCALP opportunity!
Your engine should have caught it but DIDN'T.
Instead, it flagged other (worse) stocks as "BUY"
TIMEFRAME RULES SUMMARY
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           TIMEFRAME RULES QUICK REFERENCE                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  SCALP (5-30 min)                                                                       │
│  ═════════════════                                                                      │
│  ✓ Best time: 9:20 - 11:30 AM                                                          │
│  ✓ VWAP is king - Long above, Short below                                              │
│  ✓ Volume surge required (1.5x+)                                                       │
│  ✓ Strong candle body (>70%)                                                           │
│  ✓ RSI 60-80 for longs (momentum, not overbought)                                      │
│  ✓ Tight stops (0.75x ATR)                                                             │
│  ✓ Quick targets (1-2x ATR)                                                            │
│  ✗ Avoid after 11:30 AM                                                                │
│  ✗ Never counter VWAP                                                                  │
│                                                                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  INTRADAY (30min - 6hrs)                                                                │
│  ════════════════════════                                                               │
│  ✓ Align with daily trend                                                              │
│  ✓ Entry types: ORB, VWAP bounce, Pullback, Breakout                                   │
│  ✓ Wait for first 15-30 min to establish range                                         │
│  ✓ Volume confirms direction                                                           │
│  ✓ EMA stack important (9 > 21 > 50 for longs)                                         │
│  ✓ Standard stops (1x ATR)                                                             │
│  ✓ Exit by 3:15 PM                                                                     │
│  ✗ Don't chase extended moves                                                          │
│  ✗ Avoid midday chop (11:30 - 1:30)                                                    │
│                                                                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  BTST (Overnight)                                                                        │
│  ═══════════════                                                                        │
│  ✓ Entry: 2:00 - 3:25 PM only                                                          │
│  ✓ Must close near day's high (>80% position)                                          │
│  ✓ Daily trend must be up                                                              │
│  ✓ Last 3-4 candles should be bullish                                                  │
│  ✓ Volume above average                                                                │
│  ✓ Wider stops for gap risk (1.5x ATR)                                                 │
│  ✗ Avoid Friday BTST                                                                   │
│  ✗ No distribution patterns (shooting star, etc.)                                      │
│  ✗ Exit next day by 10:30 if no follow-through                                         │
│                                                                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  SWING (3-15 days)                                                                       │
│  ═════════════════                                                                      │
│  ✓ Weekly trend bullish (above 20 WMA)                                                 │
│  ✓ Entry on pullback to 21 EMA                                                         │
│  ✓ Volume dry up during consolidation                                                  │
│  ✓ Look for base patterns (VCP, Cup & Handle)                                          │
│  ✓ Relative strength positive                                                          │
│  ✓ Wider stops (2x ATR)                                                                │
│  ✓ Target 2.5-3R minimum                                                               │
│  ✗ Don't buy extended (>8% from 21 EMA)                                                │
│  ✗ Avoid weak sectors                                                                  │
│                                                                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  POSITIONAL (2-8 weeks)                                                                  │
│  ══════════════════════                                                                 │
│  ✓ Monthly trend bullish                                                               │
│  ✓ Near 52-week high (<15% away)                                                       │
│  ✓ Strong fundamentals (revenue/profit growth)                                         │
│  ✓ Institutional accumulation signs                                                    │
│  ✓ Above weekly 21 EMA                                                                 │
│  ✓ Use weekly low for stop                                                             │
│  ✓ Add on 5% dips (SIP approach)                                                       │
│  ✓ Target 15-40% moves                                                                 │
│  ✗ Avoid stocks far from highs                                                         │
│  ✗ Review on quarterly results                                                         │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘


🎯 YOUR MISSED TRADE - TIMEFRAME ANALYSIS

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    ANALYSIS OF YOUR MISSED TRADE                                         │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  AT 09:30 AM:                                                                           │
│  ════════════                                                                           │
│                                                                                          │
│  SCALP EVALUATION:                                                                      │
│  ─────────────────                                                                      │
│  ✅ Time: 09:30 - Within scalp window (9:20-11:30)                                     │
│  ✅ VWAP: Price 8410 > VWAP ~8350 → +20                                                │
│  ✅ RSI: 72 in opening session = MOMENTUM → +15                                        │
│  ✅ Volume: 25,574 (1.7x average) → +20                                                │
│  ✅ Candle: Strong bullish (body 70%+, close near high) → +20                          │
│  ✅ EMA: Fast > Medium → +15                                                           │
│  ✅ Opening Range Breakout: Breaking above first candle high → +15                     │
│                                                                                          │
│  SCALP SCORE: +105 (capped at 100)                                                     │
│  ACTION: SCALP_LONG                                                                     │
│  ENTRY: 8410                                                                            │
│  STOP: 8335 (below VWAP)                                                                │
│  TARGET 1: 8510 (+1 ATR)                                                                │
│  TARGET 2: 8560 (+1.5 ATR)                                                              │
│                                                                                          │
│  ─────────────────────────────────────────────────────────────────────────────────────  │
│                                                                                          │
│  INTRADAY EVALUATION:                                                                   │
│  ─────────────────────                                                                  │
│  ✅ All scalp conditions + time for bigger move                                        │
│  ✅ Trade Type: ORB (Opening Range Breakout)                                           │
│                                                                                          │
│  INTRADAY SCORE: +85                                                                    │
│  ACTION: INTRADAY_STRONG_BUY                                                            │
│  TARGET 1: 8560                                                                         │
│  TARGET 2: 8660                                                                         │
│                                                                                          │
│  ─────────────────────────────────────────────────────────────────────────────────────  │
│                                                                                          │
│  WHAT ENGINE SHOULD HAVE OUTPUT:                                                        │
│  ════════════════════════════════                                                       │
│                                                                                          │
│  {                                                                                       │
│    "symbol": "XXXX",                                                                    │
│    "timestamp": "2025-11-28T09:30:00",                                                  │
│    "best_opportunity": {                                                                │
│      "timeframe": "SCALP",                                                              │
│      "action": "SCALP_LONG",                                                            │
│      "score": 100,                                                                      │
│      "direction": "LONG"                                                                │
│    },                                                                                   │
│    "signals": [                                                                         │
│      "ABOVE_VWAP",                                                                      │
│      "RSI_STRONG_MOMENTUM_72",                                                          │
│      "VOLUME_SURGE_1.7X",                                                               │
│      "STRONG_BULLISH_CANDLE",                                                           │
│      "ORB_BREAKOUT_UP",                                                                 │
│      "OPENING_SESSION_MOMENTUM"                                                         │
│    ],                                                                                   │
│    "entry": 8410,                                                                       │
│    "stop_loss": 8335,                                                                   │
│    "targets": [8510, 8560],                                                             │
│    "risk_reward": 1.33                                                                  │
│  }                                                                                       │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

This completes STEP 2: Timeframe-Specific Rules.
Key highlights:
SCALP: Fastest, tightest rules, opening session focus, VWAP mandatory
INTRADAY: Multiple entry types (ORB, VWAP, Pullback, Breakout), daily alignment needed
BTST: Late day entries only, close near high mandatory, wider stops
SWING: Weekly trend, pullback entries, base patterns, relative strength
POSITIONAL: Monthly trend, fundamentals, institutional accumulation

SUMMARY: COMPLETE TAG SYSTEM
Timeframe Tags:
SCALP_LONG, SCALP_SHORT, SCALP_BREAKOUT
INTRADAY_LONG, INTRADAY_SHORT, INTRADAY_RANGE, INTRADAY_BREAKOUT
BTST_LONG, BTST_SHORT, BTST_MOMENTUM
SWING_LONG, SWING_SHORT, SWING_BREAKOUT, SWING_CONSOLIDATING
POSITIONAL_LONG, POSITIONAL_SHORT

Action Tags:
STRONG_BUY, BUY, ADD, ACCUMULATE, DIP_BUY
HOLD, WATCH, WAIT, NO_ACTION
REDUCE, EXIT, SELL, SHORT, AVOID, STRONG_AVOID
BOOK_PARTIAL, TRAILING_STOP, MOVE_TO_COST

Phase Tags:
ACC_SPRING, ACC_SOS, ACC_LPS (Best buy zones)
MARKUP_EARLY, MARKUP_MIDDLE, MARKUP_LATE
DIST_UPTHRUST, DIST_SOW (Best short zones)
MARKDOWN_EARLY, MARKDOWN_MIDDLE, MARKDOWN_CAPITULATION
CONSOLIDATING_BULLISH, CONSOLIDATING_BEARISH, BREAKOUT_IMMINENT

Signal Tags:
VOLUME_CONFIRMATION, VOLUME_DIVERGENCE
RSI_BULLISH, RSI_BEARISH, RSI_DIVERGENCE
PATTERN_BULLISH, PATTERN_BEARISH
TREND_ALIGNED, TREND_COUNTER
BREAKOUT_VALID, BREAKOUT_FAKE

 COMPLETE TRADING FRAMEWORK
1. TRADING TIMEFRAME CLASSIFICATIONS
┌─────────────────────────────────────────────────────────────────────┐
│                    TIMEFRAME HIERARCHY                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SCALP (5-30 min)        INTRADAY (1-6 hrs)      BTST (Overnight)   │
│  ├── Scalp Long          ├── Intraday Long       ├── BTST Long      │
│  ├── Scalp Short         ├── Intraday Short      ├── BTST Short     │
│  ├── Scalp Breakout      ├── Intraday Breakout   ├── BTST Breakout  │
│  └── Scalp Reversal      ├── Intraday Reversal   └── BTST Momentum  │
│                          └── Intraday Range                          │
│                                                                      │
│  SWING (3-15 days)       POSITIONAL (2-8 weeks)  INVESTMENT (Months)│
│  ├── Swing Long          ├── Positional Long     ├── Accumulate     │
│  ├── Swing Short         ├── Positional Short    ├── Core Hold      │
│  ├── Swing Breakout      ├── Trend Following     └── SIP Addition   │
│  ├── Swing Consolidating └── Sector Rotation                        │
│  └── Swing Ready                                                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

2. ACTION TAGS (Priority Order)
┌─────────────────────────────────────────────────────────────────────┐
│                     ACTION TAG MATRIX                                │
├──────────────┬──────────────┬───────────────┬───────────────────────┤
│   BULLISH    │   NEUTRAL    │    BEARISH    │     RISK MGMT         │
├──────────────┼──────────────┼───────────────┼───────────────────────┤
│ STRONG_BUY   │ HOLD         │ REDUCE        │ STOP_LOSS_HIT         │
│ BUY          │ WATCH        │ EXIT          │ TRAILING_STOP         │
│ ADD          │ WAIT         │ SELL          │ HEDGE                 │
│ ACCUMULATE   │ CONSOLIDATE  │ SHORT         │ BOOK_PARTIAL          │
│ BREAKOUT_BUY │ NO_ACTION    │ AVOID         │ MOVE_TO_COST          │
│ DIP_BUY      │ RANGE_TRADE  │ STRONG_AVOID  │ RISK_OFF              │
└──────────────┴──────────────┴───────────────┴───────────────────────┘

3. STOCK PHASES (Complete Cycle)
                        COMPLETE MARKET CYCLE
                         
    PHASE 5: DISTRIBUTION          PHASE 1: ACCUMULATION
         (Smart Money              (Smart Money Buying)
          Selling)                        │
              │                           │
              ▼                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│    ┌──────────┐                              ┌──────────┐           │
│    │PHASE 4   │                              │PHASE 2   │           │
│    │MARKUP    │──────────────────────────────│BREAKOUT  │           │
│    │(Bullish) │         PHASE 6              │(Launch)  │           │
│    └──────────┘      ┌───────────┐           └──────────┘           │
│         ▲            │PHASE 3    │                ▲                  │
│         │            │MARKDOWN   │                │                  │
│         │            │(Bearish)  │                │                  │
│         │            └───────────┘                │                  │
│         │                  │                      │                  │
│         └──────────────────┴──────────────────────┘                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘


DETAILED SUB-PHASES (Wyckoff Model Simplified):

╔═══════════════════════════════════════════════════════════════════════╗
║  ACCUMULATION (Bottom Formation)                                       ║
╠═══════════════════════════════════════════════════════════════════════╣
║  A1: Selling Climax (SC)      → High volume panic selling             ║
║  A2: Automatic Rally (AR)     → Dead cat bounce                       ║
║  A3: Secondary Test (ST)      → Retest of lows, lower volume          ║
║  A4: Spring/Shakeout          → False breakdown, traps shorts         ║
║  A5: Sign of Strength (SOS)   → Strong move up, high volume           ║
║  A6: Last Point of Support    → Final test before markup              ║
╚═══════════════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════════════╗
║  DISTRIBUTION (Top Formation)                                          ║
╠═══════════════════════════════════════════════════════════════════════╣
║  D1: Preliminary Supply (PSY) → First sign of selling pressure        ║
║  D2: Buying Climax (BC)       → Euphoric buying, high volume          ║
║  D3: Automatic Reaction (AR)  → Sharp pullback                        ║
║  D4: Secondary Test (ST)      → Retest high, lower volume (WEAK)      ║
║  D5: Upthrust (UT)            → False breakout, traps longs           ║
║  D6: Sign of Weakness (SOW)   → Breakdown below support               ║
╚═══════════════════════════════════════════════════════════════════════╝

INDICATOR FRAMEWORK (Layered Approach)

┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 1: TREND (Foundation)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  INDICATOR     │ INTRADAY           │ SWING/POSITIONAL              │
│  ─────────────────────────────────────────────────────────────────  │
│  EMA 9         │ Scalp trend        │ Short-term momentum           │
│  EMA 21        │ Intraday trend     │ Swing trend                   │
│  EMA 50        │ Session trend      │ Intermediate trend            │
│  EMA 200       │ Major bias         │ Long-term trend               │
│  VWAP          │ ⭐ CRITICAL        │ Less relevant                 │
│  VWAP Bands    │ Mean reversion     │ --                            │
│                                                                      │
│  RULES:                                                              │
│  • Price > VWAP + All EMAs aligned = STRONG BULLISH                 │
│  • Price < VWAP + All EMAs aligned = STRONG BEARISH                 │
│  • EMAs converging = Consolidation/Squeeze                          │
│  • EMA 9 crossing EMA 21 = Trend change signal                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 2: MOMENTUM                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  RSI (14)                                                           │
│  ├── Overbought: > 70 (potential reversal)                          │
│  ├── Oversold: < 30 (potential bounce)                              │
│  ├── Bullish momentum: > 50 and rising                              │
│  ├── Bearish momentum: < 50 and falling                             │
│  ├── Hidden Bullish Divergence: Price HL + RSI LL = STRONG BUY     │
│  └── Regular Bearish Divergence: Price HH + RSI LH = WARNING        │
│                                                                      │
│  MACD (12, 26, 9)                                                   │
│  ├── Bullish Cross: MACD line crosses above Signal                  │
│  ├── Bearish Cross: MACD line crosses below Signal                  │
│  ├── Histogram expanding = Momentum increasing                      │
│  └── Histogram contracting = Momentum weakening                     │
│                                                                      │
│  ⚠️ CRITICAL RULE:                                                   │
│  • Don't buy overbought + rising                                    │
│  • Don't short oversold + falling                                   │
│  • Divergences are EARLY warnings, need confirmation                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 3: VOLUME ANALYSIS                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  VOLUME RULES (Most Important for Your Case):                        │
│                                                                      │
│  1. BREAKOUT VALIDATION:                                             │
│     • Volume must be > 1.5x average for valid breakout              │
│     • Volume declining on breakout = FAKE (your missed signal)      │
│                                                                      │
│  2. VDU (Volume Dry Up):                                            │
│     • Volume < 50% average during consolidation = GOOD              │
│     • Means supply absorbed, ready to move                          │
│                                                                      │
│  3. VOLUME PROFILE:                                                  │
│     • High volume at support = Accumulation                         │
│     • High volume at resistance = Distribution                      │
│     • Volume on up moves vs down moves (ratio)                      │
│                                                                      │
│  4. YOUR DATA SHOWED:                                                │
│     09:30 - 25,574 (HIGHEST)                                        │
│     10:30 - 14,041 (when price hit HIGH)                            │
│     11:00 - 10,648 (breakdown candle)                               │
│     → Price making highs on DECLINING volume = DISTRIBUTION         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 4: VOLATILITY & RANGE                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ATR (14)                                                           │
│  ├── Stop Loss = Entry ± 1.5-2x ATR                                 │
│  ├── Position Size = Risk $ / (ATR × Multiplier)                    │
│  ├── ATR expanding = Trend move                                     │
│  └── ATR contracting = Range/Squeeze                                │
│                                                                      │
│  BOLLINGER BANDS                                                    │
│  ├── Squeeze (bands narrow) = Breakout imminent                     │
│  ├── Walking the bands = Strong trend                               │
│  └── Mean reversion from 2σ = Counter-trend trade                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 5: RELATIVE STRENGTH                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  RPS (Relative Price Strength vs NIFTY/BANKNIFTY)                   │
│  ├── RPS > 0 and rising = Outperforming (prefer for longs)          │
│  ├── RPS < 0 and falling = Underperforming (avoid for longs)        │
│  └── RPS at inflection = Potential rotation                         │
│                                                                      │
│  SECTOR STRENGTH                                                     │
│  ├── Stock in strongest sector = Higher probability                 │
│  └── Stock in weakest sector = Lower probability (unless reversal)  │
│                                                                      │
│  MCS (Market Context Score) - Custom                                │
│  ├── Index trend + Breadth + Sector + Stock alignment              │
│  └── Score 0-100: >70 = Strong, <30 = Weak                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 6: SMART MONEY CONCEPTS                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  FVG (Fair Value Gap)                                               │
│  ├── Bullish FVG: Gap between candle 1 high and candle 3 low       │
│  ├── Bearish FVG: Gap between candle 1 low and candle 3 high       │
│  └── Price tends to fill these gaps = Support/Resistance zones      │
│                                                                      │
│  ORDER BLOCKS                                                        │
│  ├── Last opposing candle before impulsive move                     │
│  ├── Bullish OB: Last red candle before up move = Buy zone          │
│  └── Bearish OB: Last green candle before down move = Sell zone     │
│                                                                      │
│  LIQUIDITY POOLS                                                     │
│  ├── Above equal highs = Buy-side liquidity (target for shorts)     │
│  └── Below equal lows = Sell-side liquidity (target for longs)      │
│                                                                      │
│  CRP (Conflict Resolution Point)                                     │
│  └── Where multiple indicators/levels converge = High probability   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

CANDLESTICK PATTERNS (Reliability Ranked)
HIGH RELIABILITY (Use These)
┌─────────────────────────────────────────────────────────────────────┐
│              HIGH RELIABILITY PATTERNS (>65% accuracy)               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  BULLISH REVERSAL                   BEARISH REVERSAL                │
│  ─────────────────                  ────────────────                │
│                                                                      │
│  1. BULLISH ENGULFING               1. BEARISH ENGULFING            │
│     ┌───┐                              │   │                        │
│     │███│                              │   │                        │
│     │███│ ← Green engulfs red          ├───┤                        │
│     │ │ │                              │███│ ← Red engulfs green    │
│     └───┘                              │███│                        │
│                                        └───┘                        │
│                                                                      │
│  2. HAMMER (at support)             2. SHOOTING STAR (at resist)    │
│        │                                  │                         │
│        │                               ┌──┴──┐                      │
│     ┌──┴──┐                            │     │                      │
│     │     │                            │     │                      │
│     └─────┘                               │                         │
│        │                                  │                         │
│        │ (long lower wick)                                          │
│                                                                      │
│  3. MORNING STAR (3-candle)         3. EVENING STAR (3-candle)      │
│           ┌───┐                                 ┌─┐                  │
│     ┌───┐ │   │                       ┌───┐   └┬┘                  │
│     │███│ │   │                       │   │    │   ┌───┐           │
│     │███│ └─┬─┘                       │   │ ┌──┴─┐ │███│           │
│     └───┘   │                         └───┘ └────┘ │███│           │
│        ↑ Small doji ↑                              └───┘            │
│                                                                      │
│  4. THREE WHITE SOLDIERS             4. THREE BLACK CROWS           │
│              ┌───┐                                   │███│           │
│        ┌───┐ │   │                         ├───┤   │███│           │
│  ┌───┐ │   │ │   │                   ┌───┐ │███│   ├───┤           │
│  │   │ │   │ └───┘                   │   │ │███│   │███│           │
│  │   │ └───┘                         │   │ └───┘   └───┘           │
│  └───┘                               └───┘                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

⚠️ CRITICAL: Patterns MUST be at key levels (support/resistance) to be valid!

MULTI-TIMEFRAME CONFIRMATION
┌─────────────────────────────────────────────────────────────────────┐
│              MULTI-TIMEFRAME PATTERN CONFIRMATION                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  INTRADAY (15min primary):                                          │
│  ─────────────────────────                                          │
│  • 1hr chart → Trend direction & major S/R                          │
│  • 15min chart → Entry patterns                                     │
│  • 5min chart → Precise entry timing                                │
│                                                                      │
│  SWING (Daily primary):                                             │
│  ─────────────────────                                              │
│  • Weekly chart → Major trend & levels                              │
│  • Daily chart → Entry patterns                                     │
│  • 4hr/1hr chart → Entry timing                                     │
│                                                                      │
│  CONFIRMATION RULES:                                                 │
│  ✓ Higher timeframe trend MUST align with trade direction           │
│  ✓ Pattern on entry timeframe confirmed by momentum indicators      │
│  ✓ Volume supports the pattern                                      │
│  ✗ Never trade against higher timeframe trend on lower timeframe    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘



CORRECT ANALYSIS (Time-Based Perspective)
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WHAT YOUR ENGINE SHOULD HAVE SEEN                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  AT 09:15-09:30 (ENTRY WINDOW):                                             │
│  ══════════════════════════════                                             │
│                                                                              │
│  ✅ STRONG BULLISH CANDLE: Open 8172.5 → Close 8328.5 (+1.9%)               │
│  ✅ HIGH VOLUME: 18,436 then 25,574 (momentum confirmed)                    │
│  ✅ BREAKING HIGHER: Making new highs with conviction                       │
│  ✅ EARLY SESSION: Best time for momentum trades                            │
│                                                                              │
│  CORRECT SIGNAL: 🚀 INTRADAY_LONG / SCALP_BREAKOUT                          │
│  CORRECT SCORE: +70 to +85 (STRONG BUY)                                     │
│  TARGET: Previous resistance / 1-2% profit                                  │
│  STOP LOSS: Below 8131 (day low)                                            │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  AT 10:00-10:30 (PROFIT BOOKING WINDOW):                                    │
│  ═══════════════════════════════════════                                    │
│                                                                              │
│  ⚠️ VOLUME DROPPING: 25,574 → 10,973 → 14,041                               │
│  ⚠️ MOMENTUM SLOWING: Smaller candle bodies                                 │
│  ⚠️ MAKING NEW HIGH ON WEAK VOLUME: Divergence forming                      │
│                                                                              │
│  CORRECT SIGNAL: 📤 BOOK_PROFITS / TRAIL_STOP                               │
│  ACTION: Exit 50-75% position, trail stop for rest                          │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  AT 11:00+ (REVERSAL CONFIRMED):                                            │
│  ═══════════════════════════════                                            │
│                                                                              │
│  ❌ BREAKDOWN CANDLE: Open 8536 → Close 8435 (-1.2%)                        │
│  ❌ STRUCTURE BREAK: Below previous swing lows                              │
│                                                                              │
│  CORRECT SIGNAL: 🔴 EXIT_ALL / POTENTIAL_SHORT                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

THE ACTUAL TRADE THAT WAS MISSED
                         MISSED SCALP OPPORTUNITY
                          
    Price
    8600 ┤                          ╭─╮ ← HIGH 8577 (10:30)
         │                        ╭─╯ ╰─╮
    8500 ┤                    ╭───╯     ╰──╮
         │                ╭───╯            ╰──╮
    8400 ┤            ╭───╯    PROFIT ZONE     ╰───╮
         │        ╭───╯      (+4-5% move)          ╰───╮
    8300 ┤    ╭───╯                                    ╰───╮
         │ ╭──╯ ← ENTRY HERE                               ╰───
    8200 ┤─╯     (09:15-09:30)
         │
    8100 ┼─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────
             09:15 09:30 09:45 10:00 10:15 10:30 10:45 11:00 ...
             
    💰 MISSED PROFIT: ₹400+ per share (8172 → 8577)
    ⏱️ HOLDING TIME: 60-75 minutes
    📊 TYPE: Perfect intraday scalp/momentum trade

WHY YOUR ENGINE MISSED IT (Probable Causes)
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROBABLE ENGINE FLAWS                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FLAW 1: Opening Session Logic Missing                                       │
│  ─────────────────────────────────────                                       │
│  • Engine may not recognize first 30 min as "momentum opportunity window"   │
│  • Gap-up stocks need different logic than regular breakouts                 │
│  • First candle strength + volume = high probability setup                   │
│                                                                              │
│  FLAW 2: Volume Relative Comparison Missing                                  │
│  ──────────────────────────────────────────                                  │
│  • Engine may check absolute volume, not relative                            │
│  • First candle had 18,436 - is this high for this stock?                   │
│  • Need to compare vs average volume, not just a fixed threshold            │
│                                                                              │
│  FLAW 3: Momentum Detection Weak                                             │
│  ────────────────────────────────                                            │
│  • Close near high of candle = strong momentum                               │
│  • 8328.5 close vs 8340 high = 0.3% from high = VERY STRONG                 │
│  • Engine may not be measuring candle "quality"                              │
│                                                                              │
│  FLAW 4: Multi-Timeframe Not Implemented                                     │
│  ───────────────────────────────────────                                     │
│  • Daily chart might show stock was already bullish                          │
│  • This gap-up was continuation, not exhaustion                              │
│  • Engine needs higher TF context                                            │
│                                                                              │
│  FLAW 5: Wrong Scoring Weights                                               │
│  ──────────────────────────────                                              │
│  • Maybe RSI showed overbought and engine penalized it                       │
│  • Early session RSI overbought is BULLISH not bearish!                      │
│  • Context matters for indicator interpretation                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
