#!/usr/bin/env python3
# ============================================================
# queen/helpers/diagnostic_override_logger.py — v1.1
# ------------------------------------------------------------
# Centralised logging for:
#   • Trend+Volume overrides
#   • Sector-based vetoes
#   • Options / F&O sentiment vetoes (future use)
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from queen.helpers.logger import log  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    import logging

    log = logging.getLogger("queen.overrides")  # type: ignore[assignment]
    if not log.handlers:
        _h = logging.StreamHandler()
        _fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        _h.setFormatter(_fmt)
        log.addHandler(_h)
    log.setLevel(logging.INFO)


def _safe_str(v: Any) -> str:
    try:
        return str(v)
    except Exception:
        return repr(v)


# -------------------------------------------------------------------
# Trend + Volume override
# -------------------------------------------------------------------
def log_trend_volume_override(
    *,
    symbol: Optional[str],
    interval: str,
    mode: Optional[str],
    original_decision: str,
    original_bias: str,
    new_decision: str,
    new_bias: str,
    trend_ctx: Optional[Dict[str, Any]] = None,
    vol_ctx: Optional[Dict[str, Any]] = None,
    reason: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when the Trend+Volume fusion overrides a bearish/weak signal."""
    try:
        parts: list[str] = []

        sym = symbol or "UNKNOWN"
        mode_str = mode or "unknown"

        headline = (
            f"[TVO_OVERRIDE] {sym} {interval} ({mode_str}) "
            f"{original_bias}/{original_decision}→{new_bias}/{new_decision}"
        )
        parts.append(headline)

        # Build trend/volume summary if available
        tv_bits: list[str] = []
        if trend_ctx:
            tl = trend_ctx.get("Trend_Strength_Label_D")
            ts = trend_ctx.get("Trend_Strength_Score_D")
            if tl is not None:
                tv_bits.append(f"trend={tl}")
            if ts is not None:
                tv_bits.append(f"trend_score={ts}")
        if vol_ctx:
            vl = vol_ctx.get("Vol_Strength_Label_I")
            vs = vol_ctx.get("Vol_Strength_Score_I")
            if vl is not None:
                tv_bits.append(f"vol={vl}")
            if vs is not None:
                tv_bits.append(f"vol_score={vs}")

        if tv_bits:
            parts.append(" | ".join(tv_bits))

        if reason:
            parts.append(f"reason={reason}")

        if extra:
            extras_str = " ".join(
                f"{k}={_safe_str(v)}" for k, v in extra.items()
            )
            if extras_str:
                parts.append(f"extra={extras_str}")

        msg = "\n  ".join(parts)
        log.info(msg)
    except Exception:
        return


# -------------------------------------------------------------------
# Sector-based veto
# -------------------------------------------------------------------
def log_sector_veto(
    *,
    symbol: str,
    sector: str,
    interval: str,
    mode: str,
    original_decision: str,
    original_bias: str,
    new_decision: str,
    new_bias: str,
    sector_score: Optional[float],
    sector_bias: Optional[str],
    sector_trend: Optional[str],
    reason: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when sector context downgrades or vetoes a signal."""
    try:
        parts: list[str] = []

        headline = (
            f"[SECTOR_VETO] {symbol} {interval} ({mode}) "
            f"{original_bias}/{original_decision}→{new_bias}/{new_decision}"
        )
        parts.append(headline)

        sec_line = f"sector={sector}"
        if sector_score is not None:
            sec_line += f" score={sector_score:.2f}"
        if sector_bias:
            sec_line += f" bias={sector_bias}"
        if sector_trend:
            sec_line += f" trend={sector_trend}"
        parts.append(sec_line)

        if reason:
            parts.append(f"reason={reason}")

        if extra:
            extras_str = " ".join(
                f"{k}={_safe_str(v)}" for k, v in extra.items()
            )
            if extras_str:
                parts.append(f"extra={extras_str}")

        msg = "\n  ".join(parts)
        log.info(msg)
    except Exception:
        return


# -------------------------------------------------------------------
# Options / F&O sentiment veto
# -------------------------------------------------------------------
def log_options_veto(
    *,
    symbol: str,
    interval: str,
    mode: str,
    original_decision: str,
    original_bias: str,
    new_decision: str,
    new_bias: str,
    opt_bias: Optional[str],
    pcr: Optional[float] = None,
    reason: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when options sentiment vetoes or downgrades a signal."""
    try:
        parts: list[str] = []

        headline = (
            f"[OPTIONS_VETO] {symbol} {interval} ({mode}) "
            f"{original_bias}/{original_decision}→{new_bias}/{new_decision}"
        )
        parts.append(headline)

        opt_line = "opts_bias=" + (opt_bias or "Unknown")
        if pcr is not None:
            opt_line += f" pcr={pcr:.2f}"
        parts.append(opt_line)

        if reason:
            parts.append(f"reason={reason}")

        if extra:
            extras_str = " ".join(
                f"{k}={_safe_str(v)}" for k, v in extra.items()
            )
            if extras_str:
                parts.append(f"extra={extras_str}")

        msg = "\n  ".join(parts)
        log.info(msg)
    except Exception:
        return
