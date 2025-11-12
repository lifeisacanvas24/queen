# 📄 Python Documentation: `queen/`

**Generated on:** 2025-11-12 16:58:21
**Total Files:** 212

---

## `queen/__init__.py`

---

## `queen/alerts/evaluator copy.py`

### Functions

#### `def _indicator_kwargs(rule: Rule)`
#### `def _last_two(series: pl.Series)`
#### `def _cmp(op: str, a: float, b: float)`
#### `def _cross(op: str, s: pl.Series, level: float)`
Cross detection against a horizontal level (returns ok, meta).

#### `def eval_price(df: pl.DataFrame, rule: Rule)`
#### `def eval_pattern(df: pl.DataFrame, rule: Rule)`
#### `def eval_indicator(df: pl.DataFrame, rule: Rule)`
#### `def eval_rule(rule: Rule, df: pl.DataFrame)`
Top-level dispatcher. Returns (ok, meta).

---

## `queen/alerts/evaluator.py`

### Functions

#### `def _last_two(series: pl.Series)`
#### `def _cmp(op: str, a: float, b: float)`
#### `def _cross(op: str, s: pl.Series, level: float)`
#### `def eval_price(df: pl.DataFrame, rule: Rule)`
#### `def eval_indicator(df: pl.DataFrame, rule: Rule)`
#### `def eval_rule(rule: Rule, df: pl.DataFrame)`
Top-level dispatcher.

---

## `queen/alerts/rules.py`

### Classes

#### `class Rule`
**Methods:**
- `def from_dict(d: Dict[str, Any])`
- `def to_dict(self)`

### Functions

#### `def from_dict(d: Dict[str, Any])`
#### `def to_dict(self)`
#### `def load_rules(path: Optional[Union[str, Path]]=None)`
Load rules from YAML. If `path` is None, use settings.settings.alert_path_rules().
Accepts either a top-level list of rules or a dict with key 'rules'.

---

## `queen/alerts/state.py`

### Functions

#### `def _key(sym: str, rule: str)`
#### `def load_cooldowns()`
Load cooldowns from state JSONL (latest wins).

#### `def save_cooldown(sym: str, rule: str, last_fire_ts: float)`
Append a single cooldown record (append-only JSONL).

---

## `queen/cli/__init__.py`

---

## `queen/cli/list_master.py`

### Functions

#### `def _print(df: pl.DataFrame, *, grep: str | None)`
#### `def _save(df: pl.DataFrame, out: str)`
#### `def main()`
---

## `queen/cli/list_signals.py`

### Functions

#### `def main()`
---

## `queen/cli/list_technicals.py`

### Functions

#### `def parse_args()`
#### `def main()`
---

## `queen/cli/live_monitor.py`

### Functions

#### `def main()`
---

## `queen/cli/monitor_stream.py`

### Functions

#### `def _fmt(x)`
#### `def _render(rows: List[dict])`
#### `def _graceful(*_)`
#### `def main()`
---

## `queen/cli/morning_intel.py`

### Functions

#### `def main()`
---

## `queen/cli/run_strategy.py`

### Functions

#### `def _dummy_ohlcv(n: int=180, interval: str='1m')`
#### `def _wire_minimals(df: pl.DataFrame, *, sps_level: float, regime_cycle: tuple[str, str, str]=('TREND', 'RANGE', 'VOLATILE'))`
#### `def main()`
---

## `queen/cli/show_snapshot.py`

### Functions

#### `def _load_snapshot()`
#### `def main()`
---

## `queen/cli/symbol_scan.py`

### Functions

#### `def _print_table(rows: List[Dict[str, Any]])`
#### `def main()`
---

## `queen/cli/universe_scanner.py`

> Production-grade NSE/BSE universe scanner with fundamental analysis

### Functions

#### `def load_and_prefilter_symbols(symbols_path: Path, max_symbols: Optional[int]=None)`
Load symbols from NSE master CSV and aggressively pre-filter

#### `def calculate_volatility(df: pl.DataFrame)`
20-day ATR%

#### `def calculate_liquidity_score(df: pl.DataFrame, avg_volume: float)`
Recent volume vs 20-day average

#### `def calculate_momentum_score(df: pl.DataFrame)`
Current price vs 50-EMA (100 = neutral)

#### `def calculate_beta(df: pl.DataFrame, nifty_df: pl.DataFrame)`
Beta vs Nifty 50 (20-day)

#### `def calculate_spread_cost(df: pl.DataFrame)`
Intraday spread cost proxy using OHLC

#### `def get_delivery_percentage(symbol: str, hist_df: pl.DataFrame)`
Delivery percentage (proxy - replace with real NSE data)

#### `def score_parameter(value: Optional[float], ideal_range: tuple)`
Score 0-10 based on proximity to ideal range

#### `def score_fundamentals(fundamentals: Dict[str, Any])`
Score fundamentals 0-10 for trading suitability

#### `def run_cli()`
### Constants

- `MIN_AVG_DAILY_VALUE = 10000000`
- `MIN_LISTING_DAYS = 180`
- `MIN_MARKET_CAP = 500000000`
- `MAX_PLEDGED_PCT = 50.0`
- `MIN_PROMOTER_HOLDING = 20.0`
- `MAX_DEBT_TO_EQUITY = 2.0`
- `INTRADAY_WEIGHTS = {'volatility': 0.2, 'liquidity': 0.2, 'spread_cost': 0.15, '`
- `BTST_WEIGHTS = {'delivery': 0.2, 'momentum': 0.15, 'volatility': 0.15, 'bet`
- `IDEAL_RANGES = {'volatility_intraday': (2.0, 5.0), 'volatility_btst': (1.5,`
- `tier = 'Exclude'`
- `tier = 'Tier 1: Intraday Core'`
- `tier = 'Tier 2: BTST Core'`
- `tier = 'Tier 3: Mixed'`

---

## `queen/cli/validate_registry.py`

### Functions

#### `def _make_df(n: int=300)`
#### `def main()`
### Constants

- `SAMPLE_INDICATORS = ['atr', 'bollinger_bands', 'supertrend', 'adx_dmi', 'lbx']`

---

## `queen/daemons/__init__.py`

> Queen Daemon Manager (forward-compatible)

Usage:
  python -m queen.daemons list
  python -m queen.daemons clock [clock-args...]
  python -m queen.daemons scheduler [scheduler-args...]
  python -m queen.daemons alert [alert-args...]
  python -m queen.daemons alert2 [alert_v2-args...]

### Functions

#### `def _list_daemons()`
#### `def _run_child(modpath: str, child_argv: list[str])`
#### `def run_cli(argv: list[str] | None=None)`
### Constants

- `__version__ = '3.1.0'`

---

## `queen/daemons/__main__.py`

> Entry point for Queen Daemon Manager (`python -m queen.daemons`).

---

## `queen/daemons/alert_daemon.py`

### Classes

#### `class ThresholdRule`
**Methods:**
- `def check(self, last_close: float)`

#### `class Notifier`
**Methods:**
- `def __init__(self, log_only: bool=False, emit_jsonl: bool=False, http_post: Optional[str]=None, http_timeout: float=3.0)`
- `def _jsonl_write(self, payload: dict)`

### Functions

#### `def check(self, last_close: float)`
#### `def _parse_args(argv: Optional[List[str]]=None)`
#### `def __init__(self, log_only: bool=False, emit_jsonl: bool=False, http_post: Optional[str]=None, http_timeout: float=3.0)`
#### `def _jsonl_write(self, payload: dict)`
#### `def run_cli(argv: Optional[List[str]]=None)`
---

## `queen/daemons/alert_v2 copy.py`

### Functions

#### `def _backfill_days(start: date, max_days: int)`
#### `def _timeframe_key(tf: str)`
#### `def _min_bars_for(rule: Rule)`
Priority:
1) YAML override: rule.params.min_bars
2) Settings policy for indicators: indicator_policy.min_bars_for_indicator()
3) Heuristics from DEFAULTS['ALERTS'] for pattern/price

#### `def _days_for_interval(interval: str, need_bars: int)`
#### `def _desired_window(days_back: int)`
#### `def _clamp_to_listing(symbol: str, start: date, end: date)`
#### `def run_cli()`
### Constants

- `color_ok = True`
- `color_ok = False`

---

## `queen/daemons/alert_v2.py`

### Functions

#### `def _backfill_days(start: date, max_days: int)`
#### `def _min_bars_for(rule: Rule)`
Priority:
1) YAML override (rule.params.min_bars)
2) Settings policy for indicators (indicator_policy.min_bars_for_indicator)
3) Heuristics for pattern/price

#### `def _days_for_interval(interval: str, need_bars: int)`
#### `def _desired_window(days_back: int)`
#### `def _clamp_to_listing(symbol: str, start: date, end: date)`
#### `def run_cli()`
### Constants

- `market_open = True`

---

## `queen/daemons/live_engine.py`

### Classes

#### `class MonitorConfig`
### Functions

#### `def _cpr_from_last_completed_session(df: pl.DataFrame)`
Calendar-aware CPR from the last *completed* session present in df.

Logic:
  - Build a date column from timestamp in IST.
  - Identify the last completed session date:
      • If df contains today's date → use the previous date present.
      • Else → use the last date present.
  - Compute prior-day H/L and last close from that date's rows.
  - Return (H+L+C)/3 or None on failure.

#### `def _fmt(x)`
#### `def _compact_table(rows: List[Dict])`
#### `def _expanded_table(rows: List[Dict])`
#### `def _structure_and_targets(last_close: float, cpr, vwap, rsi, atr, obv)`
### Constants

- `DEFAULT_INTERVAL_MIN = 15`
- `__all__ = ['MonitorConfig', 'run_live_console', '_one_pass']`

---

## `queen/daemons/morning_intel.py`

### Classes

#### `class ForecastRow`
### Functions

#### `def _buy_sell_hold(score: int)`
#### `def _fmt_last(s: pl.Series)`
#### `def _ema_bias(daily_df: pl.DataFrame)`
EMA20/50/200 staircase bias from daily candles.

#### `def _supertrend_bias(df: pl.DataFrame)`
#### `def _vwap_zone(cmp_: Optional[float], vwap_: Optional[float])`
#### `def _score_and_reasons(ema_bias: str, supertrend_bias: str, rsi_val: Optional[float], cmp_: Optional[float], vwap_: Optional[float], e50_last: Optional[float])`
#### `def run_cli(next_session: Optional[date]=None)`
### Constants

- `st_compute = None`
- `e50_last = None`

---

## `queen/daemons/scheduler.py`

### Functions

#### `def run_cli(argv: list[str] | None=None)`
---

## `queen/docs/queen_todo.py`

> A standalone executable roadmap tracker for the Queen Quant stack.
✅ Prints active and planned tasks in colorized Rich tables.
✅ Exports to JSON / Markdown for persistence.
✅ Keeps a single source of truth for all modules (settings, market, daemons, regimes, utils).

### Functions

#### `def get_task_status_map()`
Return a {filename: status_icon} dict for visualization.

#### `def _print_sprint_snapshot()`
#### `def print_roadmap()`
#### `def export_roadmap()`
### Constants

- `TODAY_DONE = ['Upstox fetcher v9.6 — full timeframe support (schema-drive`
- `TOMORROW_PLAN = ['Alert daemon v2 — YAML/JSON rules, SMA/RSI/VWAP, cooldown/`
- `ROADMAP = {'Environment & Settings System': {'status': '🟦 Planned', 'g`

---

## `queen/fetchers/__init__.py`

---

## `queen/fetchers/fetch_router.py`

### Functions

#### `def _chunk_list(data: List[str], n: int)`
Split list into chunks of size n.

#### `def _generate_output_path(mode: str)`
Return file path for saving batch output.

#### `def run_cli()`
### Constants

- `intraday_kwargs = {}`
- `eff_interval = None`
- `cycle = 0`

---

## `queen/fetchers/upstox_fetcher.py`

### Functions

#### `def _min_rows_from_settings(token: str, fallback: int)`
Allow per-timeframe overrides via SETTINGS.FETCH, e.g.:
FETCH.MIN_ROWS_AUTO_BACKFILL_5M = 120
FETCH.MIN_ROWS_AUTO_BACKFILL_15M = 90
FETCH.MIN_ROWS_AUTO_BACKFILL = 80  # global

#### `def _headers()`
#### `def _merge_unique_sort(dfs: list[pl.DataFrame])`
#### `def _estimate_days_for_bars(unit: str, interval_num: int, bars: int)`
Convert bars → approx trading days (NSE ~375 minutes/day).

#### `def _resolve_intraday_threshold(interval_token: str | int, unit: str, interval_num: int, explicit_thr: int | None)`
Decide the min-rows threshold and return (value, source_label).
Precedence:
  1) explicit_thr (function arg)
  2) SETTINGS.FETCH.MIN_ROWS_AUTO_BACKFILL_{TOKEN} or global MIN_ROWS_AUTO_BACKFILL
  3) timeframes.MIN_ROWS_AUTO_BACKFILL table (minutes_key)

