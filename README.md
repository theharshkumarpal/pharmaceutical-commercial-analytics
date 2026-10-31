# Pharmaceutical Commercial Performance & Market Analytics Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![SQL](https://img.shields.io/badge/SQL-Star_Schema-orange.svg)](https://sqlite.org/)
[![Power BI](https://img.shields.io/badge/Power_BI-DAX_Measures-yellow.svg)](https://powerbi.microsoft.com/)
[![Life Sciences](https://img.shields.io/badge/Domain-Pharmaceutical_Commercial_Strategy-teal.svg)](https://www.bluematterconsulting.com/)

A commercial analytics platform for **Pharmaceutical Commercial Performance, Gross-to-Net (GTN) Revenue Accounting, Market Access Normalization, Customer RFM Segmentation, Headcount-Normalized Sales Productivity, and Time-Series Revenue Forecasting**.

Built for **Commercial Analytics, Life Sciences Advisory, and Global Brand Strategy**.

---

## 1. Executive Summary & Commercial KPIs

> **Data Disclosure & Synthetic Provenance:** The commercial sales dataset is **synthetic transaction-level data** generated via Python (`src/generate_commercial_data.py`, fixed seed `42`) to model multi-market launches, contract discounting, and reverse logistics. All figures are generated from modeled assumptions and do not represent actual pharmaceutical manufacturer revenue, verified market share, or proprietary secondary audit data (e.g., IQVIA MIDAS/NPA or Symphony Health PHAST).
> - **Accounting & COGS Mechanics:** Cost of Goods Sold (COGS) is retained directly from the source dataset (`cogs_usd_original`) rather than independently reconstructed from bill-of-materials master tables for each transaction. When COGS is unpopulated, an explicitly configurable synthetic assumption of 15% of WAC is applied (`cogs_fallback_pct=0.15`), calculating COGS on sales via `units_ordered * WAC * cogs_fallback_pct` and crediting inventory restocking on returns via `-units_returned * WAC * cogs_fallback_pct`.
> - **Synthetic Accounting Assumptions:** Returns are credited at contract net price (`unit_net_price_usd`) without double-counting discounts, and reverse logistics events credit inventory back via negative COGS under the operational assumption of usable return restocking.

> **Power BI Deliverables Disclosure:** **No binary Power BI `.pbix` file is included in this repository.** Power BI assets consist of a complete 17-measure DAX library in [`dashboards/powerbi/dax_measures.txt`](dashboards/powerbi/dax_measures.txt) and a comprehensive 6-page visual wireframe specification guide in [`docs/DASHBOARD_GUIDE.md`](docs/DASHBOARD_GUIDE.md).

The platform models **28,500 commercial transactions** across **6 global markets** over a 36-month horizon (2023–2025), capturing **$1.245 Billion in simulated net sales** across 9 pharmaceutical therapies spanning Central Nervous System (CNS), Oncology, and Immunology.

| Metric | Empirical Value | Business Context & Definition |
| :--- | :--- | :--- |
| **Gross Invoiced Sales** | **$1,480,438,365.00** | Top-line customer orders evaluated at Wholesale Acquisition Cost (WAC). |
| **Customer Returns / Reversals** | **$2,772,950.45** | Reverse logistics refunds (batch expiration, shipping damage, cold-chain excursion). |
| **Contract Discounts & Rebates** | **$232,655,989.02** | Institutional contracting, PBM rebates, and statutory discounts (15.71% discount burden). |
| **Net Recognized Revenue** | **$1,245,009,425.53** | Simulated net sales realized (`Gross - Contract Discounts - Returns`). |
| **Gross-to-Net (GTN) Realization** | **84.10%** | Overall commercial portfolio net revenue capture rate. |
| **Cost of Goods Sold (COGS)** | **$219,723,424.00** | Direct API formulation, sterile manufacturing, and packaging costs. |
| **Gross Margin** | **$1,025,286,001.53 (82.35%)** | Product margin supporting commercial operations and R&D reinvestment. |
| **Net Volume Sold** | **4,898,450 Units** | Commercial units distributed across 120 key institutional healthcare accounts. |

---

## 2. Platform Architecture & Star Schema Design

The relational database is architected as a Kimball star schema (`fact_sales` surrounded by 7 dimension tables) implemented in SQLite with integer surrogate keys and indexing:

```
                              ┌──────────────┐
                              │   dim_date   │
                              └──────┬───────┘
                                     │ date_key
       ┌────────────────┐            │            ┌───────────────┐
       │  dim_product   ├────────────┼────────────┤ dim_geography │
       └──────┬─────────┘ product_key│geography_key└───────┬───────┘
              │                      │                     │
              │         ┌────────────┴───────────┐         │
              └─────────┤       fact_sales       ├─────────┘
                        │ (Grain: 1 Invoice Line)│
              ┌─────────┤       28,500 rows      ├─────────┐
              │         └────────────┬───────────┘         │
              │ customer_key         │distributor_key      │ sales_rep_key / channel_key
       ┌──────┴─────────┐     ┌──────┴──────────┐   ┌──────┴────────┐
       │  dim_customer  │     │ dim_distributor │   │ dim_sales_rep │
       └────────────────┘     └─────────────────┘   │  dim_channel  │
                                                    └───────────────┘
```

- **`fact_sales`**: 28,500 verified rows tracking unit quantities, WAC prices, contract discounts, gross sales, return values, net sales, cogs, gross margin, reconciliation status, and return reasons.
- **`dim_date`**: Calendar date dimension supporting MoM, YoY, and common-period time intelligence.
- **`dim_product`**: 9 brand assets across CNS, Oncology, and Immunology.
- **`dim_geography`**: 6 country markets with metadata on launch dates and active coverage months.
- **`dim_customer`**: 120 institutional accounts (Academic Medical Centers, IDNs, Retail Pharmacy Chains).
- **`dim_distributor`**: Wholesale logistics intermediaries (McKesson, AmerisourceBergen/Cencora, Cardinal, Alliance, Medipal, Direct Pharma).
- **`dim_sales_rep`**: 24 commercial field representatives across 4 specialized commercial teams (6 reps per team).
- **`dim_channel`**: 4 commercial routes to market (Hospital Direct Tender, Wholesale, Retail Chain, Specialty Mail Order).

---

## 3. Commercial Analytics Modules

### A. Product Portfolio ABC / Pareto Analysis
- **Class A Core Drivers (64.32% of revenue):** *AmphetaDex* ($293.0M), *OlanzRx* ($193.6M), *DexMethyl* ($161.4M), and *QuetiapMax* ($152.8M).
- **Class B Specialty Assets (26.35% of revenue):** *ImmunoPax* ($120.0M), *OncoShield* ($114.3M), and *EscitaloPro* ($93.9M).
- **Volume vs. Value Finding:** Oncology therapies (*ImmunoPax* and *OncoShield*) generate **$234.3M from 61,553 units** (~$3,806/unit), whereas mature CNS therapy *AlprazPlus* moves 821,837 units to yield $79.7M (~$97/unit).

### B. Geographic Performance & Common-Period Normalization
- **The Analytical Challenge:** Countries launched at different times (US/DE/UK: 36 months; FR: 30 months; JP: 24 months; CA: 18 months).
- **The Normalized Common-Period (FY2025):** When all markets operated for a full 12 months, **Japan ($63.12M) and France ($53.91M) generated higher annualized sales than the mature UK market ($51.20M)**, highlighting expansion market velocity.

### C. Institutional Customer RFM Segmentation & Clustering
- **Five Business RFM Tiers:** Accounts are segmented into 5 operational tiers based on composite RFM scores:
  - *Tier 1 Strategic Key Accounts (Champions, 37 accounts):* High frequency, high spend ($458.7M total net revenue). Dedicated Key Account Managers assigned.
  - *Tier 2 Loyal Growth Accounts (20 accounts):* Consistent recurring ordering patterns ($248.3M net sales).
  - *Tier 3 At-Risk High-Value Accounts (18 accounts):* High historical spend ($211.3M) with purchase recency gaps > 45 days, requiring targeted field retention campaigns.
  - *Tier 4 Promising Developing Accounts (12 accounts):* Moderate spend ($119.5M) showing recent ordering acceleration.
  - *Tier 5 Low-Engagement Accounts (33 accounts):* Low frequency, tail spend ($207.2M).
- **Four Unsupervised K-Means Clusters:** Separately, unsupervised K-Means clustering ($k=4$) on standardized log-transformed features (`recency`, `frequency`, `monetary`) groups institutional accounts by behavioral geometry, distinguishing high-frequency low-ticket purchasers from bulk tender purchasers.

### D. Headcount-Normalized Commercial Sales Productivity
- **Headcount Normalization:** Performance is normalized by sales representative headcount across 4 commercial teams of 6 reps each ($/rep). This is a commercial productivity metric, not an end-to-end Sales Force Effectiveness (SFE) model; it does not claim detailing-call activity, territory market potential, or quota attainment optimization.
- **Finding:** Team Alpha (CNS North) generated $322.00M (**$53.67M/rep**) and Team Gamma (Specialty Oncology) generated $318.82M (**$53.14M/rep**), with specialty oncology achieving comparable productivity from substantially higher average transaction values ($37,000+ vs ~$15,000 in CNS).

### E. Defensible Time-Series Revenue Forecasting

- **Strict Out-of-Sample Split:** Train on first 30 months (Jan 2023–Jun 2025), Test on final 6 months (Jul 2025–Dec 2025). Zero data leakage.
- **Model Benchmark (Fixed 6-Month Test Set: H2 2025):**
  - **Baseline Seasonal Naive (12-Month Lag):** **MAPE: 4.08% | MASE: 0.61 | RMSE: $2.13M** (achieves lowest test error)
  - **Holt-Winters Exponential Smoothing (Damped Additive Trend):** **MAPE: 11.55% | MASE: 1.89 | RMSE: $6.16M**
  - **SARIMAX(1,1,1):** **MAPE: 11.86% | MASE: 1.98 | RMSE: $6.85M**
  - **Baseline Naive Persistence:** **MAPE: 11.85% | MASE: 1.99 | RMSE: $7.11M**
  - **Baseline 6-Month Moving Average:** **MAPE: 11.92% | MASE: 2.02 | RMSE: $7.45M**

- **Symmetric Rolling-Origin Cross-Validation (6 Expanding Origins × 3-Month Horizons):**
  - **Baseline Seasonal Naive:** **Avg MAPE: 4.94% | Avg MASE: 0.75 | Avg RMSE: $2.32M**
  - **Baseline 6-Month Moving Average:** **Avg MAPE: 9.49% | Avg MASE: 1.63 | Avg RMSE: $4.83M**
  - **SARIMAX(1,1,1):** **Avg MAPE: 9.91% | Avg MASE: 1.70 | Avg RMSE: $5.00M**
  - **Holt-Winters Exponential Smoothing:** **Avg MAPE: 10.45% | Avg MASE: 1.76 | Avg RMSE: $5.02M**
  - **Baseline Naive Persistence:** **Avg MAPE: 10.45% | Avg MASE: 1.79 | Avg RMSE: $5.27M**

- **Model Evaluation & Trade-off Analysis:**
  - **Seasonal Naive Performance:** The seasonal naive benchmark achieves the lowest error on both the fixed test horizon (4.08% MAPE, 0.61 MASE) and in rolling-origin cross-validation (4.94% Avg MAPE, 0.75 Avg MASE). Because MASE is below 1.0, it demonstrates superior predictive accuracy over the in-sample naive persistence benchmark, driven by pronounced 12-month annual cyclicality in commercial orders.
  - **Statistical Extrapolation Models:** Holt-Winters (11.55% test MAPE) and SARIMAX (11.86% test MAPE) model underlying secular trends. While seasonal naive is empirically superior over a historical 12-month lookback, parameterized models like Holt-Winters and SARIMAX are necessary for multi-year scenario planning and long-term forward projections where historical lags cannot project growth shifts.

---

## 4. Repository Structure & Deliverables

The repository is structured into **static platform documentation**, **source code pipelines**, and **runtime generated analytical reports**:

```text
Pharmaceutical-Commercial-Analytics/
│
├── data/
│   ├── raw/
│   │   └── pharma_commercial_sales_raw.csv    # Synthetic data generated locally via src/generate_commercial_data.py (excluded from Git)
│   └── processed/
│       ├── cleaned_sales.csv                  # 28,500 cleansed, verified transactions (with preserved original values)
│       └── pharma_commercial.db               # SQLite database with Kimball Star Schema
│
├── sql/
│   ├── 01_data_quality.sql                    # Data quality, duplicates, and orphan checks
│   ├── 02_schema.sql                          # Star Schema DDL with PK/FK constraints and indexes
│   ├── 03_transformations.sql                 # ETL staging and surrogate key mapping
│   ├── 04_kpi_analysis.sql                    # Executive GTN, MoM, and YoY calculations
│   ├── 05_product_analysis.sql                # Product portfolio & cumulative Pareto analysis
│   ├── 06_customer_analysis.sql               # Customer RFM segmentation & distributor risk
│   ├── 07_geographic_analysis.sql             # Common-period normalization & geographic velocity
│   ├── 08_sales_force_analysis.sql            # Headcount-normalized productivity & team analytics
│   └── 09_channel_analysis.sql                # Commercial channel dynamics & discount depths
│
├── src/
│   ├── generate_commercial_data.py            # Reproducible commercial dataset generator (seed 42)
│   ├── data_validation.py                     # Financial validation, row-level ledger & status tagging
│   ├── data_preprocessing.py                  # Pipeline orchestrator & star schema database builder
│   ├── eda.py                                 # Statistical profiling and KPI extraction
│   ├── customer_segmentation.py               # RFM quartile scoring and K-Means clustering
│   ├── revenue_forecasting.py                 # Time-series forecasting, MASE & rolling-origin CV
│   └── visualizations.py                      # Presentation figures saved to outputs/figures/
│
├── dashboards/
│   └── powerbi/
│       └── dax_measures.txt                   # Complete DAX measures library (17 production measures)
│
├── outputs/                                   # RUNTIME GENERATED REPORTS & ARTIFACTS
│   ├── figures/                               # Presentation-grade analytical charts (PNG)
│   │   ├── forecast_actual_vs_predicted.png
│   │   ├── geographic_market_comparison.png
│   │   ├── monthly_revenue_trend.png
│   │   ├── product_pareto_curve.png
│   │   └── sales_force_productivity.png
│   ├── metrics/                               # KPI summaries and forecast evaluations (JSON)
│   │   ├── commercial_summary_metrics.json
│   │   └── forecast_model_evaluation.json
│   └── reports/                               # Tabular audit ledgers and projections (CSV)
│       ├── financial_reconciliation_ledger.csv# Row-level audit ledger (financial_reconciliation_status, data_quality_status, cogs_source_type, reconciliation_status)
│       ├── customer_rfm_segmentation.csv
│       ├── forecast_fy2026_projections.csv
│       ├── forecast_test_set_comparison.csv
│       └── rfm_segment_summary.csv
│
├── docs/                                      # STATIC PLATFORM DOCUMENTATION
│   ├── BUSINESS_INSIGHTS.md                   # Strategic insights and analytical findings
│   ├── DASHBOARD_GUIDE.md                     # 6-page Power BI wireframes & design specification
│   ├── DATA_DICTIONARY.md                     # Data dictionary mapping fact and dimensions
│   ├── DATA_QUALITY_REPORT.md                 # Ledger of records cleansed, tagged, and retained
│   ├── INDEPENDENT_AUDIT.md                   # Complete independent audit and verification report
│   ├── KNOWN_LIMITATIONS.md                   # Data limitations, modeling assumptions, and caveats
│   ├── METHODOLOGY.md                         # Mathematical formulations and analytical setup
│   ├── METRIC_VALIDATION.md                   # Claim-by-claim metric validation ledger
│   ├── PROJECT_AUDIT.md                       # Comprehensive transformation audit
│   └── RESUME_BULLETS.md                      # Quantified project metrics and achievements
│
├── tests/                                     # AUTOMATED TEST SUITES
│   ├── test_analytics.py                      # Core commercial analytics suite (8 tests)
│   ├── test_audit_validation.py               # Independent audit & edge-case suite (13 tests)
│   ├── test_data_validation_unit.py           # Unit validation, status separation, COGS & waterfall tests (19 tests)
│   ├── test_forecasting_hardening.py          # Forecasting robustness, missing months & fit failure tests (4 tests)
│   └── test_sql_etl_consistency.py            # SQL-only ETL vs Python ETL exact consistency test (1 test)
│
├── requirements.txt                           # Python dependencies
└── README.md                                  # Project overview documentation
```

---

## 5. Quickstart & Reproducibility

### 1. Environment Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the End-to-End Pipeline
```bash
# Generate raw commercial sales dataset with real-world edge cases (fixed seed 42)
python3 src/generate_commercial_data.py

# Clean, validate, and build the Star Schema database
python3 src/data_preprocessing.py

# Run commercial analytics, RFM segmentation, forecasting, and visualizations
python3 src/eda.py
python3 src/customer_segmentation.py
python3 src/revenue_forecasting.py
python3 src/visualizations.py
```

### 3. Run Automated Tests
```bash
python3 -m unittest discover tests -v
```
*Result: 45 tests run, 100% passed (zero duplicates, 0 orphaned keys, exact financial reconciliation, status separation, COGS fallback and return restocking, discount waterfall, SQL/Python ETL consistency, and out-of-sample forecast validation).*

---

## 6. Project Documentation & Deliverables

| Deliverable Category | Document / Report | Description |
| :--- | :--- | :--- |
| **Static Platform Documentation** | [docs/BUSINESS_INSIGHTS.md](docs/BUSINESS_INSIGHTS.md) | Strategic commercial insights and business recommendations. |
| **Static Platform Documentation** | [docs/DASHBOARD_GUIDE.md](docs/DASHBOARD_GUIDE.md) | 6-page Power BI dashboard design specification and visual wireframes (no binary `.pbix` bundled). |
| **Static Platform Documentation** | [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | Complete schema data dictionary mapping fact and dimensions. |
| **Static Platform Documentation** | [docs/METHODOLOGY.md](docs/METHODOLOGY.md) | Mathematical formulations (GTN accounting, Pareto math, and forecasting). |
| **Static Platform Documentation** | [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) | Known synthetic data nuances, assumptions, and analytical constraints. |
| **Static Platform Documentation** | [docs/METRIC_VALIDATION.md](docs/METRIC_VALIDATION.md) | Claim-by-claim verification proofs for all executive figures. |
| **Static Platform Documentation** | [docs/PROJECT_AUDIT.md](docs/PROJECT_AUDIT.md) | Project architecture blueprint and phased implementation checklist. |
| **Static Platform Documentation** | [docs/RESUME_BULLETS.md](docs/RESUME_BULLETS.md) | Quantified project achievements and technical keywords. |
| **Runtime Generated Reports** | [docs/DATA_QUALITY_REPORT.md](docs/DATA_QUALITY_REPORT.md) | Quality ledger with PASS, CORRECTED, FLAGGED, and REJECTED counts. |
| **Runtime Generated Reports** | [outputs/reports/financial_reconciliation_ledger.csv](outputs/reports/financial_reconciliation_ledger.csv) | Complete 28,525-row audit ledger with independent validation statuses. |
| **Runtime Generated Reports** | [outputs/metrics/forecast_model_evaluation.json](outputs/metrics/forecast_model_evaluation.json) | Fixed-split and rolling-origin evaluation metrics (MAE, RMSE, MAPE, MASE). |
| **Runtime Generated Reports** | [outputs/reports/forecast_fy2026_projections.csv](outputs/reports/forecast_fy2026_projections.csv) | 12-month forward revenue projections for FY2026. |
| **Runtime Generated Reports** | [outputs/figures/](outputs/figures/) | Presentation-grade analytical charts (PNG format, 300 DPI). |
