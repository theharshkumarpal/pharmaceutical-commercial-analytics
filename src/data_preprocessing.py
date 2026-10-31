"""
src/data_preprocessing.py
-------------------------
Orchestrates raw data extraction, cleaning/validation, dimensional entity generation,
and storage into SQLite / CSV for reproducible analytics.
Outputs:
- data/processed/cleaned_sales.csv
- data/processed/pharma_commercial.db (SQLite database with star schema)
- docs/DATA_QUALITY_REPORT.md
"""

import os
import sqlite3
import pandas as pd
from data_validation import validate_commercial_data

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
RAW_PATH = os.path.join(BASE_DIR, "data", "raw", "pharma_commercial_sales_raw.csv")
PROCESSED_CSV = os.path.join(BASE_DIR, "data", "processed", "cleaned_sales.csv")
DB_PATH = os.path.join(BASE_DIR, "data", "processed", "pharma_commercial.db")
QUALITY_REPORT_MD = os.path.join(BASE_DIR, "docs", "DATA_QUALITY_REPORT.md")

def run_preprocessing():
    print(f"Reading raw data from {RAW_PATH}...")
    df_raw = pd.read_csv(RAW_PATH)
    
    # 1. Validation & Cleansing
    clean_df, audit = validate_commercial_data(df_raw)
    
    # Ensure processed directory exists
    os.makedirs(os.path.dirname(PROCESSED_CSV), exist_ok=True)
    clean_df.to_csv(PROCESSED_CSV, index=False)
    print(f"Saved cleaned sales records ({len(clean_df):,}) to {PROCESSED_CSV}")
    
    # 2. Generate Data Quality Report Markdown
    report_content = f"""# Data Quality & Validation Report: Commercial Sales Pipeline

**Execution Date:** 2026-10-31  
**Source Dataset:** `data/raw/pharma_commercial_sales_raw.csv`  
**Processed Target:** `data/processed/cleaned_sales.csv` & `data/processed/pharma_commercial.db`  

---

## 1. Executive Summary

A validation protocol was executed over the commercial transactional records. The pipeline strictly maintains reverse logistics integrity (identifying and categorizing returns as commercial deductions rather than silently dropping negative rows), normalizes inconsistent geographic and customer entities, eliminates exact duplicate rows, and verifies gross-to-net financial calculations.

---

## 2. Validation Metrics & Record Ledger

| Validation Rule / Step | Records Affected | Pipeline Action Taken | Business Justification |
| :--- | :--- | :--- | :--- |
| **Total Ingested Records** | **{audit['total_records_ingested']:,}** | Ingested | Complete raw ingestion. |
| **Duplicate Transactions** | **{audit['duplicate_records_dropped']:,}** | Removed | Eliminated duplicate transaction IDs to prevent revenue double-counting. |
| **Invalid / Unparseable Dates** | **{audit['invalid_dates']:,}** | Filtered / Verified | Validated ISO-8601 formatting (`YYYY-MM-DD`). |
| **Zero Quantity Entries** | **{audit['zero_quantity_records']:,}** | Dropped | Zero-quantity rows convey no volume or economic transfer. |
| **Customer Returns & Reversals** | **{audit['returns_identified']:,}** | **Preserved & Tagged** | Reverse logistics preserved with negative unit counts, return amounts, and reason codes. |
| **Country Inconsistent Casing/Spacing** | **{audit['country_casing_standardized']:,}** | Standardized | Stripped whitespace and title-cased country names (`United States`, `Germany`, etc.). |
| **Missing Customer Names** | **{audit['missing_customer_name_imputed']:,}** | Imputed via ID | Imputed customer names from known customer registry via `customer_id`. |
| **Gross-to-Net Reconciliation Mismatch** | **{audit['unmatched_gross_to_net_fixed']:,}** | Reconciled | Enforced `Gross Sales = Units * WAC` and `Net Sales = Units * Net Price`. |
| **Final Clean Analytical Records** | **{audit['clean_records_retained']:,}** | **Loaded to OLAP Core** | 100% verified, referentially sound transactions. |

---

## 3. Financial Integrity Audit

- **Gross Sales Realized (USD):** ${clean_df[clean_df['net_units'] > 0]['gross_sales_usd'].sum():,.2f}
- **Customer Returns / Reversals (USD):** ${clean_df['return_value_usd'].sum():,.2f}
- **Net Recognized Revenue (USD):** ${clean_df['net_sales_usd'].sum():,.2f}
- **Gross-to-Net Realization Rate:** {clean_df['net_sales_usd'].sum() / clean_df[clean_df['net_units'] > 0]['gross_sales_usd'].sum() * 100:.2f}%
- **Total Net Units Distributed:** {clean_df['net_units'].sum():,} units across {clean_df['country_name'].nunique()} global markets.
"""
    with open(QUALITY_REPORT_MD, "w") as f:
        f.write(report_content)
    print(f"Generated Data Quality Report at {QUALITY_REPORT_MD}")

    # 3. Create Star Schema in SQLite Database
    build_sqlite_star_schema(clean_df)