#### `def run_cli()`
### Constants

- `_MIN_ROWS_AF = {5: 120, 15: 80, 30: 60, 60: 40}`
- `_DEF_AF_DAYS = 2`

---

## `queen/helpers/__init__.py`

> Lightweight helpers package init (lazy submodule access).

Usage:
    from queen.helpers import io
    io.append_jsonl(...)

    # When (and only when) you actually need them:
    from queen.helpers import market, instruments, logger, pl_compat

### Functions

#### `def __getattr__(name: str)`
#### `def __dir__()`
### Constants

- `__all__ = ['io', 'logger', 'pl_compat', 'market', 'instruments']`

---

## `queen/helpers/common.py`

### Functions

#### `def utc_now_iso()`
UTC timestamp like 2025-10-27T06:41:12.323113Z.

#### `def next_candle_ms(now_ist: datetime, interval_min: int)`
#### `def normalize_symbol(s: str | None)`
Uppercase, stripped, empty-safe symbol normalization.

#### `def logger_supports_color(logger: logging.Logger)`
True iff output stream is a TTY and NO_COLOR is not set.

#### `def colorize(text: str, color_key: str, palette: Dict[str, str], enabled: bool)`
Wrap `text` with ANSI codes from `palette` (expects keys: 'cyan','yellow','green','red','reset').

#### `def timeframe_key(tf: str)`
Map raw tokens to policy context keys: '5m'→'intraday_5m', '1h'→'hourly_1h', '1d'→'daily', etc.

#### `def indicator_kwargs(params: Dict[str, Any] | None, *, deny: set[str] | None=None)`
Keep only indicator-native kwargs (e.g., length=14); drop policy/meta knobs.

### Constants

- `_ALIASES = {'d': 'daily', 'day': 'daily', 'daily': 'daily', '1d': 'dail`
- `_META_INDICATOR_KEYS = {'min_bars', 'timeframe', 'context', 'context_key', 'need', `

---

## `queen/helpers/fetch_utils.py`

### Functions

#### `def warn_if_same_day_eod(from_date: str | date | None, to_date: str | date | None)`
---

## `queen/helpers/instruments.py`

### Functions

#### `def _instrument_paths_for(mode: str)`
#### `def _all_instrument_paths()`
#### `def list_intraday_symbols()`
v9 shim for older imports. Uses active_universe filter if available,
otherwise returns the full INTRADAY instrument list.

#### `def _read_any(path: Path)`
Polars-first reader for parquet/csv/json/ndjson using shared IO layer.

#### `def _normalize_columns(df: pl.DataFrame)`
Normalize and sanitize instrument columns across all exchanges.

#### `def load_instruments_df(mode: str='MONTHLY')`
#### `def _merged_df_all_modes()`
#### `def get_listing_date(symbol: str)`
Return the listing date for a given symbol, or None if unavailable.

#### `def get_instrument_map(mode: str='MONTHLY')`
#### `def resolve_instrument(symbol_or_key: str, mode: str='MONTHLY')`
Resolve a symbol or instrument key to ISIN (with normalization).

#### `def get_symbol_from_isin(isin: str, mode: str='MONTHLY')`
Reverse lookup: ISIN → symbol.

#### `def get_instrument_meta(symbol: str, mode: str='MONTHLY')`
Return dict with symbol, isin, and (optional) listing_date.

#### `def validate_historical_range(symbol: str, start_date: date, mode: str='MONTHLY')`
Ensure the requested range does not predate listing.

#### `def list_symbols(mode: str='MONTHLY')`
#### `def clear_instrument_cache()`
#### `def cache_info()`
#### `def _active_universe_csv()`
#### `def load_active_universe()`
Load 'active_universe.csv' and normalize symbols.

#### `def filter_to_active_universe(symbols: Iterable[str])`
#### `def list_symbols_from_active_universe(mode: str='MONTHLY')`
If {PATHS['UNIVERSE']}/active_universe.csv exists, return intersection.

### Constants

- `VALID_MODES = ('INTRADAY', 'WEEKLY', 'MONTHLY', 'PORTFOLIO')`
- `INSTRUMENT_COLUMNS = ['symbol', 'isin', 'listing_date']`

---

## `queen/helpers/intervals.py`

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

### Functions

#### `def _coerce_token(v: Tokenish)`
Turn legacy minute numbers and canonical 'unit:n' into normalized tokens.

#### `def parse_minutes(value: Tokenish)`
Return total minutes for an intraday token/number.

#### `def to_fetcher_interval(value: Tokenish)`
Canonical interval string for fetchers (delegates to TF).

#### `def classify_unit(value: Tokenish)`
Return 'minutes' | 'hours' | 'days' | 'weeks' | 'months'.

#### `def to_token(value: Tokenish)`
Coerce legacy minute ints and canonical 'unit:n' into a normalized token string.

#### `def is_intraday(token: Tokenish)`
Return True if token represents minutes/hours (intraday).

### Constants

- `__all__ = ['parse_minutes', 'to_fetcher_interval', 'classify_unit', 't`

---

## `queen/helpers/io.py`

### Functions

#### `def _p(path: str | Path)`
#### `def ensure_dir(path: str | Path)`
#### `def _atomic_write_bytes(path: Path, data: bytes)`
#### `def read_json(path: str | Path)`
#### `def write_json(data: Any, path: str | Path, *, indent: int=2, atomic: bool=True)`
#### `def safe_write_parquet(df: pl.DataFrame, path: str | Path)`
Write parquet safely with auto-dir + atomic rename + fallback logging.

#### `def read_csv(path: str | Path)`
#### `def write_csv(df: pl.DataFrame, path: str | Path, *, atomic: bool=True)`
#### `def read_parquet(path: str | Path)`
#### `def write_parquet(df: pl.DataFrame, path: str | Path, *, atomic: bool=True)`
#### `def append_jsonl(path: str | Path, record: dict)`
#### `def read_jsonl(path: str | Path, limit: Optional[int]=None)`
#### `def tail_jsonl(path: str | Path, n: int=200)`
#### `def read_any(path: str | Path)`
#### `def read_text(path: str | Path, default: str='')`
#### `def write_text(path: str | Path, content: str, *, atomic: bool=True)`
---

## `queen/helpers/logger.py`

### Classes

#### `class JSONLFormatter(logging.Formatter)`
**Methods:**
- `def format(self, record: logging.LogRecord)`

### Functions

#### `def _resolve_log_cfg()`
Resolve log file path and LOGGING settings once.
Order of precedence:
    1️⃣ Env var override (QUEEN_LOG_FILE)
    2️⃣ settings.LOGGING + settings.PATHS["LOGS"]
    3️⃣ Fallback to queen/data/runtime/logs

#### `def format(self, record: logging.LogRecord)`
### Constants

- `_rich_handler = None`

---

## `queen/helpers/market.py`

> Market Time & Calendar Utilities
--------------------------------
✅ Delegates ALL exchange data to queen.settings.settings (no hardcoded TF tokens)
✅ Provides working-day / holiday logic, market-open gates, and async sleep helpers
❌ Does NOT parse timeframe tokens (delegated to helpers.intervals / settings.timeframes)

### Classes

#### `class _MarketGate`
Async context manager that waits until a desired gate condition is true.

**Methods:**
- `def __init__(self, mode: str='intraday')`

### Functions

#### `def _hours()`
Resolve market hours from settings (upper-cased keys internally), with safe fallbacks.

#### `def _holidays_path()`
Find the holidays file, preferring exchange config; warn if configured path is missing.

#### `def _normalize_holiday_df(df: pl.DataFrame)`
Normalize holiday 'date' column to ISO ('YYYY-MM-DD') and add year for partitioning.

#### `def _read_holidays(path: Path | None)`
#### `def _load_holidays()`
#### `def _holidays()`
#### `def reload_holidays()`
Force a reload of the holidays cache (e.g., when file updated).

#### `def ensure_tz_aware(ts: dt.datetime)`
Coerce a naive datetime to MARKET_TZ; otherwise convert to MARKET_TZ.

#### `def is_holiday(d: date | None=None)`
#### `def is_working_day(d: date)`
#### `def last_working_day(ref: date | None=None)`
#### `def next_working_day(d: date)`
#### `def offset_working_day(start: date, offset: int)`
#### `def _t(hhmm: str)`
#### `def current_session(now: Optional[dt.datetime]=None)`
#### `def is_market_open(now: Optional[dt.datetime]=None)`
#### `def _intraday_available(now: dt.datetime)`
#### `def get_gate(now: Optional[dt.datetime]=None)`
#### `def current_historical_service_day(now: dt.datetime | None=None)`
Return which calendar day should be used for historical service during different sessions.

#### `def get_market_state()`
#### `def is_trading_day(d: date)`
#### `def last_trading_day(ref: date | None=None)`
#### `def next_trading_day(d: date)`
#### `def __init__(self, mode: str='intraday')`
#### `def market_gate(mode: str='intraday')`
#### `def historical_available()`
Placeholder hook for future calendar rules around historical availability.

### Constants

- `_EX_INFO = {}`

---

## `queen/helpers/nse_fetcher.py`

### Functions

#### `def _read_cache()`
#### `def _write_cache(cache: Dict[str, dict])`
#### `def fetch_nse_bands(symbol: str, cache_refresh_minutes: int=30)`
### Constants

- `_HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15`

---

## `queen/helpers/pl_compat.py`

### Functions

#### `def _s2np(s: pl.Series)`
Robust Series → NumPy conversion (always float64).
Works across all Polars versions.

#### `def ensure_float_series(s: pl.Series)`
Guarantee float dtype (for math operations).

#### `def safe_fill_null(s: pl.Series, value: float=0.0)`
Fill nulls safely, forward/backward compatible.

#### `def safe_concat(dfs: list[pl.DataFrame])`
Safe concat that skips None/empty frames.

---

## `queen/helpers/portfolio.py`

### Functions

#### `def _finite(x: float)`
#### `def _sanitize_entry(sym: str, pos: dict)`
#### `def list_books()`
#### `def _load_one(path: Path)`
#### `def load_positions(book: str)`
#### `def position_for(symbol: str, book: str='all')`
#### `def compute_pnl(cmp_price: float, pos: Optional[dict])`
#### `def clear_positions_cache()`
---

## `queen/helpers/rate_limiter.py`

> Quant-Core — Async Token Bucket Rate Limiter.

✅ Async-safe continuous token refill
✅ Settings-integrated defaults (FETCH.MAX_REQ_PER_SEC)
✅ Structured diagnostics via Queen logger
✅ Desynchronized jitter to prevent bursts

### Classes

#### `class AsyncTokenBucket`
Asynchronous continuous-time token bucket with optional diagnostics.

**Methods:**
- `def __init__(self, rate_per_second: Optional[float]=None, name: str='generic', diag: Optional[bool]=None)`

### Functions

#### `def _get(d: dict, *keys, default=None)`
#### `def __init__(self, rate_per_second: Optional[float]=None, name: str='generic', diag: Optional[bool]=None)`
---

## `queen/helpers/schema_adapter.py`

> Queen Schema Adapter — Unified Broker Schema Bridge
------------------------------------------------------
✅ Reads broker schema via settings (single source of truth)
✅ Exposes SCHEMA at module level for consumers (DRY)
✅ Adds get_supported_intervals()/validate helpers for UX/DX
✅ Uses settings-driven log + drift paths
✅ Polars-native builders for candle frames

### Classes

#### `class UpstoxAPIError(Exception)`
**Methods:**
- `def __init__(self, code: str, message: str | None=None)`

### Functions

#### `def _load_schema()`
#### `def _parse_range_token(tok: str)`
#### `def _collect_intraday_supported()`
#### `def _collect_historical_supported()`
#### `def get_supported_intervals(unit: str | None=None, *, intraday: bool | None=None)`
#### `def validate_interval(unit: str, interval: int, *, intraday: bool | None=None)`
#### `def _checksum(cols: list[str])`
#### `def _normalize(candles: list[list[Any]])`
#### `def _safe_select(df: pl.DataFrame, cols: list[str])`
#### `def _safe_parse(df: pl.DataFrame, column: str='timestamp')`
Normalize the timestamp column to tz-aware Datetime in MARKET_TZ_NAME.

Accepted inputs:
  • tz-aware strings (ISO8601, 'Z' or '+hh:mm', with/without fractional secs)
  • naive strings (assumed to be MARKET_TZ_NAME)
  • epoch seconds / milliseconds (int/float)
  • Datetime with/without tz (attach tz if missing)

