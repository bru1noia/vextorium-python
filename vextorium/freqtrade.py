"""freqtrade helper: add Vextorium market context (funding, liquidations, market regime) to a strategy.

Calls are cached per candle, so a 5m bot on 1 pair makes at most 1 call per signal per candle
(e.g. funding: 288 calls/day x 0.009 = 2.6 USDC/day). Use refresh_minutes to call less often.

    from vextorium.freqtrade import VextoriumContext
    class MyStrategy(IStrategy):
        vx = VextoriumContext(budget_usd=2.0, refresh_minutes=60)
        def populate_indicators(self, dataframe, metadata):
            return self.vx.add_columns(dataframe, metadata["pair"])
"""
from __future__ import annotations

import logging
import time

from . import Vextorium, VextoriumError

log = logging.getLogger(__name__)


class VextoriumContext:
    def __init__(self, private_key: str | None = None, budget_usd: float = 1.0, refresh_minutes: float = 60,
                 signals=("funding", "liquidations", "regime"), client: Vextorium | None = None):
        self.vx = client or Vextorium(private_key=private_key, budget_usd=budget_usd)
        self.refresh = refresh_minutes * 60
        self.signals = set(signals)
        self._cache: dict[tuple, tuple[float, dict]] = {}

    def _get(self, service: str, **params) -> dict | None:
        key = (service, tuple(sorted(params.items())))
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < self.refresh:
            return hit[1]
        try:
            data = self.vx.call(service, **params)
        except VextoriumError as e:  # failed calls are not charged; the bot keeps running without the column
            log.warning("vextorium %s: %s", service, e)
            return hit[1] if hit else None
        self._cache[key] = (time.time(), data)
        return data

    def context(self, pair: str) -> dict:
        """Latest values for a pair like 'BTC/USDT' or 'BTC/USDT:USDT'."""
        coin = pair.split("/")[0].upper()
        out: dict = {}
        if "funding" in self.signals and (f := self._get("perp-funding", currency=coin)):
            out["vx_funding_annual_pct"] = f.get("annual_funding_pct")
            out["vx_premium_pct"] = f.get("premium_pct")
            out["vx_open_interest_usd"] = f.get("open_interest_usd")
        if "liquidations" in self.signals and (m := self._get("hyperliquid-liquidation-map", currency=coin, brackets=10)):
            out["vx_nearest_long_liq_pct"] = ((m.get("nearest_long_liquidations") or [{}])[0]).get("distance_pct")
            out["vx_nearest_short_liq_pct"] = ((m.get("nearest_short_liquidations") or [{}])[0]).get("distance_pct")
            out["vx_long_at_risk_usd"] = m.get("long_notional_at_risk_usd")
            out["vx_short_at_risk_usd"] = m.get("short_notional_at_risk_usd")
        if "regime" in self.signals and (r := self._get("market-regime")):
            out["vx_regime_score"] = r.get("score")
        return out

    def add_columns(self, dataframe, pair: str):
        """Writes the latest values on the last row (live/dry-run); past rows stay NaN (no look-ahead)."""
        for col, val in self.context(pair).items():
            if col not in dataframe:
                dataframe[col] = float("nan")
            if val is not None and len(dataframe):
                dataframe.loc[dataframe.index[-1], col] = val
        return dataframe
