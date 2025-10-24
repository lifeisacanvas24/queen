#!/usr/bin/env python3
# ============================================================
# queen/helpers/tactical_regime_adapter.py — Regime Blending Layer (v1.1)
# ============================================================
"""Adaptive tactical blending helper that dynamically adjusts model weights
based on volatility + trend regime definitions from queen.settings.regimes.

✅ Reads from Python config (not JSON)
✅ Derives regime automatically from market metrics
✅ Provides blending, scaling, and Polars export for dashboards
"""

from __future__ import annotations

from typing import Dict, Optional

import polars as pl

# Import live regime configuration
from queen.settings import regimes as regime_cfg
from rich import print


class TacticalRegimeAdapter:
    """Dynamically adjusts tactical model weights based on market regime."""

    def __init__(self, regime_name: Optional[str] = None):
        self.active_regime = regime_name or "NEUTRAL"
        self.regime_data = regime_cfg.REGIMES
        self.config = regime_cfg.get_regime_config(self.active_regime)

    # ------------------------------------------------------------
    # 🧭 Core Interface
    # ------------------------------------------------------------
    def derive(self, metrics: dict) -> str:
        """Derive and set regime automatically based on metrics."""
        regime = regime_cfg.derive_regime(metrics)
        self.set_regime(regime)
        return regime

    def set_regime(self, regime_name: str):
        if regime_name.upper() not in self.regime_data:
            raise ValueError(f"Unknown regime: {regime_name}")
        self.active_regime = regime_name.upper()
        self.config = self.regime_data[self.active_regime]

    def list_regimes(self):
        """List all available regime names."""
        return list(self.regime_data.keys())

    # ------------------------------------------------------------
    # ⚖️ Tactical Weight Adjuster
    # ------------------------------------------------------------
    def adjust_tactical_weights(
        self, base_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """Blend tactical model weights based on current regime’s actions."""
        mult = self.config["actions"].get("risk_multiplier", 1.0)
        sensitivity = self.config["actions"].get("indicator_sensitivity", 1.0)

        adjusted = {}
        for k, v in base_weights.items():
            adjusted[k] = round(v * mult * (1 / sensitivity), 4)
        return adjusted

    # ------------------------------------------------------------
    # 📊 Export / Visualization Helpers
    # ------------------------------------------------------------
    def to_polars_df(self) -> pl.DataFrame:
        """Convert regimes to Polars DataFrame for analysis or dashboard display."""
        data = []
        for name, cfg in self.regime_data.items():
            data.append(
                {
                    "Regime": name,
                    "Trend Bias": cfg["trend_bias"],
                    "Volatility": cfg["volatility_state"],
                    "Liquidity": cfg["liquidity_state"],
                    "Risk Multiplier": cfg["actions"]["risk_multiplier"],
                    "Color": cfg["color"],
                }
            )
        return pl.DataFrame(data)

    def describe(self):
        """Print current regime summary."""
        c = self.config
        print(f"\n[bold]{'🧭 Tactical Regime Adapter'}[/bold]")
        print(f"[cyan]Active Regime:[/cyan] {self.active_regime}")
        print(f"[cyan]Trend Bias:[/cyan] {c['trend_bias']}")
        print(f"[cyan]Volatility:[/cyan] {c['volatility_state']}")
        print(f"[cyan]Liquidity:[/cyan] {c['liquidity_state']}")
        print(f"[cyan]Risk Multiplier:[/cyan] {c['actions']['risk_multiplier']}")
        print(f"[cyan]Position Sizing:[/cyan] {c['actions']['position_sizing']}")
        print(
            f"[cyan]Indicator Sensitivity:[/cyan] {c['actions']['indicator_sensitivity']}"
        )
        print(f"[cyan]Description:[/cyan] {c['description']}")


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    adapter = TacticalRegimeAdapter()

    # Simulate incoming metrics (could be live feed later)
    metrics = {"rsi": 62, "adx": 25, "vix_change": -1.5, "obv_slope": 1.2}
    derived = adapter.derive(metrics)
    print(f"\n📊 Derived regime from metrics: [bold green]{derived}[/bold green]")

    # Print details
    adapter.describe()

    # Adjust example weights
    base = {"RScore": 0.5, "VolX": 0.3, "LBX": 0.2}
    adjusted = adapter.adjust_tactical_weights(base)

    print("\nBase Weights:", base)
    print("Adjusted Weights:", adjusted)

    print("\n📋 Available Regimes:")
    print(adapter.to_polars_df())
