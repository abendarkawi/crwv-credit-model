import pandas as pd
from data import ANNUAL_ACTUALS, QUARTERLY_ACTUALS

# ── Scenario definitions ──────────────────────────────────────────────────────
# Base = conservative; credit upside is capped, downside is not.
# All scenario keys match the assumption keys accepted by build_model().
SCENARIOS = {
    "base": dict(
        label="Base", color="#3b82f6",
        rationale=(
            "Conservative. ~85% of mgmt MW guidance; modest pricing normalisation; cost of capital "
            "stays elevated. Includes Apr '26 confirmed raises ($9.85B: DDTL 5.0 + HY + converts). "
            "Debt peaks ~$75B FY2028 before modest paydown. ICR stays above 2x but with no cushion. "
            "Credit investor anchor case."
        ),
        mw={"Q1 2026E": 950, "Q2 2026E": 1300, "Q3 2026E": 1750, "Q4 2026E": 2200,
            "FY 2027E": 2900, "FY 2028E": 3600, "FY 2029E": 4200},
        rev_per_mw=1.82, gross_margin=71.0,
        ebitda_margin_2026=53.0, ebitda_margin_2027=55.0,
        ebitda_margin_2028=57.0, ebitda_margin_2029=59.0,
        total_debt_2026=46850, total_debt_2027=63850,
        total_debt_2028=74850, total_debt_2029=71850,
        interest_rate=8.2, sbc_pct=13.5,
    ),
    "bull": dict(
        label="Bull", color="#10b981",
        rationale=(
            "Meets/beats guidance; Blackwell pricing premium; IG-rated DDTL + Apr '26 converts "
            "lower blended interest rate materially; MSFT share falls <50% as OpenAI/Meta ramp. "
            "Includes Apr '26 confirmed raises ($9.85B). Debt peaks ~$65B FY2028, begins deleveraging. "
            "ROIC approaches WACC by 2029."
        ),
        mw={"Q1 2026E": 1100, "Q2 2026E": 1700, "Q3 2026E": 2300, "Q4 2026E": 3000,
            "FY 2027E": 4000, "FY 2028E": 5500, "FY 2029E": 7000},
        rev_per_mw=1.95, gross_margin=73.0,
        ebitda_margin_2026=57.0, ebitda_margin_2027=61.0,
        ebitda_margin_2028=64.0, ebitda_margin_2029=66.0,
        total_debt_2026=43850, total_debt_2027=57850,
        total_debt_2028=64850, total_debt_2029=54850,
        interest_rate=7.2, sbc_pct=12.0,
    ),
    "bear": dict(
        label="Bear", color="#ef4444",
        rationale=(
            "Hyperscaler capex softens; MSFT reduces share >67%; GPU market normalises as supply loosens; "
            "contract repricing risk. Includes Apr '26 confirmed raises ($9.85B) but capital markets "
            "close thereafter. Debt spirals to ~$88B+ with no FCF inflection through 2029. "
            "Liquidity crunch risk. Bonds impaired."
        ),
        mw={"Q1 2026E": 800, "Q2 2026E": 1000, "Q3 2026E": 1250, "Q4 2026E": 1500,
            "FY 2027E": 1900, "FY 2028E": 2400, "FY 2029E": 2800},
        rev_per_mw=1.70, gross_margin=69.0,
        ebitda_margin_2026=48.0, ebitda_margin_2027=49.0,
        ebitda_margin_2028=50.0, ebitda_margin_2029=51.0,
        total_debt_2026=50850, total_debt_2027=71850,
        total_debt_2028=87850, total_debt_2029=93850,
        interest_rate=8.9, sbc_pct=15.0,
    ),
}

# Estimated lease liabilities by year-end (finance + operating); known for 2024/2025
_LEASE_EST = {2022: 50, 2023: 500, 2024: 2694, 2025: 8449,
              2026: 12500, 2027: 16500, 2028: 20500, 2029: 23500}

