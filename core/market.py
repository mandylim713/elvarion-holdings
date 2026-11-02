"""Indicative market feed.

Prices move smoothly around each asset's admin-set reference price so the trading
screens feel live. They are indicative only - set the reference price in the admin
console, or replace quote() with a call to a real price provider.
"""
import math
import time
from decimal import Decimal

PRICE_STEP = 5  # seconds between price updates


def _phase(asset):
    return (sum(ord(c) for c in asset.symbol) * 12.9898) % 6.2831


def quote(asset, now=None):
    """Return (price, change_pct) as Decimals for the asset right now."""
    t = int((now or time.time()) // PRICE_STEP) * PRICE_STEP
    ph = _phase(asset)
    vol = float(asset.volatility or 1)
    drift = (0.011 * math.sin(t / 2900.0 + ph) + 0.005 * math.sin(t / 410.0 + ph * 2)
             + 0.0018 * math.sin(t / 47.0 + ph * 3) + 0.0007 * math.sin(t / 9.0 + ph * 5)) * vol
    base = float(asset.base_price)
    price = base * (1 + drift)
    decimals = 4 if base < 10 else 2
    price_d = Decimal(str(round(price, decimals)))
    change = Decimal(str(round(drift * 100, 2)))
    return price_d, change
