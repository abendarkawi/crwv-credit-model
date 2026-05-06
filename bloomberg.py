"""
Bloomberg real-time data fetcher for the CoreWeave credit model.
Requires blpapi + Bloomberg Terminal running locally.
Falls back silently to static data.py values if unavailable.

Install on work machine (inside venv):
    pip install blpapi --index-url https://bcms.bloomberg.com/pip/simple/
"""

from __future__ import annotations
import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Try to import blpapi — graceful no-op if not installed / Terminal not running
# ---------------------------------------------------------------------------
try:
    import blpapi
    _BBG_AVAILABLE = True
except ImportError:
    _BBG_AVAILABLE = False


def _open_session() -> Optional["blpapi.Session"]:
    """Open a Desktop API session (localhost:8194). Returns None on failure."""
    if not _BBG_AVAILABLE:
        return None
    opts = blpapi.SessionOptions()
    opts.setServerHost("localhost")
    opts.setServerPort(8194)
    session = blpapi.Session(opts)
    if not session.start():
        return None
    if not session.openService("//blp/refdata"):
        session.stop()
        return None
    return session


def _bdp(session: "blpapi.Session", securities: list[str], fields: list[str]) -> dict:
    """Synchronous BDP (reference data) fetch. Returns {security: {field: value}}."""
    svc = session.getService("//blp/refdata")
    req = svc.createRequest("ReferenceDataRequest")
    for s in securities:
        req.append("securities", s)
    for f in fields:
        req.append("fields", f)

    session.sendRequest(req)
    result: dict = {s: {} for s in securities}

    done = False
    while not done:
        ev = session.nextEvent(500)
        for msg in ev:
            if msg.messageType() == blpapi.Name("ReferenceDataResponse"):
                sec_data = msg.getElement("securityData")
                for i in range(sec_data.numValues()):
                    item = sec_data.getValueAsElement(i)
                    ticker = item.getElementAsString("security")
                    fd = item.getElement("fieldData")
                    for f in fields:
                        try:
                            result[ticker][f] = fd.getElementAsFloat(f)
                        except Exception:
                            try:
                                result[ticker][f] = fd.getElementAsString(f)
                            except Exception:
                                result[ticker][f] = None
        if ev.eventType() == blpapi.Event.RESPONSE:
            done = True

    return result


# ---------------------------------------------------------------------------
# Public fetch functions
# ---------------------------------------------------------------------------

