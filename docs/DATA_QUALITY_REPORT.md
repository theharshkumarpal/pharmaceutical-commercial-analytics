# Data Quality & Validation Report: Commercial Sales Pipeline

**Execution Date:** 2026-10-31  
**Pipeline Runtime:** 0.4 seconds  
**Source Dataset:** `data/raw/pharma_commercial_sales_raw.csv`  
**Processed Target:** `data/processed/cleaned_sales.csv` & `data/processed/pharma_commercial.db`  

---

## 1. Executive Summary

A validation protocol was executed over the commercial transactional records. The pipeline strictly maintains reverse logistics integrity (identifying and categorizing returns as commercial deductions rather than silently dropping negative rows), normalizes inconsistent geographic and customer entities, eliminates exact duplicate rows, and verifies gross-to-net financial calculations.

**Financial values are recalculated from unit-level source data.** Original pre-recalculation values are preserved during validation for audit traceability (columns suffixed `_original`).

---

## 2. Validation Metrics & Record Ledger

| Validation Rule / Step | Records Affected | Pipeline Action Taken | Business Justification |
| :--- | :--- | :--- | :--- |
| **Total Ingested Records** | **28,525** | Ingested | Complete raw ingestion. |
| **Duplicate Transactions** | **25** | Removed | Eliminated duplicate transaction IDs to prevent revenue double-counting. |
| **Invalid / Unparseable Dates** | **0** | Filtered / Verified | Validated ISO-8601 formatting (`YYYY-MM-DD`). |
| **Zero Quantity Entries** | **0** | Dropped | Zero-quantity rows convey no volume or economic transfer. |
| **Customer Returns & Reversals** | **509** | **Preserved & Tagged** | Reverse logistics preserved with negative unit counts, return amounts, and reason codes. |
| **Country Inconsistent Casing/Spacing** | **15** | Standardized | Stripped whitespace and title-cased country names (`United States`, `Germany`, etc.). |
| **Missing Customer Names** | **20** | Imputed via ID | Imputed customer names from known customer registry via `customer_id`. |
| **Gross-to-Net Reconciliation Mismatch** | **0** | Reconciled | Enforced `Gross Sales = Units × WAC` and `Net Sales = Units × Net Price`. Max discrepancy: $0.00. |
| **Final Clean Analytical Records** | **28,500** | **Loaded to OLAP Core** | 100% verified, referentially sound transactions. |

---

## 3. Financial Integrity Audit

- **Gross Sales Realized (USD):** $1,480,438,365.00
- **Customer Returns / Reversals (USD):** $2,772,950.45
- **Net Recognized Revenue (USD):** $1,245,009,425.53
- **Gross-to-Net Realization Rate:** 84.10%
- **Total Net Units Distributed:** 4,898,450 units across 6 global markets.

> **Synthetic Data Disclosure:** All financial figures are derived from reproducible synthetic data generated via `src/generate_commercial_data.py` (seed 42). They do not represent actual pharmaceutical manufacturer revenue or verified market share.
