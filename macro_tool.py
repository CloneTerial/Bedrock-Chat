"""
=============================================================================
 MACRO INTELLIGENCE TOOL (COMBINED)
 Combined: Macro Engine & Macro Analyzer Summary
=============================================================================
"""

import os
import sys
import json
import time
import warnings
import requests
import traceback
import io
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import redirect_stdout
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings("ignore")

# ── Terminal colors ────────────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    C = {"ok": Fore.GREEN, "warn": Fore.YELLOW, "err": Fore.RED,
         "info": Fore.CYAN, "head": Fore.MAGENTA, "reset": Style.RESET_ALL}
except ImportError:
    C = {k: "" for k in ["ok","warn","err","info","head","reset"]}

# ── Dependencies Check ──────────────────────────────────────────────────────
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

try:
    from fredapi import Fred
    HAS_FRED = True
except ImportError:
    HAS_FRED = False

try:
    import dbnomics
    HAS_DBNOMICS = True
except ImportError:
    HAS_DBNOMICS = False

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    import statsmodels.api as sm
    HAS_SM = True
except ImportError:
    HAS_SM = False

# =============================================================================
#  CONFIGURATION
# =============================================================================

FRED_API_KEY = os.getenv("FRED_API_KEY", "002fcefb709397ac9d2f27cfb2417a82")
START_DATE = "2000-01-01"
END_DATE   = datetime.today().strftime("%Y-%m-%d")
OUTPUT_DIR = Path("macro_data_output")
OUTPUT_DIR.mkdir(exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# =============================================================================
#  FRED INDICATOR CATALOG
# =============================================================================

FRED_INDICATORS = {
    "leading": {
        "LEI_Composite"            : "USALOLITONOSTSAM",
        "Yield_Spread_10Y_2Y"      : "T10Y2Y",
        "Yield_Spread_10Y_3M"      : "T10Y3M",
        "Housing_Permits"          : "PERMIT",
        "Housing_Starts"           : "HOUST",
        "Initial_Jobless_Claims"   : "ICSA",
        "M2_Money_Supply"          : "M2SL",
        "M2_Real"                  : "M2REAL",
        "ISM_Manufacturing_PMI"    : "MANEMP",
        "Consumer_Sentiment_UMich" : "UMCSENT",
        "Conf_Board_Cons_Conf"     : "CSCICP03USM665S",
        "SP500"                    : "SP500",
        "Fed_Funds_Futures_implied": "DFEDTARU",
        "Credit_Spread_HY_OAS"     : "BAMLH0A0HYM2",
        "Credit_Spread_IG_OAS"     : "BAMLC0A0CM",
        "TED_Spread"               : "TEDRATE",
        "LIBOR_3M"                 : "USD3MTD156N",
    },
    "coincident": {
        "GDP_Real"                 : "GDPC1",
        "GDP_Nominal"              : "GDP",
        "Industrial_Production"    : "INDPRO",
        "Capacity_Utilization"     : "TCU",
        "Retail_Sales"             : "RSAFS",
        "Personal_Income"          : "PI",
        "Personal_Consumption"     : "PCE",
        "Nonfarm_Payrolls"         : "PAYEMS",
        "Trade_Balance"            : "BOPGSTB",
        "Current_Account"          : "NETFI",
        "Business_Sales_Mfg"       : "MNFCTRSMSA",
        "Real_DPI"                 : "DSPIC96",
    },
    "lagging": {
        "Unemployment_Rate"        : "UNRATE",
        "Core_CPI_YoY"            : "CPILFESL",
        "Headline_CPI_YoY"        : "CPIAUCSL",
        "PPI_Final_Demand"        : "PPIACO",
        "PPI_Final_Demand_FD"     : "PPIFID",
        "PCE_Core_Deflator"       : "PCEPILFE",
        "Prime_Rate"              : "DPRIME",
        "Commercial_Loans"        : "BUSLOANS",
        "Consumer_Credit"         : "TOTALSL",
        "Duration_Unemployment"   : "UEMPMEAN",
        "Labor_Cost_Index"        : "PRS85006112",
    },
    "liquidity": {
        "Fed_Balance_Sheet"        : "WALCL",
        "Excess_Reserves"          : "WRESBAL",
        "Fed_Funds_Rate"           : "FEDFUNDS",
        "SOFR"                     : "SOFR",
        "Repo_GCF_Rate"            : "RPONTTLD",
        "Reverse_Repo"             : "RRPONTSYD",
        "Bank_Credit_Total"        : "TOTBKCR",
        "Shadow_Banking_Proxy"     : "DPNFSL",
        "Dollar_Index_DXY"         : "DTWEXBGS",
        "EUR_USD"                  : "DEXUSEU",
        "JPY_USD"                  : "DEXJPUS",
        "CNY_USD"                  : "DEXCHUS",
        "Gold_Price"               : "GOLDAMGBD228NLBM",
        "Oil_WTI"                  : "DCOILWTICO",
        "Oil_Brent"                : "DCOILBRENTEU",
        "Copper_Price"             : "PCOPPUSDM",
    },
    "debt_fiscal": {
        "Fed_Debt_GDP"             : "GFDEGDQ188S",
        "Federal_Deficit"          : "MTSDS133FMS",
        "Treasury_10Y"             : "GS10",
        "Treasury_2Y"              : "GS2",
        "Treasury_30Y"             : "GS30",
        "Treasury_3M"              : "GS3M",
        "TIPS_10Y"                 : "DFII10",
        "Breakeven_10Y"            : "T10YIE",
        "Breakeven_5Y"             : "T5YIE",
        "Corp_Bond_Aaa"            : "DAAA",
        "Corp_Bond_Baa"            : "DBAA",
    },
    "global_trade": {
        "Imports_Total"            : "IMPGS",
        "Exports_Total"            : "EXPGS",
        "Real_Exports"             : "BOPXGS",
        "Import_Prices"            : "IR",
        "Export_Prices"            : "IQ",
        "Shipping_Baltic_Dry"      : "DBAFI",
    },
}

DBNOMICS_INDICATORS = {
    "BIS_Credit_GDP_US"   : ("BIS", "total_credit", "Q.US.P.A.M.XDC.GDP.A"),
    "BIS_Credit_GDP_CN"   : ("BIS", "total_credit", "Q.CN.P.A.M.XDC.GDP.A"),
    "BIS_Credit_GDP_JP"   : ("BIS", "total_credit", "Q.JP.P.A.M.XDC.GDP.A"),
    "BIS_Credit_GDP_DE"   : ("BIS", "total_credit", "Q.DE.P.A.M.XDC.GDP.A"),
    "IMF_WEO_Global_GDP"  : ("IMF", "WEO", "NGDP_RPCH.001"),
    "IMF_WEO_World_Inf"   : ("IMF", "WEO", "PCPIPCH.001"),
}

# =============================================================================
#  LOGGER
# =============================================================================

def log(msg, level="info"):
    icons = {"ok": "✓", "warn": "⚠", "err": "✗", "info": "→", "head": "◈"}
    colors = {"ok": C["ok"], "warn": C["warn"], "err": C["err"],
              "info": C["info"], "head": C["head"]}
    icon = icons.get(level, "•")
    color = colors.get(level, "")
    print(f"{color}{icon} {msg}{C['reset']}")

def section(title):
    print(f"\n{C['head']}{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}{C['reset']}")

# =============================================================================
#  FETCHERS & ENGINE
# =============================================================================

class MacroDashboard:
    def __init__(self, fred_key=FRED_API_KEY):
        self.fred_key = fred_key
        self.data: dict[str, pd.DataFrame] = {}
        self.errors: dict[str, str] = {}
        self.fred = None
        self._init_fred()

    def _init_fred(self):
        if not HAS_FRED:
            log("fredapi not installed.", "warn")
            return
        if not self.fred_key:
            log("FRED API key not set.", "warn")
            return
        try:
            self.fred = Fred(api_key=self.fred_key)
            log("FRED API connected.", "ok")
        except Exception as e:
            log(f"FRED initialization failed: {e}", "err")

    def fetch_fred(self):
        section("FRED — Federal Reserve Economic Data")
        if not self.fred: return
        all_series = {}
        for category, indicators in FRED_INDICATORS.items():
            log(f"Category: {category}", "info")
            for name, series_id in indicators.items():
                try:
                    s = self.fred.get_series(series_id, observation_start=START_DATE, observation_end=END_DATE)
                    s.name = name
                    all_series[name] = s
                    log(f"  {name} ({series_id}): {len(s)} obs", "ok")
                except Exception as e:
                    self.errors[f"FRED_{name}"] = str(e)
                    log(f"  {name}: {e}", "warn")
                time.sleep(0.1)
        if all_series:
            df = pd.DataFrame(all_series)
            df.index.name = "date"
            self.data["FRED_All"] = df
            for category, indicators in FRED_INDICATORS.items():
                cols = [k for k in indicators if k in df.columns]
                if cols: self.data[f"FRED_{category}"] = df[cols]

    def fetch_dbnomics(self):
        section("DBnomics")
        if not HAS_DBNOMICS: return
        results = {}
        for name, (provider, dataset, series_code) in DBNOMICS_INDICATORS.items():
            try:
                df_raw = dbnomics.fetch_series(provider, dataset, series_code)
                if df_raw is not None and not df_raw.empty:
                    s = df_raw.set_index("period")["value"].rename(name)
                    s.index = pd.to_datetime(s.index, errors="coerce")
                    results[name] = s.dropna()
                    log(f"  {name}: {len(results[name])} obs", "ok")
            except Exception as e:
                log(f"  {name}: {e}", "warn")
        if results:
            df = pd.DataFrame(results)
            df.index.name = "date"
            self.data["DBnomics_BIS_IMF"] = df

    def fetch_yfinance(self):
        section("Yahoo Finance")
        if not HAS_YF: return
        tickers = {"VIX": "^VIX", "SP500": "^GSPC", "Gold": "GC=F", "Oil": "CL=F", "DXY": "DX-Y.NYB"}
        dfs = []
        for name, ticker_sym in tickers.items():
            try:
                t = yf.Ticker(ticker_sym)
                hist = t.history(start=START_DATE, end=END_DATE, auto_adjust=True)
                if not hist.empty:
                    if isinstance(hist.columns, pd.MultiIndex):
                        s = hist["Close"][ticker_sym].rename(name)
                    else:
                        s = hist["Close"].rename(name)
                    
                    dfs.append(s)
                    log(f"  {name}: {len(s)} obs", "ok")
                else:
                    log(f"  {name}: empty data", "warn")
            except Exception as e:
                log(f"  {name}: {e}", "warn")
        if dfs:
            df = pd.concat(dfs, axis=1)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            self.data["YFinance_Markets"] = df

    def fetch_gscpi(self):
        section("GSCPI")
        url_xls = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi-data.xlsx"
        url_csv = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.csv"
        
        try:
            r = requests.get(url_xls, timeout=30)
            if r.status_code == 200:
                df = pd.read_excel(io.BytesIO(r.content), sheet_name=0)
                df = df.rename(columns={df.columns[0]: "date"})
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").dropna(how="all")
                self.data["GSCPI"] = df
                log(f"GSCPI (Excel): {len(df)} obs", "ok")
                return
        except:
            pass

        try:
            df = pd.read_csv(url_csv, parse_dates=True, index_col=0, encoding="latin1")
            self.data["GSCPI"] = df
            log(f"GSCPI (CSV): {len(df)} obs", "ok")
        except Exception as e:
            log(f"GSCPI failed: {e}", "warn")

    def analyze(self):
        section("ANALYSIS")
        if "FRED_leading" in self.data:
            df_l = self.data["FRED_leading"]
            if "Yield_Spread_10Y_2Y" in df_l.columns:
                yc = df_l["Yield_Spread_10Y_2Y"].dropna()
                self.data["ANALYSIS_YieldCurve_Summary"] = pd.DataFrame({
                    "Metric": ["Last_Value", "Inversion_Days"],
                    "Value": [yc.iloc[-1] if not yc.empty else 0, (yc < 0).sum()]
                })
        if "YFinance_Markets" in self.data:
            df_m = self.data["YFinance_Markets"]
            if "VIX" in df_m.columns:
                vix = df_m["VIX"].dropna()
                bins = [0, 15, 20, 30, 40, 100]
                labels = ["Low", "Normal", "Elevated", "High", "Crisis"]
                regime = pd.cut(vix, bins=bins, labels=labels)
                pct = regime.value_counts(normalize=True) * 100
                self.data["ANALYSIS_VIX_Regime_Pct"] = pd.DataFrame({"Regime": pct.index, "Pct_Days": pct.values})

    def save(self):
        excel_path = OUTPUT_DIR / f"macro_dashboard_{TIMESTAMP}.xlsx"
        with pd.ExcelWriter(excel_path) as writer:
            for name, df in self.data.items():
                if isinstance(df, pd.DataFrame):
                    df.to_excel(writer, sheet_name=name[:31])
        log(f"Saved: {excel_path}", "ok")
        return excel_path

    def run_all(self, sources=None):
        funcs = {"fred": self.fetch_fred, "dbnomics": self.fetch_dbnomics, "yfinance": self.fetch_yfinance, "gscpi": self.fetch_gscpi}
        to_run = sources if sources else funcs.keys()
        for k in to_run:
            if k in funcs: funcs[k]()
        self.analyze()
        self.save()
        return self.data

# =============================================================================
#  ANALYZER SUMMARY
# =============================================================================

async def run_macro_analyzer_summary(sources=None):
    dashboard = MacroDashboard()
    f = io.StringIO()
    try:
        with redirect_stdout(f):
            data = await asyncio.to_thread(dashboard.run_all, sources=sources)
        output_log = f.getvalue()
        
        summary_parts = ["### 📊 Macro Intelligence Executive Summary\n"]
        if "ANALYSIS_YieldCurve_Summary" in data:
            yc = data["ANALYSIS_YieldCurve_Summary"]
            last_val = yc[yc['Metric'] == 'Last_Value']['Value'].values[0]
            inv_days = yc[yc['Metric'] == 'Inversion_Days']['Value'].values[0]
            summary_parts.append(f"**1. Yield Curve (10Y-2Y):** {'🔴 INVERTED' if last_val < 0 else '🟢 NORMAL'}")
            summary_parts.append(f"- Current Spread: `{last_val:.3f}%` | Inversion Days: `{int(inv_days)}`")
        
        if "ANALYSIS_VIX_Regime_Pct" in data:
            vix = data["ANALYSIS_VIX_Regime_Pct"]
            summary_parts.append("\n**2. VIX Regime History:**")
            for _, row in vix.iterrows():
                summary_parts.append(f"- {row['Regime']}: `{row['Pct_Days']:.1f}%`")

        final_summary = "\n".join(summary_parts)
        print("\n" + final_summary)
        return data
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()

# =============================================================================
#  MAIN CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true", help="Run with executive summary output")
    parser.add_argument("--sources", nargs="+", default=None)
    args = parser.parse_args()

    if args.summary:
        asyncio.run(run_macro_analyzer_summary(sources=args.sources))
    else:
        db = MacroDashboard()
        db.run_all(sources=args.sources)
