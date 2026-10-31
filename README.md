# Pharmaceutical Commercial Performance & Market Analytics Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![SQL](https://img.shields.io/badge/SQL-Star_Schema-orange.svg)](https://sqlite.org/)
[![Power BI](https://img.shields.io/badge/Power_BI-DAX_Measures-yellow.svg)](https://powerbi.microsoft.com/)
[![Life Sciences](https://img.shields.io/badge/Domain-Pharmaceutical_Commercial_Strategy-teal.svg)](https://www.bluematterconsulting.com/)

An end-to-end commercial analytics platform built for **Pharmaceutical Commercial Performance, Gross-to-Net (GTN) Accounting, Market Access Normalization, Customer RFM Segmentation, Sales Force Effectiveness (SFE), and Time-Series Revenue Forecasting**.

Engineered for enterprise **Commercial Analytics, Life Sciences Advisory, and Global Brand Strategy**.

---

## 1. Executive Summary & Commercial KPIs

> **Data Disclosure & Synthetic Provenance:** The commercial sales dataset is **synthetic transaction-level data** generated via Python (`src/generate_commercial_data.py`, fixed seed `42`) to model multi-market launches, contract discounting, and reverse logistics. All figures are generated from modeled assumptions and do not represent actual pharmaceutical manufacturer revenue, verified market share, or proprietary secondary audit data (e.g., IQVIA MIDAS/NPA or Symphony Health PHAST).

The platform models **28,500 commercial transactions** across **6 global markets** over a 36-month horizon (2023–2025), capturing **$1.245 Billion in simulated net sales** across 9 pharmaceutical therapies spanning Central Nervous System (CNS), Oncology, and Immunology.

| Metric | Empirical Value | Business Context & Definition |
| :--- | :--- | :--- |
| **Gross Invoiced Sales** | **$1,480,438,365.00** | Top-line customer orders evaluated at Wholesale Acquisition Cost (WAC). |
| **Customer Returns / Reversals** | **$2,772,950.45** | Reverse logistics refunds (batch expiration, shipping damage, cold-chain excursion). |
| **Contract Discounts & Rebates** | **$232,655,989.02** | Institutional contracting, PBM rebates, and statutory discounts (15.71% discount burden). |
| **Net Recognized Revenue** | **$1,245,009,425.53** | Simulated net sales realized (`Gross - Returns - Discounts`). |
| **Gross-to-Net (GTN) Realization** | **84.10%** | Overall commercial portfolio net revenue capture rate. |
| **Cost of Goods Sold (COGS)** | **$219,723,424.00** | Direct API formulation, sterile manufacturing, and packaging costs. |
| **Gross Margin** | **$1,025,286,001.53 (82.35%)** | Product margin supporting commercial operations and R&D reinvestment. |
| **Net Volume Sold** | **4,898,450 Units** | Commercial units distributed across 120 key institutional healthcare accounts. |

---

## 2. Platform Architecture & Star Schema Design

The relational database is architected as a Kimball-style star schema (`fact_sales` surrounded by 7 dimension tables) implemented with integer surrogate keys and indexing:

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

- **`fact_sales`**: 28,500 verified rows tracking unit quantities, WAC prices, contract discounts, gross sales, return values, net sales, and return reasons.
- **`dim_date`**: Calendar date dimension supporting MoM, YoY, and common-period time intelligence.
- **`dim_product`**: 9 brand assets across CNS, Oncology, and Immunology.
- **`dim_geography`**: 6 country markets with metadata on launch dates and active coverage months.
- **`dim_customer`**: 120 institutional accounts (Academic Medical Centers, IDNs, Retail Pharmacy Chains).
- **`dim_distributor`**: Wholesale logistics intermediaries (McKesson, AmerisourceBergen/Cencora, Cardinal, Alliance, Medipal, Direct Pharma).
- **`dim_sales_rep`**: 24 field commercial representatives across 4 specialized commercial teams (6 reps per team).
- **`dim_channel`**: 4 commercial routes to market (Hospital Direct Tender, Wholesale, Retail Chain, Specialty Mail Order).

---

## 3. Advanced Commercial Analytics Modules

### A. Product Portfolio ABC / Pareto Analysis
- **Class A Core Drivers (64.32% of revenue):** *AmphetaDex* ($293.0M), *OlanzRx* ($193.6M), *DexMethyl* ($161.4M), and *QuetiapMax* ($152.8M).
- **Class B Specialty Assets (26.35% of revenue):** *ImmunoPax* ($120.0M), *OncoShield* ($114.3M), and *EscitaloPro* ($93.9M).
- **Volume vs. Value Finding:** Oncology therapies (*ImmunoPax* and *OncoShield*) generate **$234.3M from 61,553 units** (~$3,806/unit), whereas mature CNS therapy *AlprazPlus* moves 821,837 units to yield $79.7M (~$97/unit).

### B. Geographic Performance & Common-Period Normalization
- **The Analytical Challenge:** Countries launched at different times (US/DE/UK: 36 months; FR: 30 months; JP: 24 months; CA: 18 months).
- **The Normalized Common-Period (FY2025):** When all markets operated for a full 12 months, **Japan ($63.12M) and France ($53.91M) generated higher annualized sales than the mature UK market ($51.20M)**, highlighting expansion market velocity.

### C. Institutional Customer RFM Segmentation
- **Tier 1 Strategic Key Accounts (Champions, 37 accounts):** High frequency, high spend ($458.7M total net revenue). Dedicated Key Account Managers assigned.
- **Tier 3 At-Risk High-Value Accounts (18 accounts):** High historical spend ($211.3M) with purchase recency gaps > 45 days, requiring targeted field retention campaigns.

### D. Sales Force Effectiveness (SFE)
- **Headcount Normalization:** Normalized team performance by representative count across 4 teams of 6 reps each.
- **Finding:** Team Alpha (CNS North) generated $322.00M (**$53.67M/rep**) and Team Gamma (Specialty Oncology) generated $318.82M (**$53.14M/rep**), with specialty oncology achieving comparable productivity from substantially higher average transaction values ($37,000+ vs ~$15,000 in CNS).

### E. Defensible Time-Series Revenue Forecasting
- **Strict Out-of-Sample Split:** Train on first 30 months (Jan 2023–Jun 2025), Test on final 6 months (Jul 2025–Dec 2025). Zero data leakage.
- **Model Benchmark (6-Month Test Set):**
  - *Baseline Seasonal Naive (12-Month Lag):* **MAPE 4.08% | RMSE $2.13M** (captures annual cyclicality)
  - *Champion Classical Model: Holt-Winters Exponential Smoothing (Damped Additive Trend):* **MAPE 11.55% | RMSE $6.16M**
  - *SARIMAX(1,1,1):* MAPE 11.86% | RMSE $6.85M
  - *Baseline Naive Persistence:* MAPE 11.85% | RMSE $7.11M
  - *Baseline 6-Month Moving Average:* MAPE 11.92% | RMSE $7.45M
- **Rolling-Origin Cross-Validation (6 Expanding Origins):**
  - *SARIMAX (Rolling CV):* **MAPE 9.91% | RMSE $5.00M**
  - *Holt-Winters (Rolling CV):* **MAPE 10.45% | RMSE $5.02M**
- **Evaluation & Model Selection:** The Holt-Winters model utilizes a damped additive trend with no seasonal component (`trend="add"`, `damped_trend=True`, `seasonal=None`). The seasonal naive benchmark demonstrates strong annual cyclicality, while rolling-origin CV confirms that both SARIMAX (9.91%) and Holt-Winters (10.45%) maintain robust generalization error across multiple forecast horizons without overfitting.

---

## 4. Repository Structure

```text
Pharmaceutical-Commercial-Analytics/
│
├── data/
│   ├── raw/
│   │   └── pharma_commercial_sales_raw.csv    # Synthetic data generated locally via src/generate_commercial_data.py (excluded from Git)
│   └── processed/
│       ├── cleaned_sales.csv                  # 28,500 cleansed, verified transactions
│       └── pharma_commercial.db               # SQLite database with Star Schema
│
├── sql/
│   ├── 01_data_quality.sql                    # Data quality, duplicates, and orphan checks
│   ├── 02_schema.sql                          # Star Schema DDL with PK/FK constraints and indexes
│   ├── 03_transformations.sql                 # ETL staging and surrogate key mapping
│   ├── 04_kpi_analysis.sql                    # Executive GTN, MoM, and YoY calculations
│   ├── 05_product_analysis.sql                # Product portfolio & cumulative Pareto analysis
│   ├── 06_customer_analysis.sql               # Customer RFM segmentation & distributor risk
│   ├── 07_geographic_analysis.sql             # Common-period normalization & geographic velocity
│   ├── 08_sales_force_analysis.sql            # Headcount-normalized SFE & team productivity
│   └── 09_channel_analysis.sql                # Commercial channel dynamics & discount depths
│
├── src/
│   ├── generate_commercial_data.py            # Reproducible commercial dataset generator (seed 42)
│   ├── data_validation.py                     # Statistical validation & return integrity
│   ├── data_preprocessing.py                  # Pipeline orchestrator & star schema builder
│   ├── eda.py                                 # Statistical profiling and KPI extraction
│   ├── customer_segmentation.py               # RFM quartile scoring and K-Means clustering
│   ├── revenue_forecasting.py                 # Out-of-sample forecasting (Holt-Winters / SARIMAX / Baselines)
│   └── visualizations.py                      # Consulting-style presentation figures
│
├── dashboards/
│   └── powerbi/
│       └── dax_measures.txt                   # Complete DAX measures library (17 core measures)
│
├── outputs/
│   ├── figures/                               # Presentation-grade analytical charts (PNG)
│   │   ├── forecast_actual_vs_predicted.png
│   │   ├── geographic_market_comparison.png
│   │   ├── monthly_revenue_trend.png
│   │   ├── product_pareto_curve.png
│   │   └── sales_force_productivity.png
│   ├── metrics/                               # KPI summaries and forecast evaluations (JSON)
│   │   ├── commercial_summary_metrics.json
│   │   └── forecast_model_evaluation.json
│   └── reports/                               # Customer RFM tables and forecast projections (CSV)
│       ├── customer_rfm_segmentation.csv
│       ├── forecast_fy2026_projections.csv
│       ├── forecast_test_set_comparison.csv
│       └── rfm_segment_summary.csv
│
├── docs/
│   ├── BUSINESS_INSIGHTS.md                   # Strategic consulting insights and recommendations
│   ├── DASHBOARD_GUIDE.md                     # 6-page Power BI wireframes & design specification
│   ├── DATA_DICTIONARY.md                     # Data dictionary mapping fact and dimensions
│   ├── DATA_QUALITY_REPORT.md                 # Ledger of records cleansed, tagged, and retained
│   ├── INDEPENDENT_AUDIT.md                   # Complete independent audit and verification report
│   ├── KNOWN_LIMITATIONS.md                   # Known data limitations, assumptions, and caveats
│   ├── METHODOLOGY.md                         # Mathematical formulations and analytical setup
│   ├── METRIC_VALIDATION.md                   # Claim-by-claim metric validation ledger
│   ├── PROJECT_AUDIT.md                       # Comprehensive transformation audit
│   └── RESUME_BULLETS.md                      # Quantified, verified project impacts
│
├── tests/
│   ├── test_analytics.py                      # Core commercial analytics suite (8 tests)
│   └── test_audit_validation.py               # Independent audit & edge-case suite (13 tests)
│
├── requirements.txt                           # Python dependencies
└── README.md                                  # Project overview documentation
```

> **Power BI Status Note:** The repository provides a designed six-page Power BI executive dashboard specification and layout wireframes in [docs/DASHBOARD_GUIDE.md](docs/DASHBOARD_GUIDE.md), supported by 17 DAX measures in [dashboards/powerbi/dax_measures.txt](dashboards/powerbi/dax_measures.txt). No binary `.pbix` file is bundled.

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
*Result: 21 tests run, 100% passed (zero duplicates, 0 orphaned keys, exact financial reconciliation, data integrity, edge-case bounds, and out-of-sample forecast validation).*

---

## 6. Project Documentation & Deliverables

For executive stakeholders and analytical deep-dives:
- **Consulting Insights & Recommendations:** Review [Business Insights & Strategic Recommendations](docs/BUSINESS_INSIGHTS.md) for data-driven strategic actions.
- **Quantified Portfolio Impact:** Review [Quantified Impact & Deliverables](docs/RESUME_BULLETS.md) for concise, metric-driven achievements.
- **Methodology & Mathematical Formulas:** Review [Commercial Analytics Methodology](docs/METHODOLOGY.md) for GTN accounting, Pareto math, and forecasting setup.
- **Metric-by-Metric Verification Ledger:** Review [Metric Validation](docs/METRIC_VALIDATION.md) for claim-by-claim verification proofs.
- **Independent Audit Report:** Review [Independent Audit Report](docs/INDEPENDENT_AUDIT.md) for comprehensive verification results.
- **Known Limitations & Caveats:** Review [Known Limitations](docs/KNOWN_LIMITATIONS.md) for synthetic data nuances and modeling assumptions.