# Historical estimated book equity (end of period)
# Pre-IPO: large accumulated deficit. IPO March 2025 raised ~$1.5B.
_HIST_EQUITY = {2022: -100, 2023: -800,
                (2024,1): -1200, (2024,2): -1500, (2024,3): -1800, (2024,4): -2000,
                (2025,1): 3500,   # post-IPO
                (2025,2): 3200, (2025,3): 3600, (2025,4): 5000}


def get_defaults() -> dict:
    return {
        "mw": {"Q1 2026E": 1050, "Q2 2026E": 1500, "Q3 2026E": 2000, "Q4 2026E": 2500,
               "FY 2027E": 3200, "FY 2028E": 4200, "FY 2029E": 5000},
        "rev_per_mw":       1.85,
        "gross_margin":     72.0,
        "ebitda_margin_2026": 55.0, "ebitda_margin_2027": 57.0,
        "ebitda_margin_2028": 59.0, "ebitda_margin_2029": 61.0,
        "capex_per_mw":     8.0,
        "maint_capex_pct":  3.0,
        "total_debt_2026":  46850.0, "total_debt_2027":  61850.0,
        "total_debt_2028":  71850.0, "total_debt_2029":  67850.0,
        "interest_rate":    8.2,
        "da_pct":           47.0,
        "sbc_pct":          13.5,   # stock-based comp as % of revenue
        "tax_rate":         5.0,
        "wc_days":          15,
        "equity_book":      5000.0,
        "cost_of_equity":   18.0,
    }


def get_scenario_assumptions(key: str) -> dict:
    """Merge scenario overrides onto defaults."""
    a = dict(get_defaults())
    sc = SCENARIOS[key]
    for k, v in sc.items():
        if k not in ("label", "color", "rationale"):
            a[k] = v
    return a