def fetch_price_data() -> Optional[dict]:
    """
    Returns a dict matching the shape of data.PRICE_DATA, or None if Bloomberg
    is unavailable.
    """
    session = _open_session()
    if session is None:
        return None

    try:
        fields = [
            "PX_LAST", "CUR_MKT_CAP", "CURR_ENTP_VAL",
            "PX_HIGH_52WEEK", "PX_LOW_52WEEK",
            "SHORT_INT_RATIO",
        ]
        raw = _bdp(session, ["CRWV US Equity"], fields)
        d = raw.get("CRWV US Equity", {})

        price      = d.get("PX_LAST")
        mktcap_m   = d.get("CUR_MKT_CAP")       # Bloomberg returns in $M by default
        ev_m       = d.get("CURR_ENTP_VAL")
        hi52       = d.get("PX_HIGH_52WEEK")
        lo52       = d.get("PX_LOW_52WEEK")
        short_pct  = d.get("SHORT_INT_RATIO")    # days-to-cover; swap for SHORT_INT if preferred

        if price is None:
            return None

        return dict(
            current         = price,
            market_cap_b    = round(mktcap_m / 1000, 1) if mktcap_m else None,
            ev_b            = round(ev_m / 1000, 1)     if ev_m     else None,
            week_52_high    = hi52,
            week_52_low     = lo52,
            short_interest_pct = short_pct,
            as_of           = datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
    finally:
        session.stop()


def fetch_peer_multiples() -> Optional[list[dict]]:
    """
    Returns a list of peer dicts matching the shape of data.PEERS, or None.
    Uses Bloomberg tickers for US equities; AWS/Azure use AMZN/MSFT parent.
    """
    session = _open_session()
    if session is None:
        return None

    ticker_meta = {
        "CRWV US Equity": dict(name="CoreWeave",   rating="B+/Ba3", note="GPU cloud — subject"),
        "NBIS US Equity": dict(name="Nebius",       rating="N/R",    note="AI cloud (closest neocloud)"),
        "NET US Equity":  dict(name="Cloudflare",   rating="N/R",    note="Cloud infra/CDN"),
        "ALAB US Equity": dict(name="Astera Labs",  rating="N/R",    note="DC networking chips"),
        "AMZN US Equity": dict(name="AWS (AMZN)",   rating="AA/Aa1", note="Hyperscaler (parent co.)"),
        "MSFT US Equity": dict(name="Azure (MSFT)", rating="AAA/Aaa",note="Hyperscaler (parent co.)"),
    }

    try:
        fields = ["EV_TO_T12M_EBITDA", "EV_TO_T12M_SALES"]
        raw = _bdp(session, list(ticker_meta.keys()), fields)

        peers = []
        for bbg_ticker, meta in ticker_meta.items():
            d   = raw.get(bbg_ticker, {})
            tkr = bbg_ticker.split()[0]
            peers.append(dict(
                ticker   = tkr,
                name     = meta["name"],
                ev_rev   = round(d["EV_TO_T12M_SALES"],  1) if d.get("EV_TO_T12M_SALES")  else None,
                ev_ebitda= round(d["EV_TO_T12M_EBITDA"], 1) if d.get("EV_TO_T12M_EBITDA") else None,
                rating   = meta["rating"],
                note     = meta["note"],
            ))
        return peers if any(p["ev_rev"] for p in peers) else None
    finally:
        session.stop()


def fetch_bond_ytw() -> Optional[dict[str, float]]:
    """
    Returns {bond_name: ytw_pct} for the CRWV unsecured notes, or None.

    CUSIPs / ISINs as of May 2026:
      9.25% Sr Notes   Jun 2030  — CUSIP: 21874LAA8  / ISIN: US21874LAA85
      9.00% Sr Notes   Feb 2031  — CUSIP: 21874LAB6  / ISIN: US21874LAB68
      9.75% Sr Notes   Oct 2031  — CUSIP: 21874LAC4  / ISIN: US21874LAC42  (Apr '26 tap)
      1.75% Convert.   Dec 2031  — CUSIP: 21874LAD2  / ISIN: US21874LAD25
      1.75% Conv Apr26 2031/32   — CUSIP: 21874LAE0  / ISIN: US21874LAE08

    Convertibles carry no meaningful YTW (equity-linked); we skip them.
    """
    session = _open_session()
    if session is None:
        return None

    # Map CUSIP@CBBT Corp (Bloomberg's composite bond pricing) → bond name
    cusip_map = {
        "21874LAA8@CBBT Corp": "9.25% Sr Notes",
        "21874LAB6@CBBT Corp": "9.00% Sr Notes",
        "21874LAC4@CBBT Corp": "9.75% Sr Notes",
    }

    try:
        fields = ["YLD_YTM_MID", "YLD_YTW_MID", "PX_MID"]
        raw = _bdp(session, list(cusip_map.keys()), fields)

        ytw_map: dict[str, float] = {}
        for bbg_id, bond_name in cusip_map.items():
            d   = raw.get(bbg_id, {})
            ytw = d.get("YLD_YTW_MID") or d.get("YLD_YTM_MID")
            if ytw:
                ytw_map[bond_name] = round(ytw, 2)
        return ytw_map if ytw_map else None
    finally:
        session.stop()


def fetch_risk_free_rate() -> Optional[float]:
    """Returns the current 10yr UST yield (%), or None."""
    session = _open_session()
    if session is None:
        return None
    try:
        raw = _bdp(session, ["GT10 Govt"], ["YLD_YTM_MID"])
        val = raw.get("GT10 Govt", {}).get("YLD_YTM_MID")
        return round(val, 2) if val else None
    finally:
        session.stop()


def fetch_all() -> dict:
    """
    Convenience wrapper — calls all four fetches and returns a single dict:
      {
        "price":    {...} or None,
        "peers":    [...] or None,
        "bond_ytw": {...} or None,
        "rf_rate":  float or None,
        "available": bool,
        "as_of":    "YYYY-MM-DD HH:MM",
      }
    """
    available = _BBG_AVAILABLE and _open_session() is not None

    if not available:
        return dict(
            price=None, peers=None, bond_ytw=None, rf_rate=None,
            available=False,
            as_of=None,
        )

    return dict(
        price    = fetch_price_data(),
        peers    = fetch_peer_multiples(),
        bond_ytw = fetch_bond_ytw(),
        rf_rate  = fetch_risk_free_rate(),
        available= True,
        as_of    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
