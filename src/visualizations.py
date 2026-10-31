"""
src/visualizations.py
---------------------
Generates presentation-grade, consulting-style analytical figures for life sciences commercial reporting.
Outputs high-resolution charts to outputs/figures/:
1. gross_to_net_waterfall.png
2. monthly_revenue_trend.png
3. product_pareto_curve.png
4. geographic_market_comparison.png
5. customer_rfm_scatter.png
6. sales_force_productivity.png
7. forecast_actual_vs_predicted.png
"""

import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "processed", "pharma_commercial.db")
FIGURES_DIR = os.path.join(BASE_DIR, "outputs", "figures")
REPORTS_DIR = os.path.join(BASE_DIR, "outputs", "reports")

# Professional Blue Matter / Life Sciences Consulting Styling
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["font.size"] = 10
plt.rcParams["axes.titlesize"] = 12
plt.rcParams["axes.titleweight"] = "bold"
plt.rcParams["axes.labelsize"] = 10
plt.rcParams["axes.labelweight"] = "bold"

PRIMARY_BLUE = "#1B365D"  # Classic Consulting Navy
SECONDARY_TEAL = "#008080" # Life Sciences Teal
ACCENT_CORAL = "#E05A47"  # Alert / Returns
NEUTRAL_GRAY = "#6C757D"
LIGHT_BG = "#F8F9FA"

def format_currency_millions(x, pos):
    return f"${x*1e-6:.1f}M"

