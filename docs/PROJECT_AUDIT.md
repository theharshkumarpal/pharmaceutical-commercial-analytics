# Project Audit & Architecture Blueprint: Pharmaceutical Commercial Performance & Market Analytics

**Domain Focus:** Life Sciences Commercial Analytics & Strategic Advisory<br>
**Date:** October 2026  
**Status:** Architecture Specification & Transformation Blueprint Complete

---

## 1. Executive Summary & Commercial Scope

This platform is engineered exclusively for **Pharmaceutical Commercial Performance, Gross-to-Net (GTN) Revenue Accounting, Market Access Normalization, Customer RFM Segmentation, Sales Force Effectiveness (SFE), and Time-Series Revenue Forecasting**.

In life sciences commercial consulting, commercial analytics evaluates:
1. **Commercial Execution & Revenue Velocity:** Gross sales, return deductions, discounts, net sales realization, and transaction volume.
2. **Portfolio & Brand Strategy:** ABC/Pareto classification, brand lifecycle, volume vs. value contribution, and therapeutic mix.
3. **Geographic & Market Access Performance:** Unequal date coverage reconciliation, common-period market growth, and geographic concentration.
4. **Account & Channel Dynamics:** Health Systems / Hospitals vs. Retail Chains vs. Specialty Pharmacies; distributor dependency (McKesson, AmerisourceBergen/Cencora, Cardinal Health) and RFM customer segmentation.
5. **Sales Force Effectiveness (SFE):** Territory alignment, representative productivity, headcount-normalized team revenue, and quota tracking.

The platform architecture is built around:
- **Commercial Analytics Core:** An enterprise-grade, transaction-level dataset spanning multi-country, multi-channel pharmaceutical sales with real-world distribution dynamics (unequal date windows, return rates, pricing variations, customer tiers, and sales rep territories) modeled in a Kimball star schema (`fact_sales` + 7 dimensions).
- **Independent Validation & Integrity:** Rigorous financial reconciliation, automated data validation, out-of-sample forecast benchmarking, and automated regression testing.

---

## 2. Commercial Analytics Platform Architecture

### 2.1 Core Architectural Requirements
1. **Kimball Star Schema OLAP Core:** Dimensional aggregation tables with surrogate keys for time, geography, customer, product, distributor, channel, and sales rep.
2. **Gross-to-Net (GTN) Waterfall Accounting:** Rigorous accounting distinguishing gross invoicing (WAC), reverse logistics returns, statutory/contract discounts, and net recognized revenue.
3. **Common-Period Normalization:** Standardized benchmarking across non-synchronous geographic launch dates.
4. **Multi-Horizon Revenue Forecasting:** Defensible statistical time-series models evaluated against seasonal naive and persistence baselines.

---

## 3. Commercial Dataset Specification (Raw Ingestion)

To enable end-to-end commercial analytics matching top-tier consulting standards, we profile and generate a comprehensive raw transactional dataset (`data/raw/pharma_commercial_sales_raw.csv`) reflecting global pharmaceutical commercial distribution:

- **Volume:** 25,000+ transaction rows.
- **Time Horizon:** 2023-01-01 through 2025-12-31 (36 months).
- **Geographic Markets (Unequal Coverage by Design):**
  - United States (US): 2023 - 2025 (Full 36 months)
  - Germany (DE): 2023 - 2025 (Full 36 months)
  - United Kingdom (UK): 2023 - 2025 (Full 36 months)
  - France (FR): 2023-07 to 2025-12 (30 months - delayed market access launch)
  - Japan (JP): 2024-01 to 2025-12 (24 months - regulatory approval timing)
  - Canada (CA): 2024-06 to 2025-12 (18 months - provincial formulary listing)
- **Therapeutic Areas & Brands (Aligned with existing portfolio + commercial portfolio):**
  - Central Nervous System (CNS) / Psychiatry: *AmphetaDex (ADHD)*, *DexMethyl (ADHD)*, *AlprazPlus (Anxiolytic)*, *EscitaloPro (Depression)*, *OlanzRx (Schizophrenia)*, *QuetiapMax (Bipolar/Sleep)*
  - Oncology / Specialty: *OncoShield (Kinase Inhibitor)*, *ImmunoPax (mAbs)*
  - Immunology / Biologics: *RheumaCure (TNF-alpha)*
