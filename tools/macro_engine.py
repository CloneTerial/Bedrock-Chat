"""
=============================================================================
 MACRO INTELLIGENCE DASHBOARD
 Global Macroeconomic Architecture — Data Fetcher & Analyzer
=============================================================================
 Data sources:
   • FRED (Federal Reserve St. Louis)
   • DBnomics (BIS, IMF, ECB, Eurostat, OECD)
   • World Bank Open Data
   • NY Fed Global Supply Chain Pressure Index (GSCPI)
   • FAO Food Price Index (FFPI)
   • GPR Index (Caldara & Iacoviello)
   • Yahoo Finance (VIX, Equity Indices)
   • CBOE (VIX Term Structure)
   • IMF Global Debt Database
=============================================================================
 INSTALLATION:
   pip install fredapi dbnomics wbdata yfinance pandas numpy requests
               openpyxl xlsxwriter tqdm colorama scipy statsmodels
=============================================================================
"""

import os
import sys
import json
import time
import warnings
import requests
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
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

# ── Progress bar ───────────────────────────────────────────────────────────
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# ── FRED API ───────────────────────────────────────────────────────────────
try:
    from fredapi import Fred
    HAS_FRED = True
except ImportError:
    HAS_FRED = False

# ── DBnomics ───────────────────────────────────────────────────────────────
try:
    import dbnomics
    HAS_DBNOMICS = True
except ImportError:
    HAS_DBNOMICS = False

# ── Yahoo Finance ──────────────────────────────────────────────────────────
try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

# ── Scipy / Statsmodels ────────────────────────────────────────────────────
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

# FRED API key from .env file (Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html)
FRED_API_KEY = os.getenv("FRED_API_KEY")

START_DATE = "2000-01-01"
END_DATE   = datetime.today().strftime("%Y-%m-%d")

