# Data Quality & Validation Report: Commercial Sales Pipeline

**Execution Date:** 2026-10-31
**Pipeline Runtime:** 0.7 seconds
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
| **PASS** | **28,461** | **99.78%** | 100% mathematically consistent; zero anomalies or discrepancies. |
| **CORRECTED** | **35** | **0.12%** | Valid transactions with formatting (country casing) or imputed customer names reconciled. |
| **FLAGGED** | **4** | **0.01%** | Retained in analytical core, but flagged for business audit (high-value return or discount outlier). |
| **REJECTED** | **25** | **0.09%** | Dropped due to duplicate transaction ID, unparseable date, zero quantity, or invalid pricing. |
| **Total Ingested** | **28,525** | **100.00%** | Raw ERP billing transactions ingested. |
| **Clean Retained** | **28,500** | **99.91%** | Loaded into Star Schema OLAP database (`fact_sales`). |

---

## 3. Independent Financial Metric Validation

All four commercial financial dimensions were validated independently against unit-level transaction parameters:

| Commercial Financial Metric | Expected Formulation | Anomalies Identified | Reconciliation Action |
| :--- | :--- | :--- | :--- |
| **Gross Invoiced Sales** | `Units Ordered × Unit WAC Price` (or $0.00 for returns) | 0 records | Verified & reconciled against WAC price book. |
| **Customer Returns** | `Units Returned × Unit Net Price` (or $0.00 for standard sales) | 0 records | Verified & reconciled against contract net price. |
| **Net Recognized Revenue** | `Gross Sales - Returns - Contract Discounts` | 0 records | Verified & reconciled against transaction terms. |
| **Cost of Goods Sold (COGS)** | Retained from source dataset (`cogs_usd_original`); 15% WAC fallback if unpopulated | 0 records | Preserved from source dataset; verified against standard cost. |
| **Gross Margin** | `Net Sales - Cost of Goods Sold (COGS)` | 0 records | Verified independently as `expected_net - expected_cogs`. |

> **Accounting Design & COGS Disclosure:**
> - **COGS Retention:** Cost of Goods Sold is retained directly from the source dataset (`cogs_usd_original`) rather than independently reconstructed for each line item, as transactional feeds typically lack direct relational joins to manufacturing ERP bill-of-materials tables.
> - **15% Fallback Assumption:** If `cogs_usd` is absent or completely unpopulated in an ingested batch, the pipeline applies a 15% of WAC proxy (`units_ordered * WAC * 0.15`) based on pharmaceutical manufacturing cost benchmarks.

---

## 4. Financial Integrity Audit Totals

- **Gross Sales Realized (USD):** $1,480,438,365.00
- **Customer Returns / Reversals (USD):** $2,772,950.45
- **Net Recognized Revenue (USD):** $1,245,009,425.53
- **Gross-to-Net Realization Rate:** 84.10%
- **Total Net Units Distributed:** 4,898,450 units across 6 global markets.

---

## 5. Synthetic Data & Accounting Assumptions

All financial figures are derived from reproducible synthetic data generated via `src/generate_commercial_data.py` (seed 42). They do not represent actual pharmaceutical manufacturer revenue or verified market share.

**Core Synthetic Accounting Assumptions:**
1. **Return-Credit Valuation at Net Contract Price:** Returns credit the customer at `unit_net_price_usd` (the contract net price reflecting the channel discount) rather than list WAC. In this synthetic dataset, returns are generated with channel-specific contract discount rates rather than dynamically joining against historical parent invoice IDs.
2. **Inventory Restocking & COGS Reversal:** When a return transaction occurs (`net_units < 0`), COGS is credited back (`net_units * unit_cost < 0`), reducing total COGS and increasing gross margin. This assumes returned units are restocked into available inventory or credited by the supply chain rather than scrapped at 100% loss.
3. **COGS Derivation & Fallback:** Source transactional COGS is derived from product base manufacturing cost. When absent, the validation module employs a 15% WAC heuristic proxy.
