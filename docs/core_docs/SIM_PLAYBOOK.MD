# Queen of Quant — Simulation Playbook

Version: v1 (Auto-Sim: Long-Only, Price-Sized, Add-Only-When-Green, Trailing Stop)

This note explains:

- What the simulator does
- Which knobs you can tune
- What each `sim_*` column means
- How to run the 3 main CLI tools
- A small checklist you can reuse for any symbol/parquet

---

## 1. High-level behaviour

The auto-simulator runs inside `queen/services/actionable_row.py` when:

- `pos_mode="auto"` and
- `auto_side="long"`

Core rules (per symbol):

1. **Long-only synthetic positions**
   - Real broker positions are untouched.
   - Sim positions are tracked via `sim_side`, `sim_qty`, `sim_avg`, etc.

2. **Entry & pyramiding**
   - From `FLAT`:
     - `decision` in `{BUY, ADD}` → open `LONG` with a **price-based unit size**.
   - From `LONG`:
     - `BUY` → treated as another “add” (scale in).
     - `ADD` → allowed _only_ when the position is in profit and passes the unrealised PnL filter.

3. **Price-based unit sizing**
   - Uses `NOTIONAL_PER_UNIT_DEFAULT` from `queen/settings/sim_settings.py`.
   - Approximate rule:

     \[
     \text{units} \approx \frac{\text{NOTIONAL_PER_UNIT_DEFAULT}}{\text{CMP}}
     \]

   - Units are rounded to an integer and clamped between `min_units` and `max_units`.

4. **Capped pyramids**
   - Total sim size is capped at:

     \[
     \text{max position} = \text{MAX_PYRAMID_UNITS} \times \text{unit_size}
     \]

   - Further `BUY`/`ADD` signals beyond the cap are **ignored** and counted.

5. **Trailing stop**
   - While `LONG`, we track `sim_peak = max(cmp)` since entry.
   - Trailing stop level:

     \[
     \text{sim_trail_stop} = \text{sim_peak} \times (1 - \text{TRAIL_PCT})
     \]

   - If `cmp <= sim_trail_stop`:
     - Position is closed.
     - PnL is booked.
     - `sim_exit_reason="TRAILING_STOP"`.

6. **Hard exits & EOD close**
   - `decision` in `{EXIT, AVOID}` or `trade_status == "EXIT"` → hard exit:
     - `sim_exit_reason="HARD_EXIT"`.
   - If `eod_force=True` on the final bar:
     - Any open position is closed.
     - `sim_exit_reason="EOD_FORCED"`, `sim_forced_eod=True`.

7. **Ignored signals (ADD-Only-When-Green)**
   - When `ADD_ONLY_WHEN_GREEN=True`:
     - `ADD` is **ignored** if the position is not in profit or unrealised % is below `ADD_MIN_UNREAL_PCT`.
     - These “ignored” signals are counted and annotated.

---

## 2. Core knobs — `queen/settings/sim_settings.py`

Tune the simulator **only** via this file.

Typical layout:

```python
# queen/settings/sim_settings.py

# Target notional exposure per synthetic unit (in ₹).
NOTIONAL_PER_UNIT_DEFAULT: float = 3_000.0

# Max number of unit-chunks to pyramid into.
MAX_PYRAMID_UNITS: float = 2.0

# Trailing stop as a fraction of sim_peak (0.04 → 4%).
TRAIL_PCT: float = 0.04

# Should we ADD only when the position is in profit?
ADD_ONLY_WHEN_GREEN: bool = True

# Minimum unrealised PnL % required to allow ADD, if ADD_ONLY_WHEN_GREEN is True.
# Example:
#   0.0 → any positive PnL is okay.
#   1.0 → require at least +1% unrealised PnL.
ADD_MIN_UNREAL_PCT: float = 1.0
```
