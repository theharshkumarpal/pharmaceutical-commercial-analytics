# Independent Audit Report: Pharmaceutical Commercial Performance Platform

**Auditor:** Independent Senior Data Analytics Reviewer & Pharmaceutical Commercial Consultant
**Audit Scope:** Full repository source code, generated transactional data, SQLite star schema, SQL queries, Python analytical pipelines, machine learning models, and consulting documentation.
**Audit Date:** October 2026
**Status:** Audit Completed — Verification, Corrections & Defensibility Confirmed

---

## 1. Executive Summary & Verdict

This independent audit evaluated the analytical codebase, financial models, data integrity checks, and documentation against life sciences commercial analytics best practices.

### Overall Audit Verdict: **DEFENSIBLE WITH DOCUMENTED METHODOLOGY**
- **Data Engineering & Schema Integrity:** **100% Verified**. The Kimball star schema (`fact_sales` + 7 dimensions) enforces strict primary/foreign key constraints, contains zero orphaned foreign keys, zero duplicate transactions, and properly models reverse logistics returns as economic deductions rather than filtering them out.
- **Financial Reconciliation:** **100% Mathematically Sound**. `Gross Sales ($1.480B) - Returns ($2.77M) - Contract Discounts ($232.66M) = Net Sales ($1.245B)` reconciles identically across raw CSV, processed data, SQL queries, and Python pipelines. Gross Margin (`Net Sales - COGS = $1.025B`, 82.35%) reconciles to the exact cent ($0.00 discrepancy).
- **Consulting Claims & Discrepancies:** While core findings (GTN realization, ABC Pareto, and geographic common-period dynamics) were verified, two specific documented claims in earlier summaries required empirical correction:
  1. *Distributor Concentration:* Documented as 78.0% for the "Big Three"; the empirical data shows the top 3 intermediaries capture **69.65%** ($867.1M) with *Direct Pharma Logistics* being the largest at 35.01%.
  2. *Sales Force Headcount Normalization:* Documented as $59.04M vs $47.37M per rep; the actual database calculation across the 4 teams of 6 reps each shows *Team Alpha - CNS North* at **$53.67M/rep** and *Team Gamma - Specialty* at **$53.14M/rep**.

All documentation has been updated to reflect the exact, unadjusted empirical facts.

---

## 2. Dataset Provenance & Structural Audit

### 2.1 Entity Counts & Dimensions
- **Dataset Nature:** Explicitly **synthetic, transaction-level commercial distribution data** generated via `src/generate_commercial_data.py` (fixed seed `42` for exact reproducibility). It is **not** audited secondary audit data (IQVIA MIDAS / Symphony Health) or official government claims data.
- **Total Ingested Records:** 28,525 raw transactions.
- **Total Analytical Records:** 28,500 cleansed rows (25 deliberate duplicates removed).
- **Date Range:** `2023-01-01` to `2025-12-31` (1,096 calendar days, 36 months).
- **Entity Dimensions:**
  - `dim_product`: 9 pharmaceutical assets (6 CNS, 2 Oncology, 1 Immunology).
  - `dim_geography`: 6 countries across 3 regions (US, DE, UK, FR, JP, CA).
  - `dim_customer`: 120 institutional healthcare accounts (IDNs, Academic Medical Centers, Clinics).
  - `dim_distributor`: 6 wholesale logistics intermediaries.
  - `dim_sales_rep`: 24 field commercial representatives across 4 business units (6 reps/team).
  - `dim_channel`: 4 commercial distribution routes.

### 2.2 Financial Mechanics & Return Generation
- **Gross Sales:** Invoiced demand generated as `units_ordered * unit_wac_price_usd`.
- **Contract Discounts:** Modeled via channel-specific normal distributions (Hospital Tender: 22.1%, Wholesale: 15.0%, Retail: 9.9%, Specialty: 8.0%).
- **Returns & Reversals:** 0.22% of transactions feature negative quantities (`net_units < 0`), positive `return_value_usd`, and explicit return reasons (`Damaged in Transit`, `Recall / Batch Expiry`, `Customer Overstock Return`, `Temperature Excursion`).
- **COGS & Margin:** COGS is calculated as `net_units * unit_cost`. On return rows, COGS is negative (inventory credit reversal), ensuring that `Net Sales - COGS = Gross Margin` holds universally across both sales and returns.

---

## 3. Financial Reconciliation Matrix

