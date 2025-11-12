# 🧭 Queen Settings Overview — v9.3

Centralized runtime configuration for the **Queen of Quant** system.
Modules read from `settings.py` and friends to keep behavior DRY, discoverable, and environment-aware.

> Repo paths below are clickable in GitHub/VS Code.

---

## 🔗 Quick Links

- **Settings Core**
  - [`settings.py`](./settings.py) — app/env defaults, brokers, FETCH, SCHEDULER, LOGGING, EXCHANGE, paths
  - [`timeframes.py`](./timeframes.py) — timeframe map, parsing, intraday min-rows & default backfill days
  - [`../helpers/intervals.py`](../helpers/intervals.py) — thin wrapper over `timeframes` for helpers

- **Schedulers & Fetchers**
  - [`../daemons/scheduler.py`](../daemons/scheduler.py) — async loop w/ universe refresh (time-based)
  - [`../fetchers/fetch_router.py`](../fetchers/fetch_router.py) — orchestrator (batching, saving)
  - [`../fetchers/upstox_fetcher.py`](../fetchers/upstox_fetcher.py) — broker fetcher + smart intraday bridge

- **Market/Universe Helpers**
  - [`../helpers/market.py`](../helpers/market.py) — market state, candle alignment, sleep helpers
  - [`../helpers/instruments.py`](../helpers/instruments.py) — universe loading, symbol resolution
  - [`../helpers/logger.py`](../helpers/logger.py) — log setup (uses `LOGGING` block)

- **Schemas & Static**
  - `../data/static/api_upstox.json` (resolved via `BROKERS['upstox']['api_schema']`)
  - `../data/static/nse_holidays.json` (resolved via `EXCHANGE.EXCHANGES.*.HOLIDAYS`)

---

## 🧩 Settings Blocks (what they do & who reads them)

| Block           | Purpose                                   | Primary Consumers                       |
| :-------------- | :---------------------------------------- | :-------------------------------------- |
| **APP**         | name/version/env banner                   | logger, CLIs                            |
| **DEFAULTS**    | baseline app knobs (broker, alerts, etc.) | fetchers, routers, helpers              |
| **BROKERS**     | retry/rate/schema paths per broker        | `helpers.broker_config()`, fetchers     |
| **FETCH**       | concurrency & intraday density thresholds | `fetch_router`, `upstox_fetcher`        |
| **SCHEDULER**   | daemon cadence & universe refresh         | `daemons/scheduler.py`                  |
| **LOGGING**     | levels, rotation, file names              | `helpers.logger`                        |
| **DIAGNOSTICS** | debug toggles & payload preview           | fetchers, diagnostics                   |
| **EXCHANGE**    | hours, holidays, instruments & active key | `helpers.market`, `helpers.instruments` |

---

## ⚙️ FETCH — data density & limits

Defined in [`settings.py`](./settings.py).

Keys used by routers/fetchers:

| Key                                   | Default    | Read By                                    | Notes                                      |
| :------------------------------------ | :--------- | :----------------------------------------- | :----------------------------------------- |
| `max_workers`                         | 8          | `fetch_router`                             | async concurrency semaphore                |
| `max_req_per_sec` / `max_req_per_min` | 40 / 400   | rate limiter (if enabled)                  | traffic shaping                            |
| `max_retries`                         | 3          | all fetchers                               | per-request retry attempts                 |
| `max_empty_streak`                    | 5          | (reserved)                                 | guard for repeated empties                 |
| `MIN_ROWS_AUTO_BACKFILL`              | _optional_ | `upstox_fetcher._min_rows_from_settings()` | global fallback threshold                  |
| `MIN_ROWS_AUTO_BACKFILL_<TOKEN>`      | _optional_ | same                                       | per-TF override, e.g. `_5M`, `_15M`, `_1H` |

**Threshold resolution order (intraday):**

1. explicit `min_rows_auto_backfill` argument
2. `FETCH.MIN_ROWS_AUTO_BACKFILL_<TOKEN>` (e.g., `MIN_ROWS_AUTO_BACKFILL_5M`)
3. `FETCH.MIN_ROWS_AUTO_BACKFILL` (global)
4. `timeframes.MIN_ROWS_AUTO_BACKFILL` default map