#### `def to_candle_df(candles: list[list[Any]], symbol: str)`
#### `def finalize_candle_df(df: pl.DataFrame, symbol: str, isin: str)`
#### `def _detect_drift(cols: list[str])`
#### `def _log_drift(cols: list[str])`
#### `def __init__(self, code: str, message: str | None=None)`
#### `def handle_api_error(code: str)`
#### `def df_summary(df: pl.DataFrame, name='DataFrame')`
#### `def print_summary(df: pl.DataFrame, title='Schema Summary')`
#### `def run_cli()`
### Constants

- `DRIFT_LOG_MAX = 500`
- `MARKET_TZ_NAME = 'Asia/Kolkata'`
- `DEFAULT_SCHEMA = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'`

---

## `queen/helpers/shareholding_fetcher.py`

> NSE Shareholding Pattern Fetcher
Fetches promoter, FII, DII, public holdings from NSE's corporate disclosures API
Cache-enabled with 24h TTL

### Functions

#### `def load_cache()`
Load shareholding cache with TTL check

#### `def save_cache(cache: Dict[str, Dict[str, Any]])`
Save cache to disk

#### `def test_cli()`
### Constants

- `SHAREHOLDING_URL = 'https://www.nseindia.com/api/corp-share-holding'`
- `FINANCIAL_RATIOS_URL = 'https://www.nseindia.com/api/quote-equity'`
- `_HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/`

---

## `queen/helpers/tactical_regime_adapter.py`

### Classes

#### `class TacticalRegimeAdapter`
Dynamically adjusts tactical model weights based on market regime.

**Methods:**
- `def __init__(self, regime_name: Optional[str]=None)`
- `def derive(self, metrics: dict)`
  - *Derive and set regime automatically based on (possibly partial) metrics.*
- `def set_regime(self, regime_name: str)`
- `def list_regimes(self)`
- `def adjust_tactical_weights(self, base_weights: Dict[str, float])`
  - *Simple multiplicative adjustment by regime risk + sensitivity.*
- `def blend(self, base_weights: Dict[str, float], normalize: bool=True)`
  - *Return base weights blended by regime, optionally normalized to sum=1.*
- `def to_polars_df(self)`
- `def describe(self)`
- `def validate(self)`
  - *Use regimes.validate() if available; else do minimal checks.*
- `def active_config(self)`
  - *Return current regime config (read-only view).*

### Functions

#### `def __init__(self, regime_name: Optional[str]=None)`
#### `def derive(self, metrics: dict)`
Derive and set regime automatically based on (possibly partial) metrics.

#### `def set_regime(self, regime_name: str)`
#### `def list_regimes(self)`
#### `def adjust_tactical_weights(self, base_weights: Dict[str, float])`
Simple multiplicative adjustment by regime risk + sensitivity.

#### `def blend(self, base_weights: Dict[str, float], normalize: bool=True)`
Return base weights blended by regime, optionally normalized to sum=1.

#### `def to_polars_df(self)`
#### `def describe(self)`
#### `def validate(self)`
Use regimes.validate() if available; else do minimal checks.

#### `def active_config(self)`
Return current regime config (read-only view).

### Constants

- `metrics = {'rsi': 62, 'adx': 25, 'vix_change': -1.5, 'obv_slope': 1.2}`
- `base = {'RScore': 0.5, 'VolX': 0.3, 'LBX': 0.2}`

---

## `queen/intraday_cockpit.py`

> ──────────────────────────────────────────────────────────────────────────────
👑 Queen Cockpit v7.2 — Morning Intelligence System
──────────────────────────────────────────────────────────────────────────────
Author:  Aravind Kumar x GPT-5
Purpose: Autonomous intraday intelligence engine with pre-market analytics

🌄 PRE-MARKET MODULE OVERVIEW
──────────────────────────────────────────────────────────────────────────────

Your cockpit now includes a fully integrated *Morning Intelligence System*,
which auto-runs once per day between 09:00–09:15 IST and gives you:

    1️⃣ Morning Recap
        → Summarizes today’s high-confidence signals from runtime/high_signals.json
        → Displays symbol, RSI, bias, and action

    2️⃣ Multi-Day Trend Analyzer
        → Reads your archived signal files (archive/high_signals_YYYY-MM-DD.json)
        → Shows the last 5 trading days’ average signal strength trend

    3️⃣ Weekly Strength Gauge
        → Calculates a 7-day rolling average of overall sentiment
        → Displays an ASCII bar like [██████░░░░] 6.0/10

    4️⃣ Auto Archival & Reset
        → Archives yesterday’s signals before market open
        → Clears runtime/high_signals.json for the new session
        → Marks completion via runtime/morning_done.txt (so it won’t re-run twice)

──────────────────────────────────────────────────────────────────────────────
🔧 HOW TO USE
──────────────────────────────────────────────────────────────────────────────

AUTO-MODE (Recommended)
────────────────────────
✅ Already wired inside __main__:
    if _time(9, 0) <= _now_ist < _time(9, 15):
        morning_briefing()

This runs your full pre-market dashboard automatically — exactly once per day.

MANUAL-MODE (On-Demand Review)
───────────────────────────────
You can manually trigger any of the following anytime:

    morning_summary()        # Show today’s top signals
    analyze_archive_trend()  # Show 5-day average score trendline
    weekly_strength_gauge()  # Show 7-day rolling sentiment bar
    morning_briefing()       # Full pre-market dashboard (runs all of the above)

──────────────────────────────────────────────────────────────────────────────
📂 FILES & DIRECTORIES
──────────────────────────────────────────────────────────────────────────────
runtime/high_signals.json      → Current day’s signal log
runtime/morning_done.txt       → One-time run flag for today
archive/high_signals_YYYY-MM-DD.json  → Archived past sessions for backtesting

──────────────────────────────────────────────────────────────────────────────
🕓 AUTO-RUN CONDITIONS
──────────────────────────────────────────────────────────────────────────────
• Runs only if time ∈ [09:00, 09:15)
• Runs only if it hasn’t been completed yet for today
• Skips gracefully if already marked complete

──────────────────────────────────────────────────────────────────────────────
💡 Example Console Output
──────────────────────────────────────────────────────────────────────────────
🌄 Morning Briefing — Pre-Market Dashboard
📦 Archived high_signals_2025-11-04.json
🧹 Cleared current high_signals.json for new session

🌅 Morning Recap
FORCEMOT → RSI 62 | Bias: Long | Action: ⚡ Breakout Confirmed
NETWEB   → RSI 58 | Bias: Neutral | Action: 🚀 Watchlist Setup

📈 5-Day Signal Strength Trend
2025-10-31 → Avg Score: 6.5
2025-11-01 → Avg Score: 6.9
2025-11-03 → Avg Score: 7.2
2025-11-04 → Avg Score: 7.7
2025-11-05 → Avg Score: 8.0

📊 7-Day Rolling Strength Gauge
Strength [███████░░░] 7.1/10 → 💪 Moderately Bullish

✅ Morning briefing marked complete for 2025-11-05
──────────────────────────────────────────────────────────────────────────────

### Functions

#### `def log_event(msg: str)`
Append a line to runtime log file.

#### `def wait_until_next_boundary(minutes: int)`
Sleep until the next N-minute boundary.

#### `def load_nse_holidays()`
Load NSE holiday list from JSON file or fallback.

#### `def is_trading_day(d: date)`
#### `def last_trading_day(target: date | None=None)`
Return the most recent valid trading day (YYYY-MM-DD).

#### `def supertrend(df: pl.DataFrame, period: int=SUPER_TREND_PERIOD, multiplier: float=SUPER_TREND_MULTIPLIER)`
Compute Supertrend indicator using ATR-based bands.
Returns df with added columns: 'supertrend', 'supertrend_dir'.

#### `def indicators(df: pl.DataFrame)`
Compute full analytics suite:
  RSI(14), EMA(20/50/200), VWAP, ATR, OBV, CPR,
  Supertrend, VWAP bands, RSI–EMA crossover.
Returns dictionary of computed indicators.

#### `def fetch_intraday(key: str)`
Fetch authenticated Upstox intraday candles (v3) with flexible parsing.
Automatically URL-encodes instrument key and adapts to variable-length candle arrays.

#### `def fetch_daily_ohl(key: str)`
Smart, holiday-aware, cached, and auto-cleaned OHL fetch.
Falls back to intraday OHL post-market if daily unavailable.
Includes flexible candle parsing and encoded instrument keys.

#### `def run_forecast_mode(next_session_date: date)`
Analyze recent market context and generate a tactical plan for the next trading session.
v7.2b — Offline-aware forecast:
Uses daily candles (cached or recent) if intraday data unavailable.

#### `def handle_market_holiday_or_closed_day()`
Handles holiday / non-trading days by running Forecast Mode automatically.
Generates a next-session tactical plan and archives it.

#### `def render_card(sym, key, eod_mode=False)`
Render actionable card per symbol with advanced indicators (v7.1):
- Supertrend, VWAP bands, RSI–EMA cross, and urgency-colored trend meter.

#### `def log_high_confidence_signal(sym: str, cmp_: float, ind: dict, score: float)`
Append every HIGH-urgency breakout signal into runtime/high_signals.json
for daily review or journaling.

#### `def perform_cleanup()`
Trim old cache and alerts post-EOD.

#### `def morning_summary()`
Prints top 5 high-confidence signals from runtime/high_signals.json
sorted by score for quick pre-market review.

#### `def view_archive_summary(target_date: str)`
Quickly view archived high-confidence signals from a specific date.
Example: view_archive_summary("2025-11-04")

#### `def analyze_archive_trend(last_n: int=5)`
Shows the average signal strength trend from the last N archived days.
Example output: "Signal Strength → 6.3 → 7.1 → 7.8 ↑"

#### `def weekly_strength_gauge(last_n: int=7)`
Displays a simple ASCII strength bar based on the rolling average score
across the last N archived days (default = 7).
Example: Strength [██████░░░░] 6.2/10 → Moderately Bullish

#### `def morning_briefing()`
Unified pre-market dashboard that:
  1. Archives and clears yesterday's high signals
  2. Shows top signals from current file (Morning Recap)
  3. Displays 5-day trendline and 7-day rolling strength gauge
  4. Auto-runs only once per day (via .runtime/morning_done.txt flag)

#### `def morning_system_banner(stage: str='startup', duration: float=None, signals: int=None)`
Display and log console banners for the Morning Intelligence System with performance stats.

Args:
    stage (str): One of {"startup", "complete", "skipped"}
    duration (float): Duration of morning briefing (seconds)
    signals (int): Number of signals found during briefing

#### `def view_last_forecast()`
📜 View the most recent archived forecast plan (v7.2+).
Displays symbol-wise tactical summary and overall market bias.

#### `def header(top, bottom, cycles)`
### Constants

- `REFRESH_MINUTES = 5`
- `CACHE_HITS = 0`
- `CACHE_REFRESHES = 0`
- `ACTIVE_SERVICE_DAY = None`
- `LAST_CMP = {}`
- `POSITIONS = {}`
- `TICKERS = {'FORCEMOT': 'NSE_EQ|INE451A01017', 'SMLISUZU': 'NSE_EQ|INE2`
- `SUPER_TREND_PERIOD = 10`
- `SUPER_TREND_MULTIPLIER = 3`
- `live = True`
- `signals_before = 0`
- `signals_after = 0`
- `cycles = 0`
- `movers = []`

---

## `queen/intraday_cockpit_expanded.py`

### Functions

#### `def log_event(msg: str, event_type: str='INFO')`
Write timestamped log entries to daily log files.
✅ Auto-creates a new log file each trading day
✅ Prunes logs older than 7 days automatically
✅ Keeps log directory clean
✅ Non-blocking (won’t interrupt main loop)

#### `def load_nse_holidays()`
Return dict {date: description} for NSE holidays.

#### `def is_trading_day(d: date)`
#### `def last_trading_day(target: date | None=None)`
#### `def load_uc_lc_cache()`
Load persistent UC/LC band cache (auto resets if older than refresh interval).

#### `def save_uc_lc_cache()`
Persist UC/LC band cache.

#### `def fetch_nse_bands(symbol: str, cache_refresh_minutes: int=30)`
Fetch UC/LC price bands for a symbol using NSE's public API.
✅ Auto-casts values to float before caching (prevents mixed-type math errors)
✅ Persists cache for current trading day under STATE_DIR/nse_bands_cache.json
✅ Refreshes cache if data is older than `cache_refresh_minutes`
✅ Logs cache hits/misses via log_event()

#### `def fetch_intraday(key: str)`
Fetch intraday 15-min candles with numeric schema.

#### `def fetch_daily_ohl(key: str)`
Fetch OHL for today or last valid trading day (holiday aware).

