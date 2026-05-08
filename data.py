# CoreWeave (CRWV) — historical financials and market data
# Sources: SEC filings (S-1, 10-K, quarterly press releases), company investor relations
# All monetary figures in $M. MW = megawatts of active GPU compute capacity.
# Note: 2024 quarterly capex/debt estimated from annual totals + press releases;
#       2024 quarterly adj. EBITDA estimated to reconcile to ~$1,220M FY total.

ANNUAL_ACTUALS = {
    2022: dict(revenue=15.8,   gross_profit=3.7,   adj_ebitda=-5.0,  interest_expense=9.4,
               capex=72.4,    total_debt=200.0,   cash=50.0,   mw_online=20),
    2023: dict(revenue=228.9,  gross_profit=160.0,  adj_ebitda=89.3,  interest_expense=28.0,
               capex=2943.0,  total_debt=2000.0,  cash=217.0,  mw_online=100),
}

QUARTERLY_ACTUALS = {
    (2024, 1): dict(revenue=188.7,  gross_profit=129.5, adj_ebitda=100.0, interest_expense=40.7,
                    capex=1305.0,  total_debt=3500.0,  cash=400.0,  mw_online=180),
    (2024, 2): dict(revenue=395.4,  gross_profit=286.5, adj_ebitda=237.0, interest_expense=66.8,
                    capex=1740.0,  total_debt=5000.0,  cash=600.0,  mw_online=230),
    (2024, 3): dict(revenue=583.9,  gross_profit=440.8, adj_ebitda=362.0, interest_expense=104.4,
                    capex=2176.0,  total_debt=7500.0,  cash=800.0,  mw_online=280),
    (2024, 4): dict(revenue=747.4,  gross_profit=565.3, adj_ebitda=521.0, interest_expense=149.0,
                    capex=3481.0,  total_debt=10620.0, cash=1361.0, mw_online=360),
    (2025, 1): dict(revenue=981.6,  gross_profit=719.2, adj_ebitda=606.1, interest_expense=263.8,
                    capex=1900.0,  total_debt=13000.0, cash=1280.0, mw_online=420),
    (2025, 2): dict(revenue=1213.0, gross_profit=900.1, adj_ebitda=753.2, interest_expense=267.0,
                    capex=2500.0,  total_debt=16000.0, cash=1500.0, mw_online=550),
    (2025, 3): dict(revenue=1365.0, gross_profit=995.9, adj_ebitda=838.1, interest_expense=310.6,
                    capex=2100.0,  total_debt=18500.0, cash=2000.0, mw_online=700),
    (2025, 4): dict(revenue=1572.0, gross_profit=1063.0,adj_ebitda=898.0, interest_expense=388.0,
                    capex=3809.0,  total_debt=21373.0, cash=3127.0, mw_online=850),
    # Q1 2026 reported May 8 2026; gross_profit estimated at ~69% (not separately disclosed)
    # cash estimated from: $3,127M start + OCF $2,984M - CapEx $7,695M + net new debt $3,486M ≈ $1,902M
    (2026, 1): dict(revenue=2078.0, gross_profit=1434.0, adj_ebitda=1157.0, interest_expense=550.0,
                    capex=7695.0,  total_debt=24859.0, cash=1900.0, mw_online=1000),
}

# Peer multiples (as of May 5, 2026) — source: Multiples.vc, Finviz
PEERS = [
    dict(ticker="CRWV", name="CoreWeave",   ev_rev=18.7, ev_ebitda=39.9, rating="B+/Ba3",   note="GPU cloud — subject"),
    dict(ticker="NBIS", name="Nebius",       ev_rev=31.4, ev_ebitda=108.4,rating="N/R",      note="AI cloud (closest neocloud)"),
    dict(ticker="NET",  name="Cloudflare",   ev_rev=33.0, ev_ebitda=148.4,rating="N/R",      note="Cloud infra/CDN"),
    dict(ticker="ALAB", name="Astera Labs",  ev_rev=32.4, ev_ebitda=85.5, rating="N/R",      note="DC networking chips"),
    dict(ticker="AMZN", name="AWS (AMZN)",   ev_rev=3.8,  ev_ebitda=18.2, rating="AA/Aa1",   note="Hyperscaler (parent co.)"),
    dict(ticker="MSFT", name="Azure (MSFT)", ev_rev=11.0, ev_ebitda=25.1, rating="AAA/Aaa",  note="Hyperscaler (parent co.)"),
]

# Unsecured bonds outstanding (as of May 2026, incl. April 2026 raises)
BONDS = [
    dict(name="9.25% Sr Notes",        coupon=9.25, maturity="Jun 2030", face_m=2000, rating="B/B1",  ytw=8.8),
    dict(name="9.00% Sr Notes",        coupon=9.00, maturity="Feb 2031", face_m=1750, rating="B/B1",  ytw=8.8),
    dict(name="9.75% Sr Notes",        coupon=9.75, maturity="Oct 2031", face_m=2750, rating="B/B1",  ytw=9.5),
    dict(name="1.75% Convertible",     coupon=1.75, maturity="Dec 2031", face_m=2250, rating="BB-",   ytw=None),
    dict(name="1.75% Conv. (Apr '26)", coupon=1.75, maturity="2031/32",  face_m=4000, rating="N/R",   ytw=None),
]

