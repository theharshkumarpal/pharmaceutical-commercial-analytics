"""
src/eda.py
----------
Exploratory Data Analysis and statistical profiling for pharmaceutical commercial sales data.
Generates comprehensive statistical summaries and outputs metrics to outputs/metrics/.
"""

import os
import json
import sqlite3
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "processed", "pharma_commercial.db")
METRICS_DIR = os.path.join(BASE_DIR, "outputs", "metrics")

def run_eda():
    os.makedirs(METRICS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    query = """
    SELECT 
        f.transaction_id,
        d.full_date,
        d.year,
        d.quarter_name,
        d.year_month,
        p.product_id,
        p.product_name,
        p.generic_name,
        p.therapeutic_area,
        p.unit_wac_price_usd,
        g.country_code,
        g.country_name,
        g.region,
        g.coverage_months,
        c.customer_id,
        c.customer_name,
        c.customer_type,
        dst.distributor_name,
        dst.distributor_tier,
        r.sales_rep_id,
        r.sales_rep_name,
        r.sales_team,
        ch.sales_channel_name,
        f.units_ordered,
        f.units_returned,
        f.net_units,
        f.contract_discount_pct,
        f.gross_sales_usd,
        f.return_value_usd,
        f.net_sales_usd,
        f.cogs_usd,
        f.gross_margin_usd,
        f.return_reason
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    JOIN dim_product p ON f.product_key = p.product_key
    JOIN dim_geography g ON f.geography_key = g.geography_key
    JOIN dim_customer c ON f.customer_key = c.customer_key
    JOIN dim_distributor dst ON f.distributor_key = dst.distributor_key
    JOIN dim_sales_rep r ON f.sales_rep_key = r.sales_rep_key
    JOIN dim_channel ch ON f.channel_key = ch.channel_key
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Financial KPI summary
    total_gross = float(df[df["net_units"] > 0]["gross_sales_usd"].sum())
    total_returns = float(df["return_value_usd"].sum())
    total_net = float(df["net_sales_usd"].sum())
    total_cogs = float(df["cogs_usd"].sum())
    total_margin = float(df["gross_margin_usd"].sum())
    total_units = int(df["net_units"].sum())
    total_txns = len(df)
    
    metrics = {
        "dataset_summary": {
            "total_transactions": total_txns,
            "total_net_units": total_units,
            "date_min": df["full_date"].min(),
            "date_max": df["full_date"].max(),
            "unique_countries": df["country_name"].nunique(),
            "unique_products": df["product_name"].nunique(),
            "unique_customers": df["customer_id"].nunique(),
            "unique_distributors": df["distributor_name"].nunique(),
            "unique_sales_reps": df["sales_rep_id"].nunique(),
        },
        "financial_kpis": {
            "gross_sales_usd": round(total_gross, 2),
            "returns_deductions_usd": round(total_returns, 2),
            "net_recognized_sales_usd": round(total_net, 2),
            "cogs_usd": round(total_cogs, 2),
            "gross_margin_usd": round(total_margin, 2),
            "gtn_realization_pct": round(total_net / total_gross * 100, 2),
            "gross_margin_pct": round(total_margin / total_net * 100, 2),
            "avg_transaction_value_usd": round(total_net / total_txns, 2),
        },
        "product_contributions": df.groupby("product_name")["net_sales_usd"].sum().sort_values(ascending=False).to_dict(),
        "geographic_contributions": df.groupby("country_name")["net_sales_usd"].sum().sort_values(ascending=False).to_dict(),
        "channel_contributions": df.groupby("sales_channel_name")["net_sales_usd"].sum().sort_values(ascending=False).to_dict(),
        "therapeutic_area_contributions": df.groupby("therapeutic_area")["net_sales_usd"].sum().sort_values(ascending=False).to_dict(),
    }
    
    out_file = os.path.join(METRICS_DIR, "commercial_summary_metrics.json")
    with open(out_file, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved EDA statistical summary metrics to {out_file}")
    return metrics

if __name__ == "__main__":
    run_eda()
