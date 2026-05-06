import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from model import build_model, get_defaults, get_scenario_assumptions, SCENARIOS
from data import (PEERS, BONDS, SECURED_DEBT, PRICE_DATA, OPERATING_DATA,
                  RECENT_EVENTS, PF_DEBT_M, PF_LTV_PCT, NEW_DEBT_APRIL_2026_M)
import bloomberg as bbg

st.set_page_config(page_title="CoreWeave Credit Model | CRWV", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
[data-testid="stSidebar"] { background:#111827; }
.metric-card { background:#1f2937; border-radius:8px; padding:14px; margin:2px; }
.metric-label { font-size:11px; color:#9ca3af; text-transform:uppercase; letter-spacing:.05em; }
.metric-value { font-size:22px; font-weight:700; color:#f9fafb; margin:4px 0; }
.metric-delta { font-size:11px; }
.green  { color:#10b981; } .red { color:#ef4444; } .yellow { color:#f59e0b; }
.section-hdr { font-size:12px; font-weight:600; color:#6b7280; text-transform:uppercase;
               letter-spacing:.08em; margin:14px 0 6px; border-bottom:1px solid #374151;
               padding-bottom:3px; }
.quality-warn { background:#7f1d1d22; border-left:3px solid #ef4444;
                padding:10px 14px; border-radius:4px; margin:8px 0; font-size:13px; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def fm(v, d=0):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    if abs(v) >= 1000: return f"${v/1000:,.{d}f}B"
    return f"${v:,.{d}f}M"

def fp(v, d=1):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    return f"{v:.{d}f}%"

def fx(v, d=1):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    return f"{v:.{d}f}x"

def signed(v, d=0):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    if abs(v) >= 1000: s = f"${abs(v)/1000:,.{d}f}B"
    else:              s = f"${abs(v):,.{d}f}M"
    return f"({s})" if v < 0 else s

BLUE=  "#3b82f6"; ORANGE="#f97316"; GREEN="#10b981"
RED=   "#ef4444"; YELLOW="#f59e0b"; GRAY="#6b7280"
PURPLE="#8b5cf6"

# ── Scenario slider values (used both for loading into sidebar and for fixed charts) ──
SCENARIO_SLIDER_VALS = {
    "base": dict(
        mw_q1=950,  mw_q2=1200, mw_q3=1550, mw_q4=2000,
        mw_27=2700, mw_28=3500, mw_29=4200,
        rev_per_mw=1.75, gross_margin=69,
        em_26=49, em_27=51, em_28=53, em_29=55,
        capex_per_mw=8.0, maint_pct=3,
        td_26=47, td_27=60, td_28=70, td_29=67,
        int_rate=8.25, sbc_pct=14, da_pct=47,
        tax_rate=5, eq_book=5000, coe=12, wc_days=15,
    ),
    "bull": dict(
        mw_q1=1000, mw_q2=1400, mw_q3=1900, mw_q4=2500,
        mw_27=3400, mw_28=4700, mw_29=6000,
        rev_per_mw=1.88, gross_margin=72,
        em_26=53, em_27=57, em_28=60, em_29=63,
        capex_per_mw=8.0, maint_pct=3,
        td_26=44, td_27=57, td_28=63, td_29=52,
        int_rate=7.5, sbc_pct=13, da_pct=47,
        tax_rate=5, eq_book=5000, coe=12, wc_days=15,
    ),
    "bear": dict(
        mw_q1=750,  mw_q2=850,  mw_q3=1000, mw_q4=1150,
        mw_27=1500, mw_28=1900, mw_29=2200,
        rev_per_mw=1.55, gross_margin=66,
        em_26=42, em_27=43, em_28=44, em_29=45,
        capex_per_mw=8.0, maint_pct=3,
        td_26=51, td_27=68, td_28=82, td_29=90,
        int_rate=9.5, sbc_pct=16, da_pct=47,
        tax_rate=5, eq_book=5000, coe=12, wc_days=15,
    ),
}

# Initialise session state from base defaults on first load
for _k, _v in SCENARIO_SLIDER_VALS["base"].items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Bloomberg session state ───────────────────────────────────────────────────
if "bbg_data" not in st.session_state:
    st.session_state["bbg_data"] = {"available": False, "price": None,
                                     "peers": None, "bond_ytw": None,
                                     "rf_rate": None, "as_of": None}

def _apply_bbg(raw: dict):
    """Merge live Bloomberg data over static data.py values."""
    st.session_state["bbg_data"] = raw

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ CoreWeave Credit Model")
    st.caption("CRWV | May 2026 | SEC filings + press releases")

    # Bloomberg refresh
    bbg_state = st.session_state["bbg_data"]
    if bbg_state["available"]:
        st.success(f"Bloomberg live  ·  {bbg_state['as_of']}", icon="🟢")
    else:
        st.caption("Bloomberg: not connected  ·  showing static data")
    if st.button("🔄 Refresh Bloomberg data", use_container_width=True):
        with st.spinner("Fetching from Bloomberg Terminal…"):
            raw = bbg.fetch_all()
        if raw["available"]:
            _apply_bbg(raw)
            st.success("Live data loaded.", icon="✅")
            st.rerun()
        else:
            st.warning("Bloomberg unavailable. Check that Terminal is running and blpapi is installed.")
    st.divider()

    # Scenario loader
    sc_load = st.selectbox(
        "Load scenario as starting point",
        ["base", "bull", "bear", "custom"],
        format_func=lambda k: {
            "base":   "Base — conservative credit anchor",
            "bull":   "Bull — executes on guidance",
            "bear":   "Bear — severe stress",
            "custom": "Custom — manual inputs below",
        }[k],
        key="sc_load",
    )
    if sc_load != "custom" and sc_load in SCENARIO_SLIDER_VALS:
        _prev = st.session_state.get("_last_sc_load")
        if _prev != sc_load:
            for _k, _v in SCENARIO_SLIDER_VALS[sc_load].items():
                st.session_state[_k] = _v
            st.session_state["_last_sc_load"] = sc_load
            st.rerun()
    st.caption("Adjust any slider below to customise from the loaded scenario.")
    st.divider()

    with st.expander("MW Online — Core Driver", expanded=True):
        st.markdown('<div class="section-hdr">Quarterly 2026</div>', unsafe_allow_html=True)
        mw_q1 = st.slider("Q1 2026E", 500, 2500, step=50, key="mw_q1",
            help="Base: 850 MW. Mgmt guided $1.9–2.0B Q1 rev; at $1.75M/MW ≈ 1,090–1,140 MW. "
                 "Credit base uses lower ramp — execution delays common in GPU buildouts.")
        mw_q2 = st.slider("Q2 2026E", 500, 3000, step=50, key="mw_q2",
            help="Base: 1,050 MW. Apr '26 raises confirm continued buildout but ramp timing uncertain.")
        mw_q3 = st.slider("Q3 2026E", 500, 4000, step=100, key="mw_q3",
            help="Base: 1,300 MW. H2 2026 ramp. Bull: 1,900 MW if Blackwell on schedule.")
        mw_q4 = st.slider("Q4 2026E", 500, 5000, step=100, key="mw_q4",
            help="Base: 1,600 MW → ~$8.4B FY2026E revenue. Bull: 2,500 MW → ~$12.5B (in-line with guidance).")
        st.markdown('<div class="section-hdr">Annual 2027–2029 (avg. active MW)</div>', unsafe_allow_html=True)
        mw_27 = st.slider("FY 2027E", 500, 7000, step=100, key="mw_27",
            help="Base: 2,100 MW. Contracted capacity is 3.1 GW but assumes partial utilisation / delays.")
        mw_28 = st.slider("FY 2028E", 500, 9000, step=100, key="mw_28",
            help="Base: 2,700 MW. GPU obsolescence risk as Rubin / next-gen arrives.")
        mw_29 = st.slider("FY 2029E", 500, 12000, step=100, key="mw_29",
            help="Base: 3,200 MW. Credit base stays well below mgmt's 5,000+ MW target.")

    with st.expander("Unit Economics"):
        rev_per_mw   = st.number_input("Revenue / MW / Qtr ($M)", 0.5, 5.0, step=0.05, key="rev_per_mw",
            help="Base: $1.75M. FY2025 actual: $1.85M. Bear: $1.55M as GPU supply normalises. "
                 "Bull: $1.88M modest Blackwell premium.")
        gross_margin = st.slider("Gross Margin (%)", 50, 85, step=1, key="gross_margin",
            help="FY2025: 71.7%. Base: 69% — power cost inflation, lower-margin contracts.")
        st.markdown("**Adj. EBITDA Margin** — *see quality note in Credit Metrics tab*")
        em_26 = st.slider("2026E", 35, 70, step=1, key="em_26",
            help="Base: 47%. Mgmt said margins bottom Q1; credit base stays conservative full-year.")
        em_27 = st.slider("2027E", 35, 75, step=1, key="em_27",
            help="Base: 49%. Slow expansion as fixed costs are spread over more revenue.")
        em_28 = st.slider("2028E", 35, 80, step=1, key="em_28",
            help="Base: 51%.")
        em_29 = st.slider("2029E", 35, 80, step=1, key="em_29",
            help="Base: 53%. Credit base LT margin well below mgmt target of 65%+.")

    with st.expander("Capex"):
        capex_per_mw = st.number_input("Build Cost / New MW ($M)", 2.0, 20.0, step=0.5, key="capex_per_mw",
            help="All-in cost per MW. H100/H200 ~$8–12M/MW. Blackwell may be higher initially.")
        maint_pct    = st.slider("Maintenance Capex (% Revenue)", 0, 10, step=1, key="maint_pct",
            help="Ongoing maintenance. GPU useful life ~3–5 yrs; true economic maintenance capex is higher.")

    with st.expander("Debt & Interest"):
        td_26 = st.slider("Total Debt FY2026E ($B)", 20, 100, step=1, key="td_26",
            help="Base: $47B. Q4 2025: $21.4B + Apr '26 raises ($9.85B) + continued capex draws. "
                 "Bear: $51B as draws continue despite revenue miss.") * 1000.0
        td_27 = st.slider("Total Debt FY2027E ($B)", 30, 130, step=2, key="td_27",
            help="Base: $60B. DDTL 1.0 matures Mar 2028 — must refinance ~$2.3B.") * 1000.0
        td_28 = st.slider("Total Debt FY2028E ($B)", 30, 150, step=2, key="td_28",
            help="Base: $70B. Peak leverage year in base case.") * 1000.0
        td_29 = st.slider("Total Debt FY2029E ($B)", 20, 150, step=2, key="td_29",
            help="Base: $67B. Bull: ~$52B as FCF turns positive and deleveraging begins.") * 1000.0
        int_rate = st.slider("Blended Interest Rate (%)", 5.0, 15.0, step=0.25, key="int_rate",
            help="Base: 8.25%. Apr '26 converts (1.75%) drag blended rate lower vs. DDTLs. "
                 "Bear: 9.5% as capital markets tighten.")

    with st.expander("EBITDA Quality & Other"):
        sbc_pct = st.slider("SBC (% Revenue)", 5, 25, step=1, key="sbc_pct",
            help="FY2025 implied: ~13.4% ($685M). Real economic cost excluded from Adj. EBITDA.")
        da_pct   = st.slider("D&A (% Revenue)", 20, 80, step=1, key="da_pct",
            help="FY2025 implied: ~47%. D&A is real GPU asset wearing-out (3–5yr life).")
        tax_rate = st.slider("Cash Tax Rate (%)", 0, 35, step=1, key="tax_rate",
            help="Large NOL carryforward. Minimal cash taxes near-term.")
        eq_book  = st.number_input("Book Equity ($M)", 1000, 20000, step=500, key="eq_book",
            help="Estimated post-IPO book equity. Used for balance sheet.")
        coe      = st.slider("Cost of Equity (%)", 10, 30, step=1, key="coe",
            help="High-beta AI infra; beta ~2.5+. 18–22% under CAPM.")
        wc_days  = st.slider("WC Days", 5, 30, step=1, key="wc_days",
            help="Net WC as days of revenue growth.")

# ── Build custom model + scenario models ─────────────────────────────────────
custom_a = {
    "mw": {"Q1 2026E": mw_q1, "Q2 2026E": mw_q2, "Q3 2026E": mw_q3, "Q4 2026E": mw_q4,
           "FY 2027E": mw_27, "FY 2028E": mw_28, "FY 2029E": mw_29},
    "rev_per_mw": rev_per_mw, "gross_margin": gross_margin,
    "ebitda_margin_2026": em_26, "ebitda_margin_2027": em_27,
    "ebitda_margin_2028": em_28, "ebitda_margin_2029": em_29,
    "capex_per_mw": capex_per_mw, "maint_capex_pct": maint_pct,
    "total_debt_2026": td_26, "total_debt_2027": td_27,
    "total_debt_2028": td_28, "total_debt_2029": td_29,
    "interest_rate": int_rate, "da_pct": da_pct, "sbc_pct": sbc_pct,
    "tax_rate": tax_rate, "equity_book": eq_book, "cost_of_equity": coe,
    "wc_days": wc_days,
}

sc_models = {k: build_model(get_scenario_assumptions(k)) for k in SCENARIOS}
custom_m    = build_model(custom_a)
df          = custom_m["all"]
qdf         = custom_m["quarterly"]
adf         = custom_m["annual"]
latest_q    = qdf[qdf["is_actual"]].iloc[-1]

# ── Resolve live vs. static data ─────────────────────────────────────────────
_bbg = st.session_state["bbg_data"]
# Price data: overlay live fields where available
_pd = dict(PRICE_DATA)
if _bbg["price"]:
    for _k in ("current", "market_cap_b", "ev_b", "week_52_high", "week_52_low", "short_interest_pct"):
        if _bbg["price"].get(_k) is not None:
            _pd[_k] = _bbg["price"][_k]
live_price = _pd

# Peers: use live if available, else static
live_peers = _bbg["peers"] if _bbg["peers"] else PEERS

# Bonds: overlay live YTW where available
_bond_ytw = _bbg["bond_ytw"] or {}
live_bonds = []
for b in live_bonds:
    bd = dict(b)
    if bd["name"] in _bond_ytw:
        bd["ytw"] = _bond_ytw[bd["name"]]
    live_bonds.append(bd)

# Risk-free rate: expose for display (doesn't auto-adjust CoE slider)
live_rf = _bbg["rf_rate"]
bbg_as_of = _bbg["as_of"]

# ── Header ────────────────────────────────────────────────────────────────────
h1, h2, h3 = st.columns([3, 1, 1])
with h1:
    st.markdown("## CoreWeave, Inc. (CRWV)")
    st.caption("GPU Cloud Infrastructure | HY Credit | B+/Ba3 Issuer | 9.00–9.75% Sr Notes")
with h2:
    st.metric("Stock Price", f"${live_price['current']:.2f}",
              f"YTD: +{(live_price['current']/live_price['price_ytd_start']-1)*100:.1f}%")
with h3:
    st.metric("Enterprise Value", f"${live_price['ev_b']:.1f}B",
              f"Mkt Cap: ${live_price['market_cap_b']:.1f}B")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tabs = st.tabs(["📊 Summary", "📈 Income Statement", "💸 Cash Flow",
                "🏦 Credit Metrics", "🗂 Balance Sheet", "📐 ROIC / ROA",
                "🔍 Relative Value", "⚖️ Recovery Analysis"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    ltm_rev    = latest_q.get("revenue_ttm")
    ltm_ebitda = latest_q.get("adj_ebitda_ttm")
    ltm_ce     = latest_q.get("cash_ebitda_ttm")
    icr        = latest_q.get("icr_ttm")
    cash_icr   = latest_q.get("cash_icr_ttm")
    net_lev    = latest_q.get("net_lev")

    k1,k2,k3,k4,k5,k6 = st.columns(6)
    with k1: st.metric("LTM Revenue",        fm(ltm_rev,1))
    with k2: st.metric("LTM Adj. EBITDA",    fm(ltm_ebitda,1),
                       fp(ltm_ebitda/ltm_rev*100 if ltm_rev else None)+" margin")
    with k3: st.metric("LTM Cash EBITDA",    fm(ltm_ce,1),
                       "ex-SBC — credit basis")
    with k4: st.metric("ICR (TTM)",          fx(icr),
                       f"Cash ICR: {fx(cash_icr)}")
    with k5: st.metric("Net Leverage",       fx(net_lev),
                       "⚠ high" if net_lev and net_lev > 5 else "ok")
    with k6: st.metric("MW Online",          f"{int(latest_q['mw_online']):,} MW",
                       f"RPO ~${OPERATING_DATA['backlog_current_b']:.0f}B")

    # PF metrics row — reflects April 2026 confirmed raises
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.metric("PF Total Debt (Apr '26)",
                  f"${PF_DEBT_M/1000:.1f}B",
                  f"+${NEW_DEBT_APRIL_2026_M/1000:.2f}B Apr raises vs Q4'25")
    with p2:
        st.metric("PF LTV (Debt / EV)",
                  f"{PF_LTV_PCT:.1f}%",
                  f"PF Debt ${PF_DEBT_M/1000:.1f}B / EV ${live_price['ev_b']:.0f}B",
                  delta_color="inverse")
    with p3:
        gross_lev_q = latest_q.get("gross_lev")
        st.metric("Gross Leverage (TTM)",
                  fx(gross_lev_q),
                  "Total Debt / Adj. EBITDA")
    with p4:
        st.metric(f"Next Earnings — {OPERATING_DATA['next_earnings_quarter']}",
                  OPERATING_DATA["next_earnings_date_est"],
                  f"FY26 guide: ${OPERATING_DATA['guidance_rev_low']//1000}–{OPERATING_DATA['guidance_rev_high']//1000}B rev | ${OPERATING_DATA['guidance_capex_low']//1000}–{OPERATING_DATA['guidance_capex_high']//1000}B capex")

    st.divider()

    # ── Scenario comparison charts ────────────────────────────────────────────
    st.markdown("**Scenario Comparison — Base / Bull / Bear + Custom**")
    st.caption("Sidebar inputs = Custom. Scenarios are fixed assumptions — see rationale in credit assessment below.")

    ann_periods = ["FY 2024","FY 2025","FY 2026E","FY 2027E","FY 2028E","FY 2029E"]

    def sc_ann(key, col):
        m = sc_models[key]
        rows = m["all"][m["all"]["period"].isin(ann_periods)].set_index("period")
        return [rows.loc[p, col] if p in rows.index else None for p in ann_periods]

    def custom_ann(col):
        rows = df[df["period"].isin(ann_periods)].set_index("period")
        return [rows.loc[p, col] if p in rows.index else None for p in ann_periods]

    ch1, ch2 = st.columns(2)
    with ch1:
        st.markdown("*Revenue ($M)*")
        fig = go.Figure()
        # Actuals bar
        act_vals  = sc_ann("base", "revenue")[:2]
        proj_base = [None, None] + sc_ann("base",  "revenue")[2:]
        proj_bull = [None, None] + sc_ann("bull",  "revenue")[2:]
        proj_bear = [None, None] + sc_ann("bear",  "revenue")[2:]
        proj_cust = [None, None] + custom_ann("revenue")[2:]
        fig.add_bar(x=ann_periods, y=act_vals + [None]*4, name="Actual", marker_color=GRAY)
        fig.add_scatter(x=ann_periods, y=proj_base, mode="lines+markers", name="Base",
                        line=dict(color=BLUE,   width=2))
        fig.add_scatter(x=ann_periods, y=proj_bull, mode="lines+markers", name="Bull",
                        line=dict(color=GREEN,  width=2))
        fig.add_scatter(x=ann_periods, y=proj_bear, mode="lines+markers", name="Bear",
                        line=dict(color=RED,    width=2))
        fig.add_scatter(x=ann_periods, y=proj_cust, mode="lines+markers", name="Custom",
                        line=dict(color=ORANGE, width=2, dash="dot"))
        fig.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                          font=dict(color="#d1d5db"), legend=dict(orientation="h", y=1.12),
                          yaxis=dict(gridcolor="#1f2937"), height=300, margin=dict(t=5,b=30))
        st.plotly_chart(fig, use_container_width=True)

    with ch2:
        st.markdown("*FCF ($M) — negative = burning cash*")
        fig2 = go.Figure()
        fig2.add_bar(x=ann_periods, y=[None,None]+[None]*4, name="")  # spacer
        for key, col, name in [("base","fcf","Base"),("bull","fcf","Bull"),
                                ("bear","fcf","Bear")]:
            vals = [None, None] + sc_ann(key, col)[2:]
            fig2.add_scatter(x=ann_periods, y=vals, mode="lines+markers", name=name,
                             line=dict(color=SCENARIOS[key]["color"], width=2))
        cust_fcf = [None, None] + custom_ann("fcf")[2:]
        fig2.add_scatter(x=ann_periods, y=cust_fcf, mode="lines+markers", name="Custom",
                         line=dict(color=ORANGE, width=2, dash="dot"))
        fig2.add_hline(y=0, line_color="#374151", line_width=1)
        fig2.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                           font=dict(color="#d1d5db"), legend=dict(orientation="h", y=1.12),
                           yaxis=dict(gridcolor="#1f2937"), height=300, margin=dict(t=5,b=30))
        st.plotly_chart(fig2, use_container_width=True)

    ch3, ch4 = st.columns(2)
    with ch3:
        st.markdown("*Net Leverage (x) — Net Debt / Adj. EBITDA*")
        fig3 = go.Figure()
        def _get(m_all, p, col):
            rows = m_all[m_all["period"] == p]
            if rows.empty or col not in rows.columns: return None
            v = rows[col].values[0]
            return None if pd.isna(v) else float(v)

        for key in ["base","bull","bear"]:
            vals = [None, None] + [_get(sc_models[key]["all"], p, "net_lev")
                                   for p in ann_periods[2:]]
            fig3.add_scatter(x=ann_periods, y=vals, mode="lines+markers",
                             name=SCENARIOS[key]["label"],
                             line=dict(color=SCENARIOS[key]["color"], width=2))
        cust_nl = [None, None] + [_get(df, p, "net_lev") for p in ann_periods[2:]]
        fig3.add_scatter(x=ann_periods, y=cust_nl, mode="lines+markers", name="Custom",
                         line=dict(color=ORANGE, width=2, dash="dot"))
        fig3.add_hline(y=6, line_color=YELLOW, line_dash="dash", line_width=1, annotation_text="6x")
        fig3.add_hline(y=4, line_color=GREEN,  line_dash="dash", line_width=1, annotation_text="4x")
        fig3.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                           font=dict(color="#d1d5db"), legend=dict(orientation="h", y=1.12),
                           yaxis=dict(gridcolor="#1f2937"), height=300, margin=dict(t=5,b=30))
        st.plotly_chart(fig3, use_container_width=True)

    with ch4:
        st.markdown("*Total Debt ($M)*")
        fig4 = go.Figure()
        for key in ["base","bull","bear"]:
            vals = [None, None] + [
                sc_models[key]["all"][sc_models[key]["all"]["period"]==p]["total_debt"].values[0]
                if p in sc_models[key]["all"]["period"].values else None
                for p in ann_periods[2:]
            ]
            fig4.add_scatter(x=ann_periods, y=vals, mode="lines+markers",
                             name=SCENARIOS[key]["label"],
                             line=dict(color=SCENARIOS[key]["color"], width=2))
        fig4.add_bar(x=ann_periods[:2],
                     y=[df[df["period"]==p]["total_debt"].values[0] if p in df["period"].values
                        else None for p in ann_periods[:2]],
                     name="Actual", marker_color=GRAY)
        fig4.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                           font=dict(color="#d1d5db"), legend=dict(orientation="h", y=1.12),
                           yaxis=dict(gridcolor="#1f2937"), height=300, margin=dict(t=5,b=30))
        st.plotly_chart(fig4, use_container_width=True)

    # Scenario summary table
    st.markdown("**Scenario Summary — Annual Forecasts**")
    sc_rows = []
    for p in ann_periods[2:]:
        row = {"Period": p}
        for key in ["bear","base","bull"]:
            m = sc_models[key]["all"]
            r = m[m["period"]==p]
            if r.empty: continue
            row[f"{SCENARIOS[key]['label']} Rev ($M)"]    = fm(r["revenue"].iloc[0])
            row[f"{SCENARIOS[key]['label']} EBITDA Mgn"]  = fp(r["ebitda_margin_pct"].iloc[0])
            row[f"{SCENARIOS[key]['label']} FCF ($M)"]    = signed(r["fcf"].iloc[0])
            row[f"{SCENARIOS[key]['label']} Net Lev"]     = fx(r["net_lev"].iloc[0])
        sc_rows.append(row)
    st.dataframe(pd.DataFrame(sc_rows).set_index("Period"), use_container_width=True)

    # Credit assessment
    st.divider()
    st.markdown("**Credit Assessment**")

    def _ca_card(sc_key, label, border_color):
        r2029 = sc_models[sc_key]["all"]
        r2029 = r2029[r2029["period"] == "FY 2029E"]
        rev   = f"~${sc_ann(sc_key,'revenue')[-1]/1000:.0f}B"
        nlev  = fx(r2029["net_lev"].values[0]) if not r2029.empty else "—"
        fcf_v = signed(sc_ann(sc_key,'fcf')[-1])
        rat   = SCENARIOS[sc_key]["rationale"]
        st.markdown(
            f'<div style="border-left:4px solid {border_color};background:#1f2937;'
            f'border-radius:6px;padding:16px 18px;height:100%;">'
            f'<div style="font-size:14px;font-weight:700;color:#f9fafb;margin-bottom:10px;">'
            f'{label}</div>'
            f'<div style="font-size:13px;color:#d1d5db;line-height:1.7;margin-bottom:12px;">'
            f'{rat}</div>'
            f'<div style="font-size:12px;color:#9ca3af;border-top:1px solid #374151;'
            f'padding-top:10px;line-height:2.0;">'
            f'<b style="color:#f9fafb;">FY2029E</b><br>'
            f'Revenue: {rev}&nbsp;&nbsp;|&nbsp;&nbsp;'
            f'Net Lev: {nlev}&nbsp;&nbsp;|&nbsp;&nbsp;'
            f'FCF: {fcf_v}'
            f'</div></div>',
            unsafe_allow_html=True
        )

    ca1, ca2, ca3 = st.columns(3)
    with ca1: _ca_card("bull", "🐂 Bull — executes on guidance", GREEN)
    with ca2: _ca_card("base", "📊 Base — credit conservative anchor", BLUE)
    with ca3: _ca_card("bear", "🐻 Bear — severe stress / impairment", RED)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — INCOME STATEMENT
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    show_q = st.toggle("Show quarterly periods", value=True)
    if show_q:
        inc_df = df[(df["is_quarterly"]) |
                    (df["period"].isin(["FY 2022","FY 2023"])) |
                    (~df["is_quarterly"] & ~df["is_actual"] &
                     ~df["period"].str.match(r"FY (2024|2025)$"))].copy()
    else:
        inc_df = df[~df["is_quarterly"]].copy()
    inc_df = inc_df.sort_values(["year","quarter"]).reset_index(drop=True)
    cols_p = inc_df["period"].tolist()

    def make_row(label, vals, fmt_fn):
        row = {"Metric": label}
        for p, v in zip(cols_p, vals):
            row[p] = fmt_fn(v)
        return row

    rev  = inc_df["revenue"].tolist()
    gp   = inc_df["gross_profit"].tolist()
    eb   = inc_df["adj_ebitda"].tolist()
    sbc  = inc_df["sbc"].tolist()
    ce   = inc_df["cash_ebitda"].tolist()
    da   = inc_df["da"].tolist()
    ebit = inc_df["ebit"].tolist()
    ie   = inc_df["interest_expense"].tolist()
    ni   = inc_df["net_income"].tolist()
    mw   = inc_df["mw_online"].tolist()

    def pct_ch(s):
        out = []
        for i,v in enumerate(s):
            if i==0 or not s[i-1] or pd.isna(s[i-1]) or s[i-1]==0: out.append(None)
            else: out.append((v/s[i-1]-1)*100)
        return out

    tbl = [
        make_row("Revenue ($M)",           rev,  fm),
        make_row("  YoY Growth",            pct_ch(rev),
                 lambda v: f"{v:+.1f}%" if v is not None and not pd.isna(v) else "NM"),
        make_row("Gross Profit ($M)",       gp,   fm),
        make_row("  Gross Margin",           [g/r*100 if r else None for g,r in zip(gp,rev)], fp),
        make_row("",                        [""]*len(cols_p), str),
        make_row("Adj. EBITDA ($M)",        eb,   fm),
        make_row("  Adj. EBITDA Margin",    [e/r*100 if r else None for e,r in zip(eb,rev)], fp),
        make_row("  Less: SBC (est.)",      [-s if s else None for s in sbc], fm),
        make_row("= Cash EBITDA ($M) ⚠",   ce,   fm),
        make_row("  Cash EBITDA Margin",    [c/r*100 if r else None for c,r in zip(ce,rev)], fp),
        make_row("",                        [""]*len(cols_p), str),
        make_row("D&A — est. ($M)",         da,   fm),
        make_row("EBIT — est. ($M)",        ebit, fm),
        make_row("  EBIT Margin",           [e/r*100 if r and e and not pd.isna(e) else None
                                              for e,r in zip(ebit,rev)], fp),
        make_row("",                        [""]*len(cols_p), str),
        make_row("Interest Expense ($M)",   ie,   fm),
        make_row("Net Income — est. ($M)",  ni,   fm),
        make_row("",                        [""]*len(cols_p), str),
        make_row("MW Online (EOP)",         mw,
                 lambda v: f"{int(v):,}" if v and not pd.isna(v) else "—"),
    ]

    st.dataframe(pd.DataFrame(tbl).set_index("Metric"), use_container_width=True, height=560)
    st.markdown('<div class="quality-warn">⚠ <b>EBITDA Quality Note:</b> '
                '"Cash EBITDA" deducts estimated stock-based comp (~13–15% of revenue). '
                'FY2025 implied SBC ~$685M — the entire gap between Adj. EBITDA ($3.09B) and GAAP EBITDA ($2.41B). '
                'D&A (~47% of revenue) represents real GPU asset wearing-out (3–5yr life); '
                'replacement capex is not optional. Credit ICR on Cash EBITDA basis is materially lower. '
                'See Credit Metrics tab.</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — CASH FLOW
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    # Annual periods to display (years as columns)
    cf_periods = df[~df["is_quarterly"]].sort_values("year").copy()
    cf_p = cf_periods["period"].tolist()

    def cf_row(label, col, fmt_fn=fm, negate=False):
        row = {"Item": label}
        for p in cf_p:
            v = cf_periods[cf_periods["period"]==p][col].values
            v = v[0] if len(v) else None
            if v is not None and not pd.isna(v) and negate:
                v = -v
            row[p] = fmt_fn(v)
        return row

    show_fin = st.toggle("Show full financing walk (below FCF → net change in cash)", value=False)

    # Build the CF walk table (items as rows, years as columns)
    cf_rows = [
        cf_row("Adj. EBITDA ($M)",         "adj_ebitda"),
        cf_row("  Less: Cash Interest",    "interest_expense", negate=True),
        cf_row("  Less: Cash Taxes",       "cash_tax",         negate=True),
        cf_row("  ± Change in NWC",        "dwc"),
        cf_row("  ± Other",               "other_financing",  fmt_fn=lambda v: fm(v) if v else "—"),
        {"Item": "= CFO ($M)", **{p: fm(cf_periods[cf_periods["period"]==p]["cfo"].values[0])
                                   if p in cf_periods["period"].values else "—" for p in cf_p}},
        cf_row("  Less: Capex",            "capex",            negate=True),
        {"Item": "= FCF ($M)", **{p: fm(cf_periods[cf_periods["period"]==p]["fcf"].values[0])
                                   if p in cf_periods["period"].values else "—" for p in cf_p}},
    ]

    if show_fin:
        cf_rows += [
            {"Item": "── Financing ──", **{p: "" for p in cf_p}},
            cf_row("  + Change in Debt",   "change_in_debt"),
            cf_row("  + Equity Raised",    "equity_raised"),
            cf_row("  + Other Financing",  "other_financing"),
            {"Item": "= Net Change in Cash ($M)",
             **{p: fm(cf_periods[cf_periods["period"]==p]["net_change_cash"].values[0])
                if p in cf_periods["period"].values and
                   "net_change_cash" in cf_periods.columns and
                   not pd.isna(cf_periods[cf_periods["period"]==p]["net_change_cash"].values[0])
                else "—" for p in cf_p}},
            {"Item": "  Beginning Cash",
             **{p: "—" for p in cf_p}},
            {"Item": "  Ending Cash ($M)",
             **{p: fm(cf_periods[cf_periods["period"]==p]["cash"].values[0])
                if p in cf_periods["period"].values else "—" for p in cf_p}},
        ]

    cf_tbl = pd.DataFrame(cf_rows).set_index("Item")
    st.dataframe(cf_tbl, use_container_width=True, height=420 if show_fin else 310)
    st.caption("Historical CFO/FCF estimated using consistent methodology. "
               "Actual reported CFO may differ due to non-cash items and WC classification. "
               "Change in Debt = model-projected debt issuance to fund capex gap.")

    st.divider()

    # Waterfall for selected projected annual period
    proj_ann = df[~df["is_quarterly"] & ~df["is_actual"] & df["fcf"].notna()]
    if not proj_ann.empty:
        sel_period = st.selectbox("Waterfall period", proj_ann["period"].tolist(), index=0)
        row = proj_ann[proj_ann["period"] == sel_period].iloc[0]

        labels   = ["Adj. EBITDA", "– Interest", "– Tax", "± ΔWC", "= CFO", "– Capex", "= FCF"]
        vals     = [row["adj_ebitda"], -row["interest_expense"],
                    -(row.get("cash_tax") or 0), row.get("dwc") or 0,
                    row.get("cfo") or 0, -row["capex"], row.get("fcf") or 0]
        measures = ["relative","relative","relative","relative","total","relative","total"]

        if show_fin:
            labels  += ["+ ΔDebt",          "+ ΔEquity",           "= Net ΔCash"]
            vals    += [row.get("change_in_debt") or 0,
                        row.get("equity_raised")  or 0,
                        row.get("net_change_cash") or 0]
            measures+= ["relative","relative","total"]

        fig_wf = go.Figure(go.Waterfall(
            measure=measures, x=labels, y=vals,
            connector=dict(line=dict(color="#374151")),
            increasing=dict(marker_color=GREEN),
            decreasing=dict(marker_color=RED),
            totals=dict(marker_color=BLUE),
            texttemplate="%{y:+,.0f}M", textposition="outside",
        ))
        fig_wf.update_layout(
            title=f"Cash Flow Walk — {sel_period}",
            plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
            font=dict(color="#d1d5db"), showlegend=False,
            height=400, margin=dict(t=40,b=20),
            yaxis=dict(gridcolor="#1f2937"),
        )
        st.plotly_chart(fig_wf, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — CREDIT METRICS
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    qcr     = qdf[qdf["icr_ttm"].notna()]
    last_cr = qcr.iloc[-1]

    # EBITDA quality box — prominent
    sbc_v   = last_cr.get("adj_ebitda_ttm",0) - last_cr.get("cash_ebitda_ttm",0)
    adj_icr = last_cr.get("icr_ttm")
    cash_icr_v = last_cr.get("cash_icr_ttm")
    adj_lev = last_cr.get("net_lev")
    cash_lev= last_cr.get("cash_net_lev")

    st.markdown("""<div class="quality-warn">
⚠ <b>EBITDA Quality — Credit Investors Should Use Cash EBITDA</b><br>
CoreWeave's Adj. EBITDA adds back stock-based compensation (~13–15% of revenue, ~$685M in FY2025).
SBC is a real economic cost that dilutes equity holders and represents ongoing compensation expense.
D&A (~47% of revenue) reflects real GPU asset depreciation — GPUs have 3–5yr useful lives,
so the asset base requires continuous heavy reinvestment. The gap between Adj. EBITDA and FCF is not
transitory; it is structural to the business model through at least 2028.
</div>""", unsafe_allow_html=True)

    # KPI cards
    c1,c2,c3,c4 = st.columns(4)
    def card(col, lbl, val, sub, cls):
        col.markdown(f"""<div class="metric-card">
            <div class="metric-label">{lbl}</div>
            <div class="metric-value {cls}">{val}</div>
            <div class="metric-delta">{sub}</div></div>""", unsafe_allow_html=True)

    card(c1, "ICR — Adj. EBITDA (TTM)", fx(adj_icr),
         f"Cash EBITDA ICR: {fx(cash_icr_v)}",
         "green" if adj_icr and adj_icr>=2.5 else "yellow" if adj_icr and adj_icr>=2 else "red")
    card(c2, "Net Leverage — Adj. EBITDA", fx(adj_lev),
         f"Cash EBITDA basis: {fx(cash_lev)}",
         "green" if adj_lev and adj_lev<=4 else "yellow" if adj_lev and adj_lev<=6 else "red")
    card(c3, "Gross Leverage", fx(last_cr.get("gross_lev")),
         "Total Debt / Adj. EBITDA TTM",
         "green" if last_cr.get("gross_lev",99)<=5 else "yellow" if last_cr.get("gross_lev",99)<=7 else "red")
    card(c4, "Debt Service (EBITDA−Capex)/Int", fx(last_cr.get("debt_svc")),
         "Negative = burning cash vs. debt cost",
         "red" if last_cr.get("debt_svc",0)<0 else "yellow" if last_cr.get("debt_svc",0)<1 else "green")

    st.divider()
    cm1, cm2 = st.columns(2)
    with cm1:
        st.markdown("**ICR — Adj. EBITDA vs. Cash EBITDA (TTM)**")
        fig_icr = go.Figure()
        act_cr = qcr[qcr["is_actual"]]
        prj_cr = qcr[~qcr["is_actual"]]
        for sub, col, name, dash in [(act_cr,"icr_ttm","Adj. EBITDA ICR (Actual)","solid"),
                                      (prj_cr,"icr_ttm","Adj. EBITDA ICR (Proj.)","dot"),
                                      (act_cr,"cash_icr_ttm","Cash EBITDA ICR (Actual)","solid"),
                                      (prj_cr,"cash_icr_ttm","Cash EBITDA ICR (Proj.)","dot")]:
            c = BLUE if "Adj" in name else PURPLE
            if sub.empty: continue
            fig_icr.add_scatter(x=sub["period"], y=sub[col], mode="lines+markers",
                                name=name, line=dict(color=c, width=2, dash=dash))
        fig_icr.add_hline(y=2.0, line_color=YELLOW, line_dash="dash",
                          annotation_text="2.0x floor")
        fig_icr.add_hline(y=2.5, line_color=GREEN, line_dash="dash",
                          annotation_text="2.5x comfortable")
        fig_icr.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                              font=dict(color="#d1d5db"), legend=dict(orientation="h",y=1.15),
                              yaxis=dict(gridcolor="#1f2937"), height=300, margin=dict(t=5,b=30))
        st.plotly_chart(fig_icr, use_container_width=True)

    with cm2:
        st.markdown("**Net Leverage — Adj. EBITDA vs. Cash EBITDA (TTM)**")
        fig_lev = go.Figure()
        for sub, col, name, dash in [(qcr,"net_lev","Net Lev (Adj. EBITDA)","solid"),
                                      (qcr,"cash_net_lev","Net Lev (Cash EBITDA)","dot")]:
            act = sub[sub["is_actual"]]
            prj = sub[~sub["is_actual"]]
            c = RED if "Adj" in name else ORANGE
            if not act.empty:
                fig_lev.add_scatter(x=act["period"], y=act[col], mode="lines+markers",
                                    name=name+" (Act.)", line=dict(color=c,width=2,dash="solid"))
            if not prj.empty:
                fig_lev.add_scatter(x=prj["period"], y=prj[col], mode="lines+markers",
                                    name=name+" (Proj.)", line=dict(color=c,width=2,dash="dot"))
        fig_lev.add_hline(y=6, line_color=YELLOW, line_dash="dash", annotation_text="6x")
        fig_lev.add_hline(y=4, line_color=GREEN,  line_dash="dash", annotation_text="4x target")
        fig_lev.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                              font=dict(color="#d1d5db"), legend=dict(orientation="h",y=1.15),
                              yaxis=dict(gridcolor="#1f2937"), height=300, margin=dict(t=5,b=30))
        st.plotly_chart(fig_lev, use_container_width=True)

    st.divider()
    st.markdown("**Debt Structure**")
    b1, b2 = st.columns(2)
    with b1:
        st.markdown("*Unsecured Bonds — structurally subordinated*")
        bdf = pd.DataFrame(live_bonds)
        bdf["face_m"] = bdf["face_m"].apply(lambda v: f"${v:,}M")
        bdf["ytw"]    = bdf["ytw"].apply(lambda v: f"{v:.2f}%" if v else "N/A")
        bdf.columns   = ["Name","Coupon","Maturity","Face","Rating","YTW"]
        st.dataframe(bdf, use_container_width=True, hide_index=True)
    with b2:
        st.markdown("*Secured DDTL Facilities — structurally senior (GPU/contract-backed)*")
        sdf = pd.DataFrame(SECURED_DEBT)
        sdf["drawn_m"] = sdf["drawn_m"].apply(lambda v: f"${v:,}M")
        sdf.columns    = ["Facility","Drawn","Rate","Maturity","Note"]
        st.dataframe(sdf, use_container_width=True, hide_index=True)
    st.caption("DDTL 4.0 rated A3/A (first IG-rated GPU-backed financing). "
               "Unsecured HY notes are structurally subordinated to all DDTL facilities.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — BALANCE SHEET
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    bs_df = df[~df["is_quarterly"]].sort_values("year").copy()
    bs_p  = bs_df["period"].tolist()

    def bs_row(label, col, fmt_fn=fm, negate=False):
        row = {"Item": label}
        for p in bs_p:
            v = bs_df[bs_df["period"]==p][col].values
            v = v[0] if len(v) else None
            if v is not None and not pd.isna(v) and negate: v = -v
            row[p] = fmt_fn(v)
        return row

    st.markdown("**Balance Sheet — Annual (estimated / projected)**")
    st.caption("Historical items partially estimated. PP&E net = prior + capex − D&A. "
               "Leases: FY2024 ($2.7B) and FY2025 ($8.4B) from 10-K; forward years estimated. "
               "Book equity: FY2025 estimated post-IPO; forward years evolved via NI + SBC.")

    bs_rows = [
        {"Item": "─── ASSETS ───",         **{p: "" for p in bs_p}},
        bs_row("Cash & Equivalents",        "cash"),
        bs_row("Accounts Receivable (est.)", "receivables"),
        bs_row("PP&E, Net (est.)",          "ppe_net"),
        bs_row("Other Assets (est.)",       "other_assets"),
        {"Item": "Total Assets (est.)",
         **{p: fm(bs_df[bs_df["period"]==p]["total_assets"].values[0])
            if p in bs_df["period"].values else "—" for p in bs_p}},
        {"Item": "",                        **{p: "" for p in bs_p}},
        {"Item": "─── LIABILITIES ───",    **{p: "" for p in bs_p}},
        bs_row("Total Debt",                "total_debt"),
        bs_row("Finance Leases (est.)",     "lease_liabilities"),
        bs_row("Accounts Payable (est.)",   "accounts_payable"),
        {"Item": "Other Liabilities (est.)",**{p: fm(500) for p in bs_p}},
        {"Item": "Total Liabilities (est.)",
         **{p: fm(bs_df[bs_df["period"]==p]["total_liabilities"].values[0])
            if p in bs_df["period"].values else "—" for p in bs_p}},
        {"Item": "",                        **{p: "" for p in bs_p}},
        {"Item": "─── EQUITY ───",         **{p: "" for p in bs_p}},
        bs_row("Book Equity (est.)",        "book_equity"),
        {"Item": "",                        **{p: "" for p in bs_p}},
        {"Item": "─── KEY METRICS ───",    **{p: "" for p in bs_p}},
        bs_row("Net Debt",                  "net_debt"),
        bs_row("NWC (Recv − AP, est.)",    "nwc"),
        {"Item": "Debt / (Debt+Equity) %",
         **{p: fp(bs_df[bs_df["period"]==p]["total_debt"].values[0] /
                 (bs_df[bs_df["period"]==p]["total_debt"].values[0] +
                  max(1, bs_df[bs_df["period"]==p]["book_equity"].fillna(1).values[0])) * 100)
            if p in bs_df["period"].values else "—" for p in bs_p}},
    ]

    st.dataframe(pd.DataFrame(bs_rows).set_index("Item"), use_container_width=True, height=560)

    st.divider()
    bsc1, bsc2 = st.columns(2)
    with bsc1:
        st.markdown("**Asset Composition Over Time**")
        fig_bs = go.Figure()
        fig_bs.add_bar(x=bs_p, y=bs_df["cash"].fillna(0),         name="Cash",         marker_color=GREEN)
        fig_bs.add_bar(x=bs_p, y=bs_df["receivables"].fillna(0),  name="Receivables",  marker_color=BLUE)
        fig_bs.add_bar(x=bs_p, y=bs_df["ppe_net"].fillna(0),      name="PP&E Net",     marker_color=PURPLE)
        fig_bs.add_bar(x=bs_p, y=bs_df["other_assets"].fillna(0), name="Other",        marker_color=GRAY)
        fig_bs.update_layout(barmode="stack", plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                             font=dict(color="#d1d5db"), legend=dict(orientation="h",y=1.1),
                             yaxis=dict(title="$M", gridcolor="#1f2937"),
                             height=320, margin=dict(t=5,b=30))
        st.plotly_chart(fig_bs, use_container_width=True)

    with bsc2:
        st.markdown("**Liabilities & Equity Composition**")
        fig_le = go.Figure()
        fig_le.add_bar(x=bs_p, y=bs_df["total_debt"],              name="Total Debt",   marker_color=RED)
        fig_le.add_bar(x=bs_p, y=bs_df["lease_liabilities"].fillna(0), name="Leases",  marker_color=ORANGE)
        fig_le.add_bar(x=bs_p, y=bs_df["book_equity"].fillna(0),   name="Book Equity",  marker_color=BLUE)
        fig_le.update_layout(barmode="stack", plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                             font=dict(color="#d1d5db"), legend=dict(orientation="h",y=1.1),
                             yaxis=dict(title="$M", gridcolor="#1f2937"),
                             height=320, margin=dict(t=5,b=30))
        st.plotly_chart(fig_le, use_container_width=True)

    st.markdown("**NWC & Cash Through Forecast**")
    fig_nwc = go.Figure()
    fig_nwc.add_scatter(x=bs_p, y=bs_df["cash"],    mode="lines+markers", name="Cash",    line=dict(color=GREEN, width=2))
    fig_nwc.add_scatter(x=bs_p, y=bs_df["nwc"],     mode="lines+markers", name="NWC",     line=dict(color=BLUE,  width=2))
    fig_nwc.add_scatter(x=bs_p, y=-bs_df["net_debt"],mode="lines+markers", name="−Net Debt", line=dict(color=RED, width=2, dash="dot"))
    fig_nwc.add_hline(y=0, line_color="#374151")
    fig_nwc.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                          font=dict(color="#d1d5db"), legend=dict(orientation="h",y=1.1),
                          yaxis=dict(title="$M", gridcolor="#1f2937"),
                          height=280, margin=dict(t=5,b=30))
    st.plotly_chart(fig_nwc, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 — ROIC / ROA
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.markdown("""**The Core Credit Question: Is this debt-fueled arb or a real business?**
If ROIC < WACC, value is being destroyed even with positive EBITDA. The bull case requires ROIC to
converge toward WACC as the asset base matures and D&A stabilises relative to revenue. The bear case:
ROIC stays negative because the GPU fleet constantly depreciates and requires heavy reinvestment,
and the business only earns its cost of capital during periods of supply-constrained pricing.""")

    rc1, rc2 = st.columns(2)
    with rc1:
        st.markdown("**ROIC vs. WACC — Custom Scenario**")
        roic_d = df[df["roic_pct"].notna()].copy()
        fig_r  = go.Figure()
        for sub, dash, name in [(roic_d[roic_d["is_actual"]],"solid","ROIC (Actual)"),
                                 (roic_d[~roic_d["is_actual"]],"dot","ROIC (Proj.)")]:
            if sub.empty: continue
            fig_r.add_scatter(x=sub["period"], y=sub["roic_pct"], mode="lines+markers",
                              name=name, line=dict(color=BLUE, width=2, dash=dash))
        fig_r.add_scatter(x=roic_d["period"], y=roic_d["wacc_pct"], mode="lines",
                          name="WACC (est.)", line=dict(color=YELLOW, width=2, dash="longdash"))
        fig_r.add_hline(y=0, line_color="#374151")
        fig_r.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                            font=dict(color="#d1d5db"), legend=dict(orientation="h",y=1.1),
                            yaxis=dict(title="%", gridcolor="#1f2937"),
                            height=320, margin=dict(t=5,b=30))
        st.plotly_chart(fig_r, use_container_width=True)

    with rc2:
        st.markdown("**ROIC — Base / Bull / Bear**")
        fig_rsc = go.Figure()
        for key in ["base","bull","bear"]:
            sm = sc_models[key]["all"]
            sm_filt = sm[sm["roic_pct"].notna() & ~sm["is_actual"]]
            if sm_filt.empty: continue
            fig_rsc.add_scatter(x=sm_filt["period"], y=sm_filt["roic_pct"],
                                mode="lines+markers", name=SCENARIOS[key]["label"],
                                line=dict(color=SCENARIOS[key]["color"], width=2))
        fig_rsc.add_hline(y=0, line_color="#374151")
        fig_rsc.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                              font=dict(color="#d1d5db"), legend=dict(orientation="h",y=1.1),
                              yaxis=dict(title="%", gridcolor="#1f2937"),
                              height=320, margin=dict(t=5,b=30))
        st.plotly_chart(fig_rsc, use_container_width=True)

    st.divider()
    st.markdown("**ROIC Walk Table — Custom scenario (sidebar inputs)**")
    roic_tbl = []
    for _, r in df[~df["is_quarterly"] & df["invested_capital"].notna()].sort_values("year").iterrows():
        roic_tbl.append({
            "Period":       r["period"],
            "EBIT (est.)":  fm(r.get("ebit")),
            "NOPAT (est.)": fm(r.get("nopat")),
            "Inv. Capital": fm(r["invested_capital"]),
            "ROIC":         fp(r["roic_pct"]),
            "WACC (est.)":  fp(r["wacc_pct"]),
            "Spread":       fp((r["roic_pct"]-r["wacc_pct"])
                               if pd.notna(r["roic_pct"]) else None),
        })
    st.dataframe(pd.DataFrame(roic_tbl).set_index("Period"), use_container_width=True)
    st.caption("ROIC = NOPAT / (Gross PP&E + NWC). NOPAT = EBIT × (1−tax). Gross PP&E = cumulative capex deployed "
               "(net PP&E collapses as D&A >> new capex in later years — gross avoids denominator blow-up). "
               "WACC uses market-value weights anchored to current market cap ($70.3B) + total debt; "
               "WACC declines as cheaper debt displaces equity in the capital structure. All estimates.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 7 — RELATIVE VALUE
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[6]:
    rv1, rv2 = st.columns([3, 2])
    with rv1:
        st.markdown("**Peer Multiples (May 2026)**")
        pdf = pd.DataFrame(live_peers)
        pdf["EV/LTM Rev"]   = pdf["ev_rev"].apply(lambda v: f"{v:.1f}x")
        pdf["EV/LTM EBITDA"]= pdf["ev_ebitda"].apply(lambda v: f"{v:.1f}x")
        st.dataframe(pdf[["ticker","name","EV/LTM Rev","EV/LTM EBITDA","rating","note"]]
                     .rename(columns={"ticker":"Ticker","name":"Company",
                                      "rating":"Rating","note":"Note"})
                     .set_index("Ticker"), use_container_width=True)

        fig_p = go.Figure()
        for p in live_peers:
            c = RED if p["ticker"]=="CRWV" else BLUE
            sz= 28  if p["ticker"]=="CRWV" else 16
            fig_p.add_scatter(x=[p["ev_rev"]], y=[p["ev_ebitda"]],
                              mode="markers+text", text=[p["ticker"]], textposition="top center",
                              marker=dict(size=sz, color=c, opacity=0.85), name=p["name"])
        fig_p.update_layout(
            xaxis=dict(title="EV / LTM Revenue (x)", gridcolor="#1f2937"),
            yaxis=dict(title="EV / LTM EBITDA (x)",  gridcolor="#1f2937"),
            plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
            font=dict(color="#d1d5db"), showlegend=False,
            height=340, margin=dict(t=10,b=30)
        )
        st.plotly_chart(fig_p, use_container_width=True)

    with rv2:
        pd_ = live_price
        st.markdown("**Price Performance**")
        perf = {"Period": ["1 Month","MTD","YTD","Since IPO (Mar 2025)"],
                "Return":  [f"{(pd_['current']/pd_['price_1m_ago']-1)*100:+.1f}%",
                            f"{(pd_['current']/pd_['price_mtd_start']-1)*100:+.1f}%",
                            f"{(pd_['current']/pd_['price_ytd_start']-1)*100:+.1f}%",
                            f"{(pd_['current']/pd_['ipo_price']-1)*100:+.1f}%"],
                "Level":   [f"${pd_['price_1m_ago']:.2f}→${pd_['current']:.2f}",
                            f"${pd_['price_mtd_start']:.2f}→${pd_['current']:.2f}",
                            f"${pd_['price_ytd_start']:.2f}→${pd_['current']:.2f}",
                            f"${pd_['ipo_price']:.2f}→${pd_['current']:.2f}"]}
        st.dataframe(pd.DataFrame(perf).set_index("Period"), use_container_width=True)

        st.markdown("**Market Snapshot**")
        model_rev26 = sum(custom_a["mw"][f"Q{q} 2026E"]*custom_a["rev_per_mw"] for q in [1,2,3,4])
        snap = {"Metric": ["Mkt Cap","EV","52W Low","52W High","Short Interest",
                           "EV/FY25 Rev","EV/FY26E Rev (custom)"],
                "Value":  [f"${pd_['market_cap_b']:.1f}B", f"${pd_['ev_b']:.1f}B",
                           f"${pd_['week_52_low']:.2f}", f"${pd_['week_52_high']:.2f}",
                           f"{pd_['short_interest_pct']:.1f}% float",
                           f"{pd_['ev_b']*1000/5131:.1f}x",
                           f"{pd_['ev_b']*1000/model_rev26:.1f}x"]}
        st.dataframe(pd.DataFrame(snap).set_index("Metric"), use_container_width=True)

    st.divider()
    op1,op2,op3,op4 = st.columns(4)
    op1.metric("Current Backlog", f"~${OPERATING_DATA['backlog_current_b']:.0f}B")
    op2.metric("FY2025 Backlog",  f"${OPERATING_DATA['backlog_fy2025_b']:.1f}B")
    op3.metric("MSFT Rev Share",  f"{OPERATING_DATA['msft_rev_share_2025']*100:.0f}% (FY2025)")
    op4.metric("Q1 2026 Interest Guided",
               f"${OPERATING_DATA['q1_2026_interest_low']}–${OPERATING_DATA['q1_2026_interest_high']}M")

    # ── Capital structure detail ──────────────────────────────────────────────
    st.divider()
    cs1, cs2 = st.columns(2)
    with cs1:
        st.markdown("**Secured Debt (DDTL Stack) — Structurally Senior**")
        sec_rows = []
        for d in SECURED_DEBT:
            sec_rows.append({"Facility": d["name"],
                             "Drawn ($M)": f"${d['drawn_m']:,}",
                             "Rate":       d["rate"],
                             "Maturity":   d["maturity"],
                             "Note":       d["note"]})
        sec_df = pd.DataFrame(sec_rows).set_index("Facility")
        total_secured = sum(d["drawn_m"] for d in SECURED_DEBT)
        st.dataframe(sec_df, use_container_width=True)
        st.caption(f"Total secured drawn: ${total_secured:,.0f}M. Revolver undrawn ($2.5B capacity).")

    with cs2:
        st.markdown("**Unsecured Bonds & Converts — Structurally Subordinated**")
        bond_rows = []
        for b in live_bonds:
            coupon_str = f"{b['coupon']:.2f}%" if b["coupon"] else "—"
            ytw_str = f"{b['ytw']:.2f}%" if b.get("ytw") else "—"
            bond_rows.append({"Instrument": b["name"],
                              "Face ($M)": f"${b['face_m']:,}",
                              "Coupon":    coupon_str,
                              "Maturity":  b["maturity"],
                              "Rating":    b["rating"],
                              "YTW":       ytw_str})
        bond_df = pd.DataFrame(bond_rows).set_index("Instrument")
        total_unsecured = sum(b["face_m"] for b in live_bonds)
        st.dataframe(bond_df, use_container_width=True)
        annual_cash_coupon = sum(b["face_m"] * (b["coupon"] or 0) / 100 for b in live_bonds)
        st.caption(f"Total unsecured face: ${total_unsecured:,}M. "
                   f"Annual cash coupon burden: ~${annual_cash_coupon:,.0f}M.")

    # ── Recent Events ─────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### Recent Capital Markets Activity")
    st.caption(
        f"April 2026: CoreWeave raised ${NEW_DEBT_APRIL_2026_M/1000:.2f}B across three tranches. "
        f"First appears in Q2 2026 balance sheet (next reporting: {OPERATING_DATA['next_earnings_date_est']}). "
        f"Pro-forma total debt: ${PF_DEBT_M/1000:.1f}B vs. Q4 2025 actual $21.4B."
    )

    for ev in RECENT_EVENTS:
        cat_color = {"Secured DDTL": RED, "HY Bond": ORANGE, "Convertible": BLUE}.get(ev["category"], GRAY)
        st.markdown(
            f'<div style="border-left:3px solid {cat_color}; padding:10px 16px; '
            f'background:#1f2937; border-radius:4px; margin:8px 0;">'
            f'<span style="font-size:11px;color:#9ca3af;text-transform:uppercase;">'
            f'{ev["date"]} — {ev["category"]}</span><br>'
            f'<b style="font-size:15px;">{ev["instrument"]}</b>'
            f' &nbsp;<span style="color:#9ca3af;font-size:13px;">'
            f'${ev["amount_m"]:,}M | {ev["coupon"]} | OID: {ev["pricing"]} | Due {ev["maturity"]}'
            f' | {ev["rating"]}</span><br>'
            f'<span style="font-size:13px;color:#d1d5db;">{ev["commentary"]}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

    total_apr = sum(e["amount_m"] for e in RECENT_EVENTS)
    ann_interest = sum(e["amount_m"] * (float(e["coupon"].replace("%","").replace("SOFR + ","").split(" ")[0])
                                        + (4.25 if "SOFR" in e["coupon"] else 0)) / 100
                       for e in RECENT_EVENTS)
    st.markdown(
        f'<div style="background:#111827;border:1px solid #374151;border-radius:6px;'
        f'padding:12px 16px;margin-top:12px;">'
        f'<b>Combined impact:</b> ${total_apr/1000:.2f}B new debt | '
        f'~${ann_interest/1000:.2f}B incremental annual interest | '
        f'PF total debt: ${PF_DEBT_M/1000:.1f}B | '
        f'PF LTV: {PF_LTV_PCT:.1f}% (vs. EV ${live_price["ev_b"]:.0f}B) | '
        f'PF gross leverage: {PF_DEBT_M / (latest_q.get("adj_ebitda_ttm",1) or 1):.1f}x LTM EBITDA'
        f'</div>',
        unsafe_allow_html=True
    )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 8 — RECOVERY ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[7]:
    st.markdown("""**Unsecured Bondholder Recovery — Distressed Waterfall**
Assumes a restructuring/sale event. Two valuation methods: going-concern (FCF multiple)
and asset liquidation (GPU fleet at distressed values). Secured DDTL holders are senior
and assumed to recover at or near par. Unsecured bonds receive the residual.""")

    # ── Capital structure constants ───────────────────────────────────────────
    TOTAL_SECURED = sum(d["drawn_m"] for d in SECURED_DEBT if d["drawn_m"] > 0)
    TOTAL_UNSECURED = sum(b["face_m"] for b in live_bonds)
    LEASE_AT_DISTRESS = 8449.0   # FY2025 actual; grows in forward years

    # ── Recovery assumptions sidebar ─────────────────────────────────────────
    st.markdown("#### Assumptions")
    ra1, ra2, ra3 = st.columns(3)

    with ra1:
        st.markdown("**Distress Scenario**")
        distress_year = st.selectbox("Year of distress", ["FY 2026E","FY 2027E","FY 2028E","FY 2029E"], index=1)
        distress_sc   = st.selectbox("Model scenario at distress", ["base","bear"], index=1,
                                     format_func=lambda k: SCENARIOS[k]["label"])
        # Pull EBITDA and PP&E gross from selected scenario/year
        _dm = sc_models[distress_sc]["all"]
        _dr = _dm[_dm["period"] == distress_year]
        _auto_ebitda = float(_dr["adj_ebitda"].values[0]) if not _dr.empty else 2000.0
        _auto_ppe_gross = float(_dr["ppe_gross"].values[0]) if not _dr.empty and "ppe_gross" in _dr.columns else 30000.0
        _auto_debt = float(_dr["total_debt"].values[0]) if not _dr.empty else 50000.0

        distress_ebitda = st.number_input("Distress EBITDA ($M)", 500, 20000,
                                          int(round(_auto_ebitda / 100) * 100), 100,
                                          help="Auto-filled from selected scenario/year. Adjust for further stress.")
        maint_capex_pct = st.slider("Maintenance capex (% EBITDA)", 10, 60, 30,
                                    help="Ongoing GPU replacement cost. High because GPUs obsolete in 3–5 yrs.")
        tax_rate_rv = st.slider("Tax rate at distress (%)", 0, 25, 5)

    with ra2:
        st.markdown("**Going Concern (FCF Multiple)**")
        fcf_multiple  = st.slider("Unlevered FCF multiple", 4, 16, 10,
                                  help="10x = reasonable for a contracted GPU cloud with long-dated backlog. "
                                       "Comps: data center REITs 18-22x, neocloud peers 30x+ (but pre-profit).")
        reorg_ltv_pct = st.slider("Target LTV for reorganised entity (%)", 40, 75, 60,
                                  help="Max debt the restructured business can carry. 60% LTV = ~3-4x leverage "
                                       "on a stabilised EBITDA basis. Determines takeback paper sizing.")
        cash_pct      = st.slider("Cash vs. takeback paper (% cash)", 0, 100, 40,
                                  help="What % of recovery is paid in cash vs. new PIK/notes issued by reorg entity. "
                                       "Depends on liquidity available at restructuring. 40% cash is typical in HY reorg.")

    with ra3:
        st.markdown("**Asset Liquidation**")
        gpu_haircut   = st.slider("GPU fleet liquidation haircut (%)", 20, 85, 55,
                                  help="Discount to gross PP&E in a forced sale. H100/H200 clusters lose value fast "
                                       "as newer GPUs (Blackwell, Rubin) come to market. 55% haircut = conservative.")
        lease_cure_pct= st.slider("Lease liabilities cured (%)", 10, 80, 40,
                                  help="% of lease obligations assumed by acquirer / paid in full. "
                                       "Remainder rejected in bankruptcy (unsecured claim). 40% cure = base.")
        admin_cost_pct= st.slider("Admin / restructuring costs (%)", 2, 8, 4,
                                  help="Legal, advisor, operational costs as % of EV. Typically 3-5% in large HY restructurings.")

    # ── Compute waterfall values ──────────────────────────────────────────────
    unlevered_fcf   = distress_ebitda * (1 - maint_capex_pct/100) * (1 - tax_rate_rv/100)
    ev_gc           = unlevered_fcf * fcf_multiple
    ev_liq          = _auto_ppe_gross * (1 - gpu_haircut/100)
    lease_claim     = LEASE_AT_DISTRESS * (lease_cure_pct/100)  # portion cured (senior)
    other_liab      = 500.0

    def _waterfall(ev):
        admin       = ev * admin_cost_pct / 100
        post_admin  = ev - admin
        secured_rec = min(TOTAL_SECURED, post_admin)
        post_sec    = max(0.0, post_admin - TOTAL_SECURED)
        lease_rec   = min(lease_claim, post_sec)
        post_lease  = max(0.0, post_sec - lease_claim)
        other_rec   = min(other_liab, post_lease)
        avail_unsec = max(0.0, post_lease - other_liab)
        rec_pct     = min(100.0, avail_unsec / TOTAL_UNSECURED * 100)
        rec_cod     = rec_pct / 100
        # Takeback paper: max new debt = reorg EV × LTV; rest is cash
        max_new_debt = ev * reorg_ltv_pct / 100
        cash_avail  = avail_unsec * (cash_pct / 100)
        paper_face  = avail_unsec * (1 - cash_pct / 100)
        # Cents on dollar breakdown
        cash_cod    = cash_avail / TOTAL_UNSECURED
        paper_cod   = paper_face / TOTAL_UNSECURED
        return dict(ev=ev, admin=admin, post_admin=post_admin,
                    secured_rec=secured_rec, post_sec=post_sec,
                    lease_rec=lease_rec, post_lease=post_lease,
                    other_rec=other_rec, avail_unsec=avail_unsec,
                    rec_pct=rec_pct, rec_cod=rec_cod,
                    cash_cod=cash_cod, paper_cod=paper_cod,
                    max_new_debt=max_new_debt,
                    unlevered_fcf=unlevered_fcf)

    gc   = _waterfall(ev_gc)
    liq  = _waterfall(ev_liq)

    # ── Recovery summary metrics ──────────────────────────────────────────────
    st.divider()
    st.markdown(f"**Recovery Summary — {distress_year} distress | {SCENARIOS[distress_sc]['label']} scenario**")

    m1,m2,m3,m4,m5,m6 = st.columns(6)
    m1.metric("Going Concern EV",   fm(gc["ev"]),   f"{fcf_multiple}x × ${unlevered_fcf:,.0f}M uFCF")
    m2.metric("Liquidation EV",     fm(liq["ev"]),  f"{100-gpu_haircut}¢ on gross PP&E")
    m3.metric("Secured Debt (senior)", fm(TOTAL_SECURED), "DDTL 1-5 at par")
    m4.metric("Unsecured Face",     fm(TOTAL_UNSECURED), f"{len(live_bonds)} instruments")
    m5.metric("GC Recovery",        f"{gc['rec_pct']:.0f}¢ / $1",
              f"{gc['cash_cod']*100:.0f}¢ cash + {gc['paper_cod']*100:.0f}¢ paper",
              delta_color="off")
    m6.metric("Liq. Recovery",      f"{liq['rec_pct']:.0f}¢ / $1",
              f"{liq['cash_cod']*100:.0f}¢ cash + {liq['paper_cod']*100:.0f}¢ paper",
              delta_color="off")

    # ── Waterfall charts ─────────────────────────────────────────────────────
    st.divider()
    wf1, wf2 = st.columns(2)

    def _make_waterfall(w, title):
        labels = ["EV", "Admin Costs", "Secured DDTL", "Lease (cured)", "Other Liab", "→ Unsecured"]
        vals   = [w["ev"], -w["admin"], -w["secured_rec"], -w["lease_rec"], -w["other_rec"], w["avail_unsec"]]
        meas   = ["absolute","relative","relative","relative","relative","total"]
        colors = [BLUE, RED, ORANGE, YELLOW, GRAY, GREEN if w["rec_pct"] > 50 else RED]
        fig = go.Figure(go.Waterfall(
            measure=meas, x=labels, y=vals,
            connector=dict(line=dict(color="#374151", width=1)),
            decreasing=dict(marker_color=RED),
            increasing=dict(marker_color=GREEN),
            totals=dict(marker_color=BLUE),
            texttemplate="%{y:+,.0f}M", textposition="outside",
            text=[fm(v) for v in vals],
        ))
        # Unsecured face reference line
        fig.add_hline(y=TOTAL_UNSECURED, line_color=ORANGE, line_dash="dash", line_width=1.5,
                      annotation_text=f"Unsecured face ${TOTAL_UNSECURED/1000:.1f}B",
                      annotation_position="top right")
        fig.update_layout(
            title=dict(text=title, font=dict(size=13, color="#d1d5db")),
            plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
            font=dict(color="#d1d5db"),
            yaxis=dict(title="$M", gridcolor="#1f2937"),
            height=380, margin=dict(t=40,b=30),
            showlegend=False,
        )
        return fig

    with wf1:
        st.plotly_chart(_make_waterfall(gc, f"Going Concern — {fcf_multiple}x uFCF"), use_container_width=True)
    with wf2:
        st.plotly_chart(_make_waterfall(liq, f"Asset Liquidation — {100-gpu_haircut}¢ on Gross PP&E"), use_container_width=True)

    # ── Recovery detail table ────────────────────────────────────────────────
    st.divider()
    st.markdown("**Waterfall Detail**")
    wf_tbl = {
        "Item": ["Enterprise Value", "Less: Admin / Restructuring",
                 "Available post-admin",
                 "Less: Secured DDTL (par)",
                 "Less: Lease liabilities (cured portion)",
                 "Less: Other operating liabilities",
                 "= Available to Unsecured",
                 "Unsecured face value",
                 "Recovery % (cents on dollar)",
                 "  of which: cash",
                 "  of which: takeback paper (new notes)",
                 "Implied reorg EV at 60% LTV (new debt capacity)"],
        "Going Concern": [
            fm(gc["ev"]), f"({fm(gc['admin'])})", fm(gc["post_admin"]),
            f"({fm(gc['secured_rec'])})", f"({fm(gc['lease_rec'])})", f"({fm(gc['other_rec'])})",
            fm(gc["avail_unsec"]), fm(TOTAL_UNSECURED),
            f"{gc['rec_pct']:.1f}¢ / $1",
            f"{gc['cash_cod']*100:.1f}¢ / $1  (${gc['cash_cod']*TOTAL_UNSECURED:,.0f}M cash)",
            f"{gc['paper_cod']*100:.1f}¢ / $1  (${gc['paper_cod']*TOTAL_UNSECURED:,.0f}M face)",
            fm(gc["max_new_debt"]),
        ],
        "Liquidation": [
            fm(liq["ev"]), f"({fm(liq['admin'])})", fm(liq["post_admin"]),
            f"({fm(liq['secured_rec'])})", f"({fm(liq['lease_rec'])})", f"({fm(liq['other_rec'])})",
            fm(liq["avail_unsec"]), fm(TOTAL_UNSECURED),
            f"{liq['rec_pct']:.1f}¢ / $1",
            f"{liq['cash_cod']*100:.1f}¢ / $1  (${liq['cash_cod']*TOTAL_UNSECURED:,.0f}M cash)",
            f"{liq['paper_cod']*100:.1f}¢ / $1  (${liq['paper_cod']*TOTAL_UNSECURED:,.0f}M face)",
            fm(liq["max_new_debt"]),
        ],
    }
    st.dataframe(pd.DataFrame(wf_tbl).set_index("Item"), use_container_width=True)

    # ── Recovery sensitivity ─────────────────────────────────────────────────
    st.divider()
    st.markdown("**Recovery Sensitivity — Going Concern (¢ / $1)**")
    multiples  = [6, 7, 8, 9, 10, 11, 12, 13, 14]
    ebitdas    = [int(distress_ebitda * m) for m in [0.5, 0.65, 0.8, 1.0, 1.2, 1.5]]
    sens_rows  = []
    for eb in ebitdas:
        row = {f"EBITDA ${eb/1000:.1f}B": {}}
        for mult in multiples:
            ufcf_s = eb * (1 - maint_capex_pct/100) * (1 - tax_rate_rv/100)
            ev_s   = ufcf_s * mult
            w_s    = _waterfall(ev_s)
            row[f"{mult}x"] = f"{w_s['rec_pct']:.0f}¢"
        sens_rows.append({**{"EBITDA": f"${eb/1000:.1f}B"}, **{f"{m}x": f"{_waterfall(_waterfall.__defaults__ and 0 or 0)['rec_pct']:.0f}¢" for m in multiples}})

    # Build clean sensitivity table
    sens_data = []
    for eb in ebitdas:
        row_d = {"EBITDA at distress": f"${eb/1000:.1f}B"}
        for mult in multiples:
            ufcf_s = eb * (1 - maint_capex_pct/100) * (1 - tax_rate_rv/100)
            ev_s   = ufcf_s * mult
            w_s    = _waterfall(ev_s)
            row_d[f"{mult}x"] = f"{w_s['rec_pct']:.0f}¢"
        sens_data.append(row_d)
    st.dataframe(pd.DataFrame(sens_data).set_index("EBITDA at distress"), use_container_width=True)
    st.caption(
        f"Secured DDTL ${TOTAL_SECURED/1000:.1f}B assumed par recovery. "
        f"Unsecured face ${TOTAL_UNSECURED/1000:.1f}B. "
        f"Lease cure {lease_cure_pct}% (${lease_claim/1000:.1f}B). "
        f"Admin {admin_cost_pct}%. All estimates."
    )
