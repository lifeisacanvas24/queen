# 📚 Queen Quant Platform — AI-Ready Project Documentation

**Project**: `queen/` (Quantitative Trading Platform)
**Version**: v9.6+
**Architecture**: Modular, Registry-Driven, Settings-First
**Last Updated**: 2025-11-13

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

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `evaluator copy.py` | `_indicator_kwargs`, `_last_two`, `_cmp` |  |
| `evaluator.py` | `_last_two`, `_cmp`, `_cross` |  |
| `rules.py` | `from_dict`, `to_dict`, `load_rules` |  |
| `state.py` | `_key`, `load_cooldowns`, `save_cooldown` |  |

### CLI Tools

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `__init__.py` |  |  |
| `list_master.py` | `_print`, `_save`, `main` |  |
| `list_signals.py` | `main` |  |
| `list_technicals.py` | `parse_args`, `main` |  |
| `live_monitor.py` | `main` |  |
| `monitor_stream.py` | `_fmt`, `_render`, `_graceful` |  |
| `morning_intel.py` | `main` |  |
| `run_strategy.py` | `_dummy_ohlcv`, `_wire_minimals`, `main` |  |
| `show_snapshot.py` | `_load_snapshot`, `main` |  |
| `symbol_scan.py` | `_print_table`, `main` |  |
| `universe_scanner.py` | `load_and_prefilter_symbols`, `calculate_volatility`, `calculate_liquidity_score` | Production-grade NSE/BSE universe scanner with fundamental a... |
| `validate_registry.py` | `_make_df`, `main` |  |