#### `def ensure_ohl(key: str, df: pl.DataFrame)`
#### `def indicators(df: pl.DataFrame)`
#### `def build_vdu_dashboard(movers_data: list, refresh_time: str, session: str)`
Render full paged VDU dashboard — rotates through symbols automatically.

#### `def load_target_state()`
Load persistent memory of targets, SLs, re-entry.

#### `def save_target_state(state: dict)`
#### `def render_card(sym, key, eod_mode=False)`
Render rich console card for a symbol with actionable signals.

#### `def process_symbols(eod_mode=False)`
Process each symbol, handle events (targets, SL, reentry), log & summarize.

#### `def wait_until_next_boundary(interval_minutes: int)`
#### `def summarize_logs(days: int=1, export: bool=False)`
Summarize last N days of intraday logs with analytics and exportable metadata.
Exports a CSV containing:
  - Symbol event counts (UC, LC, Target, SL, Re-entry)
  - Header section with Cache Hit Rate, UC/LC counts, and Log Time Window

### Constants

- `ENABLE_DEBUG_LOGGING = True`
- `REFRESH_MINUTES = 3`
- `NSE_CACHE_REFRESH_MINUTES = 30`
- `HEADERS = {'Accept': 'application/json'}`
- `TICKERS = {'NETWEB': 'NSE_EQ|INE0NT901020', 'SMLISUZU': 'NSE_EQ|INE294`
- `VDU_MODE = True`
- `PAGE_SIZE = 3`
- `VDU_PAGE_INDEX = 0`
- `_last_printed_trading_day = None`
- `UC_LC_CACHE = {}`
- `days = 1`
- `session = 'Pre-Open'`
- `session = 'Morning'`
- `session = 'Midday'`
- `session = 'Closing'`
- `session = 'Post-Close'`
- `eod_mode = True`
- `movers_data = []`
- `reentry_alerts = []`
- `focus_line = '[bold magenta]🎯 Action Focus →[/bold magenta] '`

---

## `queen/intraday_cockpit_final.py`

### Functions

#### `def log_event(msg: str, event_type: str='INFO')`
Write timestamped log entries to daily file (auto-cleanup).

#### `def load_nse_holidays()`
#### `def is_trading_day(d: date)`
#### `def last_trading_day(target: date | None=None)`
#### `def load_uc_lc_cache()`
#### `def save_uc_lc_cache()`
#### `def fetch_nse_bands(symbol: str, cache_refresh_minutes: int=30)`
Fetch UC/LC price bands for a symbol using NSE API with caching.

#### `def fetch_daily_ohl(key: str)`
Smart, holiday-aware, cache-backed daily OHL fetch.
Falls back to intraday during post-market (15:30–23:59).

#### `def ensure_ohl(key: str, df: pl.DataFrame)`
Ensure O/H/L/PrevC values exist even if API fails.

#### `def indicators(df: pl.DataFrame)`
Compute RSI, VWAP, OBV, ATR, CPR and EMA with realistic variance.

#### `def fetch_intraday(key: str)`
Fetch authenticated Upstox intraday candles (v3), adapting the interval
dynamically to your REFRESH_MINUTES setting.

Examples:
  REFRESH_MINUTES = 3  → 3-min candles
  REFRESH_MINUTES = 5  → 5-min candles
  REFRESH_MINUTES = 15 → 15-min candles (default)

#### `def fetch_ohl_pair(key: str)`
Fetch both daily and intraday data atomically:
  - Uses authenticated Upstox v3 endpoints.
  - Returns tuple: (ohl_dict, intraday_df)
  - Ensures timestamps align for CPR, EMA, VWAP consistency.

#### `def ensure_ohl(key: str, df: pl.DataFrame | None=None)`
Ensure OHL data is always available and synchronized with intraday.
Uses fetch_ohl_pair() when df missing or out-of-sync.

#### `def render_card(sym, key, eod_mode=False)`
Render actionable card per symbol with smart OHL fetch, live metrics, and alert persistence.

#### `def wait_until_next_boundary(interval_minutes: int)`
Sleep until next boundary (e.g. next 3-minute refresh cycle).

#### `def summarize_pnl()`
Compute per-symbol P&L from journal + current CMP.

#### `def perform_cleanup()`
Auto-cleanup for cache and alerts after EOD (keeps cockpit tidy).

#### `def render_header(top=None, bottom=None, cycle_count=0)`
### Constants

- `REFRESH_MINUTES = 5`
- `NSE_CACHE_REFRESH_MINUTES = 30`
- `HEADERS = {'Accept': 'application/json'}`
- `CACHE_HITS = 0`
- `CACHE_REFRESHES = 0`
- `ACTIVE_SERVICE_DAY = None`
- `TICKERS = {'NETWEB': 'NSE_EQ|INE0NT901020', 'SMLISUZU': 'NSE_EQ|INE294`
- `POSITIONS = {'NETWEB': {'qty': 58, 'avg_price': 4128.47}, 'SMLISUZU': {'`
- `UC_LC_CACHE = {}`
- `live = True`
- `session = 'Pre-Open'`
- `session = 'Live'`
- `session = 'Post-Market'`
- `session = 'Closed'`
- `mode_label = '[green]LIVE Intraday[/green]'`
- `mode_label = '[cyan]Post-Market Intraday[/cyan]'`
- `mode_label = '[yellow]EOD Snapshot[/yellow]'`
- `cycle_count = 0`
- `movers = []`

---

## `queen/server/main.py`

### Functions

#### `def create_app()`
#### `def render(request, tpl_name: str, ctx: dict | None=None)`
Optional helper if some routers still call render().

### Constants

- `analytics = None`

---

## `queen/server/routers/alerts.py`

---

## `queen/server/routers/analytics.py`

### Functions

#### `def list_intraday_symbols()`
### Constants

- `prio = {'BUY': 0, 'ADD': 0, 'HOLD': 1}`

---

## `queen/server/routers/cockpit.py`

### Classes

#### `class ScanRequest(BaseModel)`
#### `class PulseRequest(BaseModel)`
### Functions

#### `def _render(request: Request, tpl_name: str, ctx: Optional[dict]=None)`
#### `def _universe(symbols: Optional[List[str]])`
### Constants

- `prio = {'BUY': 0, 'ADD': 0, 'HOLD': 1}`
- `__all__ = ['router', 'ROUTERS']`

---

## `queen/server/routers/health.py`

### Constants

- `age = None`
- `ok = False`

---

## `queen/server/routers/instruments.py`

---

## `queen/server/routers/intel.py`

### Constants

- `data = []`
- `rows = []`
- `headers = {'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}`

---

## `queen/server/routers/market_state.py`

### Functions

#### `def _session_label(now_ist: datetime)`
### Constants

- `is_market_live = None`
- `data_age = None`
- `is_stale = True`

---

## `queen/server/routers/monitor.py`

### Functions

#### `def list_intraday_symbols()`
### Constants

- `headers = {'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}`
- `headers = {'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}`

---

## `queen/server/routers/pnl.py`

### Constants

- `pnl_abs = None`
- `pnl_pct = None`

---

## `queen/server/routers/portfolio.py`

### Constants

- `out = []`

---

## `queen/server/routers/services.py`

---

## `queen/server/state.py`

> Global runtime state — last tick timestamp for market freshness checks.

### Functions

#### `def set_last_tick(dt)`
#### `def get_last_tick()`
---

## `queen/services/__init__.py`

---

## `queen/services/forecast.py`

### Classes

#### `class ForecastOptions`
### Functions

#### `def _infer_next_session_date(now_ist: datetime)`
#### `def _advice_for(symbol: str, cmp_price: float, score: float, row: Dict, book: str='all')`
Produce simple, transparent advice using holdings + score.
Returns dict with {position, pnl_abs, pnl_pct, advice}.

#### `def _row_to_plan(row: Dict)`
---

## `queen/services/history.py`

### Functions

#### `def load_history(max_items: int=500)`
---

## `queen/services/live.py`

### Functions

#### `def _min_bars(interval_min: int)`
#### `def _safe_float(v)`
#### `def _ctx_from_value(cmp_val: float | None, ref: float | None, eps_pct: float=0.1)`
#### `def _cpr_ctx_with_fallback(cmp_val: float | None, cpr_pp: float | None, vwap: float | None)`
#### `def _ensure_min_width_with_atr(row: Dict, atr: Optional[float])`
### Constants

- `_SETTINGS_MIN_BARS = None`
- `rsi_last = None`
- `prio = {'BUY': 0, 'ADD': 0, 'HOLD': 1}`

---

## `queen/services/morning.py`

### Functions

#### `def _read_json(path: Path, default)`
#### `def _write_json(path: Path, data)`
#### `def _archive_yesterday_signals(now_ist: datetime)`
Archive runtime/high_signals.json → archive/high_signals_YYYY-MM-DD.json (yesterday’s trading day).

#### `def _trend_last_n(n: int=5)`
#### `def _weekly_gauge(n: int=7)`
#### `def run_morning_briefing()`
DRY pre-market routine:
- archives yesterday’s high_signals
- returns summary, last-N trend, weekly gauge
- one-per-day guard (MORNING_FLAG)

#### `def build_briefing_payload(now_ist: datetime)`
---

## `queen/services/scoring.py`

### Functions

#### `def _last(series: pl.Series)`
#### `def _ema_last(df: pl.DataFrame, period: int, column: str='close')`
#### `def compute_indicators(df: pl.DataFrame)`
#### `def _normalize_signal(payload: Dict | None, name: str)`
Turn a registry signal payload into (score, reasons). Clamp to [0..5].

#### `def _fallback_early(df: pl.DataFrame, cmp_: float, vwap_: Optional[float])`
Lightweight early detector when registry signals are absent:
EMA20 upturn, RSI mid-zone upward cross, VWAP reclaim proximity.
Max 3 points.

#### `def _early_bundle(df: pl.DataFrame, cmp_: float, vwap_: Optional[float])`
Fuse registry signals; fallback if none. Max registry contribution = 6.

#### `def score_symbol(indd: Dict[str, float | str])`
#### `def _ladder_from_base(base: float, atr: Optional[float])`
Return (SL, [T1, T2, T3]) strings.

#### `def _non_position_entry(cmp_: float, vwap: Optional[float], ema20: Optional[float], cpr: Optional[float], atr: Optional[float])`
#### `def action_for(symbol: str, indd: Dict[str, float | str], book: str='all', use_uc_lc: bool=True)`
Expects `indd` to optionally include `_df` (pl.DataFrame) for early signals.
    

### Constants

- `_pre_breakout_eval = None`
- `_squeeze_pulse_eval = None`
- `_reversal_stack_eval = None`

---

## `queen/services/symbol_scan.py`

### Functions

#### `def _min_bars_for(rule: Rule)`
Priority:
1) rule.params.min_bars
2) indicator policy (for indicator)
3) patterns policy cushion
4) price fallback

#### `def _days_for_interval(interval: str, need_bars: int)`
#### `def _window(interval: str, need_bars: int)`
Daily/weekly/monthly need a date window; intraday returns (None,None).

---

## `queen/settings/__init__.py`

> Lean settings package initializer.

Intentionally avoids eager re-exports to prevent circular imports and heavy
import-time side effects. Import submodules directly:

  from queen.settings import settings as SETTINGS_MOD
  from queen.settings import indicators as IND
  from queen.settings import timeframes as TF

### Constants

- `__all__ = ()`

---

## `queen/settings/formulas.py`

### Functions

#### `def indicator_names()`
#### `def pattern_names()`
#### `def meta_layer_names()`
#### `def get_indicator(name: str)`
#### `def get_pattern(name: str)`
#### `def get_meta_layer(name: str)`
#### `def validate()`
Light sanity checks: uppercase keys + basic shapes.

### Constants

- `__all__ = ['INDICATORS', 'PATTERNS', 'META_LAYERS', 'COMPOSITE_SCORE',`

---

## `queen/settings/indicator_policy.py`

### Functions

#### `def _find_block(name: str)`
#### `def params_for(indicator: str, timeframe: str)`
Return parameters for (indicator, timeframe).

Resolution order:
    contexts[ctx_key] merged over default  →  default  →  {}
where ctx_key is produced by helpers.common.timeframe_key
  e.g. '15m' → 'intraday_15m', '1h' → 'hourly_1h', '1d' → 'daily'

#### `def has_indicator(name: str)`
#### `def available_contexts(indicator: str)`
#### `def validate_policy()`
Validate both registry and policy-level assumptions.

#### `def _norm(s: str)`
#### `def _alerts_defaults()`
#### `def _safe_int(v: Any, fallback: int)`
#### `def min_bars_for_indicator(indicator: str, timeframe: str)`
Settings-first min bars policy.

Uses DEFAULTS.ALERTS.{INDICATOR_MIN_MULT, INDICATOR_MIN_FLOOR}
and derives a canonical 'length' from known param names.

