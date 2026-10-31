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
import sys
import sqlite3
import logging
from datetime import datetime
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# Ensure sibling module imports work when run from src/
sys.path.insert(0, os.path.dirname(__file__))
from data_validation import validate_commercial_data

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
RAW_PATH = os.path.join(BASE_DIR, "data", "raw", "pharma_commercial_sales_raw.csv")
PROCESSED_CSV = os.path.join(BASE_DIR, "data", "processed", "cleaned_sales.csv")
DB_PATH = os.path.join(BASE_DIR, "data", "processed", "pharma_commercial.db")
QUALITY_REPORT_MD = os.path.join(BASE_DIR, "docs", "DATA_QUALITY_REPORT.md")

def run_preprocessing():
    pipeline_start = datetime.now()
    execution_date = pipeline_start.strftime("%Y-%m-%d %H:%M:%S")
    logger.info("Pipeline started at %s", execution_date)
    logger.info("Reading raw data from %s...", RAW_PATH)

    df_raw = pd.read_csv(RAW_PATH)
    logger.info("Ingested %d raw records", len(df_raw))

    # 1. Validation & Cleansing with Row-Level Reconciliation Ledger
    clean_df, reconciliation_ledger, audit = validate_commercial_data(df_raw)

    # Save complete row-level reconciliation ledger
    ledger_path = os.path.join(BASE_DIR, "outputs", "reports", "financial_reconciliation_ledger.csv")
    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
    reconciliation_ledger.to_csv(ledger_path, index=False)
    logger.info("Saved complete reconciliation ledger (%d records) to %s", len(reconciliation_ledger), ledger_path)

    # Ensure processed directory exists
    os.makedirs(os.path.dirname(PROCESSED_CSV), exist_ok=True)
    clean_df.to_csv(PROCESSED_CSV, index=False)
    logger.info("Saved %d cleaned sales records (with preserved originals) to %s", len(clean_df), PROCESSED_CSV)

    # 2. Generate Data Quality Report Markdown (dynamic execution date)
    execution_date_display = pipeline_start.strftime("%Y-%m-%d")

    # Compute financial summary
    positive_sales = clean_df[clean_df['net_units'] > 0]
    gross_total = positive_sales['gross_sales_usd'].sum()
    returns_total = clean_df['return_value_usd'].sum()
    net_total = clean_df['net_sales_usd'].sum()
    gtn_rate = net_total / gross_total * 100 if gross_total > 0 else 0.0
    net_units_total = clean_df['net_units'].sum()
    n_markets = clean_df['country_name'].nunique()

    report_content = f"""# Data Quality & Validation Report: Commercial Sales Pipeline

**Execution Date:** {execution_date_display}
**Pipeline Runtime:** {(datetime.now() - pipeline_start).total_seconds():.1f} seconds
**Source Dataset:** `data/raw/pharma_commercial_sales_raw.csv`
**Processed Target:** `data/processed/cleaned_sales.csv` & `data/processed/pharma_commercial.db`
**Reconciliation Ledger:** `outputs/reports/financial_reconciliation_ledger.csv`

---

## 1. Executive Summary

A validation protocol was executed over the commercial transactional records. The pipeline strictly maintains reverse logistics integrity (identifying and categorizing returns as commercial deductions rather than silently dropping negative rows), normalizes inconsistent geographic and customer entities, eliminates exact duplicate rows, and verifies gross-to-net financial calculations.

**Row-Level Status & Financial Traceability:**
- Every record is audited and classified into an explicit status: `PASS`, `CORRECTED`, `FLAGGED`, or `REJECTED`.
- Original pre-recalculation financial values are preserved (`gross_sales_usd_original`, `return_value_usd_original`, `net_sales_usd_original`, `gross_margin_usd_original`).
- A comprehensive row-level reconciliation ledger is exported to [`outputs/reports/financial_reconciliation_ledger.csv`](../outputs/reports/financial_reconciliation_ledger.csv).

---

## 2. Row-Level Reconciliation Status Summary

| Reconciliation Status | Record Count | % of Ingested | Description & Criteria |
| :--- | :--- | :--- | :--- |
| **PASS** | **{audit['status_pass_count']:,}** | **{audit['status_pass_count']/audit['total_records_ingested']*100:.2f}%** | 100% mathematically consistent; zero anomalies or discrepancies. |
| **CORRECTED** | **{audit['status_corrected_count']:,}** | **{audit['status_corrected_count']/audit['total_records_ingested']*100:.2f}%** | Valid transactions with formatting (country casing) or imputed customer names reconciled. |
| **FLAGGED** | **{audit['status_flagged_count']:,}** | **{audit['status_flagged_count']/audit['total_records_ingested']*100:.2f}%** | Retained in analytical core, but flagged for business audit (high-value return or discount outlier). |
| **REJECTED** | **{audit['status_rejected_count']:,}** | **{audit['status_rejected_count']/audit['total_records_ingested']*100:.2f}%** | Dropped due to duplicate transaction ID, unparseable date, zero quantity, or invalid pricing. |
| **Total Ingested** | **{audit['total_records_ingested']:,}** | **100.00%** | Raw ERP billing transactions ingested. |
| **Clean Retained** | **{audit['clean_records_retained']:,}** | **{audit['clean_records_retained']/audit['total_records_ingested']*100:.2f}%** | Loaded into Star Schema OLAP database (`fact_sales`). |

---

## 3. Independent Financial Metric Validation

All four commercial financial dimensions were validated independently against unit-level transaction parameters:

| Commercial Financial Metric | Expected Formulation | Anomalies Identified | Reconciliation Action |
| :--- | :--- | :--- | :--- |
| **Gross Invoiced Sales** | `Units Ordered × Unit WAC Price` (or $0.00 for returns) | {audit['independent_gross_sales_corrected']} records | Verified & reconciled against WAC price book. |
| **Customer Returns** | `Units Returned × Unit Net Price` (or $0.00 for standard sales) | {audit['independent_returns_corrected']} records | Verified & reconciled against contract net price. |
| **Net Recognized Revenue** | `Gross Sales - Returns - Contract Discounts` | {audit['independent_net_sales_corrected']} records | Verified & reconciled against transaction terms. |
| **Gross Margin** | `Net Sales - Cost of Goods Sold (COGS)` | {audit['independent_gross_margin_corrected']} records | Verified & reconciled against formulation cost basis. |

---

## 4. Financial Integrity Audit Totals

- **Gross Sales Realized (USD):** ${gross_total:,.2f}
- **Customer Returns / Reversals (USD):** ${returns_total:,.2f}
- **Net Recognized Revenue (USD):** ${net_total:,.2f}
- **Gross-to-Net Realization Rate:** {gtn_rate:.2f}%
- **Total Net Units Distributed:** {net_units_total:,} units across {n_markets} global markets.

> **Synthetic Data Disclosure:** All financial figures are derived from reproducible synthetic data generated via `src/generate_commercial_data.py` (seed 42). They do not represent actual pharmaceutical manufacturer revenue or verified market share.
"""
    os.makedirs(os.path.dirname(QUALITY_REPORT_MD), exist_ok=True)
    with open(QUALITY_REPORT_MD, "w") as f:
        f.write(report_content)
    logger.info("Generated Data Quality Report at %s", QUALITY_REPORT_MD)

    # 3. Create Star Schema in SQLite Database
    build_sqlite_star_schema(clean_df)

    elapsed = (datetime.now() - pipeline_start).total_seconds()
    logger.info("Pipeline completed in %.1f seconds", elapsed)

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

    logger.info("Building Star Schema in SQLite: %s...", DB_PATH)

    # 1. dim_date
    df = df.copy()
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
    logger.info("dim_date: %d unique dates loaded", len(dim_date))

    # 2. dim_product
    dim_product = df[[
        "product_id", "product_name", "generic_name", "therapeutic_area", "dosage_form", "unit_wac_price_usd"
    ]].drop_duplicates(subset=["product_id"]).reset_index(drop=True)
    dim_product["product_key"] = range(1, len(dim_product) + 1)
    dim_product.to_sql("dim_product", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_dim_product_key ON dim_product(product_key);")
    cur.execute("CREATE UNIQUE INDEX idx_dim_product_id ON dim_product(product_id);")
    logger.info("dim_product: %d products loaded", len(dim_product))

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
    logger.info("dim_geography: %d geographies loaded", len(dim_geography))

    # 4. dim_customer
    dim_customer = df[[
        "customer_id", "customer_name", "customer_type", "country_code"
    ]].drop_duplicates(subset=["customer_id"]).reset_index(drop=True)
    dim_customer["customer_key"] = range(1, len(dim_customer) + 1)
    dim_customer.to_sql("dim_customer", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_dim_customer_key ON dim_customer(customer_key);")
    cur.execute("CREATE UNIQUE INDEX idx_dim_customer_id ON dim_customer(customer_id);")
    logger.info("dim_customer: %d customers loaded", len(dim_customer))

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
    logger.info("dim_distributor: %d distributors loaded", len(dim_distributor))

    # 6. dim_sales_rep
    dim_sales_rep = df[[
        "sales_rep_id", "sales_rep_name", "sales_team", "country_code"
    ]].drop_duplicates(subset=["sales_rep_id"]).reset_index(drop=True)
    dim_sales_rep["sales_rep_key"] = range(1, len(dim_sales_rep) + 1)
    dim_sales_rep.to_sql("dim_sales_rep", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_dim_sales_rep_key ON dim_sales_rep(sales_rep_key);")
    cur.execute("CREATE UNIQUE INDEX idx_dim_sales_rep_id ON dim_sales_rep(sales_rep_id);")
    logger.info("dim_sales_rep: %d sales reps loaded", len(dim_sales_rep))

    # 7. dim_channel
    dim_channel = df[[
        "sales_channel_id", "sales_channel_name"
    ]].drop_duplicates(subset=["sales_channel_id"]).reset_index(drop=True)
    dim_channel["channel_key"] = range(1, len(dim_channel) + 1)
    dim_channel.to_sql("dim_channel", conn, if_exists="replace", index=False)
    cur.execute("CREATE UNIQUE INDEX idx_dim_channel_key ON dim_channel(channel_key);")
    cur.execute("CREATE UNIQUE INDEX idx_dim_channel_id ON dim_channel(sales_channel_id);")
    logger.info("dim_channel: %d channels loaded", len(dim_channel))

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
        "cogs_usd", "gross_margin_usd", "reconciliation_status", "return_reason"
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
    logger.info("Star Schema database built and indexed: %d fact rows, 7 dimensions", len(fact_sales))

if __name__ == "__main__":
    run_preprocessing()
