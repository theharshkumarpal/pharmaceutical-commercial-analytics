# Project Audit & Transformation Strategy: Pharmaceutical Commercial Performance & Market Analytics

**Author:** Pharmaceutical Commercial Analytics Associate<br>
**Target Domain:** Life Sciences Commercial Analytics Advisory (Blue Matter Consulting focus)<br>
**Date:** October 2026  
**Status:** Phase 1 Complete (Baseline Audit & Architecture Blueprint)

---

## 1. Executive Summary & Context

The initial repository was structured as a graduate portfolio project (`pharmacovigilance-pipeline`) tracking spontaneous adverse event reports from openFDA FAERS across 6 mental health drugs (Adderall, Ritalin, Xanax, Lexapro, Olanzapine, Seroquel) using Flask, PostgreSQL, and Plotly.

While valuable for clinical safety data engineering, **pharmacovigilance data alone does not support commercial performance analytics** (gross-to-net sales, product pricing, customer segmentation, territory sales rep effectiveness, distributor concentration, and channel dynamics). In life sciences commercial consulting (e.g., Blue Matter Consulting), commercial analytics evaluates:
1. **Commercial Execution & Revenue Velocity:** Gross sales, return deductions, discounts, net sales realization, and transaction volume.
2. **Portfolio & Brand Strategy:** ABC/Pareto classification, brand lifecycle, volume vs. value contribution, and therapeutic mix.
3. **Geographic & Market Access Performance:** Unequal date coverage reconciliation, common-period market growth, and geographic concentration.
4. **Account & Channel Dynamics:** Health Systems / Hospitals vs. Retail Chains vs. Specialty Pharmacies; distributor dependency (McKesson, AmerisourceBergen/Cencora, Cardinal Health) and RFM customer segmentation.
5. **Sales Force Effectiveness (SFE):** Territory alignment, representative productivity, headcount-normalized team revenue, and quota tracking.

To establish a dedicated commercial platform adhering to top-tier life sciences consulting standards, the project transitioned to a focused **Commercial Analytics Architecture**:
- **Commercial Analytics Core:** An enterprise-grade, transaction-level dataset spanning multi-country, multi-channel pharmaceutical sales with real-world complexities (unequal date windows, return rates, pricing variations, customer tiers, and sales rep territories) modeled in a star schema (`fact_sales` + 7 dimensions).
- **Repository Decoupling:** Spontaneous adverse event reporting and drug safety engineering components were decoupled into the separate repository (`Pharma-Commercial-Drug-Safety-Analytics`), allowing this repository to remain exclusively focused on commercial execution, gross-to-net waterfall accounting, and time-series forecasting.

---

## 2. Historical Baseline Audit & Commercial Transformation

### 2.1 Historical Baseline Components (Decoupled)
- `etl/extract.py` & `etl/transform_load.py`: Historical openFDA REST ingestion and JSON normalization pipeline (now housed in dedicated safety repository).
- `db/schema.sql`: Historical clinical PostgreSQL DDL.
- `app/app.py` & `app/templates/`: Historical safety visualization web interface.

### 2.2 Existing Strengths
1. **Clear Relational Schema:** Normalized entity separation following clinical regulatory standards.
2. **Robust Error Handling:** Handles rate limits (HTTP 429 backoff) and JSON normalization.
3. **Idempotent Ingestion:** Employs `ON CONFLICT (safety_report_id) DO NOTHING`.

### 2.3 Critical Limitations for Commercial Analytics
1. **Absence of Transactional Sales Attributes:** No pricing, unit volumes, discounts, customer IDs, distributors, sales territories, or net revenue.
2. **Single-Source Clinical Data:** FAERS represents spontaneous reporting, meaning it suffers from under-reporting and reporting bias, and cannot establish incidence rates or market share.
3. **Lack of Star Schema OLAP Capabilities:** Current tables are purely 3NF transactional OLTP without dimensional aggregation tables, surrogate keys for time/geography, or precomputed commercial KPIs.
4. **Absence of Gross-to-Net Accounting:** No distinction between gross invoicing, chargebacks, customer returns, and net recognized revenue.

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
- [ ] **Phase 2: Data Generation, Validation & Preprocessing Pipeline**
  - Implement `src/generate_commercial_data.py` with realistic market anomalies, unequal country coverage, and returns.
  - Implement `src/data_validation.py` and `src/data_preprocessing.py`.
  - Produce `docs/DATA_DICTIONARY.md` and `docs/DATA_QUALITY_REPORT.md`.
- [ ] **Phase 3: SQL Dimensional Model (Star Schema)**
  - Implement `sql/02_schema.sql` (Fact & 7 Dimensions with PK/FK, surrogate keys, indexing).
  - Implement `sql/03_transformations.sql` to load cleaned data into SQLite / PostgreSQL.
- [ ] **Phase 4: Advanced SQL Commercial Analytics Suite**
  - `sql/04_kpi_analysis.sql`: Executive commercial performance & Gross-to-Net.
  - `sql/05_product_analysis.sql`: Portfolio ABC/Pareto & product mix.
  - `sql/06_customer_analysis.sql`: Customer RFM segmentation & distributor concentration.
  - `sql/07_geographic_analysis.sql`: Normalized geographic performance & common-period comparisons.
  - `sql/08_sales_force_analysis.sql`: Territory & sales force productivity analytics.
  - `sql/09_channel_analysis.sql`: Commercial channel velocity & average transaction values.
- [ ] **Phase 5: Python Analytical Workflow & Defensible Forecasting**
  - `src/eda.py`: Automated statistical profiling.
  - `src/customer_segmentation.py`: RFM clustering and account profiling.
  - `src/revenue_forecasting.py`: Time series forecasting (ARIMA / Holt-Winters) with backtesting.
  - `src/visualizations.py`: High-resolution figures saved to `outputs/figures/`.
- [ ] **Phase 6: Power BI Semantic Model & Dashboard Specifications**
  - Comprehensive DAX measures library (`dashboards/powerbi/dax_measures.txt`).
  - 6-page interactive executive wireframe and consulting guide (`docs/DASHBOARD_GUIDE.md`).
- [ ] **Phase 7: Testing, Validation & Financial Reconciliation**
  - Automated tests in `tests/test_analytics.py` verifying financial reconciliation (Gross - Returns = Net).
- [ ] **Phase 8: Consulting Insights & Executive Deliverables**
  - `docs/BUSINESS_INSIGHTS.md`: Executive findings & consulting recommendations.
  - `docs/RESUME_BULLETS.md`: High-impact, quantified project metrics.