Special-cases:
  • EMA_CROSS → max(fast, slow)
  • MACD      → use slow_period
  • ICHIMOKU  → use max(tenkan, kijun, senkou_span_b)
  • Volume/VWAP family → slightly lenient

### Constants

- `__all__ = ['params_for', 'has_indicator', 'available_contexts', 'valid`

---

## `queen/settings/indicators.py`

### Functions

#### `def list_indicator_names()`
Return registry keys as-is (case preserved).

#### `def get_block(name: str)`
Case-insensitive access to an indicator block.

#### `def validate_registry()`
Light schema check for INDICATORS layout.

### Constants

- `_VALID_CONTEXTS = {'intraday_10m', 'intraday_15m', 'intraday_30m', 'daily', 'i`
- `__all__ = ['INDICATORS', 'list_indicator_names', 'get_block', 'validat`

---

## `queen/settings/meta_controller_cfg.py`

### Constants

- `META_CTRL = {'model_file': 'tactical_ai_model.pkl', 'retrain_interval_ho`

---

## `queen/settings/meta_drift.py`

### Constants

- `DRIFT_ENTRIES = [{'timestamp': '2025-10-25T11:00:00Z', 'drift': 0.03}, {'tim`

---

## `queen/settings/meta_layers.py`

### Functions

#### `def get_meta_layer(name: str)`
Return a meta-layer block (case-insensitive by key).

#### `def list_meta_layers()`
#### `def required_bars_for_days(name: str, days: int, timeframe_token: str)`
How many bars cover `days` of history at `timeframe_token` for meta-layer `name`.
Delegates to the canonical owner in timeframes.py for DRY.

#### `def required_lookback(name: str, timeframe_token: str)`
Return lookback bars required for (meta-layer, timeframe_token).

#### `def window_days_for_context(name: str, bars: int, timeframe_token: str)`
Days of data needed for `bars` @ `timeframe_token` (meta-layer aware).

#### `def params_for_meta(name: str, timeframe_token: str)`
Return the context dict for (meta-layer, timeframe_token).
Copies the dict to avoid callers mutating settings in-place.

#### `def validate()`
Strict schema & token checks (forward-only).

### Constants

- `_ALLOWED_COMMON = {'divergence_window', 'min_repeat_patterns', 'pattern_count_`

---

## `queen/settings/meta_memory.py`

### Constants

- `MEMORY_SNAPSHOTS = [{'timestamp': '2025-10-25T11:02:00Z', 'top_feature': 'RScor`

---

## `queen/settings/metrics.py`

### Functions

#### `def is_enabled(name: str)`
#### `def enable(names: Iterable[str])`
Forward-only convenience: extend ENABLED with unique names.

#### `def validate()`
#### `def summary()`
### Constants

- `__all__ = ['ENABLED', 'THRESHOLDS', 'FORMATTING', 'is_enabled', 'enabl`

---

## `queen/settings/patterns.py`

### Functions

#### `def _norm(s: str)`
#### `def _group_dict(group: str)`
#### `def get_pattern(group: str, name: str)`
Retrieve pattern definition safely (case-insensitive).

#### `def list_patterns(group: str | None=None)`
List available patterns (optionally by group).

#### `def required_candles(name: str, group: str | None=None)`
Minimum candles the pattern definition requires.

#### `def contexts_for(name: str, group: str | None=None)`
Return the contexts mapping for a pattern (or {}).

#### `def required_lookback(name: str, context_key: str)`
Return lookback bars for (pattern, context_key), with safe fallback.

#### `def validate()`
Validate structure and context tokens. Returns summary stats.

### Constants

- `__all__ = ['JAPANESE', 'CUMULATIVE', 'get_pattern', 'list_patterns', '`
- `_VALID_CONTEXTS = {'intraday_15m', 'daily', 'intraday_5m', 'hourly_1h', 'weekl`

---

## `queen/settings/profiles.py`

### Functions

#### `def get_profile(name: str)`
Retrieve profile configuration by name (case-insensitive).

#### `def all_profiles()`
List all available profile keys.

#### `def window_days(profile_key: str, bars: int, token: str | None=None)`
Return approximate calendar-days window for `bars` of a given timeframe.

#### `def validate()`
Light schema check: keys, types, positive values.

### Constants

- `__all__ = ['PROFILES', 'get_profile', 'all_profiles', 'window_days', '`

---

## `queen/settings/regimes.py`

### Functions

#### `def derive_regime(metrics: dict)`
Derive current regime from metrics (rsi, adx, vix_change, obv_slope).

#### `def get_regime_config(regime: str)`
#### `def list_regimes()`
#### `def color_for(regime: str)`
#### `def validate()`
#### `def to_polars_df()`
Flat view for dashboards / notebooks.

### Constants

- `REGIME_ORDER = ['BEARISH', 'NEUTRAL', 'BULLISH']`

---

## `queen/settings/settings.py`

### Functions

#### `def get_env()`
#### `def _env_base(env: str)`
#### `def _mk(p: Path)`
#### `def _build_paths(env: str)`
#### `def set_env(value: str)`
Switch environment AND rebuild PATHS (forward-only).

#### `def log_file(name: str)`
Return resolved path for a named log stream (e.g., 'CORE').

#### `def resolve_log_path(name: str)`
Alias of log_file(name), kept for back-compat calls in code.

#### `def broker_config(name: str | None=None)`
Return broker mapping for the active/default broker.

#### `def market_timezone()`
#### `def active_exchange()`
#### `def exchange_info(name: str | None=None)`
#### `def market_hours()`
Return hours for the active exchange (PRE_MARKET/OPEN/CLOSE/POST_MARKET).

#### `def alert_path_jsonl()`
#### `def alert_path_sqlite()`
#### `def alert_path_rules()`
#### `def alert_path_state()`
#### `def get_env_paths()`
### Constants

- `_ENV = 'dev'`
- `FETCH = {'max_workers': 8, 'max_req_per_sec': 40, 'max_req_per_min':`
- `SCHEDULER = {'default_interval': '5m', 'default_buffer': 3, 'align_to_ca`
- `LOGGING = {'LEVEL': 'INFO', 'ROTATE_ENABLED': True, 'MAX_SIZE_MB': 25,`
- `DIAGNOSTICS = {'ENABLED': True, 'FETCHER': {'url_debug': True, 'payload_pr`

---

## `queen/settings/tactical.py`

### Functions

#### `def _sum_weights()`
#### `def get_weights(normalized: bool=False)`
Return a {input: weight} map. If normalized=True, force sum to 1.0.

#### `def normalized_view()`
Snapshot suitable for dashboards / CLI.

#### `def validate()`
Light sanity checks.

#### `def summary()`
---

## `queen/settings/timeframes.py`

### Functions

#### `def normalize_tf(token: str)`
#### `def is_intraday(token: str)`
#### `def parse_tf(token: str)`
'5m' → ('minutes', 5), '1mo' → ('months', 1)

#### `def to_fetcher_interval(token: str)`
#### `def tf_to_minutes(token: str)`
#### `def validate_token(token: str)`
Raise if token is not a valid timeframe string.

#### `def bars_for_days(token: str, days: int)`
How many bars cover `days` of history at `token` (e.g., '5m','1d').

#### `def window_days_for_tf(token: str, bars: int)`
Translate 'bars needed' into an approximate calendar-day window.

#### `def get_timeframe(name: str)`
#### `def list_timeframes()`
### Constants

- `MIN_ROWS_AUTO_BACKFILL = {1: 180, 3: 140, 5: 120, 10: 100, 15: 80, 30: 60, 60: 40, 12`
- `DEFAULT_BACKFILL_DAYS_INTRADAY = 2`
- `__all__ = ['TIMEFRAME_MAP', 'TIMEFRAMES', 'MIN_ROWS_AUTO_BACKFILL', 'D`

---

## `queen/settings/universe.py`

> Active Universe Construction Parameters
------------------------------------------
🌐 Purpose:
    Defines weighting, thresholds, and risk filters used to
    build and maintain the active trading universe monthly.

💡 Usage:
    from queen.settings import universe
    factors = universe.FACTORS

### Functions

#### `def summary()`
Return unified configuration overview.

#### `def selection_window_days(timeframe_token: str)`
Days of data typically needed to run selection at `timeframe_token`.

#### `def min_bars_for_selection(timeframe_token: str)`
Minimum bars required to satisfy SELECTION['min_candles'] at `timeframe_token`.

#### `def validate()`
Light checks for config correctness.

### Constants

- `VERSION = '1.0.0'`
- `DESCRIPTION = 'Quant-Core Monthly Universe Model Parameters'`

---

## `queen/settings/weights.py`

### Functions

#### `def get_thresholds(tf: str | None=None)`
Return {'ENTRY': x, 'EXIT': y}. Per-TF overrides fall back to globals.

#### `def fusion_weights_for(present_tfs: list[str])`
Return normalized weights for the given present timeframes.
Falls back to equal weights if nothing is configured.

### Constants

- `THRESHOLDS_GLOBAL = {'ENTRY': 0.7, 'EXIT': 0.3}`
- `THRESHOLDS_PER_TF = {}`
- `_FUSION_TF = {'intraday_5m': 0.35, 'intraday_10m': 0.35, 'intraday_15m': `

---

## `queen/strategies/fusion.py`

### Functions

#### `def _last_float(df: pl.DataFrame, col: str, default: float=0.0)`
#### `def _last_str(df: pl.DataFrame, col: str, default: str='')`
#### `def _regime_to_unit(reg: str)`
#### `def _risk_band(atr_ratio: float)`
#### `def run_strategy(symbol: str, frames: Dict[str, pl.DataFrame], *, tf_weights: Dict[str, float] | None=None)`
Inputs per TF (if present): SPS, Regime_State, ATR_Ratio, (optional CPS/VDU/etc.)
Output structure:
  {
    'symbol': str,
    'per_tf': { tf: { strategy_score, bias, entry_ok, exit_ok, hold_reason, risk_band }, ... },
    'fused':  { score, bias, entry_ok, exit_ok, risk_band }
  }

### Constants

- `W = None`

---

## `queen/strategies/meta_strategy_cycle.py`

### Functions

#### `def _append_jsonl(path: Path, record: dict)`
#### `def _cap_jsonl(path: Path, max_lines: int=5000)`
Trim JSONL to last N lines (keeps file tidy).

#### `def _dummy_ohlcv(n: int=180)`
#### `def _ensure_snapshot_schema(df: pl.DataFrame)`
#### `def _frames_for(symbol: str, tfs: Iterable[str])`
Placeholder for fetch integration — returns dummy frames for now.

#### `def _last_str(df: pl.DataFrame, col: str, default: str='')`
#### `def _utc_now()`
#### `def _emit_records(symbol: str, per_tf: Dict[str, Dict[str, Any]], frames: Dict[str, pl.DataFrame])`
#### `def _write_latest_pointer(parquet_path: Path, jsonl_path: Path)`
Create/update .latest symlinks or copies for dashboards.

#### `def _append_fused_rows(df: pl.DataFrame)`
Append one 'fused' per-symbol row built from TF stack using weights.

#### `def run_meta_cycle(symbols: Iterable[str], tfs: Iterable[str]=('intraday_15m', 'hourly_1h', 'daily'), *, snapshot_parquet: Path | None=None, snapshot_jsonl: Path | None=None)`
#### `def _discover_symbols(limit: int)`
Try to load from universe/instruments if available; else fallback to DEMO.

#### `def main()`
### Constants

- `SNAPSHOT_COLS = ['timestamp', 'symbol', 'timeframe', 'Tactical_Index', 'stra`

---

## `queen/technicals/__init__.py`

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

### Constants

- `__all__ = ['build_registry', 'list_indicators', 'list_signals', 'get_i`

---

## `queen/technicals/indicators/__init__.py`

### Functions

#### `def __getattr__(name: str)`
### Constants

- `__version__ = 'v1.0'`
- `__registry_mode__ = 'settings-driven'`
- `__all__ = ['overlays', 'rsi', 'momentum_macd', 'vol_keltner', 'volume_`

---

## `queen/technicals/indicators/advanced.py`

### Functions

#### `def bollinger_bands(df: pl.DataFrame, period: int=20, stddev: float=2.0, column: str='close')`
Returns (mid, upper, lower) as Series.

#### `def supertrend(df: pl.DataFrame, period: int=10, multiplier: float=3.0)`
Returns a 'supertrend' Series (uptrend uses lower band, downtrend uses upper).

#### `def atr_channels(df: pl.DataFrame, period: int=14, multiplier: float=1.5)`
Returns (upper, lower) ATR channels around close.

#### `def attach_advanced(df: pl.DataFrame)`
Return a cloned DataFrame with advanced columns attached.

---

## `queen/technicals/indicators/adx_dmi.py`

### Functions

