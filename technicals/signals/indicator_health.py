# ============================================================
# quant/signals/utils_indicator_health.py
# ------------------------------------------------------------
# 🧭 Diagnostic and Warning Utilities for Indicators
# Config-driven with smart log rotation
# ============================================================

import os
import shutil
from datetime import datetime, timezone

import polars as pl
from rich.console import Console
from rich.table import Table

from quant.config import get, get_path

console = Console()

# ============================================================
# ⚙️ Config-driven Log Path + Rotation Parameters
# ============================================================
try:
    LOG_PATH = str(get_path("indicator_health_log"))
except Exception:
    LOG_PATH = "./quant/data/runtime/logs/indicator_health_log.csv"

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

# Dynamic log rotation parameters
MAX_LOG_SIZE_MB = float(get("logging.max_size_mb", 10))
ROTATE_ENABLED = bool(get("logging.rotate", True))
MAX_BACKUPS = int(get("logging.backups", 5))


# ============================================================
# ♻️ Log Rotation Helper
# ============================================================
def _rotate_log_if_needed():
    """Rotate indicator health log if it exceeds configured max size."""
    try:
        if not ROTATE_ENABLED or not os.path.exists(LOG_PATH):
            return

        file_size_mb = os.path.getsize(LOG_PATH) / (1024 * 1024)
        if file_size_mb < MAX_LOG_SIZE_MB:
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_path = LOG_PATH.replace(".csv", f"_{ts}.csv")
        shutil.move(LOG_PATH, rotated_path)

        # Keep only the latest N rotated files
        log_dir = os.path.dirname(LOG_PATH)
        rotated_files = sorted(
            [f for f in os.listdir(log_dir) if f.startswith("indicator_health_log_")],
            reverse=True
        )
        for old_file in rotated_files[MAX_BACKUPS:]:
            try:
                os.remove(os.path.join(log_dir, old_file))
            except Exception:
                pass

        # Create a new active log file
        open(LOG_PATH, "w").close()
        print(f"🔄 Rotated indicator health log → {rotated_path}")

    except Exception as e:
        print(f"⚠️ Log rotation failed → {e}")


# ============================================================
# 🧠 Structured Warning Logger
# ============================================================
def _log_indicator_warning(indicator: str, context: str, message: str) -> None:
    """Record structured indicator warnings for later audit."""
    _rotate_log_if_needed()  # check rotation before writing

    ts = datetime.now(timezone.utc).isoformat()
    record = f"{ts},{indicator},{context},WARN,{message}\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(record)
    except Exception as e:
        print(f"⚠️ [Indicator Logger] {indicator}:{context} failed to log → {e}")


# ============================================================
# 📖 Optional Reader for cockpit dashboards
# ============================================================
def read_indicator_health_log(limit: int = 100):
    """Return the last N lines from the indicator health log."""
    try:
        if not os.path.exists(LOG_PATH):
            return []
        with open(LOG_PATH, encoding="utf-8") as f:
            lines = f.readlines()
        return lines[-limit:]
    except Exception:
        return []


# ============================================================
# 🩺 Indicator Health Validator
# ============================================================
def indicator_health_report(df: pl.DataFrame, timeframe: str) -> list[str]:
    indicators = [
        "MACD", "ADX", "Keltner_Upper", "Keltner_Lower",
        "MFI", "Chaikin_Osc", "CMV", "SPS", "Breadth_Bias",
        "Liquidity_Trap", "Absorption_Zone", "Divergence_Signal", "Squeeze_Signal"
    ]

    summary = []
    for col in indicators:
        if col not in df.columns:
            summary.append(f"{col} ⚫ Missing")
        else:
            nulls = df[col].null_count() if df[col].dtype != pl.Utf8 else 0
            if nulls > 0:
                summary.append(f"{col} 🟡 NaN({nulls})")
            else:
                summary.append(f"{col} ✅")

    console.print(f"\n📊 Indicator Health — [bold cyan]{timeframe}[/bold cyan]")
    console.print(" | ".join(summary))
    console.print("─" * 80)
    return summary


# ============================================================
# 🌐 Global Health Summary Across Timeframes
# ============================================================
OPTIONAL_INDICATORS = {
    "Breadth_Bias", "Liquidity_Trap", "Absorption_Zone", "Divergence_Signal", "Squeeze_Signal"
}

def summarize_health_across_timeframes(global_health: dict):
    """Displays color-coded summary of indicator health for all timeframes."""
    table = Table(
        title="🩺 Global Indicator Health Summary",
        show_header=True,
        header_style="bold cyan",
        expand=True
    )
    table.add_column("Timeframe", justify="center", style="bold white")
    table.add_column("Health Status", justify="center", style="bold")
    table.add_column("Indicators OK", justify="center")

    for tf, checks in global_health.items():
        core_checks = [c for c in checks if not any(opt in c for opt in OPTIONAL_INDICATORS)]
        healthy = sum("✅" in c for c in core_checks)
        total = len(core_checks)
        ratio = healthy / total if total else 0

        if ratio > 0.8:
            badge, color = "🟢 Healthy", "green"
        elif ratio > 0.5:
            badge, color = "🟡 Partial", "yellow"
        else:
            badge, color = "🔴 Weak", "red"

        table.add_row(
            f"[white]{tf}[/white]",
            f"[bold {color}]{badge}[/bold {color}]",
            f"[cyan]{healthy}[/cyan]/[dim]{total}[/dim]"
        )

    console.print("\n")
    console.print(table)
    console.print("\n" + "─" * 80)
