# 📚 Queen Quant Platform — AI-Ready Project Documentation

**Project**: `queen/` (Quantitative Trading Platform)
**Version**: v9.6+
**Architecture**: Modular, Registry-Driven, Settings-First
**Last Updated**: 2025-12-04

---

## 📖 Table of Contents

1. [Project Overview](#project-overview)
2. [Core Systems](#core-systems)
   - [Alerts & Rules Engine](#alerts--rules-engine)
   - [CLI Tools](#cli-tools)
   - [Daemon Services](#daemon-services)
   - [Market Data Fetchers](#market-data-fetchers)
3. [Helpers & Utilities](#helpers--utilities)
4. [Server Components](#server-components)
5. [Settings & Configuration](#settings--configuration)
6. [Technical Analysis Layer](#technical-analysis-layer)
   - [Indicators Registry](#indicators-registry)
   - [Pattern Detection](#pattern-detection)
   - [Signal Fusion](#signal-fusion)
7. [Testing & Validation](#testing--validation)
8. [Architecture Summary](#architecture-summary)
9. [Usage Patterns](#usage-patterns)
10. [File Count Summary](#file-count-summary)

---

## Project Overview

**Queen** is a production-grade quantitative trading platform designed for NSE/BSE intraday and swing trading. It follows a **settings-driven architecture** where all components (indicators, signals, patterns, regimes) are registered and configured via centralized settings modules.

### Key Design Principles
- **Registry Pattern**: Auto-scanning of indicators, signals, and patterns
- **Settings-First**: Single source of truth via `{root_module}.settings.*`
- **Timeframe-Aware**: All components respect context (intraday_15m, hourly_1h, daily)
- **Plugin Architecture**: Easy extension via exports or registry decorators
- **Polars-Native**: High-performance DataFrame operations throughout

---

## Core Systems

Essential platform infrastructure

### Alerts & Rules Engine

#### `queen/alerts/evaluator.py`

**Functions:**
- `def _last_two(series: pl.Series)`
- `def _cmp(op: str, a: float, b: float)`
- `def _cross(op: str, s: pl.Series, level: float)`
- `def eval_price(df: pl.DataFrame, rule: Rule)`
- `def eval_indicator(df: pl.DataFrame, rule: Rule)`
- `def eval_rule(rule: Rule, df: pl.DataFrame)`

#### `queen/alerts/rules.py`

**Classes:**
- `class Rule`
  - `def from_dict(d: Dict[str, Any])`
  - `def to_dict(self)`

**Functions:**
- `def from_dict(d: Dict[str, Any])`
- `def to_dict(self)`
- `def load_rules(path: Optional[Union[str, Path]]=None)`

#### `queen/alerts/state.py`

**Functions:**
- `def _key(sym: str, rule: str)`
- `def load_cooldowns()`
- `def save_cooldown(sym: str, rule: str, last_fire_ts: float)`

### CLI Tools

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `__init__.py` |  |  |
| `debug_decisions.py` | `main` |  |
| `debug_fetch_unified.py` | `_summarize`, `main` |  |
| `fundamentals_cli.py` | `info`, `warning`, `error` |  |
| `g_upstox_client.py` | `__init__`, `get_auth_url`, `generate_access_token` |  |
| `list_master.py` | `_print`, `_save`, `main` |  |
| `list_signals.py` | `main` |  |
| `list_technicals.py` | `parse_args`, `main` |  |
| `live_monitor.py` | `main` |  |
| `live_monitor_cli.py` | `main` |  |
| `monitor_stream.py` | `_fmt`, `_render`, `_graceful` |  |
| `morning_intel.py` | `main` |  |
| `replay_actionable.py` | `_json_safe_row`, `_apply_auto_position_sim`, `main` |  |
| `run_strategy.py` | `_dummy_ohlcv`, `_wire_minimals`, `main` |  |
| `scan_signals.py` | `_drop_empty_struct_columns`, `_default_out_path`, `_build_rows` |  |
| `show_snapshot.py` | `_load_snapshot`, `main` |  |
| `signal_summary.py` | `_load_df`, `_print_decision_summary`, `_print_playbook_summary` |  |
| `sim_stats.py` | `_to_float`, `_load_scan_df`, `_compute_symbol_stats` |  |
| `symbol_scan.py` | `_print_table`, `main` |  |
| `universe_scanner.py` | `load_and_prefilter_symbols`, `calculate_volatility`, `calculate_liquidity_score` | Production-grade NSE/BSE universe scanner with fundamental a... |
| `validate_registry.py` | `_make_df`, `main` |  |

### Daemon Services

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `__init__.py` | `_list_daemons`, `_run_child`, `run_cli` | Queen Daemon Manager (forward-compatible)  Usage:   python -... |
| `__main__.py` |  | Entry point for Queen Daemon Manager (`python -m queen.daemo... |
| `alert_daemon.py` | `check`, `_parse_args`, `__init__` |  |
| `alert_v2.py` | `_backfill_days`, `_min_bars_for`, `_days_for_interval` |  |
| `live_engine.py` | `_fmt`, `_compact_table`, `_expanded_table` |  |
| `live_engine_cli.py` | `_cpr_from_last_completed_session`, `_fmt`, `_compact_table` |  |
| `morning_intel.py` | `_buy_sell_hold`, `_fmt_last`, `_ema_bias` |  |
| `scheduler.py` | `run_cli` |  |

### Market Data Fetchers

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `__init__.py` |  |  |
| `fetch_router.py` | `_chunk_list`, `_generate_output_path`, `run_cli` |  |
| `fundamentals_scraper.py` | `_log`, `info`, `success` | ============================================================... |
| `g_nse_fecther_cache.py` | `_clean_price`, `_quote_url`, `_referer_url` | Consolidated NSE fetcher combining: 1. Time-based disk cachi... |
| `nse_fetcher.py` | `_clean_price`, `_quote_url`, `_referer_url` |  |
| `nse_fetcher_new.py` | `_quote_url`, `_referer_url`, `_read_cache` |  |
| `options_chain.py` | `_auth_token`, `_build_headers`, `_handle_error` |  |
| `screener_scraper.py` | `_log`, `info`, `success` | ============================================================... |
| `build_monthly_universe.py` | `normalize_series`, `compute_factors`, `build_score` | Quant-Core v1.2 — Monthly Active Universe Builder (Async + D... |
| `convert_instruments_to_master.py` | `normalize_date`, `parse_nse_equity_file`, `print_summary` | Convert NSE raw equity CSV → master_active_list.json (Config... |
| `upstox_fetcher.py` | `_min_rows_from_settings`, `_headers`, `_merge_unique_sort` |  |
| `instruments.py` | `_instrument_path_for`, `_all_instrument_paths`, `_read_instruments` |  |

#### `queen/services/__init__.py`

#### `queen/services/actionable_row.py`

**Functions:**
- `def _to_float(val: Any)`
- `def _init_sim_state(sim_state: Optional[Dict[str, Any]])`
- `def _compute_unit_size(row: Dict[str, Any], *, notional_per_unit: float=NOTIONAL_PER_UNIT_DEFAULT, min_units: float=1.0, max_units: float=50.0)`
- `def _resolve_risk_profile(row: Dict[str, Any])`
- `def _step_auto_long_sim(row: Dict[str, Any], sim_state: Optional[Dict[str, Any]], *, eod_force: bool=False)`
- `def build_actionable_row(symbol: str, df: pl.DataFrame, *, interval: str, book: str, pos_mode: str='flat', auto_side: str='long', positions_map: Dict[str, Any] | None=None, cmp_anchor: float | None=None, pos: Optional[Dict[str, Any]]=None, sim_state: Dict[str, Any] | None=None, eod_force: bool=False)`

#### `queen/services/bible_engine.py`

**Classes:**
- `class SwingPoints`

**Functions:**
- `def _swing_points(df: pl.DataFrame, window: int=3, max_points: int=5)`
- `def _slope_sign(values: List[float])`
- `def _classify_structure(swings: SwingPoints, close: float, cpr: Optional[float], vwap: Optional[float])`
- `def compute_structure_block(df: pl.DataFrame, indicators: Optional[Dict[str, Any]]=None, *, lookback: int=60)`
- `def _safe_pct_diff(a: Optional[float], b: Optional[float])`
- `def _bias_from_above_below(price: Optional[float], ref: Optional[float], up_thresh: float=0.3, dn_thresh: float=-0.3)`
- `def _strength_from_distance(price: Optional[float], ref: Optional[float], tight: float=0.5, medium: float=1.5, strong: float=3.0)`
- `def compute_trend_block(indicators: Dict[str, Any])`
- `def compute_vol_block(df: pl.DataFrame, indicators: Optional[Dict[str, Any]]=None)`
- `def compute_risk_block(structure: Dict[str, Any], trend: Dict[str, Any], vol: Dict[str, Any], indicators: Optional[Dict[str, Any]]=None, pos: Optional[Dict[str, Any]]=None)`
- `def compute_alignment_block(indicators: Dict[str, Any])`
- `def trade_validity_block(metrics: Dict[str, Any])`
- `def compute_indicators_plus_bible(df: pl.DataFrame, base_indicators: Optional[Dict[str, Any]]=None, *, symbol: Optional[str]=None, interval: str='15m', pos: Optional[Dict[str, Any]]=None)`

#### `queen/services/cockpit_row.py`

**Functions:**
- `def build_cockpit_row(symbol: str, df: pl.DataFrame, *, interval: str='15m', book: str='all', tactical: Optional[Dict[str, Any]]=None, pattern: Optional[Dict[str, Any]]=None, reversal: Optional[Dict[str, Any]]=None, volatility: Optional[Dict[str, Any]]=None, pos: Optional[Dict[str, Any]]=None)`
- `def _format_risk_summary(row: Dict[str, Any])`

#### `queen/services/enrich_instruments.py`

**Functions:**
- `def _safe_float(v: Any)`
- `def _from_df(df: pl.DataFrame)`
- `def _from_nse(symbol: str)`
- `def enrich_instrument_snapshot(symbol: str, base: Dict[str, Any], *, df: Optional[pl.DataFrame]=None)`

#### `queen/services/enrich_tactical.py`

**Functions:**
- `def _merge(dst: Dict[str, Any], src: Optional[Dict[str, Any]])`
- `def enrich_indicators(base: Dict[str, Any], *, tactical: Optional[Dict[str, Any]]=None, pattern: Optional[Dict[str, Any]]=None, reversal: Optional[Dict[str, Any]]=None, volatility: Optional[Dict[str, Any]]=None)`

#### `queen/services/forecast.py`

**Classes:**
- `class ForecastOptions`

**Functions:**
- `def _infer_next_session_date(now_ist: datetime)`
- `def _advice_for(symbol: str, cmp_price: float, score: float, row: Dict, book: str='all')`
- `def _row_to_plan(row: Dict)`

#### `queen/services/history.py`

**Functions:**
- `def load_history(max_items: int=500)`

#### `queen/services/ladder_state.py`

**Classes:**
- `class LadderState`
  - `def label(self, side: str='LONG')`

**Functions:**
- `def _tf_priority(tf: str)`
- `def _today_trading_date()`
- `def label(self, side: str='LONG')`
- `def _reset_if_new_day(state: LadderState, trading_date: date)`
- `def _extract_targets_t1_t3(row: Dict[str, Any])`
- `def _extend_static_to_t6(t1: float, t2: float, t3: float, side: str)`
- `def _stage_from_price_ext(price: float, levels: List[float], side: str)`
- `def _format_targets_text(tg: Dict[str, Any] | None, *, hits: Dict[str, bool] | None=None, decimals: int=1, prefix: str='T')`
- `def _true_range(last_high: float, last_low: float, prev_close: float | None)`
- `def _is_directional_wrb(*, last_open: float, last_high: float, last_low: float, last_close: float, prev_close: float | None, atr: float, side: str, wrb_mult: float=1.5, body_ratio_min: float=0.55)`
- `def augment_targets_state(row: Dict[str, Any], interval: str)`

#### `queen/services/live.py`

**Functions:**
- `def _min_bars(interval_min: int)`
- `def structure_and_targets(last_close_val: float, cpr, vwap, rsi, atr, obv)`
- `def _to_light_actionable(row: Dict[str, Any])`
- `def project_light_actionable(row: Dict[str, Any])`

#### `queen/services/morning.py`

**Functions:**
- `def _archive_yesterday_signals(now_ist: datetime)`
- `def _trend_last_n(n: int=5)`
- `def _weekly_gauge(n: int=7)`
- `def run_morning_briefing()`
- `def build_briefing_payload(now_ist: datetime)`

#### `queen/services/scoring.py`

**Functions:**
- `def _last(series: pl.Series)`
- `def _ema_last(df: pl.DataFrame, period: int, column: str='close')`
- `def _daily_ohlc_from_intraday(df: pl.DataFrame)`
- `def _daily_risk_snapshot(df: pl.DataFrame, period: int=14)`
- `def compute_indicators(df: pl.DataFrame)`
- `def _normalize_signal(payload: Dict | None, name: str)`
- `def _fallback_early(df: pl.DataFrame, cmp_: float, vwap_: Optional[float])`
- `def _early_bundle(df: pl.DataFrame, cmp_: float, vwap_: Optional[float])`
- `def _ladder_from_base(base: float, atr: Optional[float])`
- `def _non_position_entry(cmp_: float, vwap: Optional[float], ema20: Optional[float], cpr: Optional[float], atr: Optional[float])`
- `def compute_indicators_plus_bible(df: pl.DataFrame, interval: str='15m', *, symbol: Optional[str]=None, pos: Optional[Dict[str, Any]]=None)`
- `def _apply_sector_veto_if_needed(*, symbol: str, interval: str, mode: str, decision: str, bias: str, sector_ctx: Dict[str, Any], risk_rating: Optional[str]=None, regime_name: Optional[str]=None)`
- `def score_symbol(indd: Dict[str, Any])`
- `def action_for(symbol: str, indd: Dict[str, Any], book: str='all', use_uc_lc: bool=True)`

#### `queen/services/symbol_scan.py`

**Functions:**
- `def _min_bars_for(rule: Rule)`
- `def _window(interval: str, need_bars: int)`

#### `queen/services/tactical_pipeline.py`

**Functions:**
- `def pattern_block(df: pl.DataFrame, indicators: Dict[str, Any] | None=None)`
- `def trend_block(df: pl.DataFrame, indicators: Dict[str, Any] | None=None)`
- `def alignment_block(df: pl.DataFrame, indicators: Dict[str, Any] | None=None)`
- `def reversal_block(df: pl.DataFrame, indicators: Dict[str, Any] | None=None)`
- `def volatility_block(df: pl.DataFrame, indicators: Dict[str, Any] | None=None)`
- `def risk_block(df: pl.DataFrame, indicators: Dict[str, Any] | None, structure: Dict[str, Any] | None, trend: Dict[str, Any] | None, vol: Dict[str, Any] | None, pos: Dict[str, Any] | None=None)`
- `def tactical_block(metrics: Dict[str, Any], interval: str='15m')`
- `def compute_bible_blocks(df: pl.DataFrame, indicators: Dict[str, Any], interval: str='15m')`

#### `queen/strategies/_late_exit.py`

**Functions:**
- `def _apply_late_session_soft_exit(row: Dict[str, Any])`

#### `queen/strategies/decision_engine.py`

**Classes:**
- `class PhaseView`
- `class RiskView`

**Functions:**
- `def _parse_timestamp(ts: Any)`
- `def _time_bucket_from_ts(ts: Any)`
- `def _view_phase(phase: Any)`
- `def _view_risk(risk: Any)`
- `def _normalize_decision(row: Dict[str, Any])`
- `def _pnl_pct_from_row(row: Dict[str, Any])`
- `def _choose_action_tag(row: Dict[str, Any], *, phase_view: PhaseView, risk_view: RiskView)`
- `def _phase_override_action(row: Dict[str, Any], phase_view: PhaseView, risk_view: RiskView, base_action_tag: str, base_action_reason: str)`
- `def maybe_tag_scalp_candidate(row: Dict[str, Any], *, phase_view: PhaseView, risk_view: RiskView, base_action_tag: str, base_action_reason: str)`
- `def apply_decision_overlays(row: Dict[str, Any], *, phase: Any=None, risk: Any=None, interval: Optional[str]=None)`

#### `queen/strategies/fusion.py`

**Functions:**
- `def _f_to_float(val)`
- `def _last_str(df: pl.DataFrame, col: str, default: str='')`
- `def _regime_to_unit(reg: str)`
- `def _risk_band(atr_ratio: float)`
- `def run_strategy(symbol: str, frames: Dict[str, pl.DataFrame], *, tf_weights=None)`
- `def _apply_late_session_soft_exit(row: Dict[str, Any])`
- `def apply_strategies(row: Dict[str, Any], *, interval: str | None=None, phase: str | None=None, risk: str | None=None)`

#### `queen/strategies/meta_strategy_cycle.py`

**Functions:**
- `def _append_jsonl(path: Path, record: dict)`
- `def _cap_jsonl(path: Path, max_lines: int=5000)`
- `def _dummy_ohlcv(n: int=180)`
- `def _ensure_snapshot_schema(df: pl.DataFrame)`
- `def _frames_for(symbol: str, tfs: Iterable[str])`
- `def _last_str(df: pl.DataFrame, col: str, default: str='')`
- `def _utc_now()`
- `def _emit_records(symbol: str, per_tf: Dict[str, Dict[str, Any]], frames: Dict[str, pl.DataFrame])`
- `def _write_latest_pointer(parquet_path: Path, jsonl_path: Path)`
- `def _append_fused_rows(df: pl.DataFrame)`
- `def run_meta_cycle(symbols: Iterable[str], tfs: Iterable[str]=('intraday_15m', 'hourly_1h', 'daily'), *, snapshot_parquet: Path | None=None, snapshot_jsonl: Path | None=None)`
- `def _discover_symbols(limit: int)`
- `def main()`

#### `queen/strategies/playbook.py`

**Classes:**
- `class PlaybookContext`

**Functions:**
- `def _parse_timestamp(ts: Any)`
- `def _time_bucket_from_ts(ts: Any)`
- `def _normalize_interval(interval: Optional[str])`
- `def _timeframe_from_interval(interval: str)`
- `def _get_drivers(row: Dict[str, Any])`
- `def _has_driver(drivers: List[str], prefix: str)`
- `def _has_text(haystack: str, needle: str)`
- `def _classify_intraday_playbook(row: Dict[str, Any], *, interval: str)`
- `def _classify_btst_swing_playbook(row: Dict[str, Any], *, horizon: Optional[str]=None)`
- `def assign_playbook(row: Dict[str, Any], *, phase: Any=None, risk: Any=None, interval: Optional[str]=None, horizon: Optional[str]=None)`

#### `queen/strategies/tv_fusion.py`

**Functions:**
- `def _safe_str(val: Any, default: str='')`
- `def _is_intraday_interval(interval: str | int | None)`
- `def _trend_inputs(row: Dict[str, Any])`
- `def _momentum_inputs(row: Dict[str, Any])`
- `def _risk_ok(row: Dict[str, Any])`
- `def _trend_allows_scalp(row: Dict[str, Any])`
- `def _intraday_momentum_ok(inputs: Dict[str, Any])`
- `def apply_tv_fusion(row: Dict[str, Any], *, interval: str | int | None)`

---

## Helpers & Utilities

Shared utilities and infrastructure

#### `queen/helpers/__init__.py`

> Lightweight helpers package init (lazy submodule access).

Usage:
    from queen.helpers import io
    io.append_jsonl(...)

    # When (and only when) you actually need them:
    from queen.helpers import market, instruments, logger, pl_compat

**Functions:**
- `def __getattr__(name: str)`
- `def __dir__()`

#### `queen/helpers/candle_adapter.py`

**Classes:**
- `class CandleAdapter`
  - `def to_polars(candles: Iterable[Iterable[Any]], symbol: str, isin: str)`
  - `def empty_df()`
  - `def summary(df: pl.DataFrame, name: str='candles')`

**Functions:**
- `def to_polars(candles: Iterable[Iterable[Any]], symbol: str, isin: str)`
- `def empty_df()`
- `def summary(df: pl.DataFrame, name: str='candles')`

#### `queen/helpers/candles.py`

**Functions:**
- `def ensure_sorted(df: pl.DataFrame, ts_col: str='timestamp')`
- `def last_close(df: pl.DataFrame)`

#### `queen/helpers/common.py`

**Functions:**
- `def utc_now_iso()`
- `def next_candle_ms(now_ist: datetime, interval_min: int)`
- `def normalize_symbol(s: str | None)`
- `def logger_supports_color(logger: logging.Logger)`
- `def colorize(text: str, color_key: str, palette: Dict[str, str], enabled: bool)`
- `def timeframe_key(tf: str)`
- `def indicator_kwargs(params: Dict[str, Any] | None, *, deny: set[str] | None=None)`

#### `queen/helpers/diagnostic_override_logger.py`

**Functions:**
- `def _safe_str(v: Any)`
- `def log_trend_volume_override(*, symbol: Optional[str], interval: str, mode: Optional[str], original_decision: str, original_bias: str, new_decision: str, new_bias: str, trend_ctx: Optional[Dict[str, Any]]=None, vol_ctx: Optional[Dict[str, Any]]=None, reason: str='', extra: Optional[Dict[str, Any]]=None)`
- `def log_sector_veto(*, symbol: str, sector: str, interval: str, mode: str, original_decision: str, original_bias: str, new_decision: str, new_bias: str, sector_score: Optional[float], sector_bias: Optional[str], sector_trend: Optional[str], reason: str='', extra: Optional[Dict[str, Any]]=None)`
- `def log_options_veto(*, symbol: str, interval: str, mode: str, original_decision: str, original_bias: str, new_decision: str, new_bias: str, opt_bias: Optional[str], pcr: Optional[float]=None, reason: str='', extra: Optional[Dict[str, Any]]=None)`

#### `queen/helpers/fetch_utils.py`

**Functions:**
- `def ensure_datetime(value: datetime | None, *, tz: ZoneInfo | None=None)`
- `def warn_if_same_day_eod(from_date: str | date | None, to_date: str | date | None)`

#### `queen/helpers/fno_universe.py`

**Functions:**
- `def is_fno(symbol: str)`
- `def get_expiries(symbol: str)`
- `def get_lot_size(symbol: str)`
- `def get_symbol_type(symbol: str)`
- `def select_expiry(symbol: str, mode: str='intraday')`
- `def get_atm_strike(symbol: str, ltp: float)`

#### `queen/helpers/fundamentals_adapter.py`

**Functions:**
- `def _deep_get(d: Dict[str, Any], path: List[str])`
- `def _deep_get_dot(d: Dict[str, Any], dot_path: str)`
- `def _parse_numeric(v: Any)`
- `def _latest_non_null(series: Any)`
- `def _extract_latest_period(series: Dict[str, Any])`
- `def _promote_latest_series(out: Dict[str, Any], tbl: Dict[str, Any], prefix: str='')`
- `def _safe_get_list(data: Dict[str, Any], key: str)`
- `def to_row(m: Dict[str, Any])`

#### `queen/helpers/fundamentals_polars_engine.py`

**Classes:**
- `class _FallbackLog`
  - `def info(self, msg)`
  - `def warning(self, msg)`
  - `def error(self, msg)`
  - `def debug(self, msg)`

**Functions:**
- `def info(self, msg)`
- `def warning(self, msg)`
- `def error(self, msg)`
- `def debug(self, msg)`
- `def _read_json(p: Path)`
- `def _validate_or_fallback(raw: Dict[str, Any], source: str)`
- `def _is_numeric_like_str(s: str)`
- `def _infer_dtype_for_col(values: List[Any], col: str)`
- `def _build_safe_schema(rows: List[Dict[str, Any]])`
- `def _ensure_symbol_sector(df: pl.DataFrame)`
- `def _numeric_candidates(df: pl.DataFrame)`
- `def _cast_numeric_candidates(df: pl.DataFrame)`
- `def load_one_processed(processed_dir: Union[str, Path], symbol: str)`
- `def to_polars_row(symbol_fund_json: Dict[str, Any])`
- `def build_df_from_rows(rows: Iterable[Dict[str, Any]])`
- `def build_df_from_all_processed(processed_dir: Union[str, Path])`
- `def load_all(processed_dir: Union[str, Path])`
- `def get_column_summary(df: pl.DataFrame)`
- `def print_df_summary(df: pl.DataFrame)`

#### `queen/helpers/fundamentals_registry.py`

**Classes:**
- `class _FallbackLog`
  - `def info(self, msg)`
  - `def warning(self, msg)`
  - `def error(self, msg)`
  - `def debug(self, msg)`
- `class FundamentalsRegistry`
  - `def __init__(self)`
  - `def build(self, df: pl.DataFrame, metric_columns: Optional[Sequence[str]]=None)`
  - `def _reset(self, reason: str)`
  - `def sector_stats(self, sector: str)`
  - `def sector_mean(self, sector: str, metric: str)`
  - `def sector_std(self, sector: str, metric: str)`
  - `def global_mean(self, metric: str)`
  - `def global_std(self, metric: str)`
  - `def global_min(self, metric: str)`
  - `def global_max(self, metric: str)`
  - `def get_sectors(self)`
  - `def get_metrics(self)`
  - `def compute_z_scores(self, df: pl.DataFrame, metrics: Optional[List[str]]=None)`
  - `def compute_percentile_ranks(self, df: pl.DataFrame, metrics: Optional[List[str]]=None, descending: Optional[Dict[str, bool]]=None)`
  - `def compute_sector_ranks(self, df: pl.DataFrame, metrics: Optional[List[str]]=None)`
  - `def compute_powerscore(self, df: pl.DataFrame, weights: Optional[Dict[str, float]]=None, dimension_metrics: Optional[Dict[str, List[str]]]=None)`
  - `def apply_tactical_filters(self, df: pl.DataFrame, filters: Optional[List[Dict[str, Any]]]=None)`
  - `def summary(self)`
  - `def print_summary(self)`

**Functions:**
- `def info(self, msg)`
- `def warning(self, msg)`
- `def error(self, msg)`
- `def debug(self, msg)`
- `def _pick_col(df: pl.DataFrame, candidates: Sequence[str])`
- `def _safe_float(v: Any)`
- `def _get_numeric_cols(df: pl.DataFrame, candidates: Sequence[str])`
- `def __init__(self)`
- `def build(self, df: pl.DataFrame, metric_columns: Optional[Sequence[str]]=None)`
- `def _reset(self, reason: str)`
- `def sector_stats(self, sector: str)`
- `def sector_mean(self, sector: str, metric: str)`
- `def sector_std(self, sector: str, metric: str)`
- `def global_mean(self, metric: str)`
- `def global_std(self, metric: str)`
- `def global_min(self, metric: str)`
- `def global_max(self, metric: str)`
- `def get_sectors(self)`
- `def get_metrics(self)`
- `def compute_z_scores(self, df: pl.DataFrame, metrics: Optional[List[str]]=None)`
- `def compute_percentile_ranks(self, df: pl.DataFrame, metrics: Optional[List[str]]=None, descending: Optional[Dict[str, bool]]=None)`
- `def compute_sector_ranks(self, df: pl.DataFrame, metrics: Optional[List[str]]=None)`
- `def compute_powerscore(self, df: pl.DataFrame, weights: Optional[Dict[str, float]]=None, dimension_metrics: Optional[Dict[str, List[str]]]=None)`
- `def apply_tactical_filters(self, df: pl.DataFrame, filters: Optional[List[Dict[str, Any]]]=None)`
- `def summary(self)`
- `def print_summary(self)`
- `def build_registry(df: pl.DataFrame, metric_columns: Optional[List[str]]=None)`
- `def get_registry()`

#### `queen/helpers/fundamentals_schema.py`

**Classes:**
- `class ShareholdingData(BaseModel)`
  - `def _norm_table_series(cls, v: Any)`
  - `def _norm_flat_dict(cls, v: Any)`
- `class PeerData(BaseModel)`
- `class FundamentalsModel(BaseModel)`
  - `def _coerce_numeric(cls, v: Any)`
  - `def _norm_flat_metrics(cls, v: Any)`
  - `def _norm_table_series(cls, v: Any)`
  - `def _norm_shareholding(cls, v: Any)`
  - `def _norm_peers(cls, v: Any)`
  - `def _norm_string_list(cls, v: Any)`
  - `def _fill_from_nested(self)`

**Functions:**
- `def _clean_string(x: Any)`
- `def _coerce_float(x: Any)`
- `def _coerce_dict_values(d: Dict[str, Any])`
- `def _coerce_table_series(d: Dict[str, Any])`
- `def _norm_table_series(cls, v: Any)`
- `def _norm_flat_dict(cls, v: Any)`
- `def _coerce_numeric(cls, v: Any)`
- `def _norm_flat_metrics(cls, v: Any)`
- `def _norm_table_series(cls, v: Any)`
- `def _norm_shareholding(cls, v: Any)`
- `def _norm_peers(cls, v: Any)`
- `def _norm_string_list(cls, v: Any)`
- `def _fill_from_nested(self)`
- `def validate_fundamentals(raw: Dict[str, Any])`
- `def validate_fundamentals_safe(raw: Dict[str, Any])`

#### `queen/helpers/fundamentals_timeseries_engine.py`

**Classes:**
- `class _FallbackLog`
  - `def info(self, msg)`
  - `def warning(self, msg)`
  - `def error(self, msg)`
  - `def debug(self, msg)`

**Functions:**
- `def info(self, msg)`
- `def warning(self, msg)`
- `def error(self, msg)`
- `def debug(self, msg)`
- `def _is_series_dict(x: Any)`
- `def _series_values(series_dict: Dict[str, Any])`
- `def _first_last_slope(vals: List[float])`
- `def _linear_regression_slope(vals: List[float])`
- `def _qoq_accel(vals: List[float])`
- `def _cv(vals: List[float])`
- `def _growth_rate(vals: List[float])`
- `def _pick_series_from_table(table: Any, candidates: Sequence[str])`
- `def _trend_label(slope: Optional[float], accel: Optional[float])`
- `def _momentum_score(slope: Optional[float], cv: Optional[float])`
- `def _slope_expr(table_col: str, candidates: Sequence[str], *, out_name: str, use_regression: bool=False)`
- `def _accel_expr(table_col: str, candidates: Sequence[str], *, out_name: str)`
- `def _cv_expr(table_col: str, candidates: Sequence[str], *, out_name: str)`
- `def _growth_expr(table_col: str, candidates: Sequence[str], *, out_name: str)`
- `def _label_expr(slope_col: str, accel_col: str, *, out_name: str)`
- `def _momentum_expr(slope_col: str, cv_col: str, *, out_name: str)`
- `def add_timeseries_features(df: pl.DataFrame)`
- `def add_composite_scores(df: pl.DataFrame)`
- `def analyze_timeseries(df: pl.DataFrame)`
- `def add_timeseries_and_score(df: pl.DataFrame, scorer_fn)`
- `def get_trend_columns()`

#### `queen/helpers/gemini_schema_adapter.py`

> Queen Schema Adapter — Unified Broker Schema Bridge (Refactored)
------------------------------------------------------
✅ Imports shared helpers from schema_helper.py (DRY)
✅ Focuses on candle-specific logic (e.g., interval parsing, candle normalization)

**Classes:**
- `class UpstoxAPIError(Exception)`
  - `def __init__(self, code: str, message: str | None=None)`

**Functions:**
- `def _load_schema()`
- `def _parse_range_token(tok: str)`
- `def _collect_intraday_supported()`
- `def _collect_historical_supported()`
- `def get_supported_intervals(unit: str | None=None, *, intraday: bool | None=None)`
- `def validate_interval(unit: str, interval: int, *, intraday: bool | None=None)`
- `def _normalize(candles: list[list[Any]])`
- `def to_candle_df(candles: list[list[Any]], symbol: str)`
- `def finalize_candle_df(df: pl.DataFrame, symbol: str, isin: str)`
- `def __init__(self, code: str, message: str | None=None)`
- `def handle_api_error(code: str)`
- `def run_cli()`

#### `queen/helpers/gemini_schema_helper.py`

> Common helpers for Polars DataFrame manipulation, timestamp parsing,
and schema drift detection, shared between different broker schema adapters.

**Functions:**
- `def _safe_select(df: pl.DataFrame, cols: list[str])`
- `def _safe_parse(df: pl.DataFrame, column: str='timestamp')`
- `def _checksum(cols: list[str])`
- `def _detect_drift(cols: list[str], drift_log_path: Path)`
- `def _log_drift(cols: list[str], drift_log_path: Path)`
- `def df_summary(df: pl.DataFrame, name='DataFrame')`
- `def print_summary(df: pl.DataFrame, console: Console, title='Schema Summary')`

#### `queen/helpers/gemini_schema_options_adapter.py`

> Queen Schema Options Adapter — Unified Options Schema Bridge (Refactored)
-------------------------------------------------------------
✅ Imports shared helpers from schema_helper.py (DRY)
✅ Focuses on options-specific logic (e.g., contract building, error mapping)

**Classes:**
- `class UpstoxOptionsAPIError(Exception)`
  - `def __init__(self, code: str, message: str | None=None)`

**Functions:**
- `def _load_schema()`
- `def to_contract_df(data: list[dict[str, Any]], key_col: str)`
- `def __init__(self, code: str, message: str | None=None)`
- `def handle_api_error(code: str)`
- `def run_cli()`

#### `queen/helpers/intervals.py`

> Queen Interval Helpers (DRY/forward-only)
--------------------------------------------
✅ Single source of truth: queen.settings.timeframes
✅ Human tokens like '5m','1h','1d','1w','1mo' normalized via TF
✅ Accepts canonical strings like 'minutes:5', 'hours:1' and coerces to tokens
✅ Exposes:
    - parse_minutes(token_or_num)
    - to_fetcher_interval(token_or_num)
    - classify_unit(token_or_num)
    - to_token(minutes_or_token)
    - is_intraday(token_or_num)

**Functions:**
- `def _coerce_token(v: Tokenish)`
- `def parse_minutes(value: Tokenish)`
- `def to_fetcher_interval(value: Tokenish)`
- `def classify_unit(value: Tokenish)`
- `def to_token(minutes: int)`
- `def is_intraday(token: Tokenish)`

#### `queen/helpers/io.py`

**Functions:**
- `def _p(path: str | Path)`
- `def ensure_dir(path: str | Path)`
- `def _atomic_write_bytes(path: Path, data: bytes)`
- `def write_json_atomic(path: Path | str, obj)`
- `def read_json(path: str | Path)`
- `def write_json(data: Any, path: str | Path, *, indent: int=2, atomic: bool=True)`
- `def safe_write_parquet(df: pl.DataFrame, path: str | Path)`
- `def read_csv(path: str | Path)`
- `def write_csv(df: pl.DataFrame, path: str | Path, *, atomic: bool=True)`
- `def read_parquet(path: str | Path)`
- `def write_parquet(df: pl.DataFrame, path: str | Path, *, atomic: bool=True)`
- `def append_jsonl(path: str | Path, record: dict)`
- `def read_jsonl(path: str | Path, limit: int | None=None)`
- `def tail_jsonl(path: str | Path, n: int=200)`
- `def read_any(path: str | Path)`
- `def read_text(path: str | Path, default: str='')`
- `def write_text(path: str | Path, content: str, *, atomic: bool=True)`

#### `queen/helpers/logger.py`

**Classes:**
- `class JSONLFormatter(logging.Formatter)`
  - `def format(self, record: logging.LogRecord)`

**Functions:**
- `def _resolve_log_cfg()`
- `def format(self, record: logging.LogRecord)`

#### `queen/helpers/market.py`

> Market Time & Calendar Utilities
--------------------------------
✅ Delegates ALL exchange data to queen.settings.settings (no hardcoded TF tokens)
✅ Provides working-day / holiday logic, market-open gates, and async sleep helpers
❌ Does NOT parse timeframe tokens (delegated to helpers.intervals / settings.timeframes)

**Classes:**
- `class _MarketGate`
  - `def __init__(self, mode: str='intraday')`

**Functions:**
- `def _hours()`
- `def _holidays_path()`
- `def _normalize_holiday_df(df: pl.DataFrame)`
- `def _read_holidays(path: Path | None)`
- `def _load_holidays()`
- `def _holidays()`
- `def reload_holidays()`
- `def ensure_tz_aware(ts: dt.datetime)`
- `def is_holiday(d: date | None=None)`
- `def is_working_day(d: date)`
- `def last_working_day(ref: date | None=None)`
- `def next_working_day(d: date)`
- `def offset_working_day(start: date, offset: int)`
- `def _t(hhmm: str)`
- `def current_session(now: dt.datetime | None=None)`
- `def is_market_open(now: dt.datetime | None=None)`
- `def _intraday_available(now: dt.datetime)`
- `def get_gate(now: dt.datetime | None=None)`
- `def current_historical_service_day(now: dt.datetime | None=None)`
- `def get_market_state()`
- `def is_trading_day(d: date)`
- `def last_trading_day(ref: date | None=None)`
- `def next_trading_day(d: date)`
- `def compute_sleep_delay(now: dt.datetime, interval_minutes: int, jitter_ratio: float=0.3, *, jitter_value: float | None=None)`
- `def __init__(self, mode: str='intraday')`
- `def market_gate(mode: str='intraday')`
- `def historical_available()`
- `def sessions()`

#### `queen/helpers/options_catalog.py`

**Functions:**
- `def get_strikes(symbol: str, expiry: int)`
- `def validate_expiry(symbol: str, expiry: int)`
- `def validate_strike(symbol: str, expiry: int, strike: float)`
- `def get_atm_ladder(strikes: List[float], ltp: float, width: int=2)`

#### `queen/helpers/options_schema.py`

**Classes:**
- `class OptionsSchema`
  - `def load(cls, broker: str='upstox')`
  - `def option_chain_def(self)`
  - `def option_contracts_def(self)`
  - `def explain_http_error(self, status_code: int)`

**Functions:**
- `def load(cls, broker: str='upstox')`
- `def option_chain_def(self)`
- `def option_contracts_def(self)`
- `def explain_http_error(self, status_code: int)`
- `def get_options_schema(broker: str='upstox')`

#### `queen/helpers/path_manager.py`

**Functions:**
- `def repo_root()`
- `def static_dir()`
- `def runtime_dir()`
- `def universe_dir()`
- `def log_dir()`
- `def positions_dir()`
- `def position_file(stem: str)`

#### `queen/helpers/pl_compat.py`

**Functions:**
- `def _s2np(s: pl.Series)`
- `def ensure_float_series(s: pl.Series)`
- `def safe_fill_null(s: pl.Series, value: float=0.0, *, forward: bool=True)`
- `def safe_concat(dfs: list[pl.DataFrame])`

#### `queen/helpers/portfolio.py`

**Functions:**
- `def _finite(x: float)`
- `def _sanitize_entry(sym: str, pos: dict)`
- `def _book_path_candidates(book: str)`
- `def list_books()`
- `def _load_one(path: Path)`
- `def _current_mtime_for_book_all()`
- `def _current_mtime_for_book(book: str)`
- `def load_positions(book: str)`
- `def position_for(symbol: str, book: str='all')`
- `def compute_pnl(cmp_price: float, pos: Optional[dict])`
- `def clear_positions_cache()`

#### `queen/helpers/rate_limiter.py`

**Classes:**
- `class AsyncTokenBucket`
  - `def __init__(self, rate_per_second: float | None=None, name: str='generic', diag: bool | None=None, *, jitter_min: float=0.002, jitter_max: float=0.01)`
  - `def _refill_unlocked(self, now: float)`
  - `def try_acquire(self, n: int=1)`
- `class RateLimiterPool`
  - `def __init__(self, default_qps: float | None=None, *, per_key: dict[str, float] | None=None, diag: bool | None=None)`
  - `def try_acquire(self, key: str, n: int=1)`
  - `def get(self, key: str)`
  - `def stats(self)`
  - `def keys(self)`

**Functions:**
- `def _get(d: dict, *keys, default=None)`
- `def __init__(self, rate_per_second: float | None=None, name: str='generic', diag: bool | None=None, *, jitter_min: float=0.002, jitter_max: float=0.01)`
- `def _refill_unlocked(self, now: float)`
- `def try_acquire(self, n: int=1)`
- `def __init__(self, default_qps: float | None=None, *, per_key: dict[str, float] | None=None, diag: bool | None=None)`
- `def try_acquire(self, key: str, n: int=1)`
- `def get(self, key: str)`
- `def stats(self)`
- `def keys(self)`
- `def get_pool()`
- `def rate_limited(key: str, n: int=1)`
- `def limiter(key: str, n: int=1)`

#### `queen/helpers/schema_adapter.py`

> Queen Schema Adapter — Unified Broker Schema Bridge
------------------------------------------------------
✅ Reads broker schema via settings (single source of truth)
✅ Exposes SCHEMA at module level for consumers (DRY)
✅ Adds get_supported_intervals()/validate helpers for UX/DX
✅ Uses settings-driven log + drift paths
✅ Polars-native builders for candle frames

**Classes:**
- `class UpstoxAPIError(Exception)`
  - `def __init__(self, code: str, message: str | None=None)`

**Functions:**
- `def _load_schema()`
- `def _parse_range_token(tok: str)`
- `def _collect_intraday_supported()`
- `def _collect_historical_supported()`
- `def get_supported_intervals(unit: str | None=None, *, intraday: bool | None=None)`
- `def validate_interval(unit: str, interval: int, *, intraday: bool | None=None)`
- `def _normalize(candles: list[list[Any]])`
- `def _safe_select(df: pl.DataFrame, cols: list[str])`
- `def _safe_parse(df: pl.DataFrame, column: str='timestamp')`
- `def to_candle_df(candles: list[list[Any]], symbol: str)`
- `def finalize_candle_df(df: pl.DataFrame, symbol: str, isin: str)`
- `def _checksum(cols: list[str])`
- `def _detect_drift(cols: list[str])`
- `def _log_drift(cols: list[str])`
- `def __init__(self, code: str, message: str | None=None)`
- `def handle_api_error(code: str)`
- `def df_summary(df: pl.DataFrame, name='DataFrame')`
- `def print_summary(df: pl.DataFrame, title='Schema Summary')`
- `def run_cli()`

#### `queen/helpers/shareholding_fetcher.py`

> NSE Shareholding Pattern Fetcher
Fetches promoter, FII, DII, public holdings from NSE's corporate disclosures API
Cache-enabled with 24h TTL

**Functions:**
- `def load_cache()`
- `def save_cache(cache: Dict[str, Dict[str, Any]])`
- `def test_cli()`

#### `queen/helpers/ta_math.py`

**Functions:**
- `def to_np(x: ArrayLike, *, dtype=float)`
- `def sma(series: ArrayLike, window: int, *, allow_short: bool=True)`
- `def ema(series: ArrayLike, span: int)`
- `def wilder_ema(series: ArrayLike, period: int)`
- `def true_range(high: ArrayLike, low: ArrayLike, prev_close: ArrayLike)`
- `def atr_wilder(high: ArrayLike, low: ArrayLike, close: ArrayLike, period: int=14)`
- `def normalize_0_1(x: ArrayLike, *, eps: float=1e-09)`
- `def normalize_symmetric(x: ArrayLike, *, eps: float=1e-09)`
- `def gradient_norm(x: ArrayLike, *, eps: float=1e-09)`

#### `queen/helpers/tactical_regime_adapter.py`

**Classes:**
- `class TacticalRegimeAdapter`
  - `def __init__(self, regime_name: Optional[str]=None)`
  - `def derive(self, metrics: dict)`
  - `def set_regime(self, regime_name: str)`
  - `def list_regimes(self)`
  - `def adjust_tactical_weights(self, base_weights: Dict[str, float])`
  - `def blend(self, base_weights: Dict[str, float], normalize: bool=True)`
  - `def to_polars_df(self)`
  - `def describe(self)`
  - `def validate(self)`
  - `def active_config(self)`

**Functions:**
- `def __init__(self, regime_name: Optional[str]=None)`
- `def derive(self, metrics: dict)`
- `def set_regime(self, regime_name: str)`
- `def list_regimes(self)`
- `def adjust_tactical_weights(self, base_weights: Dict[str, float])`
- `def blend(self, base_weights: Dict[str, float], normalize: bool=True)`
- `def to_polars_df(self)`
- `def describe(self)`
- `def validate(self)`
- `def active_config(self)`

#### `queen/helpers/verify.py`

**Functions:**
- `def require_columns(df: pl.DataFrame, required: Sequence[str], *, ctx: str='', strict: bool=False)`
- `def ensure_sorted(df: pl.DataFrame, by: str | Sequence[str], *, ctx: str='', ascending: bool=True)`
- `def ensure_time_ordered(df: pl.DataFrame, ts_col: str='timestamp', *, ctx: str='')`
- `def non_empty_symbols(symbols: Iterable[str | None])`

---

## Server Components

Web server and API layer

#### `queen/server/g_fastapi_upstox.py`

**Classes:**
- `class AuthConfig`
- `class APIConfig`
- `class UpstoxClient`
  - `def __init__(self, auth_config: AuthConfig, api_config: APIConfig)`
  - `def generate_auth_url(self)`
  - `def exchange_code_for_token(self, auth_code: str)`
  - `def _make_request(self, endpoint: str, params: Dict[str, Any])`
  - `def get_full_market_quote(self, instrument_keys: List[str])`
  - `def get_ltp_v3(self, instrument_keys: List[str])`

**Functions:**
- `def __init__(self, auth_config: AuthConfig, api_config: APIConfig)`
- `def generate_auth_url(self)`
- `def exchange_code_for_token(self, auth_code: str)`
- `def _make_request(self, endpoint: str, params: Dict[str, Any])`
- `def get_full_market_quote(self, instrument_keys: List[str])`
- `def get_ltp_v3(self, instrument_keys: List[str])`
- `def run_market_data_tasks(access_token: str)`
- `def home()`

#### `queen/server/main.py`

**Functions:**
- `def create_app()`
- `def render(request, tpl_name: str, ctx: dict | None=None)`

#### `queen/server/routers/alerts.py`

#### `queen/server/routers/analytics.py`

**Functions:**
- `def list_intraday_symbols()`

#### `queen/server/routers/cockpit.py`

**Classes:**
- `class ScanRequest(BaseModel)`
- `class PulseRequest(BaseModel)`

**Functions:**
- `def _render(request: Request, tpl_name: str, ctx: Optional[dict]=None)`
- `def _universe(symbols: Optional[List[str]])`

#### `queen/server/routers/health.py`

#### `queen/server/routers/instruments.py`

#### `queen/server/routers/intel.py`

#### `queen/server/routers/market_state.py`

**Functions:**
- `def _session_label(now_ist: datetime)`

#### `queen/server/routers/monitor.py`

**Functions:**
- `def list_intraday_symbols()`

#### `queen/server/routers/pnl.py`

#### `queen/server/routers/portfolio.py`

#### `queen/server/routers/services.py`

#### `queen/server/state.py`

> Global runtime state — last tick timestamp for market freshness checks.

**Functions:**
- `def set_last_tick(dt)`
- `def get_last_tick()`

---

## Settings & Configuration

Centralized configuration and policies

#### `queen/settings/__init__.py`

> Lean settings package initializer.

Intentionally avoids eager re-exports to prevent circular imports and heavy
import-time side effects. Import submodules directly:

  from queen.settings import settings as SETTINGS_MOD
  from queen.settings import indicators as IND
  from queen.settings import timeframes as TF

#### `queen/settings/breakout_settings.py`

> Breakout Detection Settings
===========================
Centralized configuration for all breakout-related indicators.
Edit these values to tune the system without touching code.

Settings grouped by module:
- FVG_SETTINGS: Fair Value Gap detection
- VOLUME_SETTINGS: Volume confirmation (RVOL, spikes)
- FALSE_BREAKOUT_SETTINGS: False breakout pattern detection
- BREAKOUT_VALIDATION_SETTINGS: Overall breakout quality scoring

**Functions:**
- `def get_quality_label(score: int)`
- `def validate_settings()`

#### `queen/settings/cockpit_schema.py`

#### `queen/settings/fno_universe.py`

**Functions:**
- `def _read_csv_safe(path: Path)`
- `def _normalize_df(df: pl.DataFrame)`
- `def _load_fno_df()`
- `def _fno_df()`
- `def reload()`
- `def get_fno_universe_df()`
- `def list_fno_symbols(*, segment: str | None=None, include_indices: bool=True, include_etf: bool=True, liquid_only: bool=False)`
- `def list_liquid_fno_intraday_symbols(*, segment: str='NSE_FO', include_indices: bool=False, include_etf: bool=False)`
- `def is_fno_symbol(symbol: str)`

#### `queen/settings/formulas.py`

**Functions:**
- `def indicator_names()`
- `def pattern_names()`
- `def meta_layer_names()`
- `def get_indicator(name: str)`
- `def get_pattern(name: str)`
- `def get_meta_layer(name: str)`
- `def validate()`

#### `queen/settings/fundamentals_map.py`

#### `queen/settings/indicator_policy.py`

**Functions:**
- `def _find_block(name: str)`
- `def params_for(indicator: str, timeframe: str)`
- `def has_indicator(name: str)`
- `def available_contexts(indicator: str)`
- `def validate_policy()`
- `def _norm(s: str)`
- `def _alerts_defaults()`
- `def _safe_int(v: Any, fallback: int)`
- `def min_bars_for_indicator(indicator: str, timeframe: str)`

#### `queen/settings/indicators.py`

**Functions:**
- `def list_indicator_names()`
- `def get_block(name: str)`
- `def validate_registry()`

#### `queen/settings/meta_controller_cfg.py`

#### `queen/settings/meta_drift.py`

#### `queen/settings/meta_layers.py`

**Functions:**
- `def get_meta_layer(name: str)`
- `def list_meta_layers()`
- `def required_bars_for_days(name: str, days: int, timeframe_token: str)`
- `def required_lookback(name: str, timeframe_token: str)`
- `def window_days_for_context(name: str, bars: int, timeframe_token: str)`
- `def params_for_meta(name: str, timeframe_token: str)`
- `def validate()`

#### `queen/settings/meta_memory.py`

#### `queen/settings/metrics.py`

**Functions:**
- `def is_enabled(name: str)`
- `def enable(names: Iterable[str])`
- `def validate()`
- `def summary()`

#### `queen/settings/patterns.py`

**Functions:**
- `def _norm(s: str)`
- `def _group_dict(group: str)`
- `def get_pattern(group: str, name: str)`
- `def list_patterns(group: str | None=None)`
- `def required_candles(name: str, group: str | None=None)`
- `def contexts_for(name: str, group: str | None=None)`
- `def required_lookback(name: str, context_key: str)`
- `def role_for(name: str, group: str | None=None)`
- `def validate()`

#### `queen/settings/profiles.py`

**Functions:**
- `def get_profile(name: str)`
- `def all_profiles()`
- `def window_days(profile_key: str, bars: int, token: str | None=None)`
- `def validate()`

#### `queen/settings/regimes.py`

**Functions:**
- `def derive_regime(metrics: dict)`
- `def get_regime_config(regime: str)`
- `def list_regimes()`
- `def color_for(regime: str)`
- `def validate()`
- `def to_polars_df()`

#### `queen/settings/settings.py`

**Functions:**
- `def get_env()`
- `def _env_base(env: str)`
- `def _mk(p: Path)`
- `def _build_paths(env: str)`
- `def set_env(value: str)`
- `def log_file(name: str)`
- `def resolve_log_path(name: str)`
- `def broker_config(name: str | None=None)`
- `def market_timezone()`
- `def active_exchange()`
- `def exchange_info(name: str | None=None)`
- `def market_hours()`
- `def alert_path_jsonl()`
- `def alert_path_sqlite()`
- `def alert_path_rules()`
- `def alert_path_state()`
- `def get_env_paths()`

#### `queen/settings/sim_settings.py`

#### `queen/settings/tactical.py`

**Functions:**
- `def _sum_weights()`
- `def get_weights(normalized: bool=False)`
- `def normalized_view()`
- `def validate()`
- `def summary()`

#### `queen/settings/timeframes.py`

**Functions:**
- `def normalize_tf(token: str)`
- `def is_intraday(token: str)`
- `def parse_tf(token: str)`
- `def to_fetcher_interval(token: str)`
- `def tf_to_minutes(token: str)`
- `def validate_token(token: str)`
- `def bars_for_days(token: str, days: int)`
- `def window_days_for_tf(token: str, bars: int)`
- `def get_timeframe(name: str)`
- `def list_timeframes()`
- `def context_to_token(context: Optional[str], default: str=_DEFAULT_TOKEN)`
- `def token_to_context(token: Optional[str], *, domain: str='intraday', default: str='intraday_15m')`

#### `queen/settings/universe.py`

> Active Universe Construction Parameters
------------------------------------------
🌐 Purpose:
    Defines weighting, thresholds, and risk filters used to
    build and maintain the active trading universe monthly.

💡 Usage:
    from queen.settings import universe
    factors = universe.FACTORS

**Functions:**
- `def summary()`
- `def selection_window_days(timeframe_token: str)`
- `def min_bars_for_selection(timeframe_token: str)`
- `def validate()`

#### `queen/settings/weights.py`

**Functions:**
- `def get_thresholds(tf: str | None=None)`
- `def fusion_weights_for(present_tfs: list[str])`
- `def reversal_weights()`
- `def tactical_component_weights()`
- `def tactical_normalization()`

---

## Technical Analysis Layer

Indicators, patterns, and signal generation

#### `queen/technicals/__init__.py`

> Indicators package.

Notes:
- The registry auto-scans this package (and its submodules) with
  pkgutil.walk_packages, so we intentionally avoid importing modules here.
- Put indicator modules under this folder (e.g., overlays.py, rsi.py, macd.py).
- Each module may expose:
    • EXPORTS = {"name": callable, ...}      # preferred
      or
    • NAME = "friendly_name"; def compute(...): ...
      or
    • def compute_<name>(df, **kwargs): ...

#### `queen/technicals/fundamentals_gate.py`

**Classes:**
- `class _FallbackLog`
  - `def info(self, msg)`
  - `def warning(self, msg)`
  - `def error(self, msg)`
  - `def debug(self, msg)`

**Functions:**
- `def info(self, msg)`
- `def warning(self, msg)`
- `def error(self, msg)`
- `def debug(self, msg)`
- `def _pick_col(df: pl.DataFrame, candidates: Sequence[str])`
- `def _ensure_symbol_col(df: pl.DataFrame, preferred: str='Symbol')`
- `def _coalesce(*vals)`
- `def fundamentals_overlay_df(fundamentals_df: pl.DataFrame, *, symbol_col: str='Symbol', include_trends: bool=True, include_raw_metrics: bool=False)`
- `def fundamentals_gate_and_boost(joined: pl.DataFrame, *, hard_gate: bool=True, boost_map: Optional[Dict[str, float]]=None, score_col: str='Technical_Score', alert_col: str='Technical_Alert', out_score_col: Optional[str]=None, out_alert_col: str='Final_Alert', pass_col: str='Fundamental_Pass', bucket_col: str='Intrinsic_Bucket')`
- `def apply_powerscore_gate(df: pl.DataFrame, *, min_powerscore: float=50.0, powerscore_col: str='PowerScore', out_col: str='PowerScore_Pass')`
- `def apply_trend_gate(df: pl.DataFrame, *, require_rising: bool=False, block_falling: bool=True, momentum_col: str='Fundamental_Momentum', out_col: str='Trend_Pass')`
- `def apply_bank_asset_gate(df: pl.DataFrame, *, block_deteriorating: bool=True, out_col: str='Bank_Asset_Pass')`
- `def apply_sector_rank_gate(df: pl.DataFrame, *, max_sector_rank: int=10, rank_col: str='Sector_Rank', out_col: str='Sector_Rank_Pass')`
- `def apply_comprehensive_gate(df: pl.DataFrame, *, require_fundamental_pass: bool=True, min_powerscore: float=40.0, block_falling_trend: bool=True, block_deteriorating_banks: bool=True, max_sector_rank: Optional[int]=None, out_col: str='Gate_Pass')`
- `def enhance_alerts_with_fundamentals(alerts_df: pl.DataFrame, fundamentals_df: pl.DataFrame, *, symbol_col: str='Symbol', boost_map: Optional[Dict[str, float]]=None)`
- `def add_combined_rank(df: pl.DataFrame, *, powerscore_weight: float=0.6, trend_weight: float=0.4, out_col: str='Combined_Rank')`

#### `queen/technicals/fundamentals_score_engine.py`

**Classes:**
- `class _FallbackLog`
  - `def info(self, msg)`
  - `def warning(self, msg)`
  - `def error(self, msg)`
  - `def debug(self, msg)`

**Functions:**
- `def info(self, msg)`
- `def warning(self, msg)`
- `def error(self, msg)`
- `def debug(self, msg)`
- `def _safe_z(x: Optional[float], mean: Optional[float], std: Optional[float])`
- `def _sigmoid(z: float)`
- `def _bucket(score: float)`
- `def _coalesce(*vals)`
- `def _pick_col(df: pl.DataFrame, candidates: List[str])`
- `def _get_flat_numeric_columns(df: pl.DataFrame)`
- `def add_zscores(df: pl.DataFrame)`
- `def add_intrinsic_score(df: pl.DataFrame)`
- `def add_powerscore(df: pl.DataFrame)`
- `def add_pass_fail(df: pl.DataFrame)`
- `def add_rankings(df: pl.DataFrame)`
- `def score_and_filter(df: pl.DataFrame)`

#### `queen/technicals/fusion_trend_volume.py`

**Functions:**
- `def _safe_pct(a: Optional[float], b: Optional[float])`
- `def _is_candidate_for_override(decision: str, bias: str)`
- `def _is_strong_up_trend(trend_ctx: Dict[str, Any])`
- `def _is_strong_volume(vol_ctx: Dict[str, Any])`
- `def _is_intraday_breakout_trend(indd: Dict[str, Any], df_ctx: pl.DataFrame, vol_ctx: Dict[str, Any])`
- `def maybe_apply_trend_volume_override(indd: Dict[str, Any], decision: str, bias: str, *, interval: str='15m', mode: str='intraday')`

#### `queen/technicals/master_index.py`

**Functions:**
- `def _scan_package(pkg: str)`
- `def master_index()`

#### `queen/technicals/microstructure/cpr.py`

**Functions:**
- `def _ensure_sorted(df: pl.DataFrame, ts_col: str='timestamp')`
- `def _pick_ohlc_cols(df: pl.DataFrame)`
- `def _width_regime(width_pct: float)`
- `def _location(last_price: float, bc: float, p: float, tc: float)`
- `def detect_cpr(df: pl.DataFrame, *, high_col: str | None=None, low_col: str | None=None, close_col: str | None=None, timestamp_col: str='timestamp')`

#### `queen/technicals/microstructure/fvg.py`

> Fair Value Gap (FVG) Detection Module
=====================================
Identifies institutional imbalances where price moved too fast,
leaving gaps that often act as magnets for future price action.

FVG Types:
- Bullish FVG: Gap between candle[i-2].high and candle[i].low (price moved up fast)
- Bearish FVG: Gap between candle[i-2].low and candle[i].high (price moved down fast)

Usage:
    from queen.technicals.microstructure.fvg import detect_fvg, summarize_fvg

    result = detect_fvg(df, lookback=50)
    summary = summarize_fvg(df, current_price=2850.0)

Settings Integration:
    All thresholds configurable via settings/breakout_settings.py

**Classes:**
- `class FVGZone`
  - `def contains_price(self, price: float)`
  - `def distance_from(self, price: float)`
- `class FVGResult`

**Functions:**
- `def contains_price(self, price: float)`
- `def distance_from(self, price: float)`
- `def _ensure_sorted(df: pl.DataFrame, ts_col: str='timestamp')`
- `def _calculate_atr(df: pl.DataFrame, period: int=14)`
- `def _detect_single_fvg(i: int, high: List[float], low: List[float], atr_val: float, timestamps: Optional[List]=None, min_gap_ratio: float=0.3)`
- `def _check_fvg_fill(zone: FVGZone, subsequent_highs: List[float], subsequent_lows: List[float], fill_tolerance: float=0.1)`
- `def detect_fvg(df: pl.DataFrame, *, lookback: int=None, min_gap_atr_ratio: float=None, fill_tolerance_pct: float=None, high_col: str='high', low_col: str='low', close_col: str='close', timestamp_col: str='timestamp')`
- `def summarize_fvg(df: pl.DataFrame, current_price: Optional[float]=None, **kwargs)`
- `def attach_fvg_signals(df: pl.DataFrame, lookback: int=50)`

#### `queen/technicals/microstructure/phases.py`

**Functions:**
- `def _ensure_sorted(df: pl.DataFrame, ts_col: str='timestamp')`
- `def _phase_from_components(structure: StructureState, volume: VolumeState, vwap: VWAPState, cpr: CPRState, risk: RiskState)`
- `def detect_phase(df: pl.DataFrame, *, timestamp_col: str='timestamp', atr_ratio: float | None=None, gap_pct: float | None=None)`

#### `queen/technicals/microstructure/risk.py`

**Functions:**
- `def _risk_band_from_atr(atr_ratio: Optional[float])`
- `def _adjust_band_for_gap(band: str, gap_pct: Optional[float])`
- `def _adjust_band_for_volume(band: str, volume_state: Optional[VolumeState])`
- `def _compose_reason(band: str, atr_ratio: Optional[float], gap_pct: Optional[float], volume_state: Optional[VolumeState])`
- `def detect_risk(*, atr_ratio: float | None, gap_pct: float | None=None, volume_state: VolumeState | None=None, vwap_state: VWAPState | None=None, cpr_state: CPRState | None=None)`

#### `queen/technicals/microstructure/state_objects.py`

**Classes:**
- `class StructureState`
  - `def is_bullish(self)`
  - `def is_bearish(self)`
  - `def is_range(self)`
- `class VolumeState`
  - `def is_vdu(self)`
  - `def is_expanding(self)`
- `class VWAPState`
  - `def bullish(self)`
  - `def bearish(self)`
- `class CPRState`
  - `def narrow(self)`
- `class RiskState`
- `class PhaseState`
  - `def is_accumulation(self)`
  - `def is_breakout_setup(self)`
  - `def is_pullback_buy(self)`
  - `def is_reversal(self)`
  - `def is_decline(self)`

**Functions:**
- `def is_bullish(self)`
- `def is_bearish(self)`
- `def is_range(self)`
- `def is_vdu(self)`
- `def is_expanding(self)`
- `def bullish(self)`
- `def bearish(self)`
- `def narrow(self)`
- `def is_accumulation(self)`
- `def is_breakout_setup(self)`
- `def is_pullback_buy(self)`
- `def is_reversal(self)`
- `def is_decline(self)`

#### `queen/technicals/microstructure/structure.py`

**Functions:**
- `def _ensure_sorted(df: pl.DataFrame, ts_col: str='timestamp')`
- `def _select_window(df: pl.DataFrame, lookback_bars: int)`
- `def _compute_trend_direction(window: pl.DataFrame, price_col: str)`
- `def _compression_ratio(window: pl.DataFrame, high_col: str, low_col: str, inner_span: int=5)`
- `def _recent_extremes(window: pl.DataFrame, high_col: str, low_col: str)`
- `def _find_swings(window: pl.DataFrame, high_col: str, low_col: str, max_points: int=3)`
- `def _structure_label(direction: TrendDirection, window: pl.DataFrame, price_col: str, high_col: str, low_col: str, compression: float)`
- `def detect_structure(df: pl.DataFrame, *, price_col: str='close', high_col: str='high', low_col: str='low', timestamp_col: str='timestamp', lookback_bars: int=20)`

#### `queen/technicals/microstructure/volume.py`

**Functions:**
- `def _ensure_sorted(df: pl.DataFrame, ts_col: str='timestamp')`
- `def _pick_volume_col(df: pl.DataFrame)`
- `def _select_window(df: pl.DataFrame, lookback_bars: int)`
- `def _volume_regime(rel_vol: float)`
- `def detect_volume(df: pl.DataFrame, *, volume_col: str | None=None, timestamp_col: str='timestamp', lookback_bars: int=20)`

#### `queen/technicals/microstructure/vwap.py`

**Functions:**
- `def _ensure_sorted(df: pl.DataFrame, ts_col: str='timestamp')`
- `def _pick_price_col(df: pl.DataFrame)`
- `def _pick_volume_col(df: pl.DataFrame)`
- `def _select_window(df: pl.DataFrame, lookback_bars: int | None)`
- `def _zone_and_band(offset_pct: float, at_tol_pct: float=0.15)`
- `def detect_vwap(df: pl.DataFrame, *, price_col: str | None=None, volume_col: str | None=None, timestamp_col: str='timestamp', lookback_bars: int | None=None)`

#### `queen/technicals/options_sentiment.py`

**Functions:**
- `def _compute_pcr(df: pl.DataFrame)`
- `def _classify_oi_change(df: pl.DataFrame)`
- `def _max_pain(df: pl.DataFrame)`
- `def compute_options_sentiment(symbol: str, mode: str, ltp: float, chain_df: pl.DataFrame, prev_chain_df: Optional[pl.DataFrame]=None)`

#### `queen/technicals/registry.py`

**Classes:**
- `class Entry`

**Functions:**
- `def _norm(name: str)`
- `def _resolve_dotted(root_mod, dotted: str)`
- `def _register_many(target: Dict[str, Entry], mod, exports: Dict)`
- `def _try_module_exports(mod, target: Dict[str, Entry])`
- `def _autoscan(pkg: str, target: Dict[str, Entry])`
- `def build_registry(force: bool=False)`
- `def list_indicators()`
- `def list_signals()`
- `def get_indicator(name: str)`
- `def get_signal(name: str)`
- `def register_indicator(name: str, fn: Callable)`
- `def register_signal(name: str, fn: Callable)`

#### `queen/technicals/sector_strength.py`

**Functions:**
- `def _compress_to_daily(df: pl.DataFrame)`
- `def _trend_structure(daily: pl.DataFrame)`
- `def _ema_alignment(daily: pl.DataFrame)`
- `def _rsi_momentum(daily: pl.DataFrame)`
- `def compute_sector_strength(df: pl.DataFrame)`

#### `queen/technicals/strategy/__init__.py`

#### `queen/technicals/trend_strength.py`

**Functions:**
- `def compute_trend_strength(df: pl.DataFrame)`

#### `queen/technicals/trend_strength_daily.py`

**Functions:**
- `def _intraday_to_daily(df: pl.DataFrame)`
- `def _hh_hl_confirm(daily: pl.DataFrame, lookback: int=5)`
- `def _lh_ll_confirm(daily: pl.DataFrame, lookback: int=5)`
- `def _ema_stack_label(ema20: float | None, ema50: float | None, ema200: float | None)`
- `def _trend_from_stack_and_structure(stack: str, hhhl: bool, lhll: bool)`
- `def compute_daily_trend_strength(df: pl.DataFrame, *, min_days: int=30)`

#### `queen/technicals/trend_strength_intraday.py`

**Functions:**
- `def _to_15m_volume_bars(df: pl.DataFrame)`
- `def _percentile_rank(series: pl.Series, value: float)`
- `def _label_from_ratio(ratio: float)`
- `def _score_from_ratio_and_rank(ratio: float, pct_rank: float)`
- `def compute_intraday_volume_strength(df: pl.DataFrame, *, min_bars: int=30, lookback_bars: int=60, avg_window: int=20)`

#### `queen/technicals/volume_confirmation.py`

> Volume Confirmation Module
==========================
Provides volume-based confirmation for breakouts and signals.
Key indicators:
- RVOL (Relative Volume): Current volume vs average
- Volume Spike Detection: Identifies unusual volume surges
- Volume Trend: Accumulation/Distribution assessment

"A breakout without volume is a fake breakout" - Market wisdom

Usage:
    from queen.technicals.indicators.volume_confirmation import (
        compute_rvol,
        detect_volume_spike,
        summarize_volume_confirmation,
    )

    # Add RVOL column to DataFrame
    df = compute_rvol(df, period=20)

    # Get volume spike detection
    spikes = detect_volume_spike(df, threshold=2.0)

    # Get summary for signal cards
    summary = summarize_volume_confirmation(df)

Settings Integration:
    All thresholds configurable via settings/volume_policy.py

**Classes:**
- `class VolumeSpike`
- `class VolumeConfirmationResult`

**Functions:**
- `def compute_rvol(df: pl.DataFrame, period: int=None, volume_col: str='volume')`
- `def detect_volume_spike(df: pl.DataFrame, threshold: float=None, lookback: int=None, volume_col: str='volume', close_col: str='close', timestamp_col: str='timestamp')`
- `def compute_volume_trend(df: pl.DataFrame, period: int=None, volume_col: str='volume')`
- `def compute_accumulation_distribution(df: pl.DataFrame, period: int=10)`
- `def check_breakout_volume_ready(df: pl.DataFrame, min_rvol: float=None)`
- `def summarize_volume_confirmation(df: pl.DataFrame, **kwargs)`
- `def attach_volume_confirmation(df: pl.DataFrame, period: int=None)`
- `def validate_breakout_volume(df: pl.DataFrame, breakout_bar_index: int=-1)`

#### `queen/technicals/volume_strength.py`

**Functions:**
- `def compute_volume_strength(df: pl.DataFrame)`

#### `queen/technicals/volume_strength_intraday.py`

**Functions:**
- `def _to_15m_volume_bars(df: pl.DataFrame)`
- `def _percentile_rank(series: pl.Series, value: float)`
- `def _label_from_ratio(ratio: float)`
- `def _score_from_ratio_and_rank(ratio: float, pct_rank: float)`
- `def compute_intraday_volume_strength(df: pl.DataFrame, *, min_bars: int=30, lookback_bars: int=60, avg_window: int=20)`

### Indicators Registry

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `__init__.py` | `__getattr__` |  |
| `advanced.py` | `bollinger_bands`, `supertrend`, `atr_channels` |  |
| `adx_dmi.py` | `adx_dmi`, `adx_summary`, `lbx` |  |
| `all.py` | `_safe_merge`, `_tf_from_context`, `_attach_core_indicators` |  |
| `breadth_cumulative.py` | `compute_breadth`, `summarize_breadth` |  |
| `breadth_momentum.py` | `compute_breadth_momentum`, `summarize_breadth_momentum`, `compute_regime_strength` |  |
| `core.py` | `sma`, `ema`, `_slope` |  |
| `keltner.py` | `compute_keltner`, `summarize_keltner`, `compute_volatility_index` |  |
| `momentum_macd.py` | `macd_config`, `compute_macd`, `summarize_macd` |  |
| `state.py` | `_ensure_series`, `_pattern_bias`, `volume_delta` |  |
| `volatility_fusion.py` | `compute_volatility_fusion`, `summarize_volatility` |  |
| `volume_chaikin.py` | `_ema_np`, `chaikin`, `summarize_chaikin` |  |
| `volume_confirmation.py` | `compute_rvol`, `detect_volume_spike`, `compute_volume_trend` | Volume Confirmation Module ========================== Provid... |
| `volume_mfi.py` | `mfi`, `compute_mfi`, `summarize_mfi` |  |

### Pattern Detection

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `__init__.py` |  |  |
| `composite.py` | `detect_composite_patterns` |  |
| `core.py` | `_false_series`, `_max2`, `_min2` |  |
| `false_breakout.py` | `is_bearish_trap`, `is_bullish_trap`, `_find_swing_points` | False Breakout Pattern Detection Module ====================... |
| `runner.py` | `run_patterns` |  |

### Signal Fusion

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `__init__.py` |  | Signals (tactical/pattern/meta) package.  Notes: - The regis... |
| `breakout_validator.py` | `get_quality_label`, `_calculate_atr`, `_check_atr_breakout` | Breakout Validator Module ========================= Combines... |
| `__init__.py` |  |  |
| `cmv.py` | `_norm_pm1`, `compute_cmv` |  |
| `liquidity_breadth.py` | `compute_liquidity_breadth_fusion`, `_norm01` |  |
| `market_regime.py` | `_norm01`, `compute_market_regime` |  |
| `pattern_fusion.py` | `compute_pattern_component` |  |
| `pre_breakout.py` | `_boll_params`, `_ensure_bollinger`, `compute_pre_breakout` |  |
| `registry.py` | `_search_packages`, `_canonical`, `_register` |  |
| `reversal_summary.py` | `_pattern_bias`, `_last_float`, `_last_bool` |  |
| `__init__.py` |  |  |
| `absorption.py` | `detect_absorption_zones`, `summarize_absorption` |  |
| `ai_inference.py` | `_model_path_default`, `load_model`, `prepare_features` |  |
| `ai_optimizer.py` | `_model_path`, `_weights_out_path`, `_feature_names_default` |  |
| `ai_recommender.py` | `_log_path`, `_ensure_ratios`, `analyze_event_log` |  |
| `ai_trainer.py` | `_event_log_path`, `_model_path`, `load_event_log` |  |
| `bias_regime.py` | `compute_bias_regime` |  |
| `cognitive_orchestrator.py` | `_maybe`, `_import_inference`, `_import_trainer` | Contract: single-cycle runner ----------------------------- ... |
| `core.py` | `_zscore`, `_minmax`, `compute_tactical_index` | Adaptive Tactical Fusion Engine — blends regime (RScore), vo... |
| `divergence.py` | `detect_divergence`, `summarize_divergence` |  |
| `event_log.py` | `_last`, `log_tactical_events` |  |
| `exhaustion.py` | `detect_exhaustion_bars` |  |
| `helpers.py` | `_norm01`, `_atr_fallback`, `_lbx_fallback` |  |
| `live_daemon.py` | `_utc_now`, `save_checkpoint`, `send_alert` |  |
| `live_supervisor.py` | `_utc_now`, `_save_health` |  |
| `meta_controller.py` | `_load_weights_dict`, `_P`, `_load_state` |  |
| `meta_introspector.py` | `_load_csv`, `_parse_ts`, `run_meta_introspector` |  |
| `reversal_stack.py` | `compute_reversal_stack` |  |
| `squeeze_pulse.py` | `detect_squeeze_pulse`, `summarize_squeeze` |  |
| `tactical_liquidity_trap.py` | `detect_liquidity_trap` |  |
| `tactical_meta_dashboard.py` | `_paths`, `load_drift_log`, `show_meta_config` |  |
| `__init__.py` |  |  |
| `indicator_template.py` | `_params_for`, `compute_indicator`, `summarize_indicator` |  |
| `utils_patterns.py` | `_catalog`, `_norm_tf`, `_titleize` |  |

---

## Testing & Validation

Validation and test suites

#### `queen/tests/__init__.py`

> Run all smoke tests sequentially via `python -m queen.tests`.

This aggregates lightweight sanity checks for helpers, IO, instruments,
and market-time logic, ensuring basic functional integrity without pytest.

**Functions:**
- `def run_all()`

#### `queen/tests/fundamentals_devcheck.py`

**Functions:**
- `def _parse_args()`
- `def _preview_extracted(symbol: str, processed_dir: Path)`
- `def _warn_if_null_metrics(df: pl.DataFrame, thresh: float)`
- `def _load_registry(df: pl.DataFrame)`
- `def main()`

#### `queen/tests/market_playback.py`

> Simulates a full market day (PRE → LIVE → POST) with CLI flags.
---------------------------------------------------------------
Now includes:
✅ --force-live   → Override holidays/weekends
✅ --no-clock     → Skip MarketClock for pure playback
✅ Live tick counter in footer
✅ Color-coded gate legend
✅ Column-aligned, terminal-polished output

**Functions:**
- `def parse_args()`
- `def style_gate(gate: str)`
- `def show_legend()`
- `def print_state(now: dt.datetime, force_live: bool)`

#### `queen/tests/market_test.py`

**Functions:**
- `def test_holidays()`
- `def test_working_days()`
- `def test_market_state()`
- `def test_time_bucket()`
- `def run_sync_tests()`

#### `queen/tests/smoke_absorption.py`

**Functions:**
- `def _build_mock(n: int=200)`
- `def test()`

#### `queen/tests/smoke_advanced.py`

**Functions:**
- `def _mk_ohlcv(n: int=240)`
- `def _is_numeric_dtype(dt: pl.DataType)`
- `def test_attach_advanced()`
- `def test_components_direct()`

#### `queen/tests/smoke_ai_inference.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_ai_optimizer_paths.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_ai_trainer_paths.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_all.py`

**Functions:**
- `def _mk_ohlcv(n: int=120)`
- `def test_attach_all()`

#### `queen/tests/smoke_bias_regime.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_bias_regime_latency.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_breadth.py`

**Functions:**
- `def _make_cmv_sps(n: int=180)`
- `def _is_float_dtype(dt)`
- `def test_compute_columns_and_types()`
- `def test_summary_keys_and_ranges()`

#### `queen/tests/smoke_breadth_combo.py`

**Functions:**
- `def _mk_breadth_frame(n: int=240)`
- `def _assert_range(series: pl.Series, lo: float, hi: float, name: str)`
- `def test_breadth_combo()`

#### `queen/tests/smoke_breadth_momentum.py`

**Functions:**
- `def _assert_between(x: float, lo: float, hi: float)`
- `def _assert_bias(token: str)`
- `def test_cmv_sps_path()`
- `def test_adv_dec_path()`

#### `queen/tests/smoke_breakout_modules.py`

> Smoke Tests for New Breakout Detection Modules
==============================================
Run: python -m queen.tests.smoke_breakout_modules

Tests:
1. FVG Detection
2. Volume Confirmation
3. False Breakout Patterns
4. Breakout Validator (integration)

**Functions:**
- `def _assert(condition: bool, msg: str='')`
- `def _make_test_df(n: int=100, with_gaps: bool=False, with_spikes: bool=False)`
- `def test_fvg_detection()`
- `def test_volume_confirmation()`
- `def test_false_breakout()`
- `def test_breakout_validator()`
- `def test_settings()`
- `def run_all()`

#### `queen/tests/smoke_chaikin.py`

**Functions:**
- `def _mk(n: int=120)`
- `def _is_float(dt)`
- `def test_columns_and_types()`
- `def test_attach_and_summary()`

#### `queen/tests/smoke_cmv_latency.py`

**Functions:**
- `def _build_df(n: int=2000)`
- `def _best_of_3(fn)`
- `def test_latency()`

#### `queen/tests/smoke_cognitive_orchestrator.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_divergence.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_divergence_latency.py`

**Functions:**
- `def _build_df(n: int=2000)`
- `def test_latency()`

#### `queen/tests/smoke_event_log.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_exhaustion_latency.py`

**Functions:**
- `def _gen_df(n: int=2000)`
- `def test_latency(n: int=2000, rounds: int=3, cap_ms: float=5.0)`

#### `queen/tests/smoke_fetch_utils.py`

**Functions:**
- `def main()`

#### `queen/tests/smoke_fundamentals.py`

**Classes:**
- `class Logger`
  - `def info(self, msg)`
  - `def warning(self, msg)`
  - `def error(self, msg)`

**Functions:**
- `def info(self, msg)`
- `def warning(self, msg)`
- `def error(self, msg)`
- `def _parse_args()`
- `def _preview_extracted(symbol: str, processed_dir: Path)`
- `def _warn_if_null_metrics(df: pl.DataFrame)`
- `def main()`

#### `queen/tests/smoke_fusion_all_latency.py`

**Functions:**
- `def _mk_df(n: int=2000)`
- `def _timeit(fn, *args, repeats=3, **kwargs)`
- `def test_all_latency()`

#### `queen/tests/smoke_fusion_latency.py`

**Functions:**
- `def _mk_ohlcv(n: int=2000)`
- `def test_latency()`

#### `queen/tests/smoke_fusion_lbx.py`

**Functions:**
- `def _mk_ohlcv(n=400)`
- `def test()`

#### `queen/tests/smoke_fusion_market_regime.py`

**Functions:**
- `def _mk(n=240)`
- `def test()`

#### `queen/tests/smoke_fusion_overall.py`

**Functions:**
- `def _mk(n: int=360)`
- `def _assert_has(df: pl.DataFrame, cols: list[str], tag: str)`
- `def test()`

#### `queen/tests/smoke_helpers.py`

**Functions:**
- `def _make_df(n: int=25)`
- `def test_parquet_roundtrip()`
- `def test_csv_roundtrip()`
- `def test_json_roundtrip_array()`
- `def test_read_any_switch()`
- `def test_jsonl_tail_append()`
- `def test_s2np_and_float_series()`
- `def test_safe_concat()`

#### `queen/tests/smoke_indicators.py`

**Functions:**
- `def _is_float_dtype(dt)`
- `def _is_str_dtype(dt)`
- `def _as_series(x, *, prefer: tuple[str, ...]=(), df: pl.DataFrame | None=None)`
- `def _make_df(n: int=400)`
- `def test_advanced_indicators_shapes()`
- `def test_adx_dmi_columns_and_types()`
- `def test_lbx_and_summary_contracts()`

#### `queen/tests/smoke_instruments.py`

**Functions:**
- `def _seed_instrument_sources()`
- `def main()`

#### `queen/tests/smoke_intervals.py`

**Functions:**
- `def _assert(cond, msg)`
- `def test_intraday_roundtrip_minutes_to_token()`
- `def test_parse_minutes_intraday_only()`
- `def test_fetcher_interval_canonical()`
- `def test_classify_unit_consistency()`
- `def test_is_intraday_flag()`
- `def run_all()`

#### `queen/tests/smoke_io.py`

**Functions:**
- `def main()`

#### `queen/tests/smoke_keltner.py`

**Functions:**
- `def _make_df(n: int=150)`
- `def test_keltner_columns()`
- `def test_volatility_index_range()`
- `def test_summary_structure()`

#### `queen/tests/smoke_lbx_latency.py`

**Functions:**
- `def _build_df(n: int=2000)`
- `def _best_of_3(fn)`
- `def test_latency()`

#### `queen/tests/smoke_liquidity_trap_latency.py`

**Functions:**
- `def _make_df(n: int=2000)`
- `def test_latency()`

#### `queen/tests/smoke_liquidity_trap_vector.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_live_daemon.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_live_supervisor.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_macd.py`

**Functions:**
- `def _make_df(n: int=200)`
- `def test_macd_columns()`
- `def test_summary_keys()`

#### `queen/tests/smoke_market_regime_latency.py`

**Functions:**
- `def _build_df(n: int=2000)`
- `def _best_of_3(fn)`
- `def test_latency()`

#### `queen/tests/smoke_market_sleep.py`

**Functions:**
- `def _assert(cond: bool, msg: str='assertion failed')`
- `def test_compute_sleep_delay()`

#### `queen/tests/smoke_market_time.py`

> Smoke test for market-time helpers
----------------------------------
✅ Confirms settings-driven calendar integration works end-to-end
✅ Ensures no crash on holiday / weekend / after-hours
✅ Lightweight: no external I/O, no Polars writes

**Functions:**
- `def test_market_time()`
- `def test_session_boundaries()`

#### `queen/tests/smoke_master_index.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_meta_controller.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_meta_dashboard.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_meta_settings_only.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_meta_strategy_cycle.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_meta_timestamps.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_mfi.py`

**Functions:**
- `def _mk(n=150)`
- `def _is_float(dt)`
- `def test_columns_and_ranges()`
- `def test_attach_and_summary()`

#### `queen/tests/smoke_ohlcv.py`

**Functions:**
- `def _dummy_df(n: int=120, interval: str='1m')`
- `def main()`

#### `queen/tests/smoke_orchestrator_contract.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_overall_latency.py`

**Functions:**
- `def _mk(n=2000)`
- `def test_latency()`

#### `queen/tests/smoke_paths_models.py`

**Functions:**
- `def test_paths_models()`

#### `queen/tests/smoke_patterns_all.py`

#### `queen/tests/smoke_patterns_composite.py`

**Functions:**
- `def _mk_ohlcv(n: int=120)`
- `def test_patterns_composite()`

#### `queen/tests/smoke_patterns_core.py`

**Functions:**
- `def _mk_ohlcv(n: int=100)`
- `def test_patterns_core()`

#### `queen/tests/smoke_patterns_latency.py`

**Functions:**
- `def _mk(n: int=2000)`
- `def test_latency()`

#### `queen/tests/smoke_patterns_runner.py`

**Functions:**
- `def _mk_ohlcv(n: int=320)`
- `def test_runner()`

#### `queen/tests/smoke_pre_breakout.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_rate_limited_decorator.py`

**Functions:**
- `def run_all()`

#### `queen/tests/smoke_rate_limiter.py`

**Functions:**
- `def run_all()`

#### `queen/tests/smoke_rate_limiter_context.py`

**Functions:**
- `def run_all()`

#### `queen/tests/smoke_rate_limiter_global.py`

**Functions:**
- `def run_all()`

#### `queen/tests/smoke_rate_limiter_pool.py`

**Functions:**
- `def run_all()`

#### `queen/tests/smoke_registry.py`

**Functions:**
- `def test_registry_build()`

#### `queen/tests/smoke_reversal_stack.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_reversal_summary.py`

**Functions:**
- `def main()`

#### `queen/tests/smoke_rsi.py`

**Functions:**
- `def _mk(n=120)`
- `def test_rsi_series()`

#### `queen/tests/smoke_schema_adapter.py`

**Functions:**
- `def run_all()`

#### `queen/tests/smoke_show_snapshot.py`

#### `queen/tests/smoke_signals_registry.py`

**Functions:**
- `def _dummy(df, **kwargs)`

#### `queen/tests/smoke_squeeze_pulse.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_strategy_fusion.py`

**Functions:**
- `def _mk(n: int=60, sps: float=0.65)`
- `def test()`

#### `queen/tests/smoke_tactical_core.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_tactical_index_modes.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_tactical_inputs.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_technicals_registry.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_template_indicator.py`

**Functions:**
- `def test()`

#### `queen/tests/smoke_test_sim.py`

> Quick local smoke test for the simulator functions with artificial rows.

Usage: python tools/smoke_test_sim.py

#### `queen/tests/smoke_utils_patterns.py`

**Functions:**
- `def test_get_patterns_for_timeframe()`
- `def test_random_and_deterministic_labels()`
- `def test_grouped_by_family()`

#### `queen/tests/smoke_volatility_fusion.py`

**Functions:**
- `def _mk(n=200)`
- `def _is_float(dt)`
- `def test_fusion_outputs_and_ranges()`

#### `queen/tests/smoke_weights.py`

**Functions:**
- `def test()`

#### `queen/tests/test_indicator_kwargs.py`

**Functions:**
- `def test_indicator_call_kwargs_filters_meta()`

#### `queen/tests/test_patterns_core.py`

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│  (universe_scan, live_monitor, morning_intel, etc.)        │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                    Services Layer                           │
│  (forecast, live, scoring, morning, symbol_scan)           │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│               Strategy & Fusion Engine                      │
│  (fusion.py, meta_strategy_cycle.py)                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│             Technical Analysis Registry                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Indicators   │  │   Patterns   │  │   Signals    │     │
│  │ (20+ modules)│  │ (Japanese,   │  │ (Tactical,   │     │
│  │              │  │  Composite)  │  │  Fusion)     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│               Helpers & Infrastructure                      │
│  (market, io, schema_adapter, instruments, logger)         │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                    Data Layer                               │
│  (Parquet/CSV/JSONL with atomic writes, caching)           │
└─────────────────────────────────────────────────────────────┘
```

---

## Usage Patterns for AI Analysis & Code Generation

When asking an AI to modify or extend this system:

1. **Always provide context**: Mention the module path + settings context
   - Example: "In `{root_module}/settings/indicator_policy.py`, add a new context for `hourly_2h`"

2. **Registry additions**:
   - Indicators: Add module to `{root_module}/technicals/indicators/` with `EXPORTS` dict
   - Signals: Add to `{root_module}/technicals/signals/` following `compute_*` pattern
   - Patterns: Extend `{root_module}/settings/patterns.py` JAPANESE/CUMULATIVE blocks

3. **Settings modifications**:
   - Timeframe configs: Edit `{root_module}/settings/timeframes.py`
   - Indicator params: Modify `{root_module}/settings/configs/indicator_policy.yaml`
   - Weights: Adjust `{root_module}/settings/configs/weights.yaml`

4. **Testing expectation**: Run corresponding `smoke_*.py` test after changes

---

## File Count Summary
- **Total Python Files**: 87
- **Core Modules**: 206
- **Test Files**: 1
- **Settings/Configs**: 1
- **Helpers/Utilities**: 1

---

*This documentation is optimized for LLM consumption with clear hierarchies, explicit signatures, and grouped logical components.*