#### `def adx_dmi(df: pl.DataFrame, timeframe: str='15m', period: int | None=None, threshold_trend: int | None=None, threshold_consolidation: int | None=None)`
Polars/Numpy hybrid — returns a DataFrame with:
  ['adx', 'di_plus', 'di_minus', 'adx_trend']

Params resolve from settings.indicator_policy (contexts) when timeframe is provided.
You may override with explicit kwargs.

#### `def adx_summary(df_or_out: pl.DataFrame)`
Accepts either the output of adx_dmi() OR a raw DF (in which case we compute adx_dmi()).
Returns a compact dict for cockpit/meta layers.

#### `def lbx(df_or_out: pl.DataFrame, timeframe: str='15m')`
Liquidity Bias (0–1): blend of average ADX and DI alignment.
Accepts either adx_dmi output or a raw DF.

---

## `queen/technicals/indicators/all.py`

### Functions

#### `def _safe_merge(df_base: pl.DataFrame, df_add: pl.DataFrame)`
Safely merge two DataFrames on shared keys (prefers timestamp/symbol).

#### `def _tf_from_context(context: str)`
Map settings context → short timeframe tokens used by some engines.

#### `def attach_all_indicators(df: pl.DataFrame, context: str='intraday_15m')`
Attach core + advanced engines safely, no side-effects.

---

## `queen/technicals/indicators/breadth_cumulative.py`

### Functions

#### `def compute_breadth(df: pl.DataFrame, context: str | None=None, **kwargs)`
#### `def summarize_breadth(df: pl.DataFrame)`
Return structured summary for cockpit/fusion layers.

---

## `queen/technicals/indicators/breadth_momentum.py`

### Functions

#### `def compute_breadth_momentum(df: pl.DataFrame, context: str | None=None, lookback: int=20, **kwargs)`
#### `def summarize_breadth_momentum(df: pl.DataFrame)`
#### `def compute_regime_strength(df: pl.DataFrame)`
### Constants

- `n = 120`

---

## `queen/technicals/indicators/core.py`

### Functions

#### `def sma(df: pl.DataFrame, period: int=20, column: str='close')`
#### `def ema(df: pl.DataFrame, period: int=20, column: str='close')`
#### `def _slope(s: pl.Series, periods: int=1)`
#### `def ema_slope(df: pl.DataFrame, length: int=21, periods: int=1, column: str='close')`
#### `def rsi(df: pl.DataFrame, period: int=14, column: str='close')`
#### `def rsi_last(close: pl.Series, period: int=14)`
Return the latest RSI value; Series-only ops (Polars version friendly).

#### `def macd(df: pl.DataFrame, fast: int=12, slow: int=26, signal: int=9, column: str='close')`
#### `def vwap(df: pl.DataFrame)`
#### `def vwap_last(df: pl.DataFrame)`
#### `def atr(df: pl.DataFrame, period: int=14)`
#### `def atr_last(df: pl.DataFrame, period: int=14)`
Latest ATR value (Series-safe; no Expr truthiness).

#### `def _prev_day_hlc(df: pl.DataFrame)`
#### `def cpr_from_prev_day(df: pl.DataFrame)`
#### `def obv_trend(df: pl.DataFrame)`
#### `def attach_indicators(df: pl.DataFrame, ema_periods=(20, 50), rsi_period: int=14, macd_cfg=(12, 26, 9))`
### Constants

- `__all__ = ['sma', 'ema', 'ema_slope', 'rsi', 'rsi_last', 'macd', 'vwap`

---

## `queen/technicals/indicators/keltner.py`

### Functions

#### `def ema(series: np.ndarray, span: int)`
Compute Exponential Moving Average.

#### `def true_range(high, low, close_prev)`
True range computation.

#### `def compute_atr(high, low, close, period=14)`
Average True Range with Wilder smoothing.

#### `def compute_keltner(df: pl.DataFrame, timeframe: str='intraday_15m')`
Compute Keltner Channel and volatility metrics (headless, settings-driven).

#### `def summarize_keltner(df: pl.DataFrame)`
Return structured summary for tactical layer.

#### `def compute_volatility_index(df: pl.DataFrame)`
Returns a normalized 0–1 volatility intensity score derived from
the Keltner Channel width. Used by Tactical Fusion Engine.

### Constants

- `n = 200`

---

## `queen/technicals/indicators/momentum_macd.py`

### Functions

#### `def ema(series: np.ndarray, span: int)`
Compute Exponential Moving Average (EMA).

#### `def compute_macd(df: pl.DataFrame, timeframe: str='intraday_15m')`
#### `def summarize_macd(df: pl.DataFrame)`
Return structured MACD summary for cockpit/fusion layers.

### Constants

- `n = 200`

---

## `queen/technicals/indicators/volatility_fusion.py`

### Functions

#### `def compute_volatility_fusion(df: pl.DataFrame, timeframe: str='15m')`
Fuse volatility diagnostics from Keltner (+ATR proxy).

#### `def summarize_volatility(df: pl.DataFrame)`
Return structured summary for cockpit/fusion layers.

### Constants

- `n = 250`

---

## `queen/technicals/indicators/volume_chaikin.py`

### Functions

#### `def _ema_np(series: np.ndarray, span: int)`
#### `def chaikin(df: pl.DataFrame, timeframe: str='15m', *, short_period: int | None=None, long_period: int | None=None)`
Compute Chaikin Oscillator & derived volume flow signals.
Returns a DataFrame with:
  'adl', 'chaikin', 'chaikin_norm', 'chaikin_bias', 'chaikin_flow'

#### `def summarize_chaikin(df: pl.DataFrame)`
Compact summary for cockpit/fusion layers.

#### `def attach_chaikin(df: pl.DataFrame, timeframe: str='15m')`
Attach chaikin outputs to the input DF (by row alignment).

---

## `queen/technicals/indicators/volume_mfi.py`

### Functions

#### `def _tf_from_context(context: str)`
#### `def mfi(df: pl.DataFrame, timeframe: str='15m', *, period: int | None=None, overbought: float | None=None, oversold: float | None=None)`
#### `def compute_mfi(df: pl.DataFrame, context: str='intraday_15m')`
Compatibility wrapper for orchestrators/tests that pass 'context'.

#### `def summarize_mfi(df: pl.DataFrame)`
#### `def attach_mfi(df: pl.DataFrame, timeframe: str='15m')`
---

## `queen/technicals/master_index.py`

### Functions

#### `def _scan_package(pkg: str)`
Generic scan: yields (name, module) by looking for:
• EXPORTS dict
• compute_* callables
• NAME + compute()

#### `def master_index()`
Return a master DataFrame with kind/name/module for:
- indicators (registry)
- signals (registry)
- patterns  (explicit scan of queen.technicals.patterns.*)

---

## `queen/technicals/patterns/__init__.py`

### Constants

- `__all__ = ['core', 'composite']`

---

## `queen/technicals/patterns/composite.py`

### Functions

#### `def detect_composite_patterns(df: pl.DataFrame)`
Detects key multi-candle Japanese candlestick patterns (2–3 candles).

Adds columns:
  - pattern_name (str)
  - pattern_bias ("bullish" | "bearish" | "neutral")
  - confidence (int, 0–100)
  - pattern_group ("composite")

Supported Patterns:
  🌅 Morning Star (3-candle bullish reversal)
  🌇 Evening Star (3-candle bearish reversal)
  ☯️ Harami (Bullish/Bearish + Cross)
  🌤 Piercing Line / Dark Cloud Cover
  🕊 Three White Soldiers / Three Black Crows
  ✂️ Tweezers Top / Bottom

---

## `queen/technicals/patterns/core.py`

### Functions

#### `def _false_series(n: int, name: str)`
#### `def _max2(a: pl.Series, b: pl.Series)`
Element-wise max(a, b) that returns a Series (not an Expr).

#### `def _min2(a: pl.Series, b: pl.Series)`
Element-wise min(a, b) that returns a Series (not an Expr).

#### `def _body(o: pl.Series, c: pl.Series)`
#### `def _upper_wick(o: pl.Series, c: pl.Series, h: pl.Series)`
#### `def _lower_wick(o: pl.Series, c: pl.Series, l: pl.Series)`
#### `def detect_doji(df: pl.DataFrame, tolerance: float=0.1, **_)`
Doji: |close - open| <= tolerance * (high - low).

#### `def hammer(df: pl.DataFrame, body_ratio: float=2.0, upper_max_mult: float=1.0, **_)`
Hammer: long lower shadow, small body near high, small upper shadow.

#### `def shooting_star(df: pl.DataFrame, body_ratio: float=2.0, lower_max_mult: float=1.0, **_)`
Shooting Star: long upper shadow, small body near low, small lower shadow.

#### `def bullish_engulfing(df: pl.DataFrame, require_wide: bool=True, **_)`
Bullish Engulfing: previous red body fully engulfed by current green body.

#### `def bearish_engulfing(df: pl.DataFrame, require_wide: bool=True, **_)`
Bearish Engulfing: previous green body fully engulfed by current red body.

---

## `queen/technicals/patterns/runner.py`

### Functions

#### `def run_patterns(df: pl.DataFrame, *, include_core: bool=True, include_composite: bool=True, core_subset: Optional[Iterable[str]]=None, drop_unhit_core: bool=False)`
Return a DataFrame with pattern outputs aligned to `df` rows.

Columns added:
  • Core (bool): doji, hammer, shooting_star, bullish_engulfing, bearish_engulfing
  • Composite: pattern_name (Utf8), pattern_bias (Utf8), confidence (Int64), pattern_group (Utf8)

---

## `queen/technicals/registry.py`

### Classes

#### `class Entry`
### Functions

#### `def _norm(name: str)`
#### `def _resolve_dotted(root_mod, dotted: str)`
Allow EXPORTS to contain dotted names ('module.func').

#### `def _register_many(target: Dict[str, Entry], mod, exports: Dict)`
#### `def _try_module_exports(mod, target: Dict[str, Entry])`
Return number of items registered for this module.

#### `def _autoscan(pkg: str, target: Dict[str, Entry])`
Scan a package for modules and register exports by convention.

#### `def build_registry(force: bool=False)`
Idempotent build for indicators & signals.

#### `def list_indicators()`
#### `def list_signals()`
#### `def get_indicator(name: str)`
#### `def get_signal(name: str)`
#### `def register_indicator(name: str, fn: Callable)`
#### `def register_signal(name: str, fn: Callable)`
---

## `queen/technicals/signals/__init__.py`

> Signals (tactical/pattern/meta) package.

Notes:
- The registry auto-scans this package (and its submodules) with
  pkgutil.walk_packages.
