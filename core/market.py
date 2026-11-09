"""Market prices.

When "Use live prices" is on (Admin > Markets), real prices are pulled from public
price feeds - CryptoCompare / CoinGecko for crypto, Yahoo Finance for stocks, gold and
silver. Prices are cached for a few seconds and refreshed in the background, so pages
never wait on the feed. If a feed cannot be reached, that asset falls back to an
indicative price that moves around the reference price set in the admin console, and
the screens say "Indicative" instead of "Live".
"""
import json
import math
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

PRICE_STEP = 5      # seconds between simulated price steps
CACHE_TTL = 15      # seconds a live price stays fresh
RETRY_AFTER = 45    # seconds before retrying a feed that failed
TIMEOUT = 5

YAHOO_MAP = {'XAU': 'GC=F', 'XAG': 'SI=F'}      # gold / silver futures
COINGECKO_IDS = {'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana', 'BNB': 'binancecoin', 'XRP': 'ripple',
                 'ADA': 'cardano', 'DOGE': 'dogecoin', 'LTC': 'litecoin', 'TRX': 'tron', 'DOT': 'polkadot',
                 'AVAX': 'avalanche-2', 'LINK': 'chainlink', 'MATIC': 'matic-network', 'TON': 'the-open-network'}

_lock = threading.Lock()
_state = {'data': {}, 'fetched': 0.0, 'failed': 0.0, 'running': False}


def _get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; ElvarionPrices/1.0)', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode('utf-8'))


def _fetch_crypto(symbols):
    out = {}
    if not symbols:
        return out
    try:
        d = _get_json('https://min-api.cryptocompare.com/data/pricemultifull?fsyms=%s&tsyms=USD' % ','.join(symbols))
        for s in symbols:
            raw = d.get('RAW', {}).get(s, {}).get('USD')
            if raw and raw.get('PRICE'):
                out[s] = (float(raw['PRICE']), float(raw.get('CHANGEPCT24HOUR') or 0))
    except Exception:
        pass
    missing = [s for s in symbols if s not in out and s in COINGECKO_IDS]
    if missing:
        try:
            ids = ','.join(COINGECKO_IDS[s] for s in missing)
            d = _get_json('https://api.coingecko.com/api/v3/simple/price?ids=%s&vs_currencies=usd&include_24hr_change=true' % ids)
            for s in missing:
                row = d.get(COINGECKO_IDS[s])
                if row and row.get('usd'):
                    out[s] = (float(row['usd']), float(row.get('usd_24h_change') or 0))
        except Exception:
            pass
    return out


def _fetch_yahoo_one(sym):
    try:
        ysym = YAHOO_MAP.get(sym, sym)
        d = _get_json('https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=5d' % urllib.parse.quote(ysym))
        meta = d['chart']['result'][0]['meta']
        price = float(meta['regularMarketPrice'])
        prev = meta.get('chartPreviousClose') or meta.get('previousClose')
        change = ((price - float(prev)) / float(prev) * 100) if prev else 0.0
        return sym, (price, change)
    except Exception:
        return sym, None


def _fetch_all(assets):
    crypto = [a.symbol for a in assets if a.category == 'crypto']
    other = [a.symbol for a in assets if a.category != 'crypto']
    out = _fetch_crypto(crypto)
    if other:
        with ThreadPoolExecutor(max_workers=6) as ex:
            for sym, val in ex.map(_fetch_yahoo_one, other):
                if val:
                    out[sym] = val
    return out


def _live_enabled():
    try:
        from .models import CompanySetting
        return CompanySetting.get_settings().use_live_prices
    except Exception:
        return False


def refresh(force=False):
    """Fetch fresh prices now (blocking). Safe to call from threads / cron."""
    from .models import TradingAsset
    now = time.time()
    with _lock:
        if _state['running']:
            return
        if not force and now - _state['fetched'] < CACHE_TTL:
            return
        if not force and now - _state['failed'] < RETRY_AFTER and now - _state['fetched'] >= CACHE_TTL and _state['failed'] > _state['fetched']:
            return
        _state['running'] = True
    try:
        assets = list(TradingAsset.objects.filter(is_active=True))
        data = _fetch_all(assets) if _live_enabled() else {}
        with _lock:
            if data:
                merged = dict(_state['data'])
                merged.update({k: (v[0], v[1], time.time()) for k, v in data.items()})
                _state['data'] = merged
                _state['fetched'] = time.time()
            else:
                _state['failed'] = time.time()
    except Exception:
        with _lock:
            _state['failed'] = time.time()
    finally:
        with _lock:
            _state['running'] = False


def _kick():
    now = time.time()
    if _state['running'] or now - _state['fetched'] < CACHE_TTL:
        return
    if _state['failed'] > _state['fetched'] and now - _state['failed'] < RETRY_AFTER:
        return
    threading.Thread(target=refresh, daemon=True).start()


def _phase(asset):
    return (sum(ord(c) for c in asset.symbol) * 12.9898) % 6.2831


def _simulated(asset, now=None):
    t = int((now or time.time()) // PRICE_STEP) * PRICE_STEP
    ph = _phase(asset)
    vol = float(asset.volatility or 1)
    drift = (0.011 * math.sin(t / 2900.0 + ph) + 0.005 * math.sin(t / 410.0 + ph * 2)
             + 0.0018 * math.sin(t / 47.0 + ph * 3) + 0.0007 * math.sin(t / 9.0 + ph * 5)) * vol
    base = float(asset.base_price)
    return base * (1 + drift), drift * 100


def _round_price(price):
    return round(price, 4 if price < 10 else 2)


def quote_full(asset, wait=False):
    """(price, change_pct, is_live). wait=True blocks briefly for a fresh live price (used when money moves)."""
    if _live_enabled():
        if wait and time.time() - _state['fetched'] > 20:
            refresh()
        else:
            _kick()
        row = _state['data'].get(asset.symbol)
        if row and time.time() - row[2] < 180:
            return Decimal(str(_round_price(row[0]))), Decimal(str(round(row[1], 2))), True
    price, change = _simulated(asset)
    return Decimal(str(_round_price(price))), Decimal(str(round(change, 2))), False


def quote(asset, now=None, wait=False):
    """Return (price, change_pct) as Decimals."""
    p, c, _ = quote_full(asset, wait=wait)
    return p, c


def feed_status():
    """'live' when real prices are flowing, otherwise 'indicative'."""
    if _live_enabled() and _state['data'] and time.time() - _state['fetched'] < 180:
        return 'live'
    return 'indicative'