| Financial Metric | Raw Ingestion | Processed CSV | SQL Fact Table (`fact_sales`) | Python Independent Audit | Reconciliation Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Gross Invoiced Sales** | $1,481,737,860.00 | $1,480,438,365.00 | $1,480,438,365.00 | $1,480,438,365.00 | **Reconciled (Exact Cent)** |
| **Return Deductions** | $2,773,858.85 | $2,772,950.45 | $2,772,950.45 | $2,772,950.45 | **Reconciled (Exact Cent)** |
| **Contract Discounts** | $232,854,821.10 | $232,655,989.02 | $232,655,989.02 | $232,655,989.02 | **Reconciled (Exact Cent)** |
| **Net Recognized Sales** | $1,246,109,180.05 | $1,245,009,425.53 | $1,245,009,425.53 | $1,245,009,425.53 | **Reconciled (Exact Cent)** |
| **Cost of Goods Sold** | $219,918,844.00 | $219,723,424.00 | $219,723,424.00 | $219,723,424.00 | **Reconciled (Exact Cent)** |
| **Commercial Gross Margin** | $1,026,190,336.05 | $1,025,286,001.53 | $1,025,286,001.53 | $1,025,286,001.53 | **Reconciled (Exact Cent)** |
| **Gross Margin %** | 82.35% | 82.35% | 82.35% | 82.35% | **Reconciled (Exact Cent)** |
| **GTN Realization Rate** | 84.10% | 84.10% | 84.10% | 84.10% | **Reconciled (Exact Cent)** |

*Note: The small delta between raw ingestion and processed data reflects the exact removal of 25 duplicate rows during validation ($1.30M in duplicate gross sales eliminated).*

---

## 4. SQL Analytics & Architecture Audit

1. **Fact Table Grain:** Evaluated at 1 record per commercial invoice line or credit return memo. No pre-aggregation distortions.
2. **Referential Integrity:** Audited via `tests/test_audit_validation.py`. Zero orphaned foreign keys across all 7 dimensions.
3. **Common Table Expressions & Window Functions:** Evaluated across `sql/04_kpi_analysis.sql` through `sql/09_channel_analysis.sql`.
   - Correctly uses `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` for cumulative Pareto calculations.
   - Correctly uses `LAG(net_sales_usd, 1) OVER (ORDER BY year_month)` for MoM and YoY calculations.
   - Correctly partitions by country for geographic product-mix percentages.

---

## 5. Forecasting Implementation Audit

- **Train/Test Temporal Split:** Evaluated in `src/revenue_forecasting.py`. 30 months training (Jan 2023–Jun 2025), 6 months test (Jul 2025–Dec 2025). **Zero future data leakage.**
- **Model Benchmark Results (Test Horizon H2 2025):**
  - *Baseline Seasonal Naive (12-Month Lag):* **MAPE 4.08% | MASE 0.61 | MAE $1,655,444 | RMSE $2,129,019**
  - *Holt-Winters Exponential Smoothing:* **MAPE 11.55% | MASE 1.89 | MAE $5,097,148 | RMSE $6,163,093**
  - *SARIMAX(1,1,1):* MAPE 11.86% | MASE 1.98 | MAE $5,339,027 | RMSE $6,853,154
  - *Baseline Naive Persistence:* MAPE 11.85% | MASE 1.99 | MAE $5,382,979 | RMSE $7,107,358
  - *Baseline 6-Month Moving Average:* MAPE 11.92% | MASE 2.02 | MAE $5,467,872 | RMSE $7,445,579
- **Statistical Defensibility & Model Comparison:** The seasonal naive benchmark achieves the lowest error (4.08% MAPE, 0.61 MASE) on the 6-month test horizon due to recurring annual purchasing cyclicality in the synthetic commercial series. Among trend-parameterized statistical models, Holt-Winters achieves 11.55% MAPE on the fixed test set and 10.45% in rolling-origin cross-validation, providing smooth multi-period forward projections.

---

## 6. Customer RFM Segmentation Audit

- **Recency Reference Date:** `2025-12-31` (latest transaction date).
- **Segmentation Distribution:**
  - *Tier 1: Strategic Key Accounts (Champions):* 37 accounts (30.8%)
  - *Tier 2: Loyal Growth Accounts:* 20 accounts (16.7%)
  - *Tier 3: At-Risk High-Value Accounts:* 18 accounts (15.0%)
  - *Tier 4: Promising Developing Accounts:* 12 accounts (10.0%)
  - *Tier 5: Low-Engagement Accounts:* 33 accounts (27.5%)
- **K-Means Clustering:** Features `recency_days`, `frequency_orders`, and `monetary_value_usd` were log-transformed (`log1p`) and standardized using `StandardScaler` before clustering into 4 defensible institutional account clusters.

---

## 7. Power BI Status Clarification

- **PBIX Binary File:** Direct graphical editing of `.pbix` binary files is unsupported in this headless terminal environment. No `.pbix` binary was modified.
- **Implemented Power BI Assets:**
  1. Complete, copy-paste ready DAX measures library in [dashboards/powerbi/dax_measures.txt](../dashboards/powerbi/dax_measures.txt) (17 core measures).
  2. Complete 6-page visual specification, wireframe layout, and slicer configuration guide in [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md).
- **Implementation Architecture:** The project establishes the dimensional star schema, complete DAX measures library, and executive wireframes for Power BI, modeling relationships as 1-to-many single directional joins against the processed database.