# Secured DDTL facilities (structurally senior to unsecured notes)
SECURED_DEBT = [
    dict(name="DDTL 1.0", drawn_m=2300,  rate="~15% float",    maturity="Mar 2028", note="GPU-asset backed"),
    dict(name="DDTL 2.0", drawn_m=4950,  rate="~11% variable", maturity="~2029",    note="Contract-backed SPV"),
    dict(name="DDTL 3.0", drawn_m=2600,  rate="SOFR+4.00%",    maturity="Aug 2030", note="Asset-backed SPV"),
    dict(name="DDTL 4.0", drawn_m=8500,  rate="SOFR+2.25%",    maturity="Mar 2032", note="First IG-rated GPU financing (A3/A)"),
    dict(name="DDTL 5.0", drawn_m=3100,  rate="SOFR+4.50%",    maturity="~2031",    note="Apr '26 raise; 99 OID — eff. ~8.75% at current SOFR"),
    dict(name="Revolver",  drawn_m=0,     rate="Variable",       maturity="Nov 2029", note="$2.5B capacity, undrawn"),
]

# April 2026 capital markets activity (confirmed; first appears in Q2 2026 filings)
NEW_DEBT_APRIL_2026_M = 9_850  # DDTL 5.0 ($3.1B) + 9.75% HY ($2.75B) + 1.75% converts ($4.0B)

RECENT_EVENTS = [
    dict(
        date="April 2026", category="Secured DDTL",
        instrument="DDTL 5.0 — New Delayed Draw Term Loan",
        amount_m=3100, coupon="SOFR + 450 bps", pricing="99 OID", maturity="~2031",
        rating="N/R (asset-backed)",
        commentary=(
            "Asset-backed secured facility; structurally senior to HY bonds. "
            "Effective cost ~8.75% at SOFR ~4.25%. 99 OID = $31M upfront cost / 1pt immediate loss on face. "
            "Consistent with DDTL 3.0 pricing (SOFR+400) — marginal increase reflects market conditions."
        ),
    ),
    dict(
        date="April 2026", category="HY Bond",
        instrument="9.75% Senior Notes",
        amount_m=2750, coupon="9.75%", pricing="Par", maturity="~2032",
        rating="B/B1",
        commentary=(
            "Consistent with existing bond curve (9.00–9.75% range). Priced at par. "
            "Structurally subordinated to all DDTL/secured debt (~$21.4B). "
            "Annual cash interest burden: ~$268M."
        ),
    ),
    dict(
        date="April 2026", category="Convertible",
        instrument="1.75% Convertible Notes",
        amount_m=4000, coupon="1.75%", pricing="Par", maturity="2031/2032",
        rating="N/R",
        commentary=(
            "Low cash coupon relieves near-term interest burden ($70M/yr vs ~$391M/yr for equivalent HY). "
            "Dilutive to equity at conversion; typically priced with 30–40% premium above stock. "
            "Blended cost drag: lowers blended debt rate from ~8.75% toward ~8.2% on combined stack."
        ),
    ),
]

# Stock / market data (as of May 5, 2026) — source: Finviz
PRICE_DATA = dict(
    current=127.89,
    ipo_price=40.00,
    price_1m_ago=114.0,
    price_mtd_start=120.0,
    price_ytd_start=71.85,
    market_cap_b=70.3,
    ev_b=96.0,
    short_interest_pct=19.1,
    week_52_low=49.06,
    week_52_high=187.00,
)

# Key operating metrics
OPERATING_DATA = dict(
    rpo_fy2024_b=15.1,
    backlog_fy2025_b=66.8,
    rpo_q1_2026_b=99.4,           # reported May 8 2026 — up from $66.8B at YE2025
    msft_rev_share_2025=0.67,
    guidance_rev_low=12000,        # FY2026 guidance reaffirmed
    guidance_rev_high=13000,
    guidance_capex_low=31000,      # updated from $30-35B → $31-35B
    guidance_capex_high=35000,
    q2_2026_rev_low=2450,          # Q2 2026 guidance: $2.45–2.60B
    q2_2026_rev_high=2600,
    q2_2026_interest_low=650,      # Q2 2026 interest guidance: $650–730M
    q2_2026_interest_high=730,
    q1_2026_ocf=2984,              # Q1 2026 operating cash flow (actual)
    next_earnings_quarter="Q2 2026",
    next_earnings_date_est="Mid-August 2026",
)

# Pro-forma debt/LTV metrics (Q1 2026 actual Mar 31 + April 2026 confirmed raises)
PF_DEBT_M = 24_859 + NEW_DEBT_APRIL_2026_M   # = 34,709
PF_LTV_PCT = PF_DEBT_M / (96_000) * 100       # PF Debt / EV ($96B) = 36.2%
