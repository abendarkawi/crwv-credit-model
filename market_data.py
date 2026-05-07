"""
Market data fetcher for the CoreWeave credit model.
- Equity / peer multiples: yfinance (real-time)
- Bond YTW + price: iShares HYG ETF daily holdings CSV (TRACE-sourced, ~1 day lag)

No API keys or authentication required.
CUSIPs confirmed from HYG holdings (May 2026):
  9.25% Sr Notes Jun 2030  -> 21873SAB4
  9.00% Sr Notes Feb 2031  -> 21873SAC2
  9.75% Sr Notes Oct 2031  -> 21873SAG3
"""

from __future__ import annotations
import csv
import datetime
import io
import re
from typing import Optional

import requests
import yfinance as yf

# ---------------------------------------------------------------------------
# Bond reference data — CUSIPs confirmed from HYG holdings file (May 2026)
# ---------------------------------------------------------------------------
BOND_META = [
    dict(name="9.25% Sr Notes", coupon=9.25, maturity="Jun 2030",
         cusip="21873SAB4", isin="US21873SAB43", face_m=2000, rating="B/B1"),
    dict(name="9.00% Sr Notes", coupon=9.00, maturity="Feb 2031",
         cusip="21873SAC2", isin="US21873SAC26", face_m=1750, rating="B/B1"),
    dict(name="9.75% Sr Notes", coupon=9.75, maturity="Oct 2031",
         cusip="21873SAG3", isin="US21873SAG30", face_m=2750, rating="B/B1"),
    dict(name="1.75% Convertible",     coupon=1.75, maturity="Dec 2031",
         cusip=None, isin=None, face_m=2250, rating="BB-"),
    dict(name="1.75% Conv. (Apr '26)", coupon=1.75, maturity="2031/32",
         cusip=None, isin=None, face_m=4000, rating="N/R"),
]

_ETF_SOURCES = [
    ("HYG",  "https://www.ishares.com/us/products/239565/ishares-iboxx-high-yield-corporate-bond-etf/"
              "1467271812596.ajax?fileType=csv&fileName=HYG_holdings&dataType=fund"),
    ("SHYG", "https://www.ishares.com/us/products/258100/ishares-0-5-year-high-yield-corporate-bond-etf/"
              "1467271812596.ajax?fileType=csv&fileName=SHYG_holdings&dataType=fund"),
]

_PEER_META = {
    "CRWV": dict(name="CoreWeave",   rating="B+/Ba3",  note="GPU cloud — subject"),
    "NBIS": dict(name="Nebius",       rating="N/R",     note="AI cloud (closest neocloud)"),
    "NET":  dict(name="Cloudflare",   rating="N/R",     note="Cloud infra/CDN"),
    "ALAB": dict(name="Astera Labs",  rating="N/R",     note="DC networking chips"),
    "AMZN": dict(name="AWS (AMZN)",   rating="AA/Aa1",  note="Hyperscaler (parent co.)"),
    "MSFT": dict(name="Azure (MSFT)", rating="AAA/Aaa", note="Hyperscaler (parent co.)"),
}


# ---------------------------------------------------------------------------
# Bond data via ETF holdings CSV
# ---------------------------------------------------------------------------

def _parse_etf_csv(text: str) -> dict[str, dict]:
    """Parse iShares holdings CSV -> {cusip: {price, ytw, as_of}}."""
    result = {}

    # Strip BOM if present
    if text.startswith("﻿"):
        text = text[1:]

    rows = list(csv.reader(io.StringIO(text)))

    # Find header row (contains "CUSIP")
    header_idx = next((i for i, row in enumerate(rows)
                       if any("CUSIP" in cell.upper() for cell in row)), None)
    if header_idx is None:
        return result

    # Extract as_of date — first row that contains "as of" (fund holdings date)
    as_of = None
    for row in rows[:header_idx]:
        if any("as of" in cell.lower() for cell in row):
            for cell in row:
                m = re.search(r"(\w+ \d{1,2}, \d{4})", cell)
                if m:
                    try:
                        as_of = datetime.datetime.strptime(m.group(1), "%b %d, %Y").strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        pass
            break

    headers = [h.strip().upper() for h in rows[header_idx]]

    def col_idx(*names):
        for name in names:
            for i, h in enumerate(headers):
                if name in h:
                    return i
        return None

    cusip_i = col_idx("CUSIP")
    price_i = col_idx("PRICE")
    ytw_i   = col_idx("YIELD TO WORST", "YTW", "YIELD")

    if cusip_i is None:
        return result

    for row in rows[header_idx + 1:]:
        if not row or len(row) <= cusip_i:
            continue
        cusip = row[cusip_i].strip()
        if not cusip or len(cusip) < 8 or cusip in ("-", "N/A"):
            continue

        def _float(idx):
            if idx is None or idx >= len(row):
                return None
            v = row[idx].strip().replace(",", "")
            try:
                return float(v) if v not in ("-", "", "N/A") else None
            except ValueError:
                return None

        price = _float(price_i)
        ytw   = _float(ytw_i)

        if price or ytw:
            result[cusip] = dict(price=price, ytw=ytw, as_of=as_of)

    return result