- **Customer Types:** Academic Medical Centers, Regional Health Systems, Retail Pharmacy Chains, Specialty Pharmacies, Government/VA Hospitals.
- **Distributors:** McKesson, AmerisourceBergen (Cencora), Cardinal Health, Alliance Healthcare, Medipal Holdings, Direct Distribution.
- **Sales Channels:** Direct Hospital Tender, Wholesale Distribution, Retail Pharmacy, E-Commerce / Mail Order.
- **Financial & Commercial Attributes:** Units Ordered, Units Returned, Unit Wholesale Price, Unit Net Price, Gross Sales, Return Value, Net Sales, Sales Rep ID, Territory Code.

---

## 4. Analytical Weaknesses & Solutions Matrix

| Area | Observed Weakness in Typical Projects | Consulting-Grade Solution |
| :--- | :--- | :--- |
| **Returns & Refunds** | Silently filtering out negative rows or treating returns as errors. | Retain negative quantities as authentic reverse logistics events. Distinguish Gross Sales vs. Returns vs. Net Sales. |
| **Geographic Comparisons** | Averaging total revenue across countries with 36 months vs. 18 months of data. | Implement strict **Common-Period Comparisons** (e.g., LTM or FY2025) and report CAGR only where time horizon is identical. |
| **Product Prioritization** | Arbitrary top-5 ranking without concentration analysis. | Formal **ABC / Pareto cumulative contribution analysis** (80% / 15% / 5%). |
| **Customer Valuation** | Basic total revenue grouping without behavioral frequency. | **RFM Segmentation** (Recency, Frequency, Monetary) classifying accounts into Champions, Loyal, At-Risk, and Inactive. |
| **Sales Force Productivity** | Attributing high revenue solely to individual rep capability. | Territory and headcount normalization: Revenue per Rep, quota attainment, and territory market potential. |
| **Forecasting** | Overfitting deep learning models on short monthly time series. | Defensible time-series forecasting using SARIMA / Exponential Smoothing and Holt-Winters with rolling train/test splits, evaluating on MAE, RMSE, and MAPE. |

---

## 5. End-to-End Implementation Roadmap

- [x] **Phase 1: Project Audit & Architectural Strategy** (`docs/PROJECT_AUDIT.md`)
- [x] **Phase 2: Data Generation, Validation & Preprocessing Pipeline**
  - Implement `src/generate_commercial_data.py` with realistic market anomalies, unequal country coverage, and returns.
  - Implement `src/data_validation.py` and `src/data_preprocessing.py`.
  - Produce `docs/DATA_DICTIONARY.md` and `docs/DATA_QUALITY_REPORT.md`.
- [x] **Phase 3: SQL Dimensional Model (Star Schema)**
  - Implement `sql/02_schema.sql` (Fact & 7 Dimensions with PK/FK, surrogate keys, indexing).
  - Implement `sql/03_transformations.sql` to load cleaned data into SQLite / PostgreSQL.
- [x] **Phase 4: Advanced SQL Commercial Analytics Suite**
  - `sql/04_kpi_analysis.sql`: Executive commercial performance & Gross-to-Net.
  - `sql/05_product_analysis.sql`: Portfolio ABC/Pareto & product mix.
  - `sql/06_customer_analysis.sql`: Customer RFM segmentation & distributor concentration.
  - `sql/07_geographic_analysis.sql`: Normalized geographic performance & common-period comparisons.
  - `sql/08_sales_force_analysis.sql`: Territory & sales force productivity analytics.
  - `sql/09_channel_analysis.sql`: Commercial channel velocity & average transaction values.
- [x] **Phase 5: Python Analytical Workflow & Defensible Forecasting**
  - `src/eda.py`: Automated statistical profiling.
  - `src/customer_segmentation.py`: RFM clustering and account profiling.
  - `src/revenue_forecasting.py`: Time series forecasting (ARIMA / Holt-Winters) with backtesting.
  - `src/visualizations.py`: High-resolution figures saved to `outputs/figures/`.
- [x] **Phase 6: Power BI Semantic Model & Dashboard Specifications**
  - Comprehensive DAX measures library (`dashboards/powerbi/dax_measures.txt`).
  - 6-page interactive executive wireframe and consulting guide (`docs/DASHBOARD_GUIDE.md`).
- [x] **Phase 7: Testing, Validation & Financial Reconciliation**
  - Automated tests in `tests/test_analytics.py` and `tests/test_audit_validation.py` verifying financial reconciliation.
- [x] **Phase 8: Consulting Insights & Executive Deliverables**
  - `docs/BUSINESS_INSIGHTS.md`: Executive findings & consulting recommendations.
  - `docs/RESUME_BULLETS.md`: High-impact, quantified project metrics.
