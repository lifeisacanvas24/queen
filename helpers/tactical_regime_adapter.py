#!/usr/bin/env python3
# ============================================================
# queen/helpers/tactical_regime_adapter.py — Regime Blending Layer (v1.2)
# ============================================================
from __future__ import annotations

from typing import Dict, Optional

import polars as pl
from rich import print

from queen.settings import regimes as regime_cfg


class TacticalRegimeAdapter:
    """Dynamically adjusts tactical model weights based on market regime."""

    def __init__(self, regime_name: Optional[str] = None):
        self.regime_data: Dict[str, dict] = regime_cfg.REGIMES
        self.active_regime: str = (regime_name or "NEUTRAL").upper()
        self.config: dict = regime_cfg.get_regime_config(self.active_regime)

    # ------------------------------------------------------------
    # 🧭 Core Interface
    # ------------------------------------------------------------
    def derive(self, metrics: dict) -> str:
        """Derive and set regime automatically based on (possibly partial) metrics."""
        metrics = dict(metrics or {})
        regime = regime_cfg.derive_regime(metrics)
        self.set_regime(regime)
        return regime

    def set_regime(self, regime_name: str) -> None:
        r = (regime_name or "").upper()
        if r not in self.regime_data:
            raise ValueError(f"Unknown regime: {regime_name}")
        self.active_regime = r
        self.config = self.regime_data[r]

    def list_regimes(self) -> list[str]:
        return list(self.regime_data.keys())

    # ------------------------------------------------------------
    # ⚖️ Tactical Weight Adjusters
    # ------------------------------------------------------------
    def adjust_tactical_weights(
        self, base_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """Simple multiplicative adjustment by regime risk + sensitivity."""
        mult = float(self.config["actions"].get("risk_multiplier", 1.0))
        sens = float(self.config["actions"].get("indicator_sensitivity", 1.0)) or 1.0
        return {
            k: round(float(v) * mult * (1.0 / sens), 6) for k, v in base_weights.items()
        }

    def blend(
        self, base_weights: Dict[str, float], normalize: bool = True
    ) -> Dict[str, float]:
        """Return base weights blended by regime, optionally normalized to sum=1."""
        adjusted = self.adjust_tactical_weights(base_weights)
        if not normalize:
            return adjusted
        s = sum(adjusted.values()) or 1.0
        return {k: v / s for k, v in adjusted.items()}

    # ------------------------------------------------------------
    # 📊 Export / Visualization Helpers
    # ------------------------------------------------------------
    def to_polars_df(self) -> pl.DataFrame:
        rows = []
        for name, cfg in self.regime_data.items():
            rows.append(
                {
                    "Regime": name,
                    "Trend Bias": cfg.get("trend_bias"),
                    "Volatility": cfg.get("volatility_state"),
                    "Liquidity": cfg.get("liquidity_state"),
                    "Risk Multiplier": cfg.get("actions", {}).get("risk_multiplier"),
                    "Indicator Sensitivity": cfg.get("actions", {}).get(
                        "indicator_sensitivity"
                    ),
                    "Color": cfg.get("color"),
                }
            )
        return pl.DataFrame(rows)

    def describe(self) -> None:
        c = self.config or {}
        actions = c.get("actions", {})
        print("\n[bold]🧭 Tactical Regime Adapter[/bold]")
        print(f"[cyan]Active Regime:[/cyan] {self.active_regime}")
        print(f"[cyan]Trend Bias:[/cyan] {c.get('trend_bias')}")
        print(f"[cyan]Volatility:[/cyan] {c.get('volatility_state')}")
        print(f"[cyan]Liquidity:[/cyan] {c.get('liquidity_state')}")
        print(f"[cyan]Risk Multiplier:[/cyan] {actions.get('risk_multiplier')}")
        print(f"[cyan]Position Sizing:[/cyan] {actions.get('position_sizing')}")
        print(f"[cyan]Indicator Sensitivity:[/cyan] {actions.get('indicator_sensitivity')}")
        print(f"[cyan]Description:[/cyan] {c.get('description')}")
    # ------------------------------------------------------------
    # ✅ Validation
    # ------------------------------------------------------------
    def validate(self) -> dict:
        """Use regimes.validate() if available; else do minimal checks."""
        if hasattr(regime_cfg, "validate") and callable(regime_cfg.validate):
            return regime_cfg.validate()
        errs = []
        for name, cfg in self.regime_data.items():
            if "actions" not in cfg:
                errs.append(f"{name}: missing actions")
        return {"ok": not errs, "errors": errs, "count": len(self.regime_data)}

    def active_config(self) -> dict:
        """Return current regime config (read-only view)."""
        return dict(self.config or {})
# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    adapter = TacticalRegimeAdapter()
    metrics = {"rsi": 62, "adx": 25, "vix_change": -1.5, "obv_slope": 1.2}
    derived = adapter.derive(metrics)
    print(f"\n📊 Derived regime: [bold green]{derived}[/bold green]")
    adapter.describe()

    base = {"RScore": 0.5, "VolX": 0.3, "LBX": 0.2}
    print("\nBase Weights:", base)
    print("Adjusted (raw):", adapter.adjust_tactical_weights(base))
    print("Adjusted (norm):", adapter.blend(base, normalize=True))
    print("\n📋 Regimes Table:")
    print(adapter.to_polars_df())