def build_model(a: dict) -> dict:
    """
    Build full CoreWeave financial model from assumptions dict.
    Returns dict with DataFrames: 'all', 'quarterly', 'annual'.
    """
    rows = []
    ppe_running = 20.0   # estimated FY2021 end net PP&E ($M)

    # ── FY 2022 / 2023 annual actuals ────────────────────────────────────────
    for yr in [2022, 2023]:
        d = ANNUAL_ACTUALS[yr]
        da = d["revenue"] * a["da_pct"] / 100
        ppe_running = ppe_running + d["capex"] - da
        sbc = d["revenue"] * a.get("sbc_pct", 13.5) / 100
        eq  = _HIST_EQUITY.get(yr, None)
        rows.append(dict(
            period=f"FY {yr}", year=yr, quarter=None, is_actual=True, is_quarterly=False,
            **d, da=da, ebit=d["adj_ebitda"]-da, sbc=sbc,
            cash_ebitda=d["adj_ebitda"]-sbc,
            ppe_net=ppe_running, book_equity=eq,
            lease_liabilities=_LEASE_EST.get(yr, None),
            receivables=d["revenue"]*30/365,
            accounts_payable=d["revenue"]*20/365,
        ))

    # ── Quarterly actuals 2024–2025 + annual totals ──────────────────────────
    for yr in [2024, 2025]:
        q_rows = []
        for q in [1, 2, 3, 4]:
            d = QUARTERLY_ACTUALS[(yr, q)]
            da  = d["revenue"] * a["da_pct"] / 100
            sbc = d["revenue"] * a.get("sbc_pct", 13.5) / 100
            ppe_running = ppe_running + d["capex"] - da
            eq  = _HIST_EQUITY.get((yr, q), None)
            row = dict(
                period=f"Q{q} {yr}", year=yr, quarter=q, is_actual=True, is_quarterly=True,
                **d, da=da, ebit=d["adj_ebitda"]-da, sbc=sbc,
                cash_ebitda=d["adj_ebitda"]-sbc,
                ppe_net=ppe_running, book_equity=eq,
                lease_liabilities=_LEASE_EST.get(yr, None),
                receivables=d["revenue"]*30/90,
                accounts_payable=d["revenue"]*20/90,
            )
            rows.append(row)
            q_rows.append(row)
        ann = _sum_quarters(f"FY {yr}", yr, True, q_rows)
        ann["ppe_net"]          = q_rows[-1]["ppe_net"]
        ann["book_equity"]      = q_rows[-1]["book_equity"]
        ann["lease_liabilities"]= _LEASE_EST.get(yr)
        ann["receivables"]      = q_rows[-1]["receivables"]
        ann["accounts_payable"] = q_rows[-1]["accounts_payable"]
        rows.append(ann)

    # ── Projected quarterly 2026 ─────────────────────────────────────────────
    last    = QUARTERLY_ACTUALS[(2025, 4)]
    prev_mw   = last["mw_online"]
    prev_rev  = last["revenue"]
    prev_debt = last["total_debt"]
    cash_now  = last["cash"]
    eq_now    = _HIST_EQUITY[(2025, 4)]
    debt_2026 = a["total_debt_2026"]
    em_26     = a["ebitda_margin_2026"] / 100

    q2026 = []
    for q in [1, 2, 3, 4]:
        label   = f"Q{q} 2026E"
        mw      = a["mw"][label]
        revenue = mw * a["rev_per_mw"]
        gp      = revenue * a["gross_margin"] / 100
        ebitda  = revenue * em_26
        sbc     = revenue * a.get("sbc_pct", 13.5) / 100
        cash_eb = ebitda - sbc
        debt    = prev_debt + (debt_2026 - last["total_debt"]) * (q / 4)
        interest= debt * a["interest_rate"] / 100 / 4
        new_mw  = max(0.0, mw - prev_mw)
        capex   = new_mw * a["capex_per_mw"] + revenue * a["maint_capex_pct"] / 100
        da      = revenue * a["da_pct"] / 100
        ebit    = ebitda - da
        ppe_running = ppe_running + capex - da
        pretax  = ebit - interest
        tax     = max(0.0, pretax) * a["tax_rate"] / 100
        ni      = pretax - tax
        dwc     = -(revenue - prev_rev) * a["wc_days"] / 365 * 4
        cfo     = ebitda - interest - tax + dwc
        fcf     = cfo - capex
        d_debt  = debt - (q2026[-1]["total_debt"] if q2026 else last["total_debt"])
        equity_raised = 0.0
        other_fin     = 0.0
        net_chg_cash  = fcf + d_debt + equity_raised + other_fin
        cash_now  = cash_now + net_chg_cash
        eq_now    = eq_now + ni + sbc + equity_raised
        recv      = revenue * 30 / 90
        ap        = revenue * 20 / 90

        row = dict(
            period=label, year=2026, quarter=q, is_actual=False, is_quarterly=True,
            revenue=revenue, gross_profit=gp, adj_ebitda=ebitda,
            interest_expense=interest, capex=capex, total_debt=debt,
            cash=cash_now, mw_online=mw, da=da, ebit=ebit, net_income=ni,
            cash_tax=tax, dwc=dwc, cfo=cfo, fcf=fcf,
            sbc=sbc, cash_ebitda=cash_eb,
            change_in_debt=d_debt, equity_raised=equity_raised,
            other_financing=other_fin, net_change_cash=net_chg_cash,
            ppe_net=ppe_running, book_equity=eq_now,
            lease_liabilities=_LEASE_EST.get(2026),
            receivables=recv, accounts_payable=ap,
        )
        rows.append(row)
        q2026.append(row)
        prev_mw, prev_rev = mw, revenue

    ann26 = _sum_quarters("FY 2026E", 2026, False, q2026)
    ann26.update(total_debt=q2026[-1]["total_debt"], cash=q2026[-1]["cash"],
                 mw_online=q2026[-1]["mw_online"], ppe_net=q2026[-1]["ppe_net"],
                 book_equity=q2026[-1]["book_equity"],
                 lease_liabilities=_LEASE_EST.get(2026),
                 receivables=q2026[-1]["receivables"],
                 accounts_payable=q2026[-1]["accounts_payable"])
    rows.append(ann26)

    # ── Projected annual 2027–2029 ────────────────────────────────────────────
    debt_map = {2027: a["total_debt_2027"], 2028: a["total_debt_2028"], 2029: a["total_debt_2029"]}
    em_map   = {2027: a["ebitda_margin_2027"]/100, 2028: a["ebitda_margin_2028"]/100,
                2029: a["ebitda_margin_2029"]/100}
    prev_ann_mw   = q2026[-1]["mw_online"]
    prev_ann_debt = q2026[-1]["total_debt"]
    prev_ann_cash = q2026[-1]["cash"]
    prev_ann_eq   = q2026[-1]["book_equity"]
    prev_ann_rev  = sum(r["revenue"] for r in q2026)

    for yr in [2027, 2028, 2029]:
        mw      = a["mw"][f"FY {yr}E"]
        revenue = mw * a["rev_per_mw"] * 4
        gp      = revenue * a["gross_margin"] / 100
        ebitda  = revenue * em_map[yr]
        sbc     = revenue * a.get("sbc_pct", 13.5) / 100
        cash_eb = ebitda - sbc
        debt    = debt_map[yr]
        interest= debt * a["interest_rate"] / 100
        new_mw  = max(0.0, mw - prev_ann_mw)
        capex   = new_mw * a["capex_per_mw"] + revenue * a["maint_capex_pct"] / 100
        da      = revenue * a["da_pct"] / 100
        ebit    = ebitda - da
        ppe_running = ppe_running + capex - da
        pretax  = ebit - interest
        tax     = max(0.0, pretax) * a["tax_rate"] / 100
        ni      = pretax - tax
        dwc     = -(revenue - prev_ann_rev) * a["wc_days"] / 365
        cfo     = ebitda - interest - tax + dwc
        fcf     = cfo - capex
        d_debt  = debt - prev_ann_debt
        equity_raised = 0.0
        other_fin     = 0.0
        net_chg_cash  = fcf + d_debt + equity_raised + other_fin
        cash_end = prev_ann_cash + net_chg_cash
        eq_end   = prev_ann_eq + ni + sbc + equity_raised
        recv     = revenue * 30 / 365
        ap       = revenue * 20 / 365

        row = dict(
            period=f"FY {yr}E", year=yr, quarter=None, is_actual=False, is_quarterly=False,
            revenue=revenue, gross_profit=gp, adj_ebitda=ebitda,
            interest_expense=interest, capex=capex, total_debt=debt,
            cash=cash_end, mw_online=mw, da=da, ebit=ebit, net_income=ni,
            cash_tax=tax, dwc=dwc, cfo=cfo, fcf=fcf,
            sbc=sbc, cash_ebitda=cash_eb,
            change_in_debt=d_debt, equity_raised=equity_raised,
            other_financing=other_fin, net_change_cash=net_chg_cash,
            ppe_net=ppe_running, book_equity=eq_end,
            lease_liabilities=_LEASE_EST.get(yr),
            receivables=recv, accounts_payable=ap,
        )
        rows.append(row)
        prev_ann_mw, prev_ann_debt = mw, debt
        prev_ann_cash, prev_ann_eq = cash_end, eq_end
        prev_ann_rev = revenue

    # ── DataFrame + derived metrics ──────────────────────────────────────────
    df = pd.DataFrame(rows)
    df["gross_margin_pct"]      = df["gross_profit"]  / df["revenue"] * 100
    df["ebitda_margin_pct"]     = df["adj_ebitda"]    / df["revenue"] * 100
    df["cash_ebitda_margin_pct"]= df["cash_ebitda"]   / df["revenue"] * 100
    df["sbc_pct_of_rev"]        = df["sbc"]           / df["revenue"] * 100
    df["net_debt"]              = df["total_debt"]    - df["cash"].fillna(0)
    df["other_assets"]          = 500.0  # flat estimate ($M)

    # Period-level ratios on full df (used by scenario charts; quarterly TTM versions on qdf)
    df["net_lev"]   = df["net_debt"]   / df["adj_ebitda"]
    df["gross_lev"] = df["total_debt"] / df["adj_ebitda"]
    df["icr"]       = df["adj_ebitda"] / df["interest_expense"]

    # Balance sheet totals
    df["total_assets"] = (df["cash"].fillna(0) + df["ppe_net"].fillna(0)
                          + df["receivables"].fillna(0) + df["other_assets"])
    df["total_liabilities"] = (df["total_debt"] + df["lease_liabilities"].fillna(0)
                               + df["accounts_payable"].fillna(0) + 500)  # +500 other liab est
    df["nwc"] = df["receivables"].fillna(0) - df["accounts_payable"].fillna(0)

    # ROIC / WACC
    df["invested_capital"] = df["total_debt"] + a["equity_book"] - df["cash"].fillna(0)
    df["nopat"] = df["ebit"].fillna(df["adj_ebitda"] * 0.2) * (1 - a["tax_rate"] / 100)
    df["roic_pct"] = df["nopat"] / df["invested_capital"] * 100
    total_cap = df["total_debt"] + a["equity_book"]
    at_debt   = a["interest_rate"] / 100 * (1 - a["tax_rate"] / 100)
    df["wacc_pct"] = (df["total_debt"] / total_cap * at_debt * 100
                      + a["equity_book"] / total_cap * a["cost_of_equity"])

    # TTM metrics on quarterly series
    qdf = df[df["is_quarterly"]].copy().reset_index(drop=True)
    for col in ["adj_ebitda", "cash_ebitda", "interest_expense", "capex", "revenue"]:
        qdf[f"{col}_ttm"] = qdf[col].rolling(4, min_periods=4).sum()
    qdf["icr_ttm"]      = qdf["adj_ebitda_ttm"]  / qdf["interest_expense_ttm"]
    qdf["cash_icr_ttm"] = qdf["cash_ebitda_ttm"] / qdf["interest_expense_ttm"]
    qdf["gross_lev"]    = qdf["total_debt"]       / qdf["adj_ebitda_ttm"]
    qdf["net_lev"]      = qdf["net_debt"]         / qdf["adj_ebitda_ttm"]
    qdf["cash_net_lev"] = qdf["net_debt"]         / qdf["cash_ebitda_ttm"]
    qdf["debt_svc"]     = (qdf["adj_ebitda_ttm"] - qdf["capex_ttm"]) / qdf["interest_expense_ttm"]

    # Annual credit metrics
    adf = df[~df["is_quarterly"]].copy()
    adf["icr_ttm"]      = adf["adj_ebitda"]  / adf["interest_expense"]
    adf["cash_icr_ttm"] = adf["cash_ebitda"] / adf["interest_expense"]
    adf["gross_lev"]    = adf["total_debt"]   / adf["adj_ebitda"]
    adf["net_lev"]      = adf["net_debt"]     / adf["adj_ebitda"]
    adf["cash_net_lev"] = adf["net_debt"]     / adf["cash_ebitda"]
    adf["debt_svc"]     = (adf["adj_ebitda"] - adf["capex"]) / adf["interest_expense"]

    return {"all": df, "quarterly": qdf, "annual": adf}


def _sum_quarters(period, year, is_actual, q_rows):
    flow = ["revenue", "gross_profit", "adj_ebitda", "interest_expense", "capex",
            "da", "ebit", "net_income", "cash_tax", "dwc", "cfo", "fcf",
            "sbc", "cash_ebitda", "change_in_debt", "equity_raised",
            "other_financing", "net_change_cash"]
    r = {"period": period, "year": year, "quarter": None,
         "is_actual": is_actual, "is_quarterly": False}
    for col in flow:
        vals = [x[col] for x in q_rows if col in x and x.get(col) is not None]
        r[col] = sum(vals) if vals else None
    r["total_debt"] = q_rows[-1].get("total_debt")
    r["cash"]       = q_rows[-1].get("cash")
    r["mw_online"]  = q_rows[-1].get("mw_online")
    return r