def build_sqlite_star_schema(df: pd.DataFrame):
    """
    Builds a high-performance relational star schema in SQLite
    comprising 1 Fact table (fact_sales) and 7 Dimension tables:
    - dim_date
    - dim_product
    - dim_geography
    - dim_customer
    - dim_distributor
    - dim_sales_rep
    - dim_channel
    """
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Enable foreign keys
    cur.execute("PRAGMA foreign_keys = ON;")
    
    print(f"Building Star Schema in SQLite: {DB_PATH}...")
    
    # 1. dim_date
    df["date_dt"] = pd.to_datetime(df["transaction_date"])
    unique_dates = df[["transaction_date", "date_dt"]].drop_duplicates().sort_values("transaction_date")
    unique_dates["date_key"] = unique_dates["date_dt"].dt.strftime("%Y%m%d").astype(int)
    unique_dates["year"] = unique_dates["date_dt"].dt.year
    unique_dates["quarter"] = unique_dates["date_dt"].dt.quarter
    unique_dates["quarter_name"] = "Q" + unique_dates["quarter"].astype(str) + " " + unique_dates["year"].astype(str)
    unique_dates["month"] = unique_dates["date_dt"].dt.month
    unique_dates["month_name"] = unique_dates["date_dt"].dt.strftime("%B")
    unique_dates["year_month"] = unique_dates["date_dt"].dt.strftime("%Y-%m")
    unique_dates["day_of_month"] = unique_dates["date_dt"].dt.day
    unique_dates["day_of_week"] = unique_dates["date_dt"].dt.day_name()
    unique_dates["is_weekend"] = unique_dates["date_dt"].dt.weekday.isin([5, 6]).astype(int)
    
    dim_date = unique_dates[[
        "date_key", "transaction_date", "year", "quarter", "quarter_name",
        "month", "month_name", "year_month", "day_of_month", "day_of_week", "is_weekend"
    ]].rename(columns={"transaction_date": "full_date"})
    dim_date.to_sql("dim_date", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_dim_date_key ON dim_date(date_key);")
    cur.execute("CREATE INDEX idx_dim_date_year_month ON dim_date(year_month);")
    
    # 2. dim_product
    dim_product = df[[
        "product_id", "product_name", "generic_name", "therapeutic_area", "dosage_form", "unit_wac_price_usd"
    ]].drop_duplicates(subset=["product_id"]).reset_index(drop=True)
    dim_product["product_key"] = range(1, len(dim_product) + 1)
    dim_product.to_sql("dim_product", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_dim_product_key ON dim_product(product_key);")
    cur.execute("CREATE UNIQUE INDEX idx_dim_product_id ON dim_product(product_id);")
    
    # 3. dim_geography
    dim_geography = df[[
        "country_code", "country_name", "region", "currency"
    ]].drop_duplicates(subset=["country_code"]).reset_index(drop=True)
    # Add market access launch date metadata
    launch_map = {
        "US": "2023-01-01", "DE": "2023-01-01", "UK": "2023-01-01",
        "FR": "2023-07-01", "JP": "2024-01-01", "CA": "2024-06-01"
    }
    dim_geography["market_launch_date"] = dim_geography["country_code"].map(launch_map)
    dim_geography["coverage_months"] = dim_geography["country_code"].map({"US": 36, "DE": 36, "UK": 36, "FR": 30, "JP": 24, "CA": 18})
    dim_geography["geography_key"] = range(1, len(dim_geography) + 1)
    dim_geography.to_sql("dim_geography", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_dim_geography_key ON dim_geography(geography_key);")
    cur.execute("CREATE UNIQUE INDEX idx_dim_geography_code ON dim_geography(country_code);")
    
    # 4. dim_customer
    dim_customer = df[[
        "customer_id", "customer_name", "customer_type", "country_code"
    ]].drop_duplicates(subset=["customer_id"]).reset_index(drop=True)
    dim_customer["customer_key"] = range(1, len(dim_customer) + 1)
    dim_customer.to_sql("dim_customer", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_dim_customer_key ON dim_customer(customer_key);")
    cur.execute("CREATE UNIQUE INDEX idx_dim_customer_id ON dim_customer(customer_id);")
    
    # 5. dim_distributor
    dim_distributor = df[[
        "distributor_id", "distributor_name"
    ]].drop_duplicates(subset=["distributor_id"]).reset_index(drop=True)
    dim_distributor["distributor_tier"] = dim_distributor["distributor_name"].apply(
        lambda x: "Tier 1 National / Global" if any(w in x for w in ["McKesson", "AmerisourceBergen", "Cardinal"]) else "Tier 2 Regional / Specialty"
    )
    dim_distributor["distributor_key"] = range(1, len(dim_distributor) + 1)
    dim_distributor.to_sql("dim_distributor", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_dim_distributor_key ON dim_distributor(distributor_key);")
    cur.execute("CREATE UNIQUE INDEX idx_dim_distributor_id ON dim_distributor(distributor_id);")
    
    # 6. dim_sales_rep
    dim_sales_rep = df[[
        "sales_rep_id", "sales_rep_name", "sales_team", "country_code"
    ]].drop_duplicates(subset=["sales_rep_id"]).reset_index(drop=True)
    dim_sales_rep["sales_rep_key"] = range(1, len(dim_sales_rep) + 1)
    dim_sales_rep.to_sql("dim_sales_rep", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_dim_sales_rep_key ON dim_sales_rep(sales_rep_key);")
    cur.execute("CREATE UNIQUE INDEX idx_dim_sales_rep_id ON dim_sales_rep(sales_rep_id);")
    
    # 7. dim_channel
    dim_channel = df[[
        "sales_channel_id", "sales_channel_name"
    ]].drop_duplicates(subset=["sales_channel_id"]).reset_index(drop=True)
    dim_channel["channel_key"] = range(1, len(dim_channel) + 1)
    dim_channel.to_sql("dim_channel", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_dim_channel_key ON dim_channel(channel_key);")
    cur.execute("CREATE UNIQUE INDEX idx_dim_channel_id ON dim_channel(sales_channel_id);")
    
    # 8. fact_sales (Map surrogate keys)
    fact_df = df.copy()
    fact_df["date_key"] = pd.to_datetime(fact_df["transaction_date"]).dt.strftime("%Y%m%d").astype(int)
    fact_df = fact_df.merge(dim_product[["product_id", "product_key"]], on="product_id", how="left")
    fact_df = fact_df.merge(dim_geography[["country_code", "geography_key"]], on="country_code", how="left")
    fact_df = fact_df.merge(dim_customer[["customer_id", "customer_key"]], on="customer_id", how="left")
    fact_df = fact_df.merge(dim_distributor[["distributor_id", "distributor_key"]], on="distributor_id", how="left")
    fact_df = fact_df.merge(dim_sales_rep[["sales_rep_id", "sales_rep_key"]], on="sales_rep_id", how="left")
    fact_df = fact_df.merge(dim_channel[["sales_channel_id", "channel_key"]], on="sales_channel_id", how="left")
    
    fact_sales = fact_df[[
        "transaction_id", "date_key", "product_key", "geography_key",
        "customer_key", "distributor_key", "sales_rep_key", "channel_key",
        "units_ordered", "units_returned", "net_units",
        "unit_wac_price_usd", "contract_discount_pct", "unit_net_price_usd",
        "gross_sales_usd", "return_value_usd", "net_sales_usd",
        "cogs_usd", "gross_margin_usd", "return_reason"
    ]].reset_index(drop=True)
    fact_sales["sales_fact_id"] = range(1, len(fact_sales) + 1)
    
    fact_sales.to_sql("fact_sales", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_fact_sales_id ON fact_sales(sales_fact_id);")
    cur.execute("CREATE INDEX idx_fact_sales_date ON fact_sales(date_key);")
    cur.execute("CREATE INDEX idx_fact_sales_product ON fact_sales(product_key);")
    cur.execute("CREATE INDEX idx_fact_sales_geography ON fact_sales(geography_key);")
    cur.execute("CREATE INDEX idx_fact_sales_customer ON fact_sales(customer_key);")
    cur.execute("CREATE INDEX idx_fact_sales_distributor ON fact_sales(distributor_key);")
    cur.execute("CREATE INDEX idx_fact_sales_rep ON fact_sales(sales_rep_key);")
    cur.execute("CREATE INDEX idx_fact_sales_channel ON fact_sales(channel_key);")
    
    conn.commit()
    conn.close()
    print("Star Schema database built and indexed successfully.")

if __name__ == "__main__":
    run_preprocessing()