OUTPUT_DIR = Path("macro_data_output")
OUTPUT_DIR.mkdir(exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# =============================================================================
#  FRED INDICATOR CATALOG
# =============================================================================

FRED_INDICATORS = {
    # ─── LEADING INDICATORS ──────────────────────────────────────────────
    "leading": {
        "LEI_Composite"            : "USALOLITONOSTSAM",  # Conference Board LEI
        "Yield_Spread_10Y_2Y"      : "T10Y2Y",            # Yield curve spread
        "Yield_Spread_10Y_3M"      : "T10Y3M",            # 10Y-3M spread
        "Housing_Permits"          : "PERMIT",             # Building permits
        "Housing_Starts"           : "HOUST",              # Housing starts
        "Initial_Jobless_Claims"   : "ICSA",               # Weekly claims
        "M2_Money_Supply"          : "M2SL",               # M2 broad money
        "M2_Real"                  : "M2REAL",             # Real M2
        "ISM_Manufacturing_PMI"    : "MANEMP",             # Mfg employment proxy
        "Consumer_Sentiment_UMich" : "UMCSENT",            # U Michigan sentiment
        "Conf_Board_Cons_Conf"     : "CSCICP03USM665S",    # Consumer confidence
        "SP500"                    : "SP500",              # S&P 500
        "Fed_Funds_Futures_implied": "DFEDTARU",           # Fed upper target
        "Credit_Spread_HY_OAS"     : "BAMLH0A0HYM2",      # HY OAS spread
        "Credit_Spread_IG_OAS"     : "BAMLC0A0CM",        # IG OAS spread
        "TED_Spread"               : "TEDRATE",            # TED spread (LIBOR-Tbill)
        "LIBOR_3M"                 : "USD3MTD156N",        # 3M USD LIBOR
    },

    # ─── COINCIDENT INDICATORS ───────────────────────────────────────────
    "coincident": {
        "GDP_Real"                 : "GDPC1",              # Real GDP
        "GDP_Nominal"              : "GDP",                # Nominal GDP
        "Industrial_Production"    : "INDPRO",             # Industrial production
        "Capacity_Utilization"     : "TCU",                # Capacity utilization
        "Retail_Sales"             : "RSAFS",              # Retail sales
        "Personal_Income"          : "PI",                 # Personal income
        "Personal_Consumption"     : "PCE",                # Personal consumption
        "Nonfarm_Payrolls"         : "PAYEMS",             # Total nonfarm payroll
        "Trade_Balance"            : "BOPGSTB",            # Trade balance
        "Current_Account"          : "NETFI",              # Current account proxy
        "Business_Sales_Mfg"       : "MNFCTRSMSA",         # Mfg & trade sales
        "Real_DPI"                 : "DSPIC96",            # Real disposable income
    },

    # ─── LAGGING INDICATORS ──────────────────────────────────────────────
    "lagging": {
        "Unemployment_Rate"        : "UNRATE",             # Unemployment rate
        "Core_CPI_YoY"            : "CPILFESL",           # Core CPI (less food/energy)
        "Headline_CPI_YoY"        : "CPIAUCSL",           # Headline CPI
        "PPI_Final_Demand"        : "PPIACO",             # PPI all commodities
        "PPI_Final_Demand_FD"     : "PPIFID",             # PPI final demand
        "PCE_Core_Deflator"       : "PCEPILFE",           # Core PCE deflator
        "Prime_Rate"              : "DPRIME",             # Bank prime rate
        "Commercial_Loans"        : "BUSLOANS",           # Commercial & industrial
        "Consumer_Credit"         : "TOTALSL",            # Total consumer credit
        "Duration_Unemployment"   : "UEMPMEAN",           # Mean weeks unemployed
        "Labor_Cost_Index"        : "PRS85006112",        # Unit labor cost
    },

    # ─── SHADOW BANKING & LIQUIDITY ──────────────────────────────────────
    "liquidity": {
        "Fed_Balance_Sheet"        : "WALCL",              # Fed total assets
        "Excess_Reserves"          : "WRESBAL",            # Reserve balances
        "Fed_Funds_Rate"           : "FEDFUNDS",           # Effective fed funds
        "SOFR"                     : "SOFR",               # SOFR rate
        "Repo_GCF_Rate"            : "RPONTTLD",           # Overnight repo
        "Reverse_Repo"             : "RRPONTSYD",          # Reverse repo
        "Bank_Credit_Total"        : "TOTBKCR",            # Total bank credit
        "Shadow_Banking_Proxy"     : "DPNFSL",             # Depository institutions
        "Dollar_Index_DXY"         : "DTWEXBGS",           # USD broad index
        "EUR_USD"                  : "DEXUSEU",            # EUR/USD
        "JPY_USD"                  : "DEXJPUS",            # JPY/USD
        "CNY_USD"                  : "DEXCHUS",            # CNY/USD
        "Gold_Price"               : "GOLDAMGBD228NLBM",   # Gold London fix
        "Oil_WTI"                  : "DCOILWTICO",         # WTI crude
        "Oil_Brent"                : "DCOILBRENTEU",       # Brent crude
        "Copper_Price"             : "PCOPPUSDM",          # Copper price
    },

    # ─── DEBT & FISCAL ───────────────────────────────────────────────────
    "debt_fiscal": {
        "Fed_Debt_GDP"             : "GFDEGDQ188S",        # Federal debt / GDP
        "Federal_Deficit"          : "MTSDS133FMS",        # Monthly budget deficit
        "Treasury_10Y"             : "GS10",               # 10Y Treasury yield
        "Treasury_2Y"              : "GS2",                # 2Y Treasury yield
        "Treasury_30Y"             : "GS30",               # 30Y Treasury yield
        "Treasury_3M"              : "GS3M",               # 3M Treasury yield
        "TIPS_10Y"                 : "DFII10",             # 10Y TIPS (real yield)
        "Breakeven_10Y"            : "T10YIE",             # 10Y inflation breakeven
        "Breakeven_5Y"             : "T5YIE",              # 5Y inflation breakeven
        "Corp_Bond_Aaa"            : "DAAA",               # AAA corporate bond
        "Corp_Bond_Baa"            : "DBAA",               # BAA corporate bond
    },

    # ─── GLOBAL / TRADE ──────────────────────────────────────────────────
    "global_trade": {
        "Imports_Total"            : "IMPGS",              # Total imports
        "Exports_Total"            : "EXPGS",              # Total exports
        "Real_Exports"             : "BOPXGS",             # Real exports
        "Import_Prices"            : "IR",                 # Import price index
        "Export_Prices"            : "IQ",                 # Export price index
        "Shipping_Baltic_Dry"      : "DBAFI",              # Baltic Dry Index
    },
}

# =============================================================================
#  DBNOMICS INDICATOR CATALOG
# =============================================================================

DBNOMICS_INDICATORS = {
    # BIS Total Credit to Private Non-Financial Sector
    "BIS_Credit_GDP_US"   : ("BIS", "total_credit", "Q.US.P.A.M.XDC.GDP.A"),
    "BIS_Credit_GDP_CN"   : ("BIS", "total_credit", "Q.CN.P.A.M.XDC.GDP.A"),
    "BIS_Credit_GDP_JP"   : ("BIS", "total_credit", "Q.JP.P.A.M.XDC.GDP.A"),
    "BIS_Credit_GDP_DE"   : ("BIS", "total_credit", "Q.DE.P.A.M.XDC.GDP.A"),
    # IMF World Economic Outlook
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
#  FETCHERS
# =============================================================================

class MacroDashboard:
    """Fetches, stores, and analyzes global macroeconomic data."""

    def __init__(self, fred_key=FRED_API_KEY):
        self.fred_key = fred_key
        self.data: dict[str, pd.DataFrame] = {}
        self.errors: dict[str, str] = {}
        self.fred = None
        self._init_fred()

    def _init_fred(self):
        if not HAS_FRED:
            log("fredapi not installed. Run `pip install fredapi`", "warn")
            return
        if not self.fred_key:
            log("FRED API key not set in .env. Skipping FRED data.", "warn")
            log("Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html", "info")
            return
        try:
            self.fred = Fred(api_key=self.fred_key)
            log("FRED API connected.", "ok")
        except Exception as e:
            log(f"FRED initialization failed: {e}", "err")

    # ─────────────────────────────────────────────────────────────────────
    # 1. FRED DATA
    # ─────────────────────────────────────────────────────────────────────
    def fetch_fred(self):
        section("FRED — Federal Reserve Economic Data")
        if not self.fred:
            log("Skipping FRED (No API key or connection).", "warn")
            return

        all_series = {}
        for category, indicators in FRED_INDICATORS.items():
            log(f"Category: {category}", "info")
            for name, series_id in indicators.items():
                try:
                    s = self.fred.get_series(series_id, observation_start=START_DATE,
                                             observation_end=END_DATE)
                    s.name = name
                    all_series[name] = s
                    log(f"  {name} ({series_id}): {len(s)} obs", "ok")
                except Exception as e:
                    self.errors[f"FRED_{name}"] = str(e)
                    log(f"  {name}: {e}", "warn")
                time.sleep(0.12)  # rate limit

        if all_series:
            df = pd.DataFrame(all_series)
            df.index.name = "date"
            self.data["FRED_All"] = df
            # Split by category
            for category, indicators in FRED_INDICATORS.items():
                cols = [k for k in indicators if k in df.columns]
                if cols:
                    self.data[f"FRED_{category}"] = df[cols]
            log(f"FRED: {len(all_series)} series successfully fetched.", "ok")

    # ─────────────────────────────────────────────────────────────────────
    # 2. DBNOMICS
    # ─────────────────────────────────────────────────────────────────────
    def fetch_dbnomics(self):
        section("DBnomics — Multi-Provider (BIS, IMF, ECB, OECD)")
        if not HAS_DBNOMICS:
            log("dbnomics not installed. Run `pip install dbnomics`", "warn")
            return

        results = {}
        for name, (provider, dataset, series_code) in DBNOMICS_INDICATORS.items():
            try:
                df_raw = dbnomics.fetch_series(provider, dataset, series_code)
                if df_raw is not None and not df_raw.empty:
                    s = df_raw.set_index("period")["value"].rename(name)
                    s.index = pd.to_datetime(s.index, errors="coerce")
                    s = s.dropna()
                    results[name] = s
                    log(f"  {name}: {len(s)} obs", "ok")
                else:
                    log(f"  {name}: empty", "warn")
            except Exception as e:
                self.errors[f"DBNOMICS_{name}"] = str(e)
                log(f"  {name}: {e}", "warn")
            time.sleep(0.3)

        # ─── BIS Global Statistics via direct API ────────────────────────
        log("Attempting BIS Statistics API...", "info")
        self._fetch_bis_api(results)

        if results:
            df = pd.DataFrame(results)
            df.index.name = "date"
            self.data["DBnomics_BIS_IMF"] = df
            log(f"DBnomics: {len(results)} series successfully fetched.", "ok")

    def _fetch_bis_api(self, results: dict):
        """BIS Direct API for key statistics."""
        BIS_SERIES = {
            "BIS_CrossBorder_Claims_USD": "https://stats.bis.org/api/v1/data/BIS,WS_LBS_D_PUB,1.0/Q.U.A.A.TO1.A.J.USD.A/?format=csv",
            "BIS_Global_Liquidity_Credit": "https://stats.bis.org/api/v1/data/BIS,WS_GLI,1.0/Q.USD.A.A.TO1.A.N.USD.A/?format=csv",
        }
        for name, url in BIS_SERIES.items():
            try:
                r = requests.get(url, timeout=30)
                if r.status_code == 200:
                    from io import StringIO
                    df_b = pd.read_csv(StringIO(r.text), skiprows=0)
                    log(f"  BIS API {name}: OK (shape={df_b.shape})", "ok")
                    self.data[f"BIS_{name}"] = df_b
                else:
                    log(f"  BIS API {name}: HTTP {r.status_code}", "warn")
            except Exception as e:
                log(f"  BIS API {name}: {e}", "warn")

    # ─────────────────────────────────────────────────────────────────────
    # 3. WORLD BANK
    # ─────────────────────────────────────────────────────────────────────
    def fetch_worldbank(self):
        section("World Bank Open Data")
        WB_INDICATORS = {
            "GDP_growth_%"          : "NY.GDP.MKTP.KD.ZG",
            "GDP_per_capita_USD"    : "NY.GDP.PCAP.CD",
            "Inflation_CPI_%"       : "FP.CPI.TOTL.ZG",
            "Govt_debt_%_GDP"       : "GC.DOD.TOTL.GD.ZS",
            "Current_account_%_GDP" : "BN.CAB.XOKA.GD.ZS",
            "FDI_net_%_GDP"         : "BX.KLT.DINV.WD.GD.ZS",
            "Exports_%_GDP"         : "NE.EXP.GNFS.ZS",
            "Imports_%_GDP"         : "NE.IMP.GNFS.ZS",
            "Gross_savings_%_GDP"   : "NY.GNS.ICTR.ZS",
        }
        COUNTRIES = ["US", "CN", "JP", "DE", "GB", "FR", "IN", "ID", "BR", "1W"]
        # "1W" = World aggregate

        all_dfs = []
        for ind_name, wb_code in WB_INDICATORS.items():
            try:
                url = (f"https://api.worldbank.org/v2/country/"
                       f"{';'.join(COUNTRIES)}/indicator/{wb_code}"
                       f"?format=json&per_page=1000&mrv=30")
                r = requests.get(url, timeout=30)
                if r.status_code == 200:
                    data_raw = r.json()
                    if len(data_raw) > 1 and data_raw[1]:
                        rows = []
                        for item in data_raw[1]:
                            rows.append({
                                "indicator" : ind_name,
                                "country"   : item["country"]["value"],
                                "iso"       : item["countryiso3code"],
                                "year"      : item["date"],
                                "value"     : item["value"],
                            })
                        df_wb = pd.DataFrame(rows)
                        all_dfs.append(df_wb)
                        log(f"  {ind_name}: {len(rows)} obs", "ok")
                    else:
                        log(f"  {ind_name}: empty data", "warn")
                else:
                    log(f"  {ind_name}: HTTP {r.status_code}", "warn")
            except Exception as e:
                self.errors[f"WB_{ind_name}"] = str(e)
                log(f"  {ind_name}: {e}", "warn")
            time.sleep(0.2)

        if all_dfs:
            df_all = pd.concat(all_dfs, ignore_index=True)
            df_all["year"] = pd.to_numeric(df_all["year"], errors="coerce")
            df_all["value"] = pd.to_numeric(df_all["value"], errors="coerce")
            self.data["WorldBank"] = df_all
            # Pivot for easy analysis: World aggregate
            df_world = df_all[df_all["iso"] == ""].copy()
            if not df_world.empty:
                df_pivot = df_world.pivot_table(index="year", columns="indicator",
                                                values="value", aggfunc="first")
                self.data["WorldBank_World_Pivot"] = df_pivot
            log(f"World Bank: {len(df_all)} total obs.", "ok")

    # ─────────────────────────────────────────────────────────────────────
    # 4. NY FED — GLOBAL SUPPLY CHAIN PRESSURE INDEX (GSCPI)
    # ─────────────────────────────────────────────────────────────────────
    def fetch_gscpi(self):
        section("NY Fed — Global Supply Chain Pressure Index (GSCPI)")
        url = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi-data.xlsx"
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                df = pd.read_excel(pd.io.common.BytesIO(r.content),
                                   sheet_name=0, skiprows=0)
                date_cols = [c for c in df.columns if "date" in str(c).lower()
                             or "month" in str(c).lower() or "period" in str(c).lower()]
                if date_cols:
                    df = df.rename(columns={date_cols[0]: "date"})
                    df["date"] = pd.to_datetime(df["date"], errors="coerce")
                    df = df.dropna(subset=["date"]).set_index("date")
                else:
                    df = df.rename(columns={df.columns[0]: "date"})
                    df["date"] = pd.to_datetime(df["date"], errors="coerce")
                    df = df.dropna(subset=["date"]).set_index("date")
                df.columns = [str(c).strip() for c in df.columns]
                self.data["GSCPI"] = df
                log(f"GSCPI: {len(df)} obs, columns: {list(df.columns)}", "ok")
            else:
                log(f"GSCPI HTTP {r.status_code}", "err")
                self._fetch_gscpi_fallback()
        except Exception as e:
            log(f"GSCPI error: {e}", "err")
            self._fetch_gscpi_fallback()

    def _fetch_gscpi_fallback(self):
        """Fallback: CSV version of GSCPI."""
        url = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.csv"
        try:
            df = pd.read_csv(url, parse_dates=True, index_col=0)
            self.data["GSCPI"] = df
            log(f"GSCPI (CSV fallback): {len(df)} obs", "ok")
        except Exception as e:
            log(f"GSCPI fallback failed: {e}", "warn")
            log("Try manual download from: https://www.newyorkfed.org/research/gscpi", "info")

    # ─────────────────────────────────────────────────────────────────────
    # 5. FAO FOOD PRICE INDEX (FFPI)
    # ─────────────────────────────────────────────────────────────────────
    def fetch_fao_ffpi(self):
        section("FAO — Food Price Index (FFPI)")
        endpoints = [
            "https://www.fao.org/fileadmin/templates/worldfood/Reports_and_docs/Food_price_indices_data_Jan25.xls",
            "https://www.fao.org/fileadmin/templates/worldfood/Reports_and_docs/Food_price_indices_data_Jul24.xls",
        ]

        for ep in endpoints:
            try:
                r = requests.get(ep, timeout=60,
                                 headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    df = pd.read_excel(pd.io.common.BytesIO(r.content),
                                       sheet_name=0, skiprows=2, header=0)
                    df = df.dropna(how="all")
                    self.data["FAO_FFPI"] = df
                    log(f"FAO FFPI: {len(df)} obs, columns: {list(df.columns[:8])}", "ok")
                    return
            except Exception as e:
                log(f"FAO endpoint {ep[-40:]}: {e}", "warn")
                continue

        try:
            csv_url = "https://ourworldindata.org/grapher/global-food-prices.csv?v=1"
            df = pd.read_csv(csv_url)
            self.data["FAO_FFPI_OWID"] = df
            log(f"FAO FFPI (OWID fallback): {len(df)} obs", "ok")
        except Exception as e:
            log(f"FAO all endpoints failed: {e}", "err")
            log("Download manually from: https://www.fao.org/worldfoodsituation/foodpricesindex/en/", "info")

    # ─────────────────────────────────────────────────────────────────────
    # 6. GEOPOLITICAL RISK INDEX (GPR — Caldara & Iacoviello)
    # ─────────────────────────────────────────────────────────────────────
    def fetch_gpr(self):
        section("GPR Index — Caldara & Iacoviello (Geopolitical Risk)")
        endpoints = [
            "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls",
            "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xlsx",
            "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.csv",
        ]

        for ep in endpoints:
            try:
                r = requests.get(ep, timeout=60,
                                 headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    if ep.endswith(".csv"):
                        df = pd.read_csv(pd.io.common.BytesIO(r.content))
                    else:
                        df = pd.read_excel(pd.io.common.BytesIO(r.content),
                                           sheet_name=0)
                    df = df.dropna(how="all")
                    date_col = [c for c in df.columns
                                if any(k in str(c).lower()
                                       for k in ["date","year","month","time"])]
                    if date_col:
                        df[date_col[0]] = pd.to_datetime(df[date_col[0]], errors="coerce")
                        df = df.rename(columns={date_col[0]: "date"})
                        df = df.dropna(subset=["date"]).set_index("date")
                    self.data["GPR_Index"] = df
                    log(f"GPR Index: {len(df)} obs, columns: {list(df.columns[:6])}", "ok")
                    return
            except Exception as e:
                log(f"GPR {ep[-40:]}: {e}", "warn")
                continue

        log("GPR: all endpoints failed. Manual download needed:", "err")
        log("  https://www.matteoiacoviello.com/gpr.htm", "info")

    # ─────────────────────────────────────────────────────────────────────
    # 7. YAHOO FINANCE — VIX, INDICES, COMMODITIES
    # ─────────────────────────────────────────────────────────────────────
    def fetch_yfinance(self):
        section("Yahoo Finance — VIX, Equity Indices, Commodities")
        if not HAS_YF:
            log("yfinance not installed. Run `pip install yfinance`", "warn")
            return

        YF_TICKERS = {
            "VIX"           : "^VIX",
            "VIX9D"         : "^VIX9D",
            "VIX3M"         : "^VIX3M",
            "MOVE_Bond_Vol" : "^MOVE",
            "SP500"         : "^GSPC",
            "NASDAQ"        : "^IXIC",
            "DJIA"          : "^DJI",
            "STOXX50"       : "^STOXX50E",
            "FTSE100"       : "^FTSE",
            "Nikkei225"     : "^N225",
            "HangSeng"      : "^HSI",
            "MSCI_EM"       : "EEM",
            "MSCI_World"    : "URTH",
            "US_10Y_Yield"  : "^TNX",
            "US_30Y_Yield"  : "^TYX",
            "US_5Y_Yield"   : "^FVX",
            "US_2Y_Yield"   : "^IRX",
            "Gold_Futures"  : "GC=F",
            "Silver"        : "SI=F",
            "WTI_Oil"       : "CL=F",
            "Brent_Oil"     : "BZ=F",
            "NatGas"        : "NG=F",
            "Copper"        : "HG=F",
            "Wheat"         : "ZW=F",
            "Corn"          : "ZC=F",
            "Soybeans"      : "ZS=F",
            "DXY_USD"       : "DX-Y.NYB",
            "EUR_USD"       : "EURUSD=X",
            "USD_JPY"       : "JPY=X",
            "USD_CNY"       : "CNY=X",
            "USD_IDR"       : "IDR=X",
            "EM_Currency"   : "CEW",
            "HY_Bond_ETF"   : "HYG",
            "IG_Bond_ETF"   : "LQD",
            "EM_Bond_ETF"   : "EMB",
        }

        dfs = []
        for name, ticker in YF_TICKERS.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(start=START_DATE, end=END_DATE, auto_adjust=True)
                if not hist.empty:
                    s = hist["Close"].rename(name)
                    dfs.append(s)
                    log(f"  {name} ({ticker}): {len(s)} obs", "ok")
                else:
                    log(f"  {name} ({ticker}): empty", "warn")
            except Exception as e:
                self.errors[f"YF_{name}"] = str(e)
                log(f"  {name}: {e}", "warn")
            time.sleep(0.05)

        if dfs:
            df = pd.concat(dfs, axis=1)
            df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
            df.index.name = "date"
            self.data["YFinance_Markets"] = df
            log(f"YFinance: {len(df.columns)} tickers successfully fetched.", "ok")

    # ─────────────────────────────────────────────────────────────────────
    # 8. IMF World Economic Outlook (WEO) — Direct API
    # ─────────────────────────────────────────────────────────────────────
    def fetch_imf_weo(self):
        section("IMF — World Economic Outlook Database")
        log("Using IMF Data Mapper API...", "info")
        IMF_INDICATORS = {
            "NGDP_RPCH"   : "Real GDP growth (%)",
            "PCPIPCH"     : "CPI Inflation (%)",
            "LUR"         : "Unemployment rate (%)",
            "BCA_NGDPD"   : "Current account (% GDP)",
            "GGXWDG_NGDP" : "Govt gross debt (% GDP)",
            "NGDPDPC"     : "GDP per capita (USD)",
        }
        COUNTRIES_IMF = {
            "US": "United States", "CN": "China", "JP": "Japan",
            "DE": "Germany", "GB": "United Kingdom", "IN": "India",
            "ID": "Indonesia", "BR": "Brazil", "001": "World",
        }

        all_rows = []
        for ind_code, ind_name in IMF_INDICATORS.items():
            for iso, cname in COUNTRIES_IMF.items():
                try:
                    url = f"https://www.imf.org/external/datamapper/api/v1/{ind_code}/{iso}"
                    r = requests.get(url, timeout=30)
                    if r.status_code == 200:
                        j = r.json()
                        vals = j.get("values", {}).get(ind_code, {}).get(iso, {})
                        for year, val in vals.items():
                            all_rows.append({
                                "indicator": ind_name,
                                "indicator_code": ind_code,
                                "country": cname,
                                "iso": iso,
                                "year": int(year),
                                "value": val,
                            })
                    time.sleep(0.1)
                except Exception as e:
                    log(f"  IMF {ind_code}/{iso}: {e}", "warn")

        if all_rows:
            df = pd.DataFrame(all_rows)
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            self.data["IMF_WEO"] = df
            log(f"IMF WEO: {len(df)} obs successfully fetched.", "ok")

    # ─────────────────────────────────────────────────────────────────────
    # 9. IIF CAPITAL FLOWS PROXY
    # ─────────────────────────────────────────────────────────────────────
    def fetch_iif_proxy(self):
        section("Capital Flows Proxy (via FRED proxies)")
        log("IIF premium data requires subscription. Using FRED proxies...", "info")
        if not self.fred:
            return
        IIF_PROXIES = {
            "US_Treasury_Foreign_Holdings" : "FDHBFIN",
            "US_Equity_Foreign_Holdings"   : "BOGZ1FL263064003Q",
        }
        results = {}
        for name, sid in IIF_PROXIES.items():
            try:
                s = self.fred.get_series(sid, observation_start=START_DATE)
                results[name] = s
                log(f"  {name}: {len(s)} obs", "ok")
            except Exception as e:
                log(f"  {name}: {e}", "warn")
        if results:
            df = pd.DataFrame(results)
            df.index.name = "date"
            self.data["Capital_Flows_Proxy"] = df

    # ─────────────────────────────────────────────────────────────────────
    # 10. SHIPPING INDICES
    # ─────────────────────────────────────────────────────────────────────
    def fetch_shipping(self):
        section("Shipping Indices (ETFs & Proxy)")
        if HAS_YF:
            shipping_tickers = {
                "BDRY_Breakwave_Dry"  : "BDRY",
                "SHIP_Index_ETF"      : "BOAT",
                "ZIM_Shipping"        : "ZIM",
                "MAERSK_Proxy"        : "AMKBY",
            }
            dfs = []
            for name, ticker in shipping_tickers.items():
                try:
                    t = yf.Ticker(ticker)
                    hist = t.history(start=START_DATE, auto_adjust=True)
                    if not hist.empty:
                        s = hist["Close"].rename(name)
                        dfs.append(s)
                        log(f"  {name} ({ticker}): {len(s)} obs", "ok")
                except Exception as e:
                    log(f"  {name}: {e}", "warn")
            if dfs:
                df = pd.concat(dfs, axis=1)
                df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
                df.index.name = "date"
                self.data["Shipping_Indices"] = df

    # ─────────────────────────────────────────────────────────────────────
    # ANALYZER
    # ─────────────────────────────────────────────────────────────────────
    def analyze(self):
        section("CORRELATION & STATISTICAL ANALYSIS")
        analysis_results = {}

        for name, df in self.data.items():
            if isinstance(df, pd.DataFrame) and df.select_dtypes("number").shape[1] > 0:
                num_df = df.select_dtypes("number")
                analysis_results[f"Stats_{name}"] = num_df.describe()

        if "FRED_leading" in self.data and "FRED_coincident" in self.data:
            df_lead = self.data["FRED_leading"].select_dtypes("number")
            df_coin = self.data["FRED_coincident"].select_dtypes("number")
            df_merged = pd.merge(df_lead, df_coin, left_index=True, right_index=True,
                                 how="inner").dropna()
            if not df_merged.empty:
                corr = df_merged.corr()
                analysis_results["Correlation_Lead_Coincident"] = corr
                log("Leading↔Coincident correlation calculated.", "ok")

        if "FRED_leading" in self.data:
            df_l = self.data["FRED_leading"]
            if "Yield_Spread_10Y_2Y" in df_l.columns:
                yc = df_l["Yield_Spread_10Y_2Y"].dropna()
                inversions = (yc < 0).sum()
                last_val = yc.iloc[-1] if len(yc) > 0 else 0
                log(f"Yield Curve (10Y-2Y): last={last_val:.3f}%, inversion days={inversions}", "ok")
                analysis_results["YieldCurve_Summary"] = pd.DataFrame({
                    "Metric": ["Last_Value", "Inversion_Days", "Mean", "Min", "Max"],
                    "Value": [last_val, inversions, yc.mean(), yc.min(), yc.max()]
                })

        if "YFinance_Markets" in self.data:
            df_mkt = self.data["YFinance_Markets"]
            if "VIX" in df_mkt.columns:
                vix = df_mkt["VIX"].dropna()
                bins = [0, 15, 20, 30, 40, 100]
                labels = ["Low(<15)", "Normal(15-20)", "Elevated(20-30)",
                          "High(30-40)", "Crisis(>40)"]
                regime = pd.cut(vix, bins=bins, labels=labels)
                regime_pct = regime.value_counts(normalize=True) * 100
                analysis_results["VIX_Regime_Pct"] = pd.DataFrame({
                    "Regime": regime_pct.index,
                    "Pct_Days": regime_pct.values
                })
                log(f"VIX last: {vix.iloc[-1]:.1f}", "ok")

        self.data.update({f"ANALYSIS_{k}": v for k, v in analysis_results.items()})
        log(f"Analysis complete: {len(analysis_results)} outputs.", "ok")

    # ─────────────────────────────────────────────────────────────────────
    # SAVE ALL DATA
    # ─────────────────────────────────────────────────────────────────────
    def save(self):
        section("SAVING DATA")
        excel_path = OUTPUT_DIR / f"macro_dashboard_{TIMESTAMP}.xlsx"
        csv_dir = OUTPUT_DIR / "csv"
        csv_dir.mkdir(exist_ok=True)

        saved = []
        skipped = []

        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            for sheet_name, df in self.data.items():
                if not isinstance(df, pd.DataFrame) or df.empty:
                    skipped.append(sheet_name)
                    continue
                safe_name = sheet_name[:31].replace("/", "_")
                try:
                    df_save = df.copy()
                    if isinstance(df_save.index, pd.DatetimeIndex):
                        df_save.index = df_save.index.strftime("%Y-%m-%d")
                    df_save.to_excel(writer, sheet_name=safe_name)
                    csv_path = csv_dir / f"{sheet_name}.csv"
                    df_save.to_csv(csv_path)
                    saved.append(sheet_name)
                    log(f"  → {safe_name} ({df.shape})", "ok")
                except Exception as e:
                    log(f"  ✗ {safe_name}: {e}", "warn")
                    skipped.append(sheet_name)

        log(f"\nExcel saved: {excel_path}", "ok")
        log(f"CSV folder: {csv_dir}", "ok")
        log(f"Saved: {len(saved)} datasets | Skipped: {len(skipped)}", "info")

        if self.errors:
            err_path = OUTPUT_DIR / f"errors_{TIMESTAMP}.json"
            with open(err_path, "w") as f:
                json.dump(self.errors, f, indent=2)
            log(f"Error log: {err_path} ({len(self.errors)} items)", "warn")

        return excel_path

    # ─────────────────────────────────────────────────────────────────────
    # MASTER RUNNER
    # ─────────────────────────────────────────────────────────────────────
    def run_all(self, sources=None):
        """Execute all fetchers."""
        ALL_SOURCES = {
            "fred"       : self.fetch_fred,
            "dbnomics"   : self.fetch_dbnomics,
            "worldbank"  : self.fetch_worldbank,
            "gscpi"      : self.fetch_gscpi,
            "fao"        : self.fetch_fao_ffpi,
            "gpr"        : self.fetch_gpr,
            "yfinance"   : self.fetch_yfinance,
            "imf_weo"    : self.fetch_imf_weo,
            "iif_proxy"  : self.fetch_iif_proxy,
            "shipping"   : self.fetch_shipping,
        }

        print(f"""
{C['head']}
╔══════════════════════════════════════════════════════════╗
║      MACRO INTELLIGENCE DASHBOARD — Data Fetcher         ║
║      Based on: Global Macroeconomic Architecture         ║
╚══════════════════════════════════════════════════════════╝{C['reset']}
  Start  : {START_DATE}
  End    : {END_DATE}
  Output : {OUTPUT_DIR.resolve()}
""")

        to_run = sources if sources else list(ALL_SOURCES.keys())

        for key in to_run:
            if key in ALL_SOURCES:
                try:
                    ALL_SOURCES[key]()
                except Exception as e:
                    log(f"FATAL ERROR in {key}: {e}", "err")
                    traceback.print_exc()
            else:
                log(f"Fetcher '{key}' unknown.", "warn")

        self.analyze()
        excel_path = self.save()

        section("FINAL SUMMARY")
        total_rows = sum(
            len(df) for df in self.data.values()
            if isinstance(df, pd.DataFrame)
        )
        log(f"Datasets successfully fetched : {len(self.data)}", "ok")
        log(f"Total data rows               : {total_rows:,}", "ok")
        log(f"Errors/Warnings               : {len(self.errors)}", "warn" if self.errors else "ok")
        log(f"Primary output file           : {excel_path}", "ok")
        print(f"\n{C['info']}Open the Excel file in {OUTPUT_DIR.name}/ for analysis.{C['reset']}\n")
        return self.data


# =============================================================================
#  QUICK ANALYSIS HELPER
# =============================================================================

def quick_analysis(data: dict, target_dataset="FRED_All", target_cols=None):
    """Run quick analysis on a specific dataset."""
    if target_dataset not in data:
        print(f"Dataset '{target_dataset}' not found.")
        print(f"Available datasets: {list(data.keys())}")
        return

    df = data[target_dataset]
    if not isinstance(df, pd.DataFrame):
        print("Not a DataFrame.")
        return

    num_df = df.select_dtypes("number")
    if target_cols:
        num_df = num_df[[c for c in target_cols if c in num_df.columns]]

    print(f"\n{'='*60}")
    print(f"  Quick Analysis: {target_dataset}")
    print(f"{'='*60}")
    print(f"Shape       : {df.shape}")
    print(f"Date range  : {df.index.min()} → {df.index.max()}")
    print(f"\n--- Descriptive Statistics ---")
    print(num_df.describe().round(3).to_string())

    if HAS_SCIPY and num_df.shape[1] >= 2:
        print(f"\n--- Correlation Matrix ---")
        print(num_df.corr().round(3).to_string())


# =============================================================================
#  MAIN
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Macro Intelligence Dashboard — Global Macro Data Fetcher"
    )
    parser.add_argument(
        "--fred-key", type=str, default=FRED_API_KEY,
        help="FRED API key (Get free at fred.stlouisfed.org)"
    )
    parser.add_argument(
        "--sources", nargs="+",
        choices=["fred","dbnomics","worldbank","gscpi","fao","gpr",
                 "yfinance","imf_weo","iif_proxy","shipping"],
        default=None,
        help="Select specific data sources (default: all)"
    )
    parser.add_argument(
        "--start", type=str, default=START_DATE,
        help=f"Start date (default: {START_DATE})"
    )
    parser.add_argument(
        "--end", type=str, default=END_DATE,
        help=f"End date (default: today)"
    )
    args = parser.parse_args()

    # Override globals
    START_DATE = args.start
    END_DATE   = args.end

    dashboard = MacroDashboard(fred_key=args.fred_key)
    data = dashboard.run_all(sources=args.sources)

    # Example quick analysis
    quick_analysis(data, target_dataset="FRED_liquidity",
                   target_cols=["Fed_Balance_Sheet", "Fed_Funds_Rate",
                                "Dollar_Index_DXY", "Gold_Price", "Oil_WTI"])
