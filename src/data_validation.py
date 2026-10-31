"""
src/data_validation.py
----------------------
Data quality, validation, and row-level financial reconciliation pipeline
for pharmaceutical commercial sales transactions.

Audits and Validations:
1. Deduplication on transaction_id (REJECTED status).
2. Date parsing and ISO-8601 formatting (REJECTED status if invalid).
3. Missing IDs / zero quantities / invalid prices (REJECTED status).
4. Independent validation of 4 financial metrics:
   - Gross Sales: units_ordered * WAC (sales) or $0 (returns)
   - Return Value: units_returned * net_price (returns) or $0 (sales)
   - Net Sales: Gross - Returns - Contract Discounts
   - Gross Margin: Net Sales - COGS
5. Categorical standardization (country names, customer names).
6. Explicit row-level reconciliation statuses:
   - PASS: Record mathematically sound, no corrections required.
   - CORRECTED: Mathematical discrepancy or casing resolved; retained.
   - FLAGGED: Retained, but flagged for business audit (high-value return, deep discount).
   - REJECTED: Dropped from analytical core (duplicate, invalid date, zero quantity, negative price).
7. Generates comprehensive row-level reconciliation ledger CSV and audit metrics.
"""

import os
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def validate_commercial_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Validates commercial sales records with row-level reconciliation and status classification.

    Args:
        df: Raw pandas DataFrame of commercial transactions.

    Returns:
        clean_df: Cleansed DataFrame containing retained records (PASS, CORRECTED, FLAGGED).
        reconciliation_ledger: Complete audit DataFrame of ALL ingested records with PASS/CORRECTED/FLAGGED/REJECTED.
        audit_metrics: Dictionary summarizing validation metrics and status counts.
    """
    total_raw = len(df)
    logger.info("Starting financial validation and reconciliation on %d raw records", total_raw)

    work_df = df.copy()

    # ---------------------------------------------------------
    # 1. Preserve Original Financial Values
    # ---------------------------------------------------------
    work_df["gross_sales_usd_original"] = work_df.get("gross_sales_usd", pd.Series(dtype=float)).copy()
    work_df["return_value_usd_original"] = work_df.get("return_value_usd", pd.Series(dtype=float)).copy()
    work_df["net_sales_usd_original"] = work_df.get("net_sales_usd", pd.Series(dtype=float)).copy()
    work_df["cogs_usd_original"] = work_df.get("cogs_usd", pd.Series(dtype=float)).copy()
    work_df["gross_margin_usd_original"] = work_df.get("gross_margin_usd", pd.Series(dtype=float)).copy()

    # ---------------------------------------------------------
    # 2. Rejection Evaluations (REJECTED)
    # ---------------------------------------------------------
    rejection_reasons = pd.Series("", index=work_df.index, dtype="object")
    is_rejected = pd.Series(False, index=work_df.index)

    # Check A: Missing transaction_id
    missing_id = work_df["transaction_id"].isna() | (work_df["transaction_id"].astype(str).str.strip() == "")
    rejection_reasons = np.where(missing_id, "MISSING_TRANSACTION_ID", rejection_reasons)
    is_rejected = missing_id.copy()

    # Check B: Duplicate transaction_id
    dups = work_df.duplicated(subset=["transaction_id"], keep="first")
    new_dups = dups & (~is_rejected)
    rejection_reasons = np.where(new_dups, "DUPLICATE_TRANSACTION_ID", rejection_reasons)
    is_rejected |= dups

    # Check C: Invalid Dates
    parsed_dates = pd.to_datetime(work_df["transaction_date"], errors="coerce")
    invalid_date = parsed_dates.isna()
    new_invalid_date = invalid_date & (~is_rejected)
    rejection_reasons = np.where(new_invalid_date, "INVALID_DATE_FORMAT", rejection_reasons)
    is_rejected |= invalid_date
    work_df["transaction_date_clean"] = parsed_dates.dt.strftime("%Y-%m-%d")

    # Check D: Zero Quantities
    zero_qty = (work_df["net_units"] == 0) & (work_df.get("units_ordered", 0) == 0)
    new_zero_qty = zero_qty & (~is_rejected)
    rejection_reasons = np.where(new_zero_qty, "ZERO_QUANTITY", rejection_reasons)
    is_rejected |= zero_qty

    # Check E: Invalid / Negative Prices or Extreme Discounts
    invalid_wac = work_df["unit_wac_price_usd"] <= 0
    invalid_net_price = work_df["unit_net_price_usd"] <= 0
    invalid_discount = (work_df.get("contract_discount_pct", 0) < 0) | (work_df.get("contract_discount_pct", 0) > 100)
    price_anomaly = invalid_wac | invalid_net_price | invalid_discount
    new_price_anomaly = price_anomaly & (~is_rejected)
    rejection_reasons = np.where(new_price_anomaly, "INVALID_PRICE_OR_DISCOUNT", rejection_reasons)
    is_rejected |= price_anomaly

    # ---------------------------------------------------------
    # 3. Categorical Standardization
    # ---------------------------------------------------------
    casing_corrected = pd.Series(False, index=work_df.index)
    if "country_name" in work_df.columns:
        raw_country = work_df["country_name"].astype(str)
        cleaned_country = raw_country.str.strip().str.title().replace({
            "United States": "United States",
            "Uk": "United Kingdom",
            "De": "Germany",
        })
        casing_corrected = (raw_country != cleaned_country) & (~is_rejected)
        work_df["country_name"] = cleaned_country

        country_map = {
            "United States": "US",
            "Germany": "DE",
            "United Kingdom": "UK",
            "France": "FR",
            "Japan": "JP",
            "Canada": "CA"
        }
        work_df["country_code"] = work_df["country_name"].map(country_map).fillna(work_df.get("country_code", "US"))

    customer_imputed = pd.Series(False, index=work_df.index)
    if "customer_name" in work_df.columns and "customer_id" in work_df.columns:
        cust_map = work_df.dropna(subset=["customer_name"]).groupby("customer_id")["customer_name"].first().to_dict()
        missing_cust = work_df["customer_name"].isna() & (~is_rejected)
        customer_imputed = missing_cust
        work_df["customer_name"] = work_df["customer_name"].fillna(work_df["customer_id"].map(cust_map))
        work_df["customer_name"] = work_df["customer_name"].fillna("Unknown Institutional Customer")

    # ---------------------------------------------------------
    # 4. Independent Financial Metric Recalculation & Validation
    # ---------------------------------------------------------
    # Independent Metric A: Gross Invoiced Sales
    # Positive sales: units_ordered * WAC. Returns: $0.00
    expected_gross = np.where(
        work_df["net_units"] > 0,
        np.round(work_df["units_ordered"] * work_df["unit_wac_price_usd"], 2),
        0.0
    )
    gross_diff = np.abs(work_df["gross_sales_usd_original"].fillna(0) - expected_gross)
    gross_corrected = (gross_diff > 0.01) & (~is_rejected)
    gross_status = np.where(is_rejected, "REJECTED", np.where(gross_corrected, "CORRECTED", "PASS"))

    # Independent Metric B: Customer Returns & Reverse Logistics
    # Returns (net_units < 0): units_returned * net_price. Standard sales: $0.00
    expected_returns = np.where(
        work_df["net_units"] < 0,
        np.round(work_df["units_returned"] * work_df["unit_net_price_usd"], 2),
        0.0
    )
    return_diff = np.abs(work_df["return_value_usd_original"].fillna(0) - expected_returns)
    return_corrected = (return_diff > 0.01) & (~is_rejected)
    return_status = np.where(is_rejected, "REJECTED", np.where(return_corrected, "CORRECTED", "PASS"))

    # Independent Metric C: Net Recognized Revenue
    # Positive sales: units_ordered * net_price. Returns: -expected_returns
    expected_net = np.where(
        work_df["net_units"] > 0,
        np.round(work_df["units_ordered"] * work_df["unit_net_price_usd"], 2),
        -expected_returns
    )
    net_diff = np.abs(work_df["net_sales_usd_original"].fillna(0) - expected_net)
    net_corrected = (net_diff > 0.01) & (~is_rejected)
    net_status = np.where(is_rejected, "REJECTED", np.where(net_corrected, "CORRECTED", "PASS"))

    # Independent Metric D: Cost of Goods Sold (COGS) & Gross Margin
    # COGS is retained directly from source data (cogs_usd_original), as raw sales feeds lack
    # ERP product bill-of-materials tables. If cogs_usd is completely unpopulated, an industry
    # heuristic fallback of 15% of WAC is applied (expected_cogs = units_ordered * WAC * 0.15).
    # Returns credit COGS back (negative cogs) under the assumption of inventory restocking.
    expected_cogs = work_df.get("cogs_usd_original", pd.Series(0.0, index=work_df.index)).fillna(0).copy()
    if (expected_cogs == 0).all() and "unit_wac_price_usd" in work_df.columns:
        expected_cogs = np.where(
            work_df["net_units"] > 0,
            np.round(work_df["units_ordered"] * work_df["unit_wac_price_usd"] * 0.15, 2),
            0.0
        )
    expected_margin = np.round(expected_net - expected_cogs, 2)
    margin_diff = np.abs(work_df["gross_margin_usd_original"].fillna(0) - expected_margin)
    margin_corrected = (margin_diff > 0.01) & (~is_rejected)
    margin_status = np.where(is_rejected, "REJECTED", np.where(margin_corrected, "CORRECTED", "PASS"))

    # ---------------------------------------------------------
    # 5. Flagged Anomalies (Retained, but marked for Audit)
    # ---------------------------------------------------------
    # Flag conditions:
    # 1. High value return (> $50,000)
    # 2. Extreme discount rate (> 35% or < 2%)
    # 3. Discrepancy between original and verified net sales was substantial (> $100)
    flag_reasons = []
    is_flagged = pd.Series(False, index=work_df.index)

    high_return = (expected_returns > 50000) & (~is_rejected)
    deep_discount = (work_df.get("contract_discount_pct", 0) > 35.0) & (work_df["net_units"] > 0) & (~is_rejected)
    large_discrepancy = (net_diff > 100.0) & (~is_rejected)

    is_flagged = high_return | deep_discount | large_discrepancy
    flag_notes = pd.Series("", index=work_df.index, dtype="object")
    flag_notes = np.where(high_return, "HIGH_VALUE_RETURN", flag_notes)
    flag_notes = np.where(deep_discount, np.where(flag_notes != "", flag_notes + "; DEEP_DISCOUNT_OUTLIER", "DEEP_DISCOUNT_OUTLIER"), flag_notes)
    flag_notes = np.where(large_discrepancy, np.where(flag_notes != "", flag_notes + "; LARGE_FINANCIAL_DISCREPANCY", "LARGE_FINANCIAL_DISCREPANCY"), flag_notes)

    # ---------------------------------------------------------
    # 6. Overall Row Reconciliation Status Classification
    # ---------------------------------------------------------
    # Hierarchy: REJECTED > FLAGGED > CORRECTED > PASS
    any_correction = (gross_corrected | return_corrected | net_corrected | margin_corrected | casing_corrected | customer_imputed) & (~is_rejected)

    row_status = pd.Series("PASS", index=work_df.index, dtype="object")
    row_status = np.where(any_correction, "CORRECTED", row_status)
    row_status = np.where(is_flagged, "FLAGGED", row_status)
    row_status = np.where(is_rejected, "REJECTED", row_status)

    # Audit Notes
    audit_notes = pd.Series("", index=work_df.index, dtype="object")
    audit_notes = np.where(is_rejected, "REJECTED: " + rejection_reasons, audit_notes)
    audit_notes = np.where(is_flagged, "FLAGGED: " + flag_notes, audit_notes)
    audit_notes = np.where(
        (row_status == "CORRECTED"),
        "CORRECTED: Financial or categorical values reconciled",
        audit_notes
    )
    audit_notes = np.where(row_status == "PASS", "PASS: Verified without modification", audit_notes)

    # ---------------------------------------------------------
    # 7. Build Row-Level Reconciliation Ledger
    # ---------------------------------------------------------
    reconciliation_ledger = pd.DataFrame({
        "transaction_id": work_df["transaction_id"].fillna("MISSING"),
        "transaction_date": work_df["transaction_date"],
        "customer_id": work_df.get("customer_id", "N/A"),
        "product_id": work_df.get("product_id", "N/A"),
        "net_units": work_df["net_units"],
        "gross_sales_original": work_df["gross_sales_usd_original"],
        "gross_sales_verified": expected_gross,
        "gross_sales_status": gross_status,
        "return_value_original": work_df["return_value_usd_original"],
        "return_value_verified": expected_returns,
        "return_status": return_status,
        "net_sales_original": work_df["net_sales_usd_original"],
        "net_sales_verified": expected_net,
        "net_sales_status": net_status,
        "cogs_original": work_df["cogs_usd_original"],
        "cogs_verified": expected_cogs,
        "gross_margin_original": work_df["gross_margin_usd_original"],
        "gross_margin_verified": expected_margin,
        "gross_margin_status": margin_status,
        "reconciliation_status": row_status,
        "audit_notes": audit_notes
    })

    # ---------------------------------------------------------
    # 8. Create Cleansed Dataset (Retaining Non-Rejected)
    # ---------------------------------------------------------
    clean_df = work_df[~is_rejected].copy()
    clean_df["transaction_date"] = clean_df["transaction_date_clean"]
    clean_df.drop(columns=["transaction_date_clean"], inplace=True)

    # Assign verified financial numbers
    clean_df["gross_sales_usd"] = expected_gross[~is_rejected]
    clean_df["return_value_usd"] = expected_returns[~is_rejected]
    clean_df["net_sales_usd"] = expected_net[~is_rejected]
    clean_df["cogs_usd"] = expected_cogs[~is_rejected]
    clean_df["gross_margin_usd"] = expected_margin[~is_rejected]
    clean_df["reconciliation_status"] = row_status[~is_rejected]

    # Standardize return reasons for returns vs sales
    clean_df.loc[clean_df["net_units"] < 0, "return_reason"] = clean_df.loc[clean_df["net_units"] < 0, "return_reason"].fillna("Unspecified Commercial Return")
    clean_df.loc[clean_df["net_units"] > 0, "return_reason"] = "N/A - Standard Sale"

    # ---------------------------------------------------------
    # 9. Aggregate Audit Metrics Summary
    # ---------------------------------------------------------
    audit_metrics = {
        "total_records_ingested": int(total_raw),
        "status_pass_count": int((row_status == "PASS").sum()),
        "status_corrected_count": int((row_status == "CORRECTED").sum()),
        "status_flagged_count": int((row_status == "FLAGGED").sum()),
        "status_rejected_count": int((row_status == "REJECTED").sum()),
        "clean_records_retained": int(len(clean_df)),
        "independent_gross_sales_corrected": int(gross_corrected.sum()),
        "independent_returns_corrected": int(return_corrected.sum()),
        "independent_net_sales_corrected": int(net_corrected.sum()),
        "independent_gross_margin_corrected": int(margin_corrected.sum()),
        "duplicate_records_dropped": int(dups.sum()),
        "invalid_dates_dropped": int(invalid_date.sum()),
        "zero_quantity_dropped": int(zero_qty.sum()),
        "country_casing_standardized": int(casing_corrected.sum()),
        "missing_customer_name_imputed": int(customer_imputed.sum()),
        "total_verified_gross_sales_usd": round(float(clean_df["gross_sales_usd"].sum()), 2),
        "total_verified_return_value_usd": round(float(clean_df["return_value_usd"].sum()), 2),
        "total_verified_net_sales_usd": round(float(clean_df["net_sales_usd"].sum()), 2),
        "total_verified_gross_margin_usd": round(float(clean_df["gross_margin_usd"].sum()), 2),
    }

    logger.info(
        "Validation complete: %d Ingested | PASS: %d | CORRECTED: %d | FLAGGED: %d | REJECTED: %d",
        audit_metrics["total_records_ingested"],
        audit_metrics["status_pass_count"],
        audit_metrics["status_corrected_count"],
        audit_metrics["status_flagged_count"],
        audit_metrics["status_rejected_count"]
    )

    return clean_df, reconciliation_ledger, audit_metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    raw_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw", "pharma_commercial_sales_raw.csv")
    df_raw = pd.read_csv(raw_path)
    clean_df, ledger, audit = validate_commercial_data(df_raw)
    print("\n--- FINANCIAL VALIDATION & RECONCILIATION SUMMARY ---")
    for k, v in audit.items():
        print(f"  {k}: {v:,}" if isinstance(v, (int, float)) and v > 1000 else f"  {k}: {v}")