Example overrides:

```python
FETCH = {
  "max_workers": 8,
  # thinness thresholds (optional)
  "MIN_ROWS_AUTO_BACKFILL": 80,
  "MIN_ROWS_AUTO_BACKFILL_5M": 120,
  "MIN_ROWS_AUTO_BACKFILL_1H": 40,
}


⸻

⏱️ SCHEDULER — daemon cadence & universe refresh

Defined in settings.py￼; consumed by ../daemons/scheduler.py￼.

Key	Default	Purpose
INTERVAL_MINUTES	5	base loop interval for intraday daemon
DEFAULT_MODE	“intraday”	"intraday" or "daily"
MAX_SYMBOLS	250	per-cycle cap
UNIVERSE_REFRESH_MINUTES	60	reload instruments every N minutes (0 disables)
LOG_UNIVERSE_STATS	True	log universe size & diffs
default_interval	“5m”	token used by router alignment
refresh_map	{ “5m”: 30, … }	optional per-token cadence hints
align_to_candle	True	align cycles with candle boundaries

CLI overrides (from scheduler.py):

--interval-minutes 3
--max-symbols 500
--mode intraday|daily
--once

Universe refresh behavior:
The daemon keeps a stopwatch; when UNIVERSE_REFRESH_MINUTES elapses, it reloads INSTRUMENTS and logs size/diff (if LOG_UNIVERSE_STATS).

⸻

📆 EXCHANGE — market hours, holidays, instruments

Defined in settings.py￼; used by helpers.market & helpers.instruments.
	•	EXCHANGE.ACTIVE selects the profile (e.g., "NSE_BSE").
	•	Hours: PRE_MARKET, OPEN, CLOSE, POST_MARKET
	•	Holidays JSON path (per exchange)
	•	Instruments JSON/CSV paths:
	•	INSTRUMENTS.MONTHLY, WEEKLY, INTRADAY (JSON)
	•	PORTFOLIO, APPROVED_SYMBOLS, NSE_UNIVERSE, BSE_UNIVERSE (CSV)

DEFAULTS["EXCHANGE"] is synced from EXCHANGE.ACTIVE for convenience.

⸻

🕒 Timeframes (parsing & conversions)

See timeframes.py￼ (single owner):
	•	TIMEFRAME_MAP — friendly → canonical ("5m" → "minutes:5")
	•	parse_tf, to_fetcher_interval, tf_to_minutes
	•	MIN_ROWS_AUTO_BACKFILL — baseline thinness (minutes map incl. 1h→60, etc.)
	•	DEFAULT_BACKFILL_DAYS_INTRADAY — used by historical bridge when caller omits days

Helper facade: ../helpers/intervals.py￼
	•	parse_minutes("15m") → 15, to_fetcher_interval("1w") → weeks:1, is_intraday(...), etc.

⸻

🧱 Paths (auto-created)

Built from QUEEN_ENV (dev/prod) in settings.py:
	•	PATHS["LOGS"], ["EXPORTS"], ["ALERTS"], ["CACHE"], ["UNIVERSE"], …
	•	Switch env at runtime with settings.set_env("prod").

⸻

🧪 Sanity Checks
	•	timeframes.py runnable: python timeframes.py prints a quick check.
	•	scheduler.py --once runs a single cycle with current settings.
	•	fetch_router.py --mode daily --symbols TCS --from 2025-01-01 --to 2025-01-31
to validate historical paths & save output.

⸻

📌 Notes for contributors
	•	Add new knobs only to settings.py (or the dedicated *settings/*.py module) and read them via helpers/daemons/fetchers — never hard-code.
	•	Keep defaults safe; per-machine overrides can come from environment variables or local patches.
	•	When adding a new broker, populate BROKERS[broker]['api_schema'] and teach the fetcher to read from SCHEMA.

⸻

Last synced: v9.3, November 2025

---

want me to also drop a tiny **badge-style header** (ASCII banner with current `APP.version` and active exchange) at the top of your CLI outputs so it’s visually tied to these settings?
```
