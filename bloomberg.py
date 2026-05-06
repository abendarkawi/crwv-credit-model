"""
Market data fetcher for the CoreWeave credit model.
Uses yfinance for real-time equity price and peer multiples.
Bond YTW remains static (Bloomberg/Refinitiv required for live bond data).

No setup required — yfinance is installed via pip.
"""

from __future__ import annotations
import datetime
from typing import Optional

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

# Peer ticker map: yfinance ticker → display metadata
_PEER_META = {
    "CRWV": dict(name="CoreWeave",   rating="B+/Ba3",  note="GPU cloud — subject"),
    "NBIS": dict(name="Nebius",       rating="N/R",     note="AI cloud (closest neocloud)"),
    "NET":  dict(name="Cloudflare",   rating="N/R",     note="Cloud infra/CDN"),
    "ALAB": dict(name="Astera Labs",  rating="N/R",     note="DC networking chips"),
    "AMZN": dict(name="AWS (AMZN)",   rating="AA/Aa1",  note="Hyperscaler (parent co.)"),
    "MSFT": dict(name="Azure (MSFT)", rating="AAA/Aaa", note="Hyperscaler (parent co.)"),
}


def fetch_price_data() -> Optional[dict]:
    """
    Returns live price/market data for CRWV, or None on failure.
    Shape matches data.PRICE_DATA.
    """
    if not _YF_AVAILABLE:
        return None
    try:
        info = yf.Ticker("CRWV").info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return None
        mktcap_b = info.get("marketCap", 0) / 1e9
        ev_b     = info.get("enterpriseValue", 0) / 1e9
        return dict(
            current            = round(price, 2),
            market_cap_b       = round(mktcap_b, 1),
            ev_b               = round(ev_b, 1),
            week_52_high       = info.get("fiftyTwoWeekHigh"),
            week_52_low        = info.get("fiftyTwoWeekLow"),
            short_interest_pct = round((info.get("shortPercentOfFloat") or 0) * 100, 1),
            as_of              = datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
    except Exception:
        return None


def fetch_peer_multiples() -> Optional[list[dict]]:
    """
    Returns live EV/Revenue and EV/EBITDA for each peer, or None on failure.
    yfinance provides TTM multiples via .info.
    """
    if not _YF_AVAILABLE:
        return None
    try:
        tickers = list(_PEER_META.keys())
        data = yf.download(
            tickers, period="1d", auto_adjust=True, progress=False
        )  # prime the cache; actual multiples come from .info

        peers = []
        for tkr, meta in _PEER_META.items():
            try:
                info     = yf.Ticker(tkr).info
                ev       = info.get("enterpriseValue") or 0
                rev_ttm  = info.get("totalRevenue") or 0
                ebitda   = info.get("ebitda") or 0
                ev_rev    = round(ev / rev_ttm, 1) if rev_ttm and rev_ttm > 0  else None
                ev_ebitda = round(ev / ebitda,  1) if ebitda   and ebitda  > 0 else None
                peers.append(dict(
                    ticker   = tkr,
                    name     = meta["name"],
                    ev_rev   = ev_rev,
                    ev_ebitda= ev_ebitda,
                    rating   = meta["rating"],
                    note     = meta["note"],
                ))
            except Exception:
                peers.append(dict(ticker=tkr, name=meta["name"],
                                  ev_rev=None, ev_ebitda=None,
                                  rating=meta["rating"], note=meta["note"]))

        return peers if any(p["ev_rev"] for p in peers) else None
    except Exception:
        return None


def fetch_bond_ytw() -> Optional[dict]:
    """
    Bond YTW requires Bloomberg/Refinitiv — not available via yfinance.
    Returns None; static data.py values are used as fallback.
    """
    return None


def fetch_risk_free_rate() -> Optional[float]:
    """10yr UST yield via yfinance (^TNX = CBOE 10yr Treasury yield index)."""
    if not _YF_AVAILABLE:
        return None
    try:
        hist = yf.Ticker("^TNX").history(period="1d")
        if hist.empty:
            return None
        return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        return None


def fetch_all() -> dict:
    """
    Fetch all available live data. Returns:
      { price, peers, bond_ytw, rf_rate, available, as_of }
    bond_ytw is always None (static fallback used in app).
    """
    if not _YF_AVAILABLE:
        return dict(price=None, peers=None, bond_ytw=None, rf_rate=None,
                    available=False, as_of=None)

    price   = fetch_price_data()
    rf_rate = fetch_risk_free_rate()

    # Peers are slow (6 separate .info calls) — fetch after price check
    peers = fetch_peer_multiples() if price else None

    available = price is not None
    return dict(
        price    = price,
        peers    = peers,
        bond_ytw = None,
        rf_rate  = rf_rate,
        available= available,
        as_of    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
