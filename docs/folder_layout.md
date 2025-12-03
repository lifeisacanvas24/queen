```plaintext
queen/
├── alerts/
│   │   ├── evaluator copy.py
│   │   ├── evaluator.py
│   │   ├── rules.py
│   │   └── state.py
├── apps/
│   │   ├── fastapi/
│   │   └── terminal/
├── cli/
│   │   ├── __init__.py
│   │   ├── debug_decisions.py
│   │   ├── debug_fetch_unified.py
│   │   ├── fundamentals_cli.py
│   │   ├── g_upstox_client.py
│   │   ├── list_master.py
│   │   ├── list_signals.py
│   │   ├── list_technicals.py
│   │   ├── live_monitor.py
│   │   ├── live_monitor_cli.py
│   │   ├── monitor_stream.py
│   │   ├── morning_intel.py
│   │   ├── replay_actionable.py
│   │   ├── run_strategy.py
│   │   ├── scan_signals.py
│   │   ├── show_snapshot.py
│   │   ├── sim_stats.py
│   │   ├── symbol_scan.py
│   │   ├── universe_scanner.py
│   │   └── validate_registry.py
├── configs/
│   │   ├── alert_1d_rules.yaml
│   │   ├── alert_intraday_rules.yaml
│   │   ├── alert_rules.yaml
│   │   └── alert_rules_demo.yaml
├── daemons/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── alert_daemon.py
│   │   ├── alert_v2 copy.py
│   │   ├── alert_v2.py
│   │   ├── live_engine.py
│   │   ├── live_engine_cli.py
│   │   ├── morning_intel.py
│   │   └── scheduler.py
├── data/
│   └── [runtime files...]
├── demos/
│   │   ├── __init__.py
│   │   └── pattern_tactical_chain.py
├── docs/
│   │   ├── core/
│   │   │   │   │   ├── feedback-fixes.txt
│   │   │   │   │   ├── new-gpt-roadmap.txt
│   │   │   │   │   ├── part-1-n-part-2-road-map.txt
│   │   │   │   │   ├── part-1.txt
│   │   │   │   │   ├── part-2.txt
│   │   │   │   │   ├── PRE_TODO.MD
│   │   │   │   │   ├── roadmap.md
│   │   │   │   │   ├── roadmap.txt
│   │   │   │   │   └── TODO.MD
│   │   ├── core_docs/
│   │   │   │   │   ├── bible-flow.txt
│   │   │   │   │   ├── claude-discussions-more.md
│   │   │   │   │   ├── claude-discussions.md
│   │   │   │   │   ├── claude-pcr-fvg-indicators.png
│   │   │   │   │   ├── claude-timeframe.html
│   │   │   │   │   ├── claude-timeframe.png
│   │   │   │   │   ├── claude-timeframes.md
│   │   │   │   │   ├── feedback-from-chatgpt.txt
│   │   │   │   │   ├── fundamentals-pipline-test.txt
│   │   │   │   │   ├── master-todo.txt
│   │   │   │   │   ├── quant.md
│   │   │   │   │   ├── todo-index-20-11-2025-nov.txt
│   │   │   │   │   └── upcoming-todo-20-11-2025-nov.txt
│   │   ├── alerts-fastapi.txt
│   │   ├── ATR-DYNAMIC.png
│   │   ├── Breakout_Bible_v10.pdf
│   │   ├── Breakout_Bible_v10_4_FULL.pdf
│   │   ├── Breakout_Bible_v10_5_FULL.pdf
│   │   ├── changelog.md
│   │   ├── cockpit.txt
│   │   ├── curl-test.txt
│   │   ├── daemons-todo.txt
│   │   ├── developers_commands.md
│   │   ├── documentation.md
│   │   ├── git_commands.md
│   │   ├── image.png
│   │   ├── important-libraries.txt
│   │   ├── indicators-bible.txt
│   │   ├── intraday_cockpit.txt
│   │   ├── key-indicators.txt
│   │   ├── pending-to-bedone.txt
│   │   ├── queen_todo.py
│   │   ├── release.md
│   │   ├── router-upstox-todo.txt
│   │   ├── Screenshot 2025-11-04 at 1.48.45 PM.png
│   │   ├── tactical-blueprint.txt
│   │   ├── temp-settings-feedback.txt
│   │   ├── to-do-for-25th.txt
│   │   ├── todo-for-24.txt
│   │   └── transfering-chat.txt
├── dustbin/
│   │   ├── all_eq.json
│   │   ├── all_fo.json
│   │   ├── all_options.json
│   │   ├── all_symbols.json
│   │   ├── complete.json
│   │   ├── extract_instruments.py
│   │   ├── from_kiwi_bible.py
│   │   ├── fundamental_data.csv
│   │   ├── fundamental_data.parquet
│   │   ├── fundamentals_scraper_v2.py
│   │   ├── google_gemini_upstox.py
│   │   ├── google_gemini_upstox_v2.py
│   │   └── symbols.json
├── fetchers/
│   │   ├── universe/
│   │   │   │   │   ├── build_monthly_universe.py
│   │   │   │   │   └── convert_instruments_to_master.py
│   │   ├── __init__.py
│   │   ├── fetch_router.py
│   │   ├── fundamentals_scraper.py
│   │   ├── g_nse_fecther_cache.py
│   │   ├── nse_fetcher.py
│   │   ├── nse_fetcher_new.py
│   │   ├── options_chain.py
│   │   ├── screener_scraper.py
│   │   └── upstox_fetcher.py
├── helpers/
│   │   ├── __init__.py
│   │   ├── candle_adapter.py
│   │   ├── candles.py
│   │   ├── common.py
│   │   ├── diagnostic_override_logger.py
│   │   ├── fetch_utils.py
│   │   ├── fno_universe.py
│   │   ├── fundamentals_adapter.py
│   │   ├── fundamentals_polars_engine.py
│   │   ├── fundamentals_registry.py
│   │   ├── fundamentals_schema.py
│   │   ├── fundamentals_timeseries_engine.py
│   │   ├── gemini_schema_adapter.py
│   │   ├── gemini_schema_helper.py
│   │   ├── gemini_schema_options_adapter.py
│   │   ├── instruments.py
│   │   ├── intervals.py
│   │   ├── io.py
│   │   ├── logger.py
│   │   ├── market.py
│   │   ├── options_catalog.py
│   │   ├── options_schema.py
│   │   ├── path_manager.py
│   │   ├── pl_compat.py
│   │   ├── portfolio.py
│   │   ├── rate_limiter.py
│   │   ├── schema_adapter.py
│   │   ├── shareholding_fetcher.py
│   │   ├── ta_math.py
│   │   ├── tactical_regime_adapter.py
│   │   └── verify.py
├── scrapers/
│   │   ├── bse_batch_processor.py
│   │   ├── bse_scraper.py
│   │   ├── fundamental_data.csv
│   │   ├── fundamental_data.json
│   │   ├── fundamental_data.parquet
│   │   └── fundamentals_scraper.py
├── server/
│   │   ├── routers/
│   │   │   │   │   ├── alerts.py
│   │   │   │   │   ├── analytics.py
│   │   │   │   │   ├── cockpit.py
│   │   │   │   │   ├── health.py
│   │   │   │   │   ├── instruments.py
│   │   │   │   │   ├── intel.py
│   │   │   │   │   ├── market_state.py
│   │   │   │   │   ├── monitor.py
│   │   │   │   │   ├── pnl.py
│   │   │   │   │   ├── portfolio.py
│   │   │   │   │   └── services.py
│   │   ├── static/
│   │   │   │   │   ├── js/
│   │   │   │   │   │   │   │   │   ├── cockpit_cards.js
│   │   │   │   │   │   │   │   │   ├── cockpit_compat.js
│   │   │   │   │   │   │   │   │   ├── cockpit_core.js
│   │   │   │   │   │   │   │   │   ├── cockpit_live.js
│   │   │   │   │   │   │   │   │   ├── cockpit_portfolio.js
│   │   │   │   │   │   │   │   │   ├── cockpit_session.js
│   │   │   │   │   │   │   │   │   └── cockpit_ui.js
│   │   │   │   │   ├── positions/
│   │   │   │   │   └── queen.css
│   │   ├── templates/
│   │   │   │   │   ├── _layouts/
│   │   │   │   │   │   │   │   │   └── base.html
│   │   │   │   │   ├── _partials/
│   │   │   │   │   │   │   │   │   ├── footer.html
│   │   │   │   │   │   │   │   │   ├── head.html
│   │   │   │   │   │   │   │   │   ├── header.html
│   │   │   │   │   │   │   │   │   ├── panel_actionables.html
│   │   │   │   │   │   │   │   │   ├── panel_portfolio.html
│   │   │   │   │   │   │   │   │   ├── panel_top_actionables.html
│   │   │   │   │   │   │   │   │   └── status_strip.html
│   │   │   │   │   ├── alerts/
│   │   │   │   │   │   │   │   │   └── alerts.html
│   │   │   │   │   ├── cockpit/
│   │   │   │   │   │   │   │   │   ├── analytics.html
│   │   │   │   │   │   │   │   │   ├── history.html
│   │   │   │   │   │   │   │   │   ├── live.html
│   │   │   │   │   │   │   │   │   ├── summary.html
│   │   │   │   │   │   │   │   │   └── upcoming.html
│   │   │   │   │   ├── new-design/
│   │   │   │   │   │   │   │   │   ├── split-version/
│   │   │   │   │   │   │   │   │   │   │   │   │   │   ├── css/
│   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   └── styles.css
│   │   │   │   │   │   │   │   │   │   │   │   │   │   ├── includes/
│   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   ├── footer.html
│   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   └── header.html
│   │   │   │   │   │   │   │   │   │   │   │   │   │   └── index.html
│   │   │   │   │   │   │   │   │   └── index.html
│   │   │   │   │   ├── index.html
│   │   │   │   │   └── summary.html
│   │   ├── g_fastapi_upstox.py
│   │   ├── main.py
│   │   └── state.py
├── services/
│   │   ├── __init__.py
│   │   ├── actionable_row.py
│   │   ├── bible_engine.py
│   │   ├── cockpit_row.py
│   │   ├── enrich_instruments.py
│   │   ├── enrich_tactical.py
│   │   ├── forecast.py
│   │   ├── history.py
│   │   ├── ladder_state.py
│   │   ├── live.py
│   │   ├── morning.py
│   │   ├── scoring.py
│   │   ├── symbol_scan.py
│   │   └── tactical_pipeline.py
├── settings/
│   │   ├── __init__.py
│   │   ├── cockpit_schema.py
│   │   ├── fno_universe.py
│   │   ├── formulas.py
│   │   ├── fundamentals_map.py
│   │   ├── indicator_policy.py
│   │   ├── indicators.py
│   │   ├── meta_controller_cfg.py
│   │   ├── meta_drift.py
│   │   ├── meta_layers.py
│   │   ├── meta_memory.py
│   │   ├── metrics.py
│   │   ├── patterns.py
│   │   ├── profiles.py
│   │   ├── README_settings.md
│   │   ├── regimes.py
│   │   ├── settings.py
│   │   ├── sim_settings.py
│   │   ├── tactical.py
│   │   ├── timeframes.py
│   │   ├── universe.py
│   │   └── weights.py
├── strategies/
│   │   ├── _late_exit.py
│   │   ├── decision_engine.py
│   │   ├── fusion.py
│   │   ├── meta_strategy_cycle.py
│   │   ├── playbook.py
│   │   └── tv_fusion.py
├── technicals/
│   │   ├── indicators/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── advanced.py
│   │   │   │   │   ├── adx_dmi.py
│   │   │   │   │   ├── all.py
│   │   │   │   │   ├── breadth_cumulative.py
│   │   │   │   │   ├── breadth_momentum.py
│   │   │   │   │   ├── core.py
│   │   │   │   │   ├── keltner.py
│   │   │   │   │   ├── momentum_macd.py
│   │   │   │   │   ├── state.py
│   │   │   │   │   ├── volatility_fusion.py
│   │   │   │   │   ├── volume_chaikin.py
│   │   │   │   │   └── volume_mfi.py
│   │   ├── microstructure/
│   │   │   │   │   ├── cpr.py
│   │   │   │   │   ├── phases.py
│   │   │   │   │   ├── risk.py
│   │   │   │   │   ├── state_objects.py
│   │   │   │   │   ├── structure.py
│   │   │   │   │   ├── volume.py
│   │   │   │   │   └── vwap.py
│   │   ├── patterns/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── composite.py
│   │   │   │   │   ├── core.py
│   │   │   │   │   └── runner.py
│   │   ├── signals/
│   │   │   │   │   ├── fusion/
│   │   │   │   │   │   │   │   │   ├── __init__.py
│   │   │   │   │   │   │   │   │   ├── cmv.py
│   │   │   │   │   │   │   │   │   ├── liquidity_breadth.py
│   │   │   │   │   │   │   │   │   └── market_regime.py
│   │   │   │   │   ├── tactical/
│   │   │   │   │   │   │   │   │   ├── __init__.py
│   │   │   │   │   │   │   │   │   ├── absorption.py
│   │   │   │   │   │   │   │   │   ├── ai_inference.py
│   │   │   │   │   │   │   │   │   ├── ai_optimizer.py
│   │   │   │   │   │   │   │   │   ├── ai_recommender.py
│   │   │   │   │   │   │   │   │   ├── ai_trainer.py
│   │   │   │   │   │   │   │   │   ├── bias_regime.py
│   │   │   │   │   │   │   │   │   ├── cognitive_orchestrator.py
│   │   │   │   │   │   │   │   │   ├── core.py
│   │   │   │   │   │   │   │   │   ├── divergence.py
│   │   │   │   │   │   │   │   │   ├── event_log.py
│   │   │   │   │   │   │   │   │   ├── exhaustion.py
│   │   │   │   │   │   │   │   │   ├── helpers.py
│   │   │   │   │   │   │   │   │   ├── live_daemon.py
│   │   │   │   │   │   │   │   │   ├── live_supervisor.py
│   │   │   │   │   │   │   │   │   ├── meta_controller.py
│   │   │   │   │   │   │   │   │   ├── meta_introspector.py
│   │   │   │   │   │   │   │   │   ├── reversal_stack.py
│   │   │   │   │   │   │   │   │   ├── squeeze_pulse.py
│   │   │   │   │   │   │   │   │   ├── tactical_liquidity_trap.py
│   │   │   │   │   │   │   │   │   └── tactical_meta_dashboard.py
│   │   │   │   │   ├── templates/
│   │   │   │   │   │   │   │   │   ├── __init__.py
│   │   │   │   │   │   │   │   │   └── indicator_template.py
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── pattern_fusion.py
│   │   │   │   │   ├── pre_breakout.py
│   │   │   │   │   ├── registry.py
│   │   │   │   │   ├── reversal_summary.py
│   │   │   │   │   └── utils_patterns.py
│   │   ├── strategy/
│   │   │   │   │   └── __init__.py
│   │   ├── __init__.py
│   │   ├── fundamentals_gate.py
│   │   ├── fundamentals_score_engine.py
│   │   ├── fusion_trend_volume.py
│   │   ├── master_index.py
│   │   ├── options_sentiment.py
│   │   ├── registry.py
│   │   ├── sector_strength.py
│   │   ├── trend_strength.py
│   │   ├── trend_strength_daily.py
│   │   ├── trend_strength_intraday.py
│   │   ├── volume_strength.py
│   │   └── volume_strength_intraday.py
├── tests/
│   │   ├── __init__.py
│   │   ├── fundamentals_devcheck.py
│   │   ├── market_playback.py
│   │   ├── market_test.py
│   │   ├── smoke_absorption.py
│   │   ├── smoke_advanced.py
│   │   ├── smoke_ai_inference.py
│   │   ├── smoke_ai_optimizer_paths.py
│   │   ├── smoke_ai_trainer_paths.py
│   │   ├── smoke_all.py
│   │   ├── smoke_bias_regime.py
│   │   ├── smoke_bias_regime_latency.py
│   │   ├── smoke_breadth.py
│   │   ├── smoke_breadth_combo.py
│   │   ├── smoke_breadth_momentum.py
│   │   ├── smoke_chaikin.py
│   │   ├── smoke_cmv_latency.py
│   │   ├── smoke_cognitive_orchestrator.py
│   │   ├── smoke_divergence.py
│   │   ├── smoke_divergence_latency.py
│   │   ├── smoke_event_log.py
│   │   ├── smoke_exhaustion_latency.py
│   │   ├── smoke_fetch_utils.py
│   │   ├── smoke_fundamentals.py
│   │   ├── smoke_fusion_all_latency.py
│   │   ├── smoke_fusion_latency.py
│   │   ├── smoke_fusion_lbx.py
│   │   ├── smoke_fusion_market_regime.py
│   │   ├── smoke_fusion_overall.py
│   │   ├── smoke_helpers.py
│   │   ├── smoke_indicators.py
│   │   ├── smoke_instruments.py
│   │   ├── smoke_intervals.py
│   │   ├── smoke_io.py
│   │   ├── smoke_keltner.py
│   │   ├── smoke_lbx_latency.py
│   │   ├── smoke_liquidity_trap_latency.py
│   │   ├── smoke_liquidity_trap_vector.py
│   │   ├── smoke_live_daemon.py
│   │   ├── smoke_live_supervisor.py
│   │   ├── smoke_macd.py
│   │   ├── smoke_market_regime_latency.py
│   │   ├── smoke_market_sleep.py
│   │   ├── smoke_market_time.py
│   │   ├── smoke_master_index.py
│   │   ├── smoke_meta_controller.py
│   │   ├── smoke_meta_dashboard.py
│   │   ├── smoke_meta_settings_only.py
│   │   ├── smoke_meta_strategy_cycle.py
│   │   ├── smoke_meta_timestamps.py
│   │   ├── smoke_mfi.py
│   │   ├── smoke_ohlcv.py
│   │   ├── smoke_orchestrator_contract.py
│   │   ├── smoke_overall_latency.py
│   │   ├── smoke_paths_models.py
│   │   ├── smoke_patterns_all.py
│   │   ├── smoke_patterns_composite.py
│   │   ├── smoke_patterns_core.py
│   │   ├── smoke_patterns_latency.py
│   │   ├── smoke_patterns_runner.py
│   │   ├── smoke_pre_breakout.py
│   │   ├── smoke_rate_limited_decorator.py
│   │   ├── smoke_rate_limiter.py
│   │   ├── smoke_rate_limiter_context.py
│   │   ├── smoke_rate_limiter_global.py
│   │   ├── smoke_rate_limiter_pool.py
│   │   ├── smoke_registry.py
│   │   ├── smoke_reversal_stack.py
│   │   ├── smoke_reversal_summary.py
│   │   ├── smoke_rsi.py
│   │   ├── smoke_schema_adapter.py
│   │   ├── smoke_show_snapshot.py
│   │   ├── smoke_signals_registry.py
│   │   ├── smoke_squeeze_pulse.py
│   │   ├── smoke_strategy_fusion.py
│   │   ├── smoke_tactical_core.py
│   │   ├── smoke_tactical_index_modes.py
│   │   ├── smoke_tactical_inputs.py
│   │   ├── smoke_technicals_registry.py
│   │   ├── smoke_template_indicator.py
│   │   ├── smoke_utils_patterns.py
│   │   ├── smoke_volatility_fusion.py
│   │   ├── smoke_weights.py
│   │   ├── test_indicator_kwargs.py
│   │   └── test_patterns_core.py
├── .gitignore
├── __init__.py
├── intraday_cockpit.py
├── intraday_cockpit_expanded.py
├── intraday_cockpit_final.py
├── pytest.ini
├── README.md
└── test_scanner.py
```