# Data Quality & Validation Report: Commercial Sales Pipeline

**Execution Date:** 2026-10-31
**Pipeline Runtime:** 0.8 seconds
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

## 2. Row-Level Reconciliation Status & Business Anomaly Summary

| Metric Dimension | Classification | Record Count | % of Ingested | Description & Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **Financial Status** | **PASS** | **28,500** | **99.91%** | 100% mathematically consistent without financial adjustment. |
| **Financial Status** | **CORRECTED** | **0** | **0.00%** | Financial amounts adjusted to enforce gross-to-net waterfall identity. |
| **Financial Status** | **REJECTED** | **25** | **0.09%** | Fatal financial invalidity (negative price, impossible discount, duplicates). |
| **Data Quality Status** | **PASS** | **28,465** | **99.79%** | Clean entity attributes requiring no structural transformation. |
| **Data Quality Status** | **STANDARDIZED** | **35** | **0.12%** | Entity casing cleaned (15) or missing customer name imputed (20). |
| **Data Quality Status** | **REJECTED** | **25** | **0.09%** | Malformed dates, blank IDs, or duplicate records rejected upfront. |
| **Overall Record Status** | **PASS** | **28,465** | **99.79%** | Retained unmodified across both financial and categorical checks. |
| **Overall Record Status** | **CORRECTED** | **35** | **0.12%** | Categorically standardized or financially reconciled records. |
| **Overall Record Status** | **REJECTED** | **25** | **0.09%** | Dropped due to duplicate transaction ID, unparseable date, or invalid pricing. |
| **COGS Provenance** | **SOURCE** | **28,500** | **100.00%** | COGS retained directly from ingested source data. |
| **COGS Provenance** | **ESTIMATED** | **0** | **0.00%** | Estimated via configurable fallback assumption (15% WAC). |
| **Business Anomaly Flags** | **FLAGGED** | **4** | **0.01%** | Retained in analytical core, tagged with business anomaly flag (deep discount outlier). |
| **Total Ingested** | **Raw Records** | **28,525** | **100.00%** | Raw ERP billing transactions ingested. |
| **Clean Retained** | **Fact Table** | **28,500** | **99.91%** | Loaded into Star Schema OLAP database (`fact_sales`). |

---

## 3. Independent Financial Metric Validation & Waterfall

All commercial financial dimensions were validated independently against unit-level transaction parameters:

| Commercial Financial Metric | Expected Formulation | Anomalies Identified | Reconciliation Action |
| :--- | :--- | :--- | :--- |
| **Gross Invoiced Sales** | `Units Ordered × Unit WAC Price` (or $0.00 for returns) | 0 records | Verified & reconciled against WAC price book. |
| **Contract Discounts** | `Units Ordered × (WAC - Net Price)` (or $0.00 for returns) | 0 records | Reconciled in gross-to-net waterfall. |
| **Customer Returns** | `Units Returned × Unit Net Price` (or $0.00 for standard sales) | 0 records | Verified & reconciled against contract net price. |
| **Net Recognized Revenue** | `Gross Sales - Contract Discounts - Returns` | 0 records | Waterfall identity holds to the exact cent. |
| **Cost of Goods Sold (COGS)** | Retained from source dataset (`cogs_usd_original`); configurable fallback proxy | 0 fallback rows | Preserved from source dataset; returns credit inventory. |
| **Gross Margin** | `Net Sales - Cost of Goods Sold (COGS)` | 0 records | Verified independently as `expected_net - expected_cogs`. |

---

## 4. Financial Integrity Audit Totals

- **Gross Sales Realized (USD):** $1,480,438,365.00
- **Contract Discounts & Rebates (USD):** $232,655,989.02
- **Customer Returns / Reversals (USD):** $2,772,950.45
- **Net Recognized Revenue (USD):** $1,245,009,425.53
- **Gross-to-Net Realization Rate:** 84.10%
- **Total Net Units Distributed:** 4,898,450 units across 6 global markets.

> **Synthetic Data & Accounting Disclosures:**
> 1. All financial figures are derived from reproducible synthetic data generated via `src/generate_commercial_data.py` (seed 42). They do not represent actual pharmaceutical manufacturer revenue or verified market share.
> 2. **COGS Accounting:** Cost of Goods Sold is retained from source records. In unpopulated datasets, a configurable synthetic fallback (defaulting to 15% of WAC) estimates COGS, crediting returns.
> 3. **Reverse Logistics:** Returns credit net invoice price, and returned inventory credits COGS under the operational assumption of product restocking.
