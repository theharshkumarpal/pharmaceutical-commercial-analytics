"""
src/data_validation.py
----------------------
Data quality, validation, and row-level financial reconciliation pipeline
for pharmaceutical commercial sales transactions.

Audits and Validations:
1. Required Schema Validation:
   - Enforces required columns upfront (raises SchemaValidationError if missing).
   - Rejects rows with Null, NaN, Inf, or non-numeric values in required numeric fields.
2. Rejection Evaluations (REJECTED status):
   - Missing or blank transaction_id.
   - Duplicate transaction_id.
   - Malformed, invalid, or ambiguous dates.
   - Zero-quantity transactions.
   - Inconsistent quantity relationships (e.g., negative net units without returns).
   - Negative unit prices or invalid contract discount percentages (> 100% or < 0%).
3. Categorical Standardization:
   - Country names standardized to Title Case (CORRECTED status).
   - Missing customer names imputed from customer_id mapping (CORRECTED status).
4. Independent Financial Metric Validation & Waterfall:
   - Gross Sales: units_ordered * WAC (sales) or $0.00 (returns).
   - Contract Discount: units_ordered * (WAC - net_price) (sales) or $0.00 (returns).
   - Return Value: units_returned * net_price (returns) or $0.00 (sales).
   - Net Sales Waterfall: Gross - Contract Discounts - Return Credits == Net Sales.
   - COGS Retention & Configurable Fallback: COGS retained from source data; configurable
     fallback proxy (cogs_fallback_pct) applies for unpopulated rows, crediting inventory on returns.
   - Gross Margin: Net Sales - COGS.
5. Separation of Reconciliation Status and Business Anomaly Flags:
   - reconciliation_status: PASS, CORRECTED, or REJECTED.
   - anomaly_flag: NONE, DEEP_DISCOUNT_OUTLIER, HIGH_VALUE_RETURN, LARGE_FINANCIAL_DISCREPANCY.
   - Ensures transactions that are both corrected and flagged retain correction information.
6. Comprehensive Row-Level Reconciliation Ledger:
   - Retains original values (preserving missing as NaN) alongside verified values and statuses.
   - Accumulates ALL audit reasons per record without overwriting.
"""

import os
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "transaction_id",
    "transaction_date",
    "product_id",
    "customer_id",
    "net_units",
    "unit_wac_price_usd",
    "unit_net_price_usd",
]


def append_reason(series: pd.Series, mask: pd.Series, reason: str) -> pd.Series:
    """Helper to accumulate semicolon-delimited audit reasons without overwriting."""
    return pd.Series(
        np.where(mask, np.where(series != "", series + "; " + reason, reason), series),
        index=series.index,
        dtype="object"
    )


