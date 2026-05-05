import asyncio
import os
import json
import sys
import io
import pandas as pd
from datetime import datetime
from contextlib import redirect_stdout
from tools.macro_engine import MacroDashboard

async def run_macro_analyzer(inp: dict):
    """
    Execute the Macro Intelligence Dashboard and provide a structured data summary.
    """
    sources = inp.get("sources", None)
    start_date = inp.get("start", "2000-01-01")
    end_date = inp.get("end", datetime.today().strftime("%Y-%m-%d"))
    
    dashboard = MacroDashboard()
    
    f = io.StringIO()
    try:
        with redirect_stdout(f):
            data = await asyncio.to_thread(dashboard.run_all, sources=sources)
            
        output_log = f.getvalue()
        
        summary_parts = ["### 📊 Macro Intelligence Executive Summary\n"]
        
        # 1. Yield Curve Check
        if "ANALYSIS_YieldCurve_Summary" in data:
            yc = data["ANALYSIS_YieldCurve_Summary"]
            last_val = yc[yc['Metric'] == 'Last_Value']['Value'].values[0]
            inv_days = yc[yc['Metric'] == 'Inversion_Days']['Value'].values[0]
            status = "🔴 INVERTED" if last_val < 0 else "🟢 NORMAL"
            summary_parts.append(f"**1. Yield Curve (10Y-2Y):** {status}")
            summary_parts.append(f"- Current Spread: `{last_val:.3f}%`")
            summary_parts.append(f"- Total Inversion Days in Dataset: `{int(inv_days)}` days\n")

        # 2. VIX Regime Check
        if "ANALYSIS_VIX_Regime_Pct" in data:
            vix_regime = data["ANALYSIS_VIX_Regime_Pct"]
            summary_parts.append("**2. Market Volatility (VIX) History:**")
            for _, row in vix_regime.iterrows():
                summary_parts.append(f"- {row['Regime']}: `{row['Pct_Days']:.1f}%` of the time")
            summary_parts.append("")

        # 3. Correlation Check
        if "ANALYSIS_GSCPI_CPI_Correlation" in data:
            corr = data["ANALYSIS_GSCPI_CPI_Correlation"]
            r_val = corr['Pearson_r'].values[0]
            summary_parts.append(f"**3. Supply Chain ↔ Inflation Correlation:**")
            summary_parts.append(f"- Pearson R: `{r_val:.3f}` ({'Strong' if abs(r_val) > 0.5 else 'Moderate'} correlation)\n")

        # 4. Output File Info
        summary_parts.append(f"**📂 Full Reports Generated:**")
        summary_parts.append(f"- Folder: `macro_data_output/`")
        summary_parts.append(f"- Excel: `macro_dashboard_*.xlsx` (Full daily data & correlation analysis)")

        final_summary = "\n".join(summary_parts)
        
        return {
            "status": "success",
            "message": "Macro Analysis Complete.",
            "summary": final_summary,
            "stdout_preview": output_log[-1000:],
            "data_keys": list(data.keys())
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": f"Failed to run Macro Engine: {str(e)}",
            "traceback": traceback.format_exc()
        }
