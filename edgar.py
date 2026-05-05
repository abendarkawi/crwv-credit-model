"""
Pull and standardize public company financials from SEC EDGAR.

Usage:
    python edgar.py AAPL
    python edgar.py MSFT --facts revenue net_income
"""

import sys
import argparse
import requests
import pandas as pd

# SEC requires a descriptive User-Agent with your contact email.
HEADERS = {"User-Agent": "edgar-tool alibendarkawi@gmail.com"}

# Maps friendly names to the XBRL concept used in SEC filings.
CONCEPT_MAP = {
    "revenue":           "us-gaap/Revenues",
    "net_income":        "us-gaap/NetIncomeLoss",
    "total_assets":      "us-gaap/Assets",
    "total_liabilities": "us-gaap/Liabilities",
    "equity":            "us-gaap/StockholdersEquity",
    "cash":              "us-gaap/CashAndCashEquivalentsAtCarryingValue",
    "operating_income":  "us-gaap/OperatingIncomeLoss",
    "eps_basic":         "us-gaap/EarningsPerShareBasic",
}


def get_cik(ticker: str) -> str:
    """Look up a company's CIK number from its stock ticker."""
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    for entry in resp.json().values():
        if entry["ticker"].upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    raise ValueError(f"Ticker '{ticker}' not found in SEC database.")


def get_company_name(cik: str) -> str:
    """Return the company's official name from its EDGAR submissions."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json().get("name", "Unknown")


def fetch_concept(cik: str, concept_path: str) -> pd.DataFrame:
    """
    Fetch all reported values for one XBRL concept (e.g. us-gaap/Revenues).
    Returns a tidy DataFrame with columns: end, val, form, accn.
    """
    taxonomy, concept = concept_path.split("/", 1)
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{concept}.json"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code == 404:
        return pd.DataFrame()
    resp.raise_for_status()

    data = resp.json()
    units = data.get("units", {})
    # Most financial figures are in USD; EPS uses USD/shares.
    rows = units.get("USD") or units.get("USD/shares") or []
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)[["end", "val", "form", "accn"]]
    df["end"] = pd.to_datetime(df["end"])
    return df


def annual_only(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only annual filings (10-K) and deduplicate by fiscal year end."""
    if df.empty:
        return df
    df = df[df["form"] == "10-K"].copy()
    df = df.sort_values("end").drop_duplicates(subset="end", keep="last")
    df = df.rename(columns={"end": "fiscal_year_end", "val": "value"})
    df["fiscal_year"] = df["fiscal_year_end"].dt.year
    return df[["fiscal_year", "fiscal_year_end", "value", "accn"]].reset_index(drop=True)


def get_financials(ticker: str, facts: list[str]) -> pd.DataFrame:
    """
    Return a tidy DataFrame of annual financials for the given ticker.
    Columns: fiscal_year, fiscal_year_end, metric, value
    """
    cik = get_cik(ticker)
    name = get_company_name(cik)
    print(f"Company : {name}  (CIK {cik})")

    frames = []
    for fact in facts:
        concept = CONCEPT_MAP.get(fact)
        if concept is None:
            print(f"  [skip] '{fact}' is not in CONCEPT_MAP — add it to edgar.py")
            continue
        raw = fetch_concept(cik, concept)
        annual = annual_only(raw)
        if annual.empty:
            print(f"  [skip] no 10-K data found for '{fact}'")
            continue
        annual.insert(0, "metric", fact)
        annual.insert(0, "ticker", ticker.upper())
        frames.append(annual)
        print(f"  [ok]   {fact}: {len(annual)} annual periods")

    if not frames:
        print("No data retrieved.")
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description="Pull annual financials from SEC EDGAR.")
    parser.add_argument("ticker", help="Stock ticker, e.g. AAPL")
    parser.add_argument(
        "--facts",
        nargs="+",
        default=list(CONCEPT_MAP.keys()),
        help="Which metrics to pull (default: all). Options: " + ", ".join(CONCEPT_MAP),
    )
    parser.add_argument("--out", default=None, help="Optional CSV output path")
    args = parser.parse_args()

    df = get_financials(args.ticker, args.facts)
    if df.empty:
        sys.exit(1)

    # Pretty-print a pivot table so it's easy to read in the terminal.
    pivot = df.pivot_table(
        index="fiscal_year", columns="metric", values="value", aggfunc="first"
    )
    # Show columns in the order the user requested.
    ordered_cols = [f for f in args.facts if f in pivot.columns]
    print("\n--- Annual Financials (USD) ---")
    print(pivot[ordered_cols].to_string())

    if args.out:
        df.to_csv(args.out, index=False)
        print(f"\nSaved tidy data to {args.out}")


if __name__ == "__main__":
    main()