- Keep signal modules here (e.g., tactical/* or simple signal files).
- Expose via EXPORTS, NAME/compute, or compute_<name>() like indicators.

### Constants

- `__all__ = ['fusion', 'tactical', 'templates']`

---

## `queen/technicals/signals/fusion/__init__.py`

### Constants

- `__all__ = []`

---

## `queen/technicals/signals/fusion/cmv.py`

### Functions

#### `def _norm_pm1(arr: np.ndarray, lo: float | None=None, hi: float | None=None)`
#### `def compute_cmv(df: pl.DataFrame)`
Compute Composite Momentum Vector (CMV) and bias.

---

## `queen/technicals/signals/fusion/liquidity_breadth.py`

### Functions

#### `def compute_liquidity_breadth_fusion(df: pl.DataFrame, *, context: str='default')`
Fuse CMV + SPS + Volume into Liquidity–Breadth Index (LBX).

#### `def _norm01(arr: np.ndarray)`
---

## `queen/technicals/signals/fusion/market_regime.py`

### Functions

#### `def _norm01(arr: np.ndarray)`
#### `def compute_market_regime(df: pl.DataFrame, *, context: str='default')`
Compute composite RScore and bias classification.

---

## `queen/technicals/signals/pre_breakout.py`

### Functions

#### `def _boll_params(tf_token: str | None)`
Derive BB-like params from settings.CPR defaults/contexts, else fallback.

#### `def _ensure_bollinger(df: pl.DataFrame, *, period: int, stddev: float, price_col: str='close')`
#### `def compute_pre_breakout(df: pl.DataFrame, *, timeframe: str='intraday_15m', price_col: str='close', volume_col: str='volume')`
Compute CPR-like width and a simple SPS score.

Outputs:
  • cpr_width      — (BB_upper - BB_lower) / |BB_mid|
  • VPR            — volume pressure ratio (if absent upstream → 1.0)
  • SPS            — VPR / (1 + cpr_width)
  • momentum       — close.diff()
  • momentum_smooth— rolling mean of momentum (5)
  • trend_up       — 1 if momentum_smooth > 0 else 0

### Constants

- `n = 200`

---

## `queen/technicals/signals/registry.py`

### Functions

#### `def _search_packages()`
#### `def _canonical(name: str)`
#### `def _register(name: str, obj: Any, module_name: str)`
#### `def _scan_module(mod)`
#### `def build_registry()`
#### `def get(name: str)`
#### `def names()`
#### `def names_with_modules()`
Return [(canonical_name, module_name)] for CLI/debug.

#### `def reset_registry()`
Testing helper: clear cache so discovery runs fresh.

### Constants

- `_DEFAULT_PACKAGES = ['queen.technicals.signals.fusion', 'queen.technicals.signal`

---

## `queen/technicals/signals/reversal_summary.py`

### Functions

#### `def _safe_last(df: pl.DataFrame, col: str, default=None)`
#### `def summarize_reversal_stacks(global_dfs: dict[str, pl.DataFrame])`
Render a Rich summary table of current Reversal Stack alerts.

global_dfs: timeframe -> DataFrame (after compute_reversal_stack)
Requires columns: 'Reversal_Stack_Alert', 'Reversal_Score'

---

## `queen/technicals/signals/tactical/__init__.py`

### Constants

- `__all__ = []`

---

## `queen/technicals/signals/tactical/absorption.py`

### Functions

#### `def detect_absorption_zones(df: pl.DataFrame, *, cmv_col: str='CMV', volume_col: str='volume', mfi_col: str='MFI', chaikin_col: str='Chaikin_Osc', flat_eps: float=0.05, v_trend_lb: int=2, score_weights: Dict[str, float] | None=None)`
Polars-native absorption detector. No Python loops.

Heuristic:
  • Hidden accumulation  : CMV ~ flat, Volume ↑,  MFI ↑,  Chaikin > 0  → +score
  • Hidden distribution : CMV ~ flat, Volume ↑,  MFI ↓,  Chaikin < 0  → -score

#### `def summarize_absorption(df: pl.DataFrame)`
---

## `queen/technicals/signals/tactical/ai_inference.py`

### Functions

#### `def _model_path_default()`
#### `def load_model(model_path: str | None=None)`
#### `def prepare_features(df: pl.DataFrame, features: list[str] | None=None)`
#### `def predict_next_move(model, scaler, df_live: Dict[str, pl.DataFrame], *, features: list[str] | None=None, buy_threshold: float=0.6, sell_threshold: float=0.6)`
#### `def render_ai_forecast(df_out: pl.DataFrame)`
#### `def run_ai_inference(df_live: Dict[str, pl.DataFrame], *, model_path: str | None=None, features: list[str] | None=None)`
### Constants

- `DEFAULT_FEATURES = ['CMV', 'Reversal_Score', 'Confidence', 'ATR_Ratio', 'BUY_Ra`

---

## `queen/technicals/signals/tactical/ai_optimizer.py`

### Functions

#### `def _model_path()`
#### `def _weights_out_path()`
#### `def _feature_names_default()`
#### `def optimize_indicator_weights(model_path: str | None=None, out_path: str | None=None, feature_names: list[str] | None=None)`
---

## `queen/technicals/signals/tactical/ai_recommender.py`

### Functions

#### `def _log_path()`
#### `def _ensure_ratios(df: pl.DataFrame)`
#### `def analyze_event_log(log_path: str | None=None)`
#### `def compute_forecast(df_stats: pl.DataFrame)`
#### `def render_ai_recommender(log_path: str | None=None)`
---

## `queen/technicals/signals/tactical/ai_trainer.py`

### Functions

#### `def _event_log_path()`
#### `def _model_path()`
#### `def load_event_log(path: str | Path | None=None)`
#### `def preprocess(df: pl.DataFrame)`
#### `def train_model(X, y)`
#### `def save_model(bundle, path: str | Path | None=None)`
#### `def run_training(log_path: str | Path | None=None, model_path: str | Path | None=None)`
---

## `queen/technicals/signals/tactical/bias_regime.py`

### Functions

#### `def compute_bias_regime(df: pl.DataFrame, *, cmv_col: str='CMV', adx_col: str='ADX', close_col: str='close', window_atr: int=14, window_flip: int=10)`
Classify regime using ADX strength, CMV direction, ATR expansion, and flip density.

Adds:
  - ATR           : rolling ATR proxy via TR rolling mean
  - ATR_Ratio     : ATR / rolling(ATR)
  - CMV_Flips     : rolling count of sign flips over window_flip
  - Regime_State  : TREND / RANGE / VOLATILE / NEUTRAL
  - Regime_Emoji  : 🟢 / ⚪ / 🟠 / ⚫ with label

### Constants

- `n = 200`

---

## `queen/technicals/signals/tactical/cognitive_orchestrator.py`

> Contract: single-cycle runner
-----------------------------
`run_cognitive_cycle(...)` MUST perform exactly one cognition pass and return.
It must NOT loop, sleep, or block. Looping/scheduling/backoff belong in:
  • `tactical/live_daemon.py`  → retry + checkpoints (can run once or loop)
  • `tactical/live_supervisor.py` → concurrent single-cycle fan-out

This separation prevents nested sleep-loops and keeps tests deterministic.

### Functions

#### `def _maybe(fn)`
#### `def _import_inference()`
#### `def _import_trainer()`
#### `def _import_recommender()`
#### `def _safe_run(label: str, f, *args, **kwargs)`
#### `def run_cognitive_cycle(global_health_dfs: dict[str, pl.DataFrame] | None=None)`
Contract: single-cycle runner (no loops/sleeps).
Accepts optional global_health_dfs mapping (timeframe -> DataFrame).

#### `def run_autonomous_loop(*, interval_sec: int=6 * 60 * 60, df_live: dict[str, pl.DataFrame] | None=None)`
---

## `queen/technicals/signals/tactical/core.py`

> Adaptive Tactical Fusion Engine — blends regime (RScore), volatility (VolX),
and liquidity (LBX) metrics into a unified Tactical Index.

✅ Settings-driven (queen.settings.settings)
✅ Dynamically re-weights based on timeframe (weights.json)
✅ Emits regime classification (Bullish / Neutral / Bearish)
✅ Pure Polars where DF is used; otherwise dict-friendly

### Functions

#### `def _safe_read_json(path: Path | str, fallback: dict=None)`
#### `def _zscore(values: Dict[str, float])`
#### `def _minmax(values: Dict[str, float])`
#### `def compute_tactical_index(metrics: Dict[str, Any] | pl.DataFrame, *, interval: str='15m')`
Blend RScore, VolX, and LBX into a normalized Tactical Index (settings-driven).

### Constants

- `SETTINGS = None`

---

## `queen/technicals/signals/tactical/divergence.py`

### Functions

#### `def detect_divergence(df: pl.DataFrame, *, price_col: str='close', cmv_col: str='CMV', lookback: int=5, threshold: float=0.02)`
Detect CMV–Price divergences (momentum disagreement zones).

#### `def summarize_divergence(df: pl.DataFrame)`
Quick summary string; safe if columns missing/empty.

---

## `queen/technicals/signals/tactical/event_log.py`

### Functions

#### `def _last(df: pl.DataFrame, col: str)`
#### `def log_tactical_events(global_health_dfs: Dict[str, pl.DataFrame])`
Parameters
----------
global_health_dfs : dict[str, pl.DataFrame]
    Mapping { timeframe: df } containing latest tactical data per TF.

Returns
-------
pl.DataFrame
    The freshly created records (one per timeframe).

### Constants

- `SETTINGS = None`

---

## `queen/technicals/signals/tactical/exhaustion.py`

### Functions

#### `def detect_exhaustion_bars(df: pl.DataFrame, *, cmv_col: str='CMV', volume_col: str='volume', high_col: str='high', low_col: str='low', close_col: str='close', lookback_vol: int=20, wick_threshold: float=0.6, cmv_drop: float=0.4)`
Add:
    • Volume_Spike  (× of rolling mean volume)
    • Wick_Ratio    ((range - body) / (body + eps), clamped ≥ 0)
    • CMV_Delta     (first difference of CMV)
    • Exhaustion_Signal  (🟥/🟩/➡️)

Works across older/newer Polars APIs (no Expr.clip usage).

### Constants

- `__all__ = ['detect_exhaustion_bars']`
- `n = 120`

---

## `queen/technicals/signals/tactical/helpers.py`

### Functions

#### `def _norm01(expr: pl.Expr)`
#### `def _atr_fallback(df: pl.DataFrame, lookback: int=14)`
#### `def _lbx_fallback(df: pl.DataFrame)`
#### `def _rscore_blend(lbx_norm: pl.Expr, volx_norm: pl.Expr)`
#### `def compute_tactical_inputs(df: pl.DataFrame, *, context: str='intraday_15m')`
Returns dict: {"RScore": float, "VolX": float, "LBX": float}
Uses native fusion modules if present; otherwise robust fallbacks.

### Constants

- `SETTINGS = None`
- `__all__ = ['compute_tactical_inputs']`

---

## `queen/technicals/signals/tactical/live_daemon.py`

### Functions

#### `def _utc_now()`
#### `def save_checkpoint(status: str, details: str='')`
#### `def send_alert(message: str)`
#### `def run_daemon_once(global_health_dfs: Dict[str, pl.DataFrame] | None=None)`
Run exactly one cognition cycle; return True on success.

#### `def run_daemon(global_health_dfs: Dict[str, pl.DataFrame] | None=None, interval_sec: int | None=None, once: bool=False)`
Run cognition cycles forever (or once if `once=True`).

### Constants

- `SETTINGS = None`

---

## `queen/technicals/signals/tactical/live_supervisor.py`

### Functions

#### `def _utc_now()`
#### `def _save_health(status: Dict[str, Any])`
### Constants

- `SETTINGS = None`
- `cycle = 0`

---

## `queen/technicals/signals/tactical/meta_controller.py`

### Functions

#### `def _load_weights_dict()`
#### `def _P()`
#### `def _load_state()`
#### `def _save_state(st: Dict[str, Any])`
#### `def _hours_since(ts: str | None)`
#### `def _detect_drift(model_path: Path, event_log_path: Path, drift_threshold: float)`
#### `def _append_meta_memory_row(state: Dict[str, Any])`
#### `def _maybe_retrain(state: Dict[str, Any], drift_flag: bool)`
#### `def meta_controller_run()`
### Constants

- `SETTINGS = None`
- `DEFAULTS = {'retrain_interval_hours': 24, 'drift_threshold': 0.1, 'last`

---

## `queen/technicals/signals/tactical/meta_introspector.py`

### Functions

#### `def _load_csv(path: str)`
#### `def _parse_ts(df: pl.DataFrame, col: str='timestamp')`
#### `def run_meta_introspector()`
### Constants

- `MEMORY_LOG = 'queen/data/runtime/logs/meta_memory_log.csv'`
- `DRIFT_LOG = 'queen/data/runtime/logs/meta_drift_log.csv'`

---

## `queen/technicals/signals/tactical/reversal_stack.py`

### Functions

#### `def compute_reversal_stack(df: pl.DataFrame, *, bias_col: str='Regime_State', div_col: str='Divergence_Signal', squeeze_col: str='Squeeze_Signal', trap_col: str='Liquidity_Trap', exhaust_col: str='Exhaustion_Signal', out_score: str='Reversal_Score', out_alert: str='Reversal_Stack_Alert')`
Confluence score (BUY/SELL/Stable) using vectorized rules.

### Constants

- `n = 60`

---

## `queen/technicals/signals/tactical/squeeze_pulse.py`

### Functions

#### `def detect_squeeze_pulse(df: pl.DataFrame, *, bb_upper_col: str='bb_upper', bb_lower_col: str='bb_lower', keltner_upper_col: str='keltner_upper', keltner_lower_col: str='keltner_lower', squeeze_threshold: float=0.015, out_col: str='Squeeze_Signal')`
Flags:
⚡ Squeeze Ready  (BB inside Keltner)
🚀 Squeeze Release (BB across/outside Keltner with width expansion)
➡️ Stable  (otherwise)

#### `def summarize_squeeze(df: pl.DataFrame, col: str='Squeeze_Signal')`
### Constants

- `n = 200`

---

## `queen/technicals/signals/tactical/tactical_liquidity_trap.py`

### Functions

#### `def detect_liquidity_trap(df: pl.DataFrame, *, cmv_col: str='CMV', sps_col: str='SPS', mfi_col: str='MFI', chaikin_col: str='Chaikin_Osc', threshold_sps: float=0.85, lookback: int=5, out_col: str='Liquidity_Trap', out_score_col: str='Liquidity_Trap_Score')`
Vectorized trap detection.

Rules (per bar):
  • CMV sign flip AND SPS exhaustion (post-peak cool-off)
  • + bearish absorption: Chaikin<0 & MFI↓  → 🟥 Bear Trap (short squeeze risk)
  • + bullish absorption: Chaikin>0 & MFI<40 → 🟩 Bull Trap (long liquidation risk)

Outputs:
  - {out_col}: 🟥/🟩/➡️
  - {out_score_col}: +2 (bear trap), -2 (bull trap), 0 (stable)

### Constants

- `__all__ = ['detect_liquidity_trap']`
- `n = 120`

---

## `queen/technicals/signals/tactical/tactical_meta_dashboard.py`

### Functions

#### `def _paths()`
#### `def load_drift_log()`
#### `def show_meta_config()`
#### `def render_indicator_weights()`
#### `def plot_drift_timeline(df: pl.DataFrame)`
#### `def render_meta_dashboard()`
---

## `queen/technicals/signals/templates/__init__.py`

### Constants

- `__all__ = []`

---

## `queen/technicals/signals/templates/indicator_template.py`

### Functions

#### `def _params_for(tf_token: str | None)`
#### `def compute_indicator(df: pl.DataFrame, *, timeframe: str | None=None, column: str='close')`
Minimal headless pattern:
• validates required columns
• reads params from settings.indicators
• appends result columns

#### `def summarize_indicator(df: pl.DataFrame)`
### Constants

- `IND_NAME = 'TEMPLATE_INDICATOR'`
- `n = 200`

---

## `queen/technicals/signals/utils_patterns.py`

### Functions

#### `def _catalog()`
#### `def _norm_tf(s: str)`
#### `def _titleize(name: str)`
#### `def get_patterns_for_timeframe(timeframe: str)`
Return [(label, family_icon), ...] applicable to a given timeframe key.

#### `def get_random_pattern_label(timeframe: str)`
#### `def get_deterministic_pattern_label(timeframe: str, index: int)`
#### `def get_patterns_grouped_by_family(timeframe: str)`
Return { family_name: [(label, icon), ...] } filtered by timeframe.

### Constants

- `__all__ = ['get_patterns_for_timeframe', 'get_random_pattern_label', '`

---

## `queen/technicals/strategy/__init__.py`

### Constants

- `__all__ = []`

---

## `queen/test_scanner.py`

> Test the scanner with a small symbol set

### Functions

#### `def main()`
---

## `queen/tests/market_playback.py`

> Simulates a full market day (PRE → LIVE → POST) with CLI flags.
---------------------------------------------------------------
Now includes:
✅ --force-live   → Override holidays/weekends
✅ --no-clock     → Skip MarketClock for pure playback
✅ Live tick counter in footer
✅ Color-coded gate legend
✅ Column-aligned, terminal-polished output

### Functions

#### `def parse_args()`
#### `def style_gate(gate: str)`
#### `def show_legend()`
#### `def print_state(now: dt.datetime, force_live: bool)`
Render playback state line with aligned columns.

### Constants

- `tick_counter = 0`
- `tick_count = 0`
- `clock = None`

---

## `queen/tests/market_test.py`

### Functions

#### `def test_holidays()`
#### `def test_working_days()`
#### `def test_market_state()`
#### `def test_time_bucket()`
#### `def run_sync_tests()`
### Constants

- `n = 0`

---

## `queen/tests/smoke_absorption.py`

### Functions

#### `def _build_mock(n: int=200)`
#### `def test()`
---

## `queen/tests/smoke_advanced.py`

### Functions

#### `def _mk_ohlcv(n: int=240)`
#### `def _is_numeric_dtype(dt: pl.DataType)`
#### `def test_attach_advanced()`
#### `def test_components_direct()`
---

## `queen/tests/smoke_ai_inference.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_ai_optimizer_paths.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_ai_trainer_paths.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_all.py`

### Functions

#### `def _mk_ohlcv(n: int=120)`
#### `def test_attach_all()`
---

## `queen/tests/smoke_bias_regime.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_bias_regime_latency.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_breadth.py`

### Functions

#### `def _make_cmv_sps(n: int=180)`
Synthetic CMV/SPS series — simple sin/cos with noise.

#### `def _is_float_dtype(dt)`
#### `def test_compute_columns_and_types()`
#### `def test_summary_keys_and_ranges()`
---

## `queen/tests/smoke_breadth_combo.py`

### Functions

#### `def _mk_breadth_frame(n: int=240)`
#### `def _assert_range(series: pl.Series, lo: float, hi: float, name: str)`
#### `def test_breadth_combo()`
---

## `queen/tests/smoke_breadth_momentum.py`

### Functions

#### `def _assert_between(x: float, lo: float, hi: float)`
#### `def _assert_bias(token: str)`
#### `def test_cmv_sps_path()`
#### `def test_adv_dec_path()`
---

## `queen/tests/smoke_chaikin.py`

### Functions

#### `def _mk(n: int=120)`
#### `def _is_float(dt)`
#### `def test_columns_and_types()`
#### `def test_attach_and_summary()`
### Constants

- `EXPECTED = {'chaikin', 'chaikin_flow', 'chaikin_norm', 'chaikin_bias', `

---

## `queen/tests/smoke_cmv_latency.py`

### Functions

#### `def _build_df(n: int=2000)`
#### `def _best_of_3(fn)`
#### `def test_latency()`
---

## `queen/tests/smoke_cognitive_orchestrator.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_divergence.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_divergence_latency.py`

### Functions

#### `def _build_df(n: int=2000)`
#### `def test_latency()`
---

## `queen/tests/smoke_event_log.py`

### Functions

#### `def test()`
### Constants

- `SETTINGS = None`

---

## `queen/tests/smoke_exhaustion_latency.py`

### Functions

#### `def _gen_df(n: int=2000)`
#### `def test_latency(n: int=2000, rounds: int=3, cap_ms: float=5.0)`
---

## `queen/tests/smoke_fusion_all_latency.py`

### Functions

#### `def _mk_df(n: int=2000)`
#### `def _timeit(fn, *args, repeats=3, **kwargs)`
#### `def test_all_latency()`
### Constants

- `HAVE_LBX = True`
- `compute_lbx = None`
- `HAVE_LBX = False`

---

## `queen/tests/smoke_fusion_latency.py`

### Functions

#### `def _mk_ohlcv(n: int=2000)`
#### `def test_latency()`
---

## `queen/tests/smoke_fusion_lbx.py`

### Functions

#### `def _mk_ohlcv(n=400)`
#### `def test()`
---

## `queen/tests/smoke_fusion_market_regime.py`

### Functions

#### `def _mk(n=240)`
#### `def test()`
---

## `queen/tests/smoke_fusion_overall.py`

### Functions

#### `def _mk(n: int=360)`
#### `def _assert_has(df: pl.DataFrame, cols: list[str], tag: str)`
#### `def test()`
---

## `queen/tests/smoke_helpers.py`

### Functions

#### `def _make_df(n: int=25)`
#### `def test_parquet_roundtrip()`
#### `def test_csv_roundtrip()`
#### `def test_json_roundtrip_array()`
#### `def test_read_any_switch()`
#### `def test_jsonl_tail_append()`
#### `def test_s2np_and_float_series()`
#### `def test_safe_concat()`
---

## `queen/tests/smoke_indicators.py`

### Functions

#### `def _is_float_dtype(dt)`
#### `def _is_str_dtype(dt)`
#### `def _as_series(x, *, prefer: tuple[str, ...]=(), df: pl.DataFrame | None=None)`
#### `def _make_df(n: int=400)`
#### `def test_advanced_indicators_shapes()`
#### `def test_adx_dmi_columns_and_types()`
#### `def test_lbx_and_summary_contracts()`
---

## `queen/tests/smoke_intervals.py`

> Ensures helpers.intervals <-> settings.timeframes stay in lockstep.

Checks:
- Normalization round-trips for intraday tokens (e.g., 5 -> "5m")
- Canonical fetcher interval mapping matches TIMEFRAME_MAP / parse_tf
- Unit classification is consistent
- is_intraday() correctness
- Reasonable errors for bad tokens

### Functions

#### `def test_intraday_roundtrip_minutes_to_token()`
#### `def test_parse_minutes_intraday_only()`
#### `def test_fetcher_interval_canonical()`
#### `def test_classify_unit_consistency()`
#### `def test_is_intraday_flag()`
#### `def test_bad_tokens_raise()`
### Constants

- `INTRADAY_TOKENS = ['1m', '3m', '5m', '10m', '15m', '30m', '1h', '2h', '4h']`
- `DAILY_PLUS_TOKENS = ['1d', '1w', '1mo']`

---

## `queen/tests/smoke_io.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_keltner.py`

### Functions

#### `def _make_df(n: int=150)`
#### `def test_keltner_columns()`
#### `def test_volatility_index_range()`
#### `def test_summary_structure()`
---

## `queen/tests/smoke_lbx_latency.py`

### Functions

#### `def _build_df(n: int=2000)`
#### `def _best_of_3(fn)`
#### `def test_latency()`
---

## `queen/tests/smoke_liquidity_trap_latency.py`

### Functions

#### `def _make_df(n: int=2000)`
#### `def test_latency()`
---

## `queen/tests/smoke_liquidity_trap_vector.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_live_daemon.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_live_supervisor.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_macd.py`

### Functions

#### `def _make_df(n: int=200)`
#### `def test_macd_columns()`
#### `def test_summary_keys()`
---

## `queen/tests/smoke_market_regime_latency.py`

### Functions

#### `def _build_df(n: int=2000)`
#### `def _best_of_3(fn)`
#### `def test_latency()`
---

## `queen/tests/smoke_market_time.py`

> Smoke test for market-time helpers
----------------------------------
✅ Confirms settings-driven calendar integration works end-to-end
✅ Ensures no crash on holiday / weekend / after-hours
✅ Lightweight: no external I/O, no Polars writes

### Functions

#### `def test_market_time()`
#### `def test_session_boundaries()`
Each configured session must have start < end.

---

## `queen/tests/smoke_master_index.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_meta_controller.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_meta_dashboard.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_meta_settings_only.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_meta_strategy_cycle.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_meta_timestamps.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_mfi.py`

### Functions

#### `def _mk(n=150)`
#### `def _is_float(dt)`
#### `def test_columns_and_ranges()`
#### `def test_attach_and_summary()`
---

## `queen/tests/smoke_ohlcv.py`

### Functions

#### `def _dummy_df(n: int=120, interval: str='1m')`
#### `def main()`
---

## `queen/tests/smoke_orchestrator_contract.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_overall_latency.py`

### Functions

#### `def _mk(n=2000)`
#### `def test_latency()`
---

## `queen/tests/smoke_paths_models.py`

### Functions

#### `def test_paths_models()`
---

## `queen/tests/smoke_patterns_all.py`

---

## `queen/tests/smoke_patterns_composite.py`

### Functions

#### `def _mk_ohlcv(n: int=120)`
#### `def test_patterns_composite()`
---

## `queen/tests/smoke_patterns_core.py`

### Functions

#### `def _mk_ohlcv(n: int=100)`
#### `def test_patterns_core()`
---

## `queen/tests/smoke_patterns_latency.py`

### Functions

#### `def _mk(n: int=2000)`
#### `def test_latency()`
---

## `queen/tests/smoke_patterns_runner.py`

### Functions

#### `def _mk_ohlcv(n: int=320)`
#### `def test_runner()`
---

## `queen/tests/smoke_pre_breakout.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_registry.py`

### Functions

#### `def test_registry_build()`
---

## `queen/tests/smoke_reversal_stack.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_reversal_summary.py`

### Functions

#### `def main()`
---

## `queen/tests/smoke_rsi.py`

### Functions

#### `def _mk(n=120)`
#### `def test_rsi_series()`
---

## `queen/tests/smoke_show_snapshot.py`

---

## `queen/tests/smoke_signals_registry.py`

### Functions

#### `def _dummy(df, **kwargs)`
---

## `queen/tests/smoke_squeeze_pulse.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_strategy_fusion.py`

### Functions

#### `def _mk(n: int=60, sps: float=0.65)`
#### `def test()`
---

## `queen/tests/smoke_tactical_core.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_tactical_index_modes.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_tactical_inputs.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_technicals_registry.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_template_indicator.py`

### Functions

#### `def test()`
---

## `queen/tests/smoke_utils_patterns.py`

### Functions

#### `def test_get_patterns_for_timeframe()`
#### `def test_random_and_deterministic_labels()`
#### `def test_grouped_by_family()`
### Constants

- `MOCK_PATTERNS = {'japanese': {'hammer': {'contexts': {'intraday_15m': {}, 'd`

---

## `queen/tests/smoke_volatility_fusion.py`

### Functions

#### `def _mk(n=200)`
#### `def _is_float(dt)`
#### `def test_fusion_outputs_and_ranges()`
---

## `queen/tests/smoke_weights.py`

### Functions

#### `def test()`
---

## `queen/tests/test_indicator_kwargs.py`

### Functions

#### `def test_indicator_call_kwargs_filters_meta()`
---

## `queen/tests/test_patterns_core.py`

---