def validate_commercial_data(df: pd.DataFrame, cogs_fallback_pct: float = 0.15) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Validates commercial sales records with robust schema checks, row-level reconciliation,
    and separation of financial reconciliation status from business anomaly flags.

    Args:
        df: Raw pandas DataFrame of commercial transactions.
        cogs_fallback_pct: Configurable synthetic assumption for estimating COGS when unpopulated (default: 0.15).

    Returns:
        clean_df: Cleansed DataFrame containing retained records (PASS, CORRECTED).
        reconciliation_ledger: Complete audit DataFrame of ALL ingested records.
        audit_metrics: Dictionary summarizing validation metrics, status counts, and financial totals.
    """
    total_raw = len(df)
    logger.info("Starting robust financial validation and reconciliation on %d raw records", total_raw)

    # ---------------------------------------------------------
    # 1. Required-Column Schema Validation
    # ---------------------------------------------------------
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"SchemaValidationError: Missing required columns: {sorted(missing_cols)}")

    work_df = df.copy()

    # ---------------------------------------------------------
    # 2. Preserve Original Financial Values (Preserving Missing as NaN)
    # ---------------------------------------------------------
    work_df["gross_sales_usd_original"] = work_df.get("gross_sales_usd", pd.Series(np.nan, index=work_df.index)).copy()
    work_df["contract_discount_usd_original"] = work_df.get("contract_discount_usd", pd.Series(np.nan, index=work_df.index)).copy()
    work_df["return_value_usd_original"] = work_df.get("return_value_usd", pd.Series(np.nan, index=work_df.index)).copy()
    work_df["net_sales_usd_original"] = work_df.get("net_sales_usd", pd.Series(np.nan, index=work_df.index)).copy()
    work_df["cogs_usd_original"] = work_df.get("cogs_usd", pd.Series(np.nan, index=work_df.index)).copy()
    work_df["gross_margin_usd_original"] = work_df.get("gross_margin_usd", pd.Series(np.nan, index=work_df.index)).copy()

    # ---------------------------------------------------------
    # 3. Comprehensive Rejection Evaluations (REJECTED)
    # ---------------------------------------------------------
    rejection_reasons = pd.Series("", index=work_df.index, dtype="object")

    # Check A: Missing or Blank transaction_id
    raw_tx = work_df["transaction_id"]
    missing_id = raw_tx.isna() | (raw_tx.astype(str).str.strip() == "")
    rejection_reasons = append_reason(rejection_reasons, missing_id, "MISSING_TRANSACTION_ID")

    # Check B: Duplicate transaction_id
    dups = work_df.duplicated(subset=["transaction_id"], keep="first")
    rejection_reasons = append_reason(rejection_reasons, dups, "DUPLICATE_TRANSACTION_ID")

    # Check C: Invalid or Ambiguous Dates
    parsed_dates = pd.to_datetime(work_df["transaction_date"], errors="coerce")
    invalid_date = parsed_dates.isna()
    rejection_reasons = append_reason(rejection_reasons, invalid_date, "INVALID_DATE_FORMAT")
    work_df["transaction_date_clean"] = parsed_dates.dt.strftime("%Y-%m-%d")

    # Check D: Numeric Validity (Null, NaN, Inf, Non-numeric)
    numeric_anomaly = pd.Series(False, index=work_df.index)
    for col in ["net_units", "unit_wac_price_usd", "unit_net_price_usd"]:
        coerced = pd.to_numeric(work_df[col], errors="coerce")
        bad_num = coerced.isna() | np.isinf(coerced)
        numeric_anomaly |= bad_num
        rejection_reasons = append_reason(rejection_reasons, bad_num, f"INVALID_NUMERIC_{col.upper()}")
        work_df[col] = coerced

    # Optional order/return quantity fields
    if "units_ordered" in work_df.columns:
        coerced_ord = pd.to_numeric(work_df["units_ordered"], errors="coerce")
        bad_ord = coerced_ord.isna() | np.isinf(coerced_ord)
        numeric_anomaly |= bad_ord
        rejection_reasons = append_reason(rejection_reasons, bad_ord, "INVALID_NUMERIC_UNITS_ORDERED")
        work_df["units_ordered"] = coerced_ord
    else:
        work_df["units_ordered"] = np.where(work_df["net_units"] > 0, work_df["net_units"], 0)

    if "units_returned" in work_df.columns:
        coerced_ret = pd.to_numeric(work_df["units_returned"], errors="coerce")
        bad_ret = coerced_ret.isna() | np.isinf(coerced_ret)
        numeric_anomaly |= bad_ret
        rejection_reasons = append_reason(rejection_reasons, bad_ret, "INVALID_NUMERIC_UNITS_RETURNED")
        work_df["units_returned"] = coerced_ret
    else:
        work_df["units_returned"] = np.where(work_df["net_units"] < 0, np.abs(work_df["net_units"]), 0)

    # Check E: Zero Quantities
    zero_qty = (work_df["net_units"] == 0) & (work_df["units_ordered"] == 0) & (work_df["units_returned"] == 0)
    rejection_reasons = append_reason(rejection_reasons, zero_qty, "ZERO_QUANTITY")

    # Check F: Inconsistent Quantity Relationships
    sales_mismatch = (work_df["net_units"] > 0) & (
        (work_df["units_ordered"] != work_df["net_units"]) | (work_df["units_returned"] != 0) | (work_df["units_ordered"] <= 0)
    )
    return_mismatch = (work_df["net_units"] < 0) & (
        (work_df["units_returned"] != np.abs(work_df["net_units"])) | (work_df["units_ordered"] != 0) | (work_df["units_returned"] <= 0)
    )
    negative_qty = (work_df["units_ordered"] < 0) | (work_df["units_returned"] < 0)
    inconsistent_qty = sales_mismatch | return_mismatch | negative_qty
    rejection_reasons = append_reason(rejection_reasons, inconsistent_qty, "INCONSISTENT_QUANTITY_FIELDS")

    # Check G: Invalid / Negative Prices or Extreme Discounts
    invalid_wac = work_df["unit_wac_price_usd"] <= 0
    invalid_net_price = work_df["unit_net_price_usd"] <= 0
    disc_val = pd.to_numeric(work_df.get("contract_discount_pct", pd.Series(0.0, index=work_df.index)), errors="coerce")
    invalid_discount = disc_val.isna() | (disc_val < 0) | (disc_val > 100)
    price_anomaly = invalid_wac | invalid_net_price | invalid_discount
    rejection_reasons = append_reason(rejection_reasons, price_anomaly, "INVALID_PRICE_OR_DISCOUNT")

    # Consolidated Rejection Mask
    is_rejected = (
        missing_id | dups | invalid_date | numeric_anomaly |
        zero_qty | inconsistent_qty | price_anomaly
    )

    # ---------------------------------------------------------
    # 4. Categorical Standardization
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
    # 5. Independent Financial Metric Recalculation & Validation
    # ---------------------------------------------------------
    # Metric A: Gross Invoiced Sales
    # Positive sales: units_ordered * WAC. Returns: $0.00
    expected_gross = np.where(
        work_df["net_units"] > 0,
        np.round(work_df["units_ordered"] * work_df["unit_wac_price_usd"], 2),
        0.0
    )
    gross_orig = work_df["gross_sales_usd_original"]
    gross_diff = np.where(gross_orig.isna(), 0.0, np.abs(gross_orig - expected_gross))
    gross_corrected = (gross_orig.isna() | (gross_diff > 0.01)) & (~is_rejected)
    gross_status = np.where(is_rejected, "REJECTED", np.where(gross_corrected, "CORRECTED", "PASS"))

    # Metric B: Contract Discounts
    # Positive sales: units_ordered * (WAC - net_price). Returns: $0.00
    expected_discount = np.where(
        work_df["net_units"] > 0,
        np.round(work_df["units_ordered"] * (work_df["unit_wac_price_usd"] - work_df["unit_net_price_usd"]), 2),
        0.0
    )
    discount_orig = work_df["contract_discount_usd_original"]
    discount_diff = np.where(discount_orig.isna(), 0.0, np.abs(discount_orig - expected_discount))
    discount_corrected = (discount_orig.notna() & (discount_diff > 0.01)) & (~is_rejected)
    discount_status = np.where(is_rejected, "REJECTED", np.where(discount_corrected, "CORRECTED", "PASS"))

    # Metric C: Customer Returns & Reverse Logistics
    # Returns (net_units < 0): units_returned * net_price. Standard sales: $0.00
    expected_returns = np.where(
        work_df["net_units"] < 0,
        np.round(work_df["units_returned"] * work_df["unit_net_price_usd"], 2),
        0.0
    )
    return_orig = work_df["return_value_usd_original"]
    return_diff = np.where(return_orig.isna(), 0.0, np.abs(return_orig - expected_returns))
    return_corrected = (return_orig.isna() | (return_diff > 0.01)) & (~is_rejected)
    return_status = np.where(is_rejected, "REJECTED", np.where(return_corrected, "CORRECTED", "PASS"))

    # Metric D: Net Recognized Revenue (Independent and Waterfall Reconciled)
    # Positive sales: units_ordered * net_price. Returns: -expected_returns
    # Waterfall: Gross Sales - Contract Discounts - Return Credits = Net Sales
    expected_net = np.where(
        work_df["net_units"] > 0,
        np.round(work_df["units_ordered"] * work_df["unit_net_price_usd"], 2),
        -expected_returns
    )
    net_orig = work_df["net_sales_usd_original"]
    net_diff = np.where(net_orig.isna(), 0.0, np.abs(net_orig - expected_net))
    net_corrected = (net_orig.isna() | (net_diff > 0.01)) & (~is_rejected)
    net_status = np.where(is_rejected, "REJECTED", np.where(net_corrected, "CORRECTED", "PASS"))

    # Metric E: Cost of Goods Sold (COGS) & Gross Margin
    # COGS is retained from source dataset (cogs_usd_original) rather than independently reconstructed.
    # Configurable fallback proxy (cogs_fallback_pct) applies when COGS is missing/unpopulated,
    # crediting inventory on returns consistently with the documented restocking assumption.
    cogs_orig = work_df["cogs_usd_original"]
    cogs_missing = cogs_orig.isna() | np.isinf(pd.to_numeric(cogs_orig, errors="coerce"))
    cogs_fallback_val = np.where(
        work_df["net_units"] > 0,
        np.round(work_df["units_ordered"] * work_df["unit_wac_price_usd"] * cogs_fallback_pct, 2),
        np.where(
            work_df["net_units"] < 0,
            -np.round(work_df["units_returned"] * work_df["unit_wac_price_usd"] * cogs_fallback_pct, 2),
            0.0
        )
    )
    expected_cogs = np.where(cogs_missing, cogs_fallback_val, cogs_orig)
    cogs_fallback_applied = cogs_missing & (~is_rejected)
    cogs_source_type = np.where(cogs_missing, "ESTIMATED", "SOURCE")

    expected_margin = np.round(expected_net - expected_cogs, 2)
    margin_orig = work_df["gross_margin_usd_original"]
    margin_diff = np.where(margin_orig.isna(), 0.0, np.abs(margin_orig - expected_margin))
    margin_corrected = (margin_orig.isna() | (margin_diff > 0.01)) & (~is_rejected)
    margin_status = np.where(is_rejected, "REJECTED", np.where(margin_corrected, "CORRECTED", "PASS"))

    # ---------------------------------------------------------
    # 6. Business Anomaly Flags (Separated from Financial Status)
    # ---------------------------------------------------------
    high_return = (expected_returns > 50000) & (~is_rejected)
    deep_discount = (disc_val > 35.0) & (work_df["net_units"] > 0) & (~is_rejected)
    large_discrepancy = (net_diff > 100.0) & (~is_rejected)

    is_flagged = high_return | deep_discount | large_discrepancy
    raw_anomaly_flag = pd.Series("", index=work_df.index, dtype="object")
    raw_anomaly_flag = append_reason(raw_anomaly_flag, high_return, "HIGH_VALUE_RETURN")
    raw_anomaly_flag = append_reason(raw_anomaly_flag, deep_discount, "DEEP_DISCOUNT_OUTLIER")
    raw_anomaly_flag = append_reason(raw_anomaly_flag, large_discrepancy, "LARGE_FINANCIAL_DISCREPANCY")
    anomaly_flag = np.where(raw_anomaly_flag == "", "NONE", raw_anomaly_flag)

    # ---------------------------------------------------------
    # 7. Explicit Status Classifications
    # ---------------------------------------------------------
    # Financial corrections: strictly dollar recalculations or COGS fallback estimation
    financial_corrected = (
        gross_corrected | discount_corrected | return_corrected | net_corrected |
        margin_corrected | cogs_fallback_applied
    ) & (~is_rejected)

    # Data quality / categorical standardization: text casing or missing customer name imputation
    categorical_standardized = (casing_corrected | customer_imputed) & (~is_rejected)

    # A. Financial Reconciliation Status: PASS, CORRECTED, REJECTED
    financial_reconciliation_status = pd.Series("PASS", index=work_df.index, dtype="object")
    financial_reconciliation_status = np.where(financial_corrected, "CORRECTED", financial_reconciliation_status)
    financial_reconciliation_status = np.where(is_rejected, "REJECTED", financial_reconciliation_status)

    # B. Data Quality Status: PASS, STANDARDIZED, REJECTED
    data_quality_status = pd.Series("PASS", index=work_df.index, dtype="object")
    data_quality_status = np.where(categorical_standardized, "STANDARDIZED", data_quality_status)
    data_quality_status = np.where(is_rejected, "REJECTED", data_quality_status)

    # C. Backward-compatible Overall Record Status: PASS, CORRECTED, REJECTED
    overall_corrected = (financial_corrected | categorical_standardized) & (~is_rejected)
    reconciliation_status = pd.Series("PASS", index=work_df.index, dtype="object")
    reconciliation_status = np.where(overall_corrected, "CORRECTED", reconciliation_status)
    reconciliation_status = np.where(is_rejected, "REJECTED", reconciliation_status)

    # ---------------------------------------------------------
    # 8. Accumulate All Audit Notes Without Overwriting
    # ---------------------------------------------------------
    correction_notes = pd.Series("", index=work_df.index, dtype="object")
    correction_notes = append_reason(correction_notes, gross_corrected, "GROSS_SALES_RECONCILED")
    correction_notes = append_reason(correction_notes, discount_corrected, "CONTRACT_DISCOUNT_RECONCILED")
    correction_notes = append_reason(correction_notes, return_corrected, "RETURN_VALUE_RECONCILED")
    correction_notes = append_reason(correction_notes, net_corrected, "NET_SALES_RECONCILED")
    correction_notes = append_reason(correction_notes, margin_corrected, "GROSS_MARGIN_RECONCILED")
    correction_notes = append_reason(correction_notes, cogs_fallback_applied, "COGS_ESTIMATED_VIA_FALLBACK")
    correction_notes = append_reason(correction_notes, casing_corrected, "COUNTRY_CASING_STANDARDIZED")
    correction_notes = append_reason(correction_notes, customer_imputed, "CUSTOMER_NAME_IMPUTED")

    audit_notes = pd.Series("", index=work_df.index, dtype="object")
    audit_notes = np.where(is_rejected, "REJECTED: " + rejection_reasons, audit_notes)
    audit_notes = np.where(
        (~is_rejected) & overall_corrected,
        np.where(audit_notes != "", audit_notes + "; CORRECTED: " + correction_notes, "CORRECTED: " + correction_notes),
        audit_notes
    )
    audit_notes = np.where(
        (~is_rejected) & is_flagged,
        np.where(audit_notes != "", audit_notes + "; FLAGGED: " + raw_anomaly_flag, "FLAGGED: " + raw_anomaly_flag),
        audit_notes
    )
    audit_notes = np.where(audit_notes == "", "PASS: Verified without modification", audit_notes)

    # ---------------------------------------------------------
    # 9. Build Row-Level Reconciliation Ledger
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
        "contract_discount_original": work_df["contract_discount_usd_original"],
        "contract_discount_verified": expected_discount,
        "contract_discount_status": discount_status,
        "return_value_original": work_df["return_value_usd_original"],
        "return_value_verified": expected_returns,
        "return_status": return_status,
        "net_sales_original": work_df["net_sales_usd_original"],
        "net_sales_verified": expected_net,
        "net_sales_status": net_status,
        "cogs_original": work_df["cogs_usd_original"],
        "cogs_verified": expected_cogs,
        "cogs_source_type": cogs_source_type,
        "gross_margin_original": work_df["gross_margin_usd_original"],
        "gross_margin_verified": expected_margin,
        "gross_margin_status": margin_status,
        "financial_reconciliation_status": financial_reconciliation_status,
        "data_quality_status": data_quality_status,
        "reconciliation_status": reconciliation_status,
        "anomaly_flag": anomaly_flag,
        "audit_notes": audit_notes
    })

    # ---------------------------------------------------------
    # 10. Create Cleansed Dataset (Retaining Non-Rejected)
    # ---------------------------------------------------------
    clean_df = work_df[~is_rejected].copy()
    clean_df["transaction_date"] = clean_df["transaction_date_clean"]
    clean_df.drop(columns=["transaction_date_clean"], inplace=True)

    # Assign verified financial numbers and statuses
    clean_df["gross_sales_usd"] = expected_gross[~is_rejected]
    clean_df["contract_discount_usd"] = expected_discount[~is_rejected]
    clean_df["return_value_usd"] = expected_returns[~is_rejected]
    clean_df["net_sales_usd"] = expected_net[~is_rejected]
    clean_df["cogs_usd"] = expected_cogs[~is_rejected]
    clean_df["gross_margin_usd"] = expected_margin[~is_rejected]
    clean_df["cogs_source_type"] = cogs_source_type[~is_rejected]
    clean_df["financial_reconciliation_status"] = financial_reconciliation_status[~is_rejected]
    clean_df["data_quality_status"] = data_quality_status[~is_rejected]
    clean_df["reconciliation_status"] = reconciliation_status[~is_rejected]
    clean_df["anomaly_flag"] = anomaly_flag[~is_rejected]

    # Standardize return reasons
    clean_df.loc[clean_df["net_units"] < 0, "return_reason"] = clean_df.loc[clean_df["net_units"] < 0, "return_reason"].fillna("Unspecified Commercial Return")
    clean_df.loc[clean_df["net_units"] > 0, "return_reason"] = "N/A - Standard Sale"

    # ---------------------------------------------------------
    # 11. Aggregate Audit Metrics Summary
    # ---------------------------------------------------------
    audit_metrics = {
        "total_records_ingested": int(total_raw),
        "status_pass_count": int((reconciliation_status == "PASS").sum()),
        "status_corrected_count": int((reconciliation_status == "CORRECTED").sum()),
        "status_flagged_count": int((anomaly_flag != "NONE").sum()),
        "status_rejected_count": int((reconciliation_status == "REJECTED").sum()),
        "financial_status_pass_count": int((financial_reconciliation_status == "PASS").sum()),
        "financial_status_corrected_count": int((financial_reconciliation_status == "CORRECTED").sum()),
        "financial_status_rejected_count": int((financial_reconciliation_status == "REJECTED").sum()),
        "data_quality_pass_count": int((data_quality_status == "PASS").sum()),
        "data_quality_standardized_count": int((data_quality_status == "STANDARDIZED").sum()),
        "data_quality_rejected_count": int((data_quality_status == "REJECTED").sum()),
        "cogs_source_count": int((cogs_source_type == "SOURCE")[~is_rejected].sum()),
        "cogs_estimated_count": int((cogs_source_type == "ESTIMATED")[~is_rejected].sum()),
        "clean_records_retained": int(len(clean_df)),
        "independent_gross_sales_corrected": int(gross_corrected.sum()),
        "independent_discount_corrected": int(discount_corrected.sum()),
        "independent_returns_corrected": int(return_corrected.sum()),
        "independent_net_sales_corrected": int(net_corrected.sum()),
        "independent_gross_margin_corrected": int(margin_corrected.sum()),
        "cogs_fallback_applied_count": int(cogs_fallback_applied.sum()),
        "duplicate_records_dropped": int(dups.sum()),
        "invalid_dates_dropped": int(invalid_date.sum()),
        "zero_quantity_dropped": int(zero_qty.sum()),
        "country_casing_standardized": int(casing_corrected.sum()),
        "missing_customer_name_imputed": int(customer_imputed.sum()),
        "total_verified_gross_sales_usd": round(float(clean_df["gross_sales_usd"].sum()), 2),
        "total_verified_contract_discount_usd": round(float(clean_df["contract_discount_usd"].sum()), 2),
        "total_verified_return_value_usd": round(float(clean_df["return_value_usd"].sum()), 2),
        "total_verified_net_sales_usd": round(float(clean_df["net_sales_usd"].sum()), 2),
        "total_verified_gross_margin_usd": round(float(clean_df["gross_margin_usd"].sum()), 2),
    }

    logger.info(
        "Validation complete: %d Ingested | Financial PASS: %d, CORRECTED: %d | DQ PASS: %d, STANDARDIZED: %d | REJECTED: %d",
        audit_metrics["total_records_ingested"],
        audit_metrics["financial_status_pass_count"],
        audit_metrics["financial_status_corrected_count"],
        audit_metrics["data_quality_pass_count"],
        audit_metrics["data_quality_standardized_count"],
        audit_metrics["financial_status_rejected_count"]
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
