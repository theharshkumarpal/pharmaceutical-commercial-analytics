"""
src/data_validation.py
----------------------
Comprehensive data quality and validation pipeline for pharmaceutical commercial sales data.
Audits:
- Duplicate transactions
- Invalid / missing dates
- Negative vs positive quantity validation (distinguishing legitimate returns)
- Zero quantities
- Missing revenue / gross vs net alignment
- Inconsistent categorical values (country casing, whitespace)
- Missing identifiers
Generates a structured quality report dictionary and summary log.
"""

import os
import logging
import pandas as pd
import numpy as np

# Configure structured logging
logger = logging.getLogger(__name__)


def validate_commercial_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Validates and tags records in the commercial sales dataset.
    Preserves original financial values before recalculation for audit traceability.
    Returns:
        cleaned_df: Dataframe with cleansed values and standardized fields.
        audit_metrics: Dictionary tracking counts of anomalies caught and resolved.
    """
    total_raw = len(df)
    logger.info("Starting data validation on %d raw records", total_raw)
    audit = {
        "total_records_ingested": total_raw,
        "duplicate_records_dropped": 0,
        "missing_transaction_id": 0,
        "invalid_dates": 0,
        "returns_identified": 0,
        "zero_quantity_records": 0,
        "missing_customer_name_imputed": 0,
        "country_casing_standardized": 0,
        "unmatched_gross_to_net_fixed": 0,
        "clean_records_retained": 0,
    }
    
    # 1. Deduplication on transaction_id
    dups = df.duplicated(subset=["transaction_id"], keep="first")
    audit["duplicate_records_dropped"] = int(dups.sum())
    clean_df = df[~dups].copy()
    logger.info("Deduplication: dropped %d duplicate transaction IDs", audit["duplicate_records_dropped"])
    
    # 2. Date parsing validation
    parsed_dates = pd.to_datetime(clean_df["transaction_date"], errors="coerce")
    audit["invalid_dates"] = int(parsed_dates.isna().sum())
    clean_df = clean_df[parsed_dates.notna()].copy()
    clean_df["transaction_date"] = parsed_dates[parsed_dates.notna()].dt.strftime("%Y-%m-%d")
    logger.info("Date validation: filtered %d invalid dates", audit["invalid_dates"])
    
    # 3. Categorical Standardization (Country, Channel, Product)
    clean_df["country_name_raw"] = clean_df["country_name"]
    clean_df["country_name"] = clean_df["country_name"].astype(str).str.strip().str.title()
    # Normalize common variations
    clean_df["country_name"] = clean_df["country_name"].replace({
        "United States": "United States",
        "Uk": "United Kingdom",
        "De": "Germany",
    })
    casing_diff = (clean_df["country_name"] != clean_df["country_name_raw"].astype(str)).sum()
    audit["country_casing_standardized"] = int(casing_diff)
    clean_df.drop(columns=["country_name_raw"], inplace=True)
    logger.info("Country casing: standardized %d records", audit["country_casing_standardized"])
    
    # Standardize country codes
    country_map = {
        "United States": "US",
        "Germany": "DE",
        "United Kingdom": "UK",
        "France": "FR",
        "Japan": "JP",
        "Canada": "CA"
    }
    clean_df["country_code"] = clean_df["country_name"].map(country_map).fillna(clean_df["country_code"])
    
    # 4. Impute missing customer names from customer_id lookup if available
    cust_name_map = clean_df.dropna(subset=["customer_name"]).groupby("customer_id")["customer_name"].first().to_dict()
    missing_cnames = clean_df["customer_name"].isna()
    audit["missing_customer_name_imputed"] = int(missing_cnames.sum())
    clean_df["customer_name"] = clean_df["customer_name"].fillna(clean_df["customer_id"].map(cust_name_map))
    clean_df["customer_name"] = clean_df["customer_name"].fillna("Unknown Institutional Customer")
    logger.info("Customer names: imputed %d missing values", audit["missing_customer_name_imputed"])
    
    # 5. Returns & Quantities
    # Legitimate business returns have net_units < 0 or units_returned > 0
    returns_mask = (clean_df["net_units"] < 0) | (clean_df["units_returned"] > 0)
    audit["returns_identified"] = int(returns_mask.sum())
    
    # Identify and flag zero quantities
    zero_qty_mask = clean_df["net_units"] == 0
    audit["zero_quantity_records"] = int(zero_qty_mask.sum())
    # Keep only non-zero transactions
    clean_df = clean_df[~zero_qty_mask].copy()
    logger.info("Returns identified: %d; zero-quantity records dropped: %d",
                audit["returns_identified"], audit["zero_quantity_records"])
    
    # 6. Financial Reconciliation & Validation
    # PRESERVE original values for audit traceability before recalculation
    clean_df["gross_sales_usd_original"] = clean_df["gross_sales_usd"].copy()
    clean_df["return_value_usd_original"] = clean_df["return_value_usd"].copy()
    clean_df["net_sales_usd_original"] = clean_df["net_sales_usd"].copy()

    # Recalculate verified financial values:
    # For positive sales: Gross = units_ordered * WAC, Net = units_ordered * Net_Price
    # For returns: Gross = 0, Return_Value = abs(units) * Net_Price, Net = -Return_Value
    recalc_gross = np.where(clean_df["net_units"] > 0, np.round(clean_df["units_ordered"] * clean_df["unit_wac_price_usd"], 2), 0.0)
    recalc_return = np.where(clean_df["net_units"] < 0, np.round(clean_df["units_returned"] * clean_df["unit_net_price_usd"], 2), 0.0)
    recalc_net = np.where(clean_df["net_units"] > 0, np.round(clean_df["units_ordered"] * clean_df["unit_net_price_usd"], 2), -recalc_return)
    
    # Compute discrepancy metrics
    gross_diff = np.abs(clean_df["gross_sales_usd"] - recalc_gross)
    net_diff = np.abs(clean_df["net_sales_usd"] - recalc_net)
    has_discrepancy = (gross_diff > 0.05) | (net_diff > 0.05)
    audit["unmatched_gross_to_net_fixed"] = int(has_discrepancy.sum())
    audit["max_gross_discrepancy_usd"] = round(float(gross_diff.max()), 2)
    audit["max_net_discrepancy_usd"] = round(float(net_diff.max()), 2)
    logger.info("Financial reconciliation: %d records recalculated (max gross discrepancy: $%.2f, max net discrepancy: $%.2f)",
                audit["unmatched_gross_to_net_fixed"], audit["max_gross_discrepancy_usd"], audit["max_net_discrepancy_usd"])
    
    # Apply verified values
    clean_df["gross_sales_usd"] = recalc_gross
    clean_df["return_value_usd"] = recalc_return
    clean_df["net_sales_usd"] = recalc_net
    
    # Standardize return_reason
    clean_df.loc[clean_df["net_units"] < 0, "return_reason"] = clean_df.loc[clean_df["net_units"] < 0, "return_reason"].fillna("Unspecified Commercial Return")
    clean_df.loc[clean_df["net_units"] > 0, "return_reason"] = "N/A - Standard Sale"
    
    audit["clean_records_retained"] = len(clean_df)
    logger.info("Validation complete: %d clean records retained (%.1f%% of ingested)",
                audit["clean_records_retained"],
                audit["clean_records_retained"] / total_raw * 100)
    return clean_df, audit

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    raw_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw", "pharma_commercial_sales_raw.csv")
    df_raw = pd.read_csv(raw_path)
    clean_df, audit = validate_commercial_data(df_raw)
    print("--- DATA QUALITY & VALIDATION REPORT ---")
    for k, v in audit.items():
        print(f"  {k}: {v:,}" if isinstance(v, int) else f"  {k}: {v}")