### Daemon Services

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `__init__.py` | `_list_daemons`, `_run_child`, `run_cli` | Queen Daemon Manager (forward-compatible)  Usage:   python -... |
| `__main__.py` |  | Entry point for Queen Daemon Manager (`python -m queen.daemo... |
| `alert_daemon.py` | `check`, `_parse_args`, `__init__` |  |
| `alert_v2 copy.py` | `_backfill_days`, `_timeframe_key`, `_min_bars_for` |  |
| `alert_v2.py` | `_backfill_days`, `_min_bars_for`, `_days_for_interval` |  |
| `live_engine.py` | `_cpr_from_last_completed_session`, `_fmt`, `_compact_table` |  |
| `morning_intel.py` | `_buy_sell_hold`, `_fmt_last`, `_ema_bias` |  |
| `scheduler.py` | `run_cli` |  |

### Market Data Fetchers

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `__init__.py` |  |  |
| `fetch_router.py` | `_chunk_list`, `_generate_output_path`, `run_cli` |  |
| `nse_fetcher.py` | `_quote_url`, `_referer_url`, `_read_cache` |  |
| `upstox_fetcher.py` | `_min_rows_from_settings`, `_headers`, `_merge_unique_sort` |  |
| `instruments.py` | `_instrument_path_for`, `_all_instrument_paths`, `_read_instruments` |  |

#### `queen/services/__init__.py`

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

#### `queen/services/live.py`

**Functions:**
- `def _min_bars(interval_min: int)`
- `def _safe_float(v)`
- `def _ctx_from_value(cmp_val: float | None, ref: float | None, eps_pct: float=0.1)`
- `def _cpr_ctx_with_fallback(cmp_val: float | None, cpr_pp: float | None, vwap: float | None)`
- `def _ensure_min_width_with_atr(row: Dict, atr: Optional[float])`

#### `queen/services/morning.py`

**Functions:**
- `def _read_json(path: Path, default)`
- `def _write_json(path: Path, data)`
- `def _archive_yesterday_signals(now_ist: datetime)`
- `def _trend_last_n(n: int=5)`
- `def _weekly_gauge(n: int=7)`
- `def run_morning_briefing()`
- `def build_briefing_payload(now_ist: datetime)`

#### `queen/services/scoring.py`

**Functions:**
- `def _last(series: pl.Series)`
- `def _ema_last(df: pl.DataFrame, period: int, column: str='close')`
- `def compute_indicators(df: pl.DataFrame)`
- `def _normalize_signal(payload: Dict | None, name: str)`
- `def _fallback_early(df: pl.DataFrame, cmp_: float, vwap_: Optional[float])`
- `def _early_bundle(df: pl.DataFrame, cmp_: float, vwap_: Optional[float])`
- `def score_symbol(indd: Dict[str, float | str])`
- `def _ladder_from_base(base: float, atr: Optional[float])`
- `def _non_position_entry(cmp_: float, vwap: Optional[float], ema20: Optional[float], cpr: Optional[float], atr: Optional[float])`
- `def action_for(symbol: str, indd: Dict[str, float | str], book: str='all', use_uc_lc: bool=True)`

#### `queen/services/symbol_scan.py`

**Functions:**
- `def _min_bars_for(rule: Rule)`
- `def _days_for_interval(interval: str, need_bars: int)`
- `def _window(interval: str, need_bars: int)`

#### `queen/strategies/fusion.py`

**Functions:**
- `def _last_float(df: pl.DataFrame, col: str, default: float=0.0)`
- `def _last_str(df: pl.DataFrame, col: str, default: str='')`
- `def _regime_to_unit(reg: str)`
- `def _risk_band(atr_ratio: float)`
- `def run_strategy(symbol: str, frames: Dict[str, pl.DataFrame], *, tf_weights: Dict[str, float] | None=None)`

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

#### `queen/helpers/common.py`

**Functions:**
- `def utc_now_iso()`
- `def next_candle_ms(now_ist: datetime, interval_min: int)`
- `def normalize_symbol(s: str | None)`
- `def logger_supports_color(logger: logging.Logger)`
- `def colorize(text: str, color_key: str, palette: Dict[str, str], enabled: bool)`
- `def timeframe_key(tf: str)`
- `def indicator_kwargs(params: Dict[str, Any] | None, *, deny: set[str] | None=None)`

#### `queen/helpers/fetch_utils.py`

**Functions:**
- `def warn_if_same_day_eod(from_date: str | date | None, to_date: str | date | None)`

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

#### `queen/settings/formulas.py`

**Functions:**
- `def indicator_names()`
- `def pattern_names()`
- `def meta_layer_names()`
- `def get_indicator(name: str)`
- `def get_pattern(name: str)`
- `def get_meta_layer(name: str)`
- `def validate()`

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

#### `queen/technicals/master_index.py`

**Functions:**
- `def _scan_package(pkg: str)`
- `def master_index()`

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

#### `queen/technicals/strategy/__init__.py`

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
| `keltner.py` | `ema`, `true_range`, `compute_atr` |  |
| `momentum_macd.py` | `ema`, `compute_macd`, `summarize_macd` |  |
| `state.py` | `volume_delta`, `_compute_rsi_series`, `rsi_density` |  |
| `volatility_fusion.py` | `compute_volatility_fusion`, `summarize_volatility` |  |
| `volume_chaikin.py` | `_ema_np`, `chaikin`, `summarize_chaikin` |  |
| `volume_mfi.py` | `_tf_from_context`, `mfi`, `compute_mfi` |  |

### Pattern Detection

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `__init__.py` |  |  |
| `composite.py` | `detect_composite_patterns` |  |
| `core.py` | `_false_series`, `_max2`, `_min2` |  |
| `runner.py` | `run_patterns` |  |

### Signal Fusion

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| `__init__.py` |  | Signals (tactical/pattern/meta) package.  Notes: - The regis... |
| `__init__.py` |  |  |
| `cmv.py` | `_norm_pm1`, `compute_cmv` |  |
| `liquidity_breadth.py` | `compute_liquidity_breadth_fusion`, `_norm01` |  |
| `market_regime.py` | `_norm01`, `compute_market_regime` |  |
| `pre_breakout.py` | `_boll_params`, `_ensure_bollinger`, `compute_pre_breakout` |  |
| `registry.py` | `_search_packages`, `_canonical`, `_register` |  |
| `reversal_summary.py` | `_safe_last`, `summarize_reversal_stacks` |  |
| `__init__.py` |  |  |
| `absorption.py` | `detect_absorption_zones`, `summarize_absorption` |  |
| `ai_inference.py` | `_model_path_default`, `load_model`, `prepare_features` |  |
| `ai_optimizer.py` | `_model_path`, `_weights_out_path`, `_feature_names_default` |  |
| `ai_recommender.py` | `_log_path`, `_ensure_ratios`, `analyze_event_log` |  |
| `ai_trainer.py` | `_event_log_path`, `_model_path`, `load_event_log` |  |
| `bias_regime.py` | `compute_bias_regime` |  |
| `cognitive_orchestrator.py` | `_maybe`, `_import_inference`, `_import_trainer` | Contract: single-cycle runner ----------------------------- ... |
| `core.py` | `_safe_read_json`, `_zscore`, `_minmax` | Adaptive Tactical Fusion Engine — blends regime (RScore), vo... |
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
- **Total Python Files**: 83
- **Core Modules**: 137
- **Test Files**: 1
- **Settings/Configs**: 1
- **Helpers/Utilities**: 1

---

*This documentation is optimized for LLM consumption with clear hierarchies, explicit signatures, and grouped logical components.*