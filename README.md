<p align="center">
  <a href="https://vextorium.com"><img src="https://raw.githubusercontent.com/bru1noia/vextorium-python/main/assets/logo.png" alt="Vextorium" width="96" height="96"></a>
</p>

<h1 align="center">Vextorium for Python</h1>

<p align="center">
  <b>Data your trading bot or AI agent pays for per call: no accounts, no API keys.</b><br>
  <a href="https://vextorium.com">Website</a> ·
  <a href="https://api.vextorium.com/catalog.json">Catalog (552 services)</a> ·
  <a href="https://api.vextorium.com/openapi.json">OpenAPI</a> ·
  <a href="https://github.com/bru1noia/vextorium-mcp">MCP server</a> ·
  <a href="https://x402.org">x402</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/vextorium/"><img src="https://img.shields.io/pypi/v/vextorium" alt="PyPI"></a>
  <img src="https://img.shields.io/pypi/pyversions/vextorium" alt="Python">
  <img src="https://img.shields.io/badge/paid%20in-USDC%20on%20Base-00FF66" alt="USDC on Base">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT">
</p>

550+ pay-per-call data services for trading bots and AI agents: perp funding, liquidation maps, Hyperliquid
markets and whales, market regime, prices, on-chain data on 30+ chains, DeFi, official statistics and more.

**No API keys, no sign-up.** A Base wallet with a little USDC is the account; each call is paid automatically
via [x402](https://x402.org) (typically 0.003–0.01 USDC). Failed calls are not charged.

```bash
pip install vextorium            # or: pip install "vextorium[freqtrade]"
```

```python
from vextorium import Vextorium

vx = Vextorium(private_key="0x...", budget_usd=1.0, max_price_usd=0.02)  # use a separate small wallet
vx.call("perp-funding", currency="BTC")        # funding, premium, open interest
vx.call("hyperliquid-liquidation-map", currency="ETH", brackets=10)
vx.call("market-regime")                       # risk-on / risk-off score
vx.services("funding")                         # free: search the catalog
print(vx.spent / 1e6, "USDC spent")
```

Safety: every call is capped by `max_price_usd`, the session by `budget_usd` (`BudgetExceeded` is raised
before paying), payments only go out on Base USDC, and one payment runs at a time per wallet.

## freqtrade

Add funding, nearest liquidations and market regime as columns (latest candle only, no look-ahead), cached so
a bot calls each service at most once per `refresh_minutes`:

```python
from vextorium.freqtrade import VextoriumContext

class MyStrategy(IStrategy):
    vx = VextoriumContext(budget_usd=2.0, refresh_minutes=60)   # key from VEXTORIUM_KEY

    def populate_indicators(self, dataframe, metadata):
        dataframe = self.vx.add_columns(dataframe, metadata["pair"])
        # vx_funding_annual_pct, vx_premium_pct, vx_open_interest_usd, vx_nearest_long_liq_pct,
        # vx_nearest_short_liq_pct, vx_long_at_risk_usd, vx_short_at_risk_usd, vx_regime_score
        return dataframe
```

Cost example: 1 pair, refresh 60 min, 3 signals ≈ 24 × 0.019 = 0.46 USDC/day.

Full catalog: https://api.vextorium.com/catalog.json · OpenAPI: https://api.vextorium.com/openapi.json ·
MCP server: https://github.com/bru1noia/vextorium-mcp

License: MIT
