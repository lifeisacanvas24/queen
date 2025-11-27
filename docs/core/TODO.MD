Task ID,Description,Status
1.1,"CMP Normalization: Create universal get_cmp(), remove conflicts in live.py, scoring.",[ ]
1.2,"Indicator Layer Stabilization: Create INDICATOR_SCHEMA, standardize names (EMA, CPR, VWAP), unify output.",[ ]
1.3,"Bible Engine Cleanup: Merge all CPR/VWAP context keys, make blocks pure, add ""Near/Choppy"" state.",[ ]
1.4,"Tactical Fusion v1.0 (Critical): Create tactical_fusion.py, merge all tactical signals, output unified tactical_index.",[ ]
1.5,"Scoring Engine v1.0 (Most Important): Create score_engine.py, define inputs/outputs (Score, Decision, Conviction), enforce consistency.",[ ]
1.6,"Ladder Integration (v1.4): Merge reversible-runner logic, add Ladder influence into scoring, integrate with alerts.",[ ]
1.7,"Actionables Pipeline Rewrite: Split actionables_for() into clean sequential steps, guarantee consistent fields.",[ ]
1.8,"Cockpit Schema Freeze (UI Contract): Define mandatory output fields for backend, stabilize Cockpit UI.",[ ]
1.9,"Alerts Engine Upgrade: Add tactical, breakout, WRB/runner, and CPR/VWAP reclaim alerts.",[ ]
1.10,"Performance Pass: Implement caching for indicators, bible blocks, and parallel universe scanning.",[ ]
Task ID,Description,Status
2.1,"FO Module (Futures & Options): Add OI Delta, PCR, IV Capture, FO risk ratings, FO breakout signals, and FO-specific universe.",[ ]
2.2,"Tactical Fusion v2.0: Multi-timeframe fusion (5m+15m+30m), Pattern confidence, Regime-aware weighting, Order-block detection.",[ ]
2.3,"Cockpit Enhancements: Add Heatmap, Radar view, Sparkline mini-charts, and Sector filter.",[ ]
Task ID,Description,Status
3.1,"Supervisor v2: Implement live engine heartbeat, auto-restart, crash-localization, and latency alerts.",[ ]
3.2,"Morning Intel v2: Overnight ranking, Sector momentum, Gap analysis, Pre-market breakout probability.",[ ]
3.3,"Portfolio Agent: Risk-based sizing, Ladder-aware trailing, Trade quality filters, PnL optimization rules.",[ ]
Task ID,Description,Status
4.1,"Cognitive Layer Integration: Integrate Meta_Controller, Drift Detector, and Cognitive Orchestrator.",[ ]
4.2,"AI Fusion Model: Predict breakout probability, fakeouts, and liquidity trap likelihood.",[ ]
4.3,"AI Recommender: Recommend top candidates, label high-probability symbols, predict best timing window.",[ ]
4.4,"AI Trainer + Dataset: Auto dataset creation, auto model training, and auto inference.",[ ]
Task ID,Description,Status
3.2.1,"SWING ENGINE (Daily/Weekly): Build swing_engine.py, define inputs (Daily/Weekly OHLC, Patterns, WRB), produce swing_signal, swing_score.",[ ]
3.2.2,"BTST ENGINE (1–3 Day): Build btst_engine.py, define inputs (Prev-day intraday, Gap context), compute BTST_probability, produce btst_signal.",[ ]
3.2.4,"Candlestick Pattern Runner: Validate/define core patterns (Morning Star, Engulfing), add pattern confidence scoring, ensure feed into Swing/BTST.",[ ]
3.2.5,"WRB Engine Integration: Identify WRB large bars/clusters, mark climax, define WRB-based signals (Breakout Confirmation, Fake Breakout), add wrb_context.",[ ]
Task ID,Description,Status
3.3.1,"Create Master Registry: Build queen/settings/indicators.py, define structure (name, category, applicable_tf, default_params).",[ ]
3.3.2,"Indicator Categories: Define/document Intraday, Swing, and FO Core (OI Delta, PCR, IV Capture) indicator sets.",[ ]
3.3.3,"Missing Indicators: Implement Volume Profile (POC, VAH/VAL), VDU Detector, WRB Intensity, and Breadth Metrics.",[ ]
Task ID,Description,Status
3.4.1,"Build Master Converter: Load raw NSE CSV, clean fields, validate ISIN, build standard JSON dict per symbol.",[ ]
3.4.2,"NSE + BSE Merge Logic: Use ISIN as primary key to merge NSE/BSE, add derived flags (fo_eligible, illiquid_flag).",[ ]
3.4.4,"Universe Tiering System: Build build_intraday_universe.py, define score weighting (liquidity, institutional, fundamental), define Tier 1/2/3 thresholds.",[ ]
3.4.6,API + Routers Integration: Add routers/universe.py endpoints for intraday/swing/master.,[ ]
Task ID,Description,Status
3.5.1,"Refactor Existing Scrapers: Migrate/clean existing scrapers, add error-handling and caching.",[ ]
3.5.2,"Standardize Output Schema: Define mandatory fields (roe_3yr, debt_to_equity, fii_holding), add schema validator.",[ ]
3.5.4,"Quality Score Engine (0–100): Create fundamental_engine.py, define components (Profitability, Growth, Balance Sheet, Institutional Interest), calculate final Quality Score.",[ ]
3.5.5,Integrate Fundamentals: Merge quality_score and key metrics into the Symbol Master (Part 3.4) using ISIN.,[ ]
3.5.6,Universe Builder Integration: Use quality_score as a major filter for both Intraday and Swing universes.,[ ]
