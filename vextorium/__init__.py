"""Vextorium: 550+ pay-per-call data services for bots and AI agents, paid automatically in USDC on Base (x402).

No API keys, no sign-up: a Base wallet with a little USDC is the account. Every call is capped (max_price) and
there is a spend limit per session (budget), so a bot left running can never spend more than you allow.

    from vextorium import Vextorium
    vx = Vextorium(private_key=os.environ["VEXTORIUM_KEY"], budget_usd=1.0)
    vx.call("perp-funding", symbol="BTC")
    vx.services(query="funding")          # free: search the catalog
"""
from __future__ import annotations

import os
import threading

import requests

__version__ = "0.1.2"
__all__ = ["Vextorium", "VextoriumError", "BudgetExceeded"]

API = "https://api.vextorium.com"
BASE = "eip155:8453"
USDC_BASE = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"


class VextoriumError(Exception):
    """The service answered with an error (failed calls are not charged)."""


class BudgetExceeded(VextoriumError):
    """The call would go over the spend limit you set."""


class Vextorium:
    def __init__(self, private_key: str | None = None, budget_usd: float = 1.0, max_price_usd: float = 0.02,
                 api: str = API, timeout: float = 60):
        from eth_account import Account
        from x402 import x402ClientSync
        from x402.client_base import max_amount, prefer_network
        from x402.http.clients import x402_requests
        from x402.mechanisms.evm.exact import register_exact_evm_client
        from x402.mechanisms.evm.signers import EthAccountSigner

        key = private_key or os.environ.get("VEXTORIUM_KEY")
        if not key:
            raise ValueError("private_key (or VEXTORIUM_KEY): a Base wallet with USDC; use a separate small wallet")
        self.account = Account.from_key(key)
        self.api, self.timeout = api.rstrip("/"), timeout
        self.budget = int(round(budget_usd * 1e6))
        self.max_price = int(round(max_price_usd * 1e6))
        self.spent = 0  # USDC atomic units actually charged in this session
        self._lock = threading.Lock()
        client = x402ClientSync()
        register_exact_evm_client(client, EthAccountSigner(self.account), networks=[BASE],
                                  policies=[prefer_network(BASE), max_amount(self.max_price)])
        self._pay = x402_requests(client)
        self._free = requests.Session()

    # -- free -----------------------------------------------------------------
    def services(self, query: str | None = None) -> list[dict]:
        """Catalog (free). Optional text filter on path/description."""
        items = self._free.get(f"{self.api}/catalog.json", timeout=self.timeout).json()["services"]
        if query:
            q = query.lower()
            items = [s for s in items if q in (str(s.get("endpoint", "")) + str(s.get("description", "")) + " ".join(s.get("tags") or [])).lower()]
        return items

    # -- paid -----------------------------------------------------------------
    def call(self, service: str, **params):
        """Call one service, e.g. call("crypto-price", symbol="ETH"). Pays the listed price (≤ max_price)."""
        path = service if service.startswith("/") else "/v1/" + service
        with self._lock:  # one payment at a time per wallet (nonces) and an exact budget
            probe = self._free.post(self.api + path, json=params, timeout=self.timeout)
            if probe.status_code != 402:
                return self._result(probe)
            price = self._price(probe)
            if price is None:
                raise VextoriumError(f"{path}: no USDC-on-Base offer within max_price")
            if self.spent + price > self.budget:
                raise BudgetExceeded(f"{path} costs {price / 1e6} USDC; spent {self.spent / 1e6} of {self.budget / 1e6}")
            r = self._pay.post(self.api + path, json=params, timeout=self.timeout)
            if r.ok and (r.headers.get("PAYMENT-RESPONSE") or r.headers.get("X-PAYMENT-RESPONSE")):
                self.spent += price
            return self._result(r)

    def _price(self, r) -> int | None:
        try:
            offers = r.json().get("accepts") or []
        except ValueError:
            return None
        ok = [int(o["amount"]) for o in offers if o.get("network") == BASE and str(o.get("asset", "")).lower() == USDC_BASE
              and int(o.get("amount", 0)) <= self.max_price]
        return min(ok) if ok else None

    @staticmethod
    def _result(r):
        try:
            data = r.json()
        except ValueError:
            data = r.text
        if not r.ok:
            raise VextoriumError(f"HTTP {r.status_code}: {str(data)[:300]}")
        return data