def fetch_bond_data() -> Optional[dict[str, dict]]:
    """
    Returns {bond_name: {ytw, price, as_of}} for the three HY Sr Notes.
    Convertibles have no public ETF source and are skipped.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    holdings: dict[str, dict] = {}

    for _, url in _ETF_SOURCES:
        try:
            r = requests.get(url, headers=headers, timeout=25)
            if r.status_code == 200:
                holdings.update(_parse_etf_csv(r.text))
            if holdings:
                break
        except Exception:
            continue

    if not holdings:
        return None

    result = {}
    for bond in BOND_META:
        cusip = bond.get("cusip")
        if cusip and cusip in holdings:
            h = holdings[cusip]
            result[bond["name"]] = dict(ytw=h.get("ytw"), price=h.get("price"), as_of=h.get("as_of"))

    return result if result else None


# ---------------------------------------------------------------------------
# Equity data via yfinance
# ---------------------------------------------------------------------------

def fetch_price_data() -> Optional[dict]:
    try:
        info  = yf.Ticker("CRWV").info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return None
        return dict(
            current            = round(price, 2),
            market_cap_b       = round((info.get("marketCap") or 0) / 1e9, 1),
            ev_b               = round((info.get("enterpriseValue") or 0) / 1e9, 1),
            week_52_high       = info.get("fiftyTwoWeekHigh"),
            week_52_low        = info.get("fiftyTwoWeekLow"),
            short_interest_pct = round((info.get("shortPercentOfFloat") or 0) * 100, 1),
            as_of              = datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
    except Exception:
        return None


def fetch_peer_multiples() -> Optional[list[dict]]:
    try:
        peers = []
        for tkr, meta in _PEER_META.items():
            try:
                info      = yf.Ticker(tkr).info
                ev        = info.get("enterpriseValue") or 0
                rev_ttm   = info.get("totalRevenue") or 0
                ebitda    = info.get("ebitda") or 0
                ev_rev    = round(ev / rev_ttm, 1) if rev_ttm > 0 else None
                ev_ebitda = round(ev / ebitda,  1) if ebitda  > 0 else None
                peers.append(dict(ticker=tkr, name=meta["name"], ev_rev=ev_rev,
                                  ev_ebitda=ev_ebitda, rating=meta["rating"], note=meta["note"]))
            except Exception:
                peers.append(dict(ticker=tkr, name=meta["name"], ev_rev=None,
                                  ev_ebitda=None, rating=meta["rating"], note=meta["note"]))
        return peers if any(p["ev_rev"] for p in peers) else None
    except Exception:
        return None


def fetch_risk_free_rate() -> Optional[float]:
    try:
        hist = yf.Ticker("^TNX").history(period="1d")
        return round(float(hist["Close"].iloc[-1]), 2) if not hist.empty else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Combined fetch — called by the refresh button in app.py
# ---------------------------------------------------------------------------

def fetch_all() -> dict:
    price      = fetch_price_data()
    bond_data  = fetch_bond_data()
    rf_rate    = fetch_risk_free_rate()
    peers      = fetch_peer_multiples() if price else None

    bond_ytw   = {k: v["ytw"]   for k, v in bond_data.items() if v.get("ytw")}   if bond_data else None
    bond_price = {k: v["price"] for k, v in bond_data.items() if v.get("price")} if bond_data else None

    return dict(
        price      = price,
        peers      = peers,
        bond_ytw   = bond_ytw,
        bond_price = bond_price,
        bond_as_of = next((v["as_of"] for v in bond_data.values() if v.get("as_of")), None) if bond_data else None,
        rf_rate    = rf_rate,
        available  = bool(price or bond_ytw),
        as_of      = datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


if __name__ == "__main__":
    print("Testing market data fetcher...")
    d = fetch_all()
    print(f"CRWV price:  ${d['price']['current'] if d['price'] else 'N/A'}")
    print(f"10yr UST:    {d['rf_rate']}%")
    print(f"Bond data as of: {d.get('bond_as_of')}")
    if d["bond_ytw"]:
        for name, ytw in d["bond_ytw"].items():
            price = (d.get("bond_price") or {}).get(name)
            print(f"  {name}: {ytw:.2f}% YTW  |  price {price:.2f}" if price else f"  {name}: {ytw:.2f}% YTW")
    if d["peers"]:
        for p in d["peers"]:
            print(f"  {p['ticker']:6s}  EV/Rev={p['ev_rev']}  EV/EBITDA={p['ev_ebitda']}")