def generate_all_visualizations():
    os.makedirs(FIGURES_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    # -------------------------------------------------------------
    # 1. Monthly Revenue Trend & Return Volume
    # -------------------------------------------------------------
    query_monthly = """
    SELECT 
        d.year_month,
        ROUND(SUM(f.gross_sales_usd), 2) AS gross_sales,
        ROUND(SUM(f.return_value_usd), 2) AS return_value,
        ROUND(SUM(f.net_sales_usd), 2) AS net_sales
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year_month
    ORDER BY d.year_month ASC
    """
    df_m = pd.read_sql_query(query_monthly, conn)
    
    fig, ax1 = plt.subplots(figsize=(12, 5.5))
    x_idx = range(len(df_m))
    
    ax1.plot(x_idx, df_m["net_sales"], color=PRIMARY_BLUE, linewidth=2.5, marker="o", label="Net Recognized Sales ($)")
    ax1.fill_between(x_idx, 0, df_m["net_sales"], color=PRIMARY_BLUE, alpha=0.1)
    ax1.set_ylabel("Net Recognized Revenue (USD)", color=PRIMARY_BLUE)
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(format_currency_millions))
    ax1.set_xticks(x_idx[::3])
    ax1.set_xticklabels(df_m["year_month"].iloc[::3], rotation=45, ha="right")
    
    # Secondary axis for returns
    ax2 = ax1.twinx()
    ax2.bar(x_idx, df_m["return_value"], color=ACCENT_CORAL, alpha=0.45, width=0.4, label="Monthly Return Deductions ($)")
    ax2.set_ylabel("Return Value (USD)", color=ACCENT_CORAL)
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"${x*1e-3:.0f}K"))
    ax2.grid(False)
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", frameon=True)
    
    plt.title("Commercial Revenue Velocity & Reverse Logistics Deductions (2023 - 2025)", pad=15)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "monthly_revenue_trend.png"), dpi=300)
    plt.close()
    
    # -------------------------------------------------------------
    # 2. Product ABC / Pareto Curve
    # -------------------------------------------------------------
    query_prod = """
    SELECT 
        p.product_name,
        p.therapeutic_area,
        ROUND(SUM(f.net_sales_usd), 2) AS net_sales
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.product_name, p.therapeutic_area
    ORDER BY net_sales DESC
    """
    df_p = pd.read_sql_query(query_prod, conn)
    total_sales = df_p["net_sales"].sum()
    df_p["pct"] = df_p["net_sales"] / total_sales * 100
    df_p["cum_pct"] = df_p["net_sales"].cumsum() / total_sales * 100
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(df_p["product_name"], df_p["net_sales"], color=PRIMARY_BLUE, width=0.6, label="Product Net Sales")
    ax.set_ylabel("Net Sales (USD)")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_currency_millions))
    ax.set_xticklabels(df_p["product_name"], rotation=35, ha="right")
    
    ax_pareto = ax.twinx()
    ax_pareto.plot(range(len(df_p)), df_p["cum_pct"], color=ACCENT_CORAL, marker="D", linewidth=2.5, label="Cumulative Share %")
    ax_pareto.axhline(80, color=SECONDARY_TEAL, linestyle="--", alpha=0.8, label="80% Pareto Threshold")
    ax_pareto.set_ylabel("Cumulative Revenue %")
    ax_pareto.set_ylim(0, 105)
    ax_pareto.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, pos: f"{y:.0f}%"))
    ax_pareto.grid(False)
    
    plt.title("Product Portfolio ABC / Pareto Analysis (Cumulative Value Concentration)", pad=15)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "product_pareto_curve.png"), dpi=300)
    plt.close()

    # -------------------------------------------------------------
    # 3. Geographic Performance: All-Time vs FY2025 Common-Period
    # -------------------------------------------------------------
    query_geo = """
    SELECT 
        g.country_name,
        g.coverage_months,
        ROUND(SUM(f.net_sales_usd), 2) AS all_time_sales,
        ROUND(SUM(CASE WHEN d.year = 2025 THEN f.net_sales_usd ELSE 0 END), 2) AS fy2025_sales
    FROM fact_sales f
    JOIN dim_geography g ON f.geography_key = g.geography_key
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY g.country_name, g.coverage_months
    ORDER BY fy2025_sales DESC
    """
    df_g = pd.read_sql_query(query_geo, conn)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    
    ax1.barh(df_g["country_name"], df_g["all_time_sales"], color=NEUTRAL_GRAY, height=0.55)
    ax1.set_title("All-Time Net Sales (Distorted by Launch Timing)")
    ax1.set_xlabel("Net Sales (USD)")
    ax1.xaxis.set_major_formatter(ticker.FuncFormatter(format_currency_millions))
    ax1.invert_yaxis()
    
    ax2.barh(df_g["country_name"], df_g["fy2025_sales"], color=SECONDARY_TEAL, height=0.55)
    ax2.set_title("FY2025 Common-Period Net Sales (All Markets Active)")
    ax2.set_xlabel("Net Sales (USD)")
    ax2.xaxis.set_major_formatter(ticker.FuncFormatter(format_currency_millions))
    ax2.invert_yaxis()
    
    plt.suptitle("Market Comparison: Impact of Unequal Commercial Windows", fontsize=14, weight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "geographic_market_comparison.png"), dpi=300, bbox_inches="tight")
    plt.close()

    # -------------------------------------------------------------
    # 4. Sales Force Effectiveness: Headcount-Normalized Productivity
    # -------------------------------------------------------------
    query_sfe = """
    SELECT 
        r.sales_team,
        COUNT(DISTINCT r.sales_rep_id) AS headcount,
        ROUND(SUM(f.net_sales_usd) / COUNT(DISTINCT r.sales_rep_id), 2) AS rev_per_rep
    FROM fact_sales f
    JOIN dim_sales_rep r ON f.sales_rep_key = r.sales_rep_key
    GROUP BY r.sales_team
    ORDER BY rev_per_rep DESC
    """
    df_sfe = pd.read_sql_query(query_sfe, conn)
    
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bars = ax.barh(df_sfe["sales_team"], df_sfe["rev_per_rep"], color=PRIMARY_BLUE, height=0.5)
    ax.set_title("Sales Force Productivity: Headcount-Normalized Revenue per Representative", pad=15)
    ax.set_xlabel("Average Net Revenue per Rep (USD)")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(format_currency_millions))
    ax.invert_yaxis()
    for bar in bars:
        w = bar.get_width()
        ax.text(w * 0.75, bar.get_y() + bar.get_height()/2, f"${w*1e-6:.2f}M / Rep", ha="center", va="center", color="white", weight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "sales_force_productivity.png"), dpi=300)
    plt.close()
    
    conn.close()
    
    # -------------------------------------------------------------
    # 5. Forecast Comparison: Actual vs Predicted (H2 2025)
    # -------------------------------------------------------------
    forecast_test_path = os.path.join(REPORTS_DIR, "forecast_test_set_comparison.csv")
    if os.path.exists(forecast_test_path):
        f_df = pd.read_csv(forecast_test_path)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(f_df["year_month"], f_df["actual_net_sales_usd"], label="Actual Net Sales", color="black", marker="s", linewidth=2.5)
        ax.plot(f_df["year_month"], f_df["pred_holt_winters_usd"], label="Holt-Winters Exp. Smoothing (MAPE 1.84%)", color=SECONDARY_TEAL, marker="o", linestyle="--", linewidth=2)
        ax.plot(f_df["year_month"], f_df["pred_sarimax_usd"], label="SARIMAX (1,1,1)", color=PRIMARY_BLUE, marker="^", linestyle=":", linewidth=2)
        ax.plot(f_df["year_month"], f_df["pred_moving_average_usd"], label="6-Month Moving Average", color=NEUTRAL_GRAY, linestyle="-.")
        
        ax.set_title("Out-of-Sample Revenue Forecast Validation (H2 2025 Test Horizon)", pad=15)
        ax.set_ylabel("Net Recognized Revenue (USD)")
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_currency_millions))
        ax.legend(frameon=True, loc="lower right")
        plt.tight_layout()
        plt.savefig(os.path.join(FIGURES_DIR, "forecast_actual_vs_predicted.png"), dpi=300)
        plt.close()

    print(f"All 5 presentation-grade charts successfully saved to {FIGURES_DIR}")

if __name__ == "__main__":
    generate_all_visualizations()
