# Metric Validation & Claim-by-Claim Verification Ledger

**Auditor:** Independent Senior Data Analytics Reviewer & Pharmaceutical Commercial Consultant  
**Audit Target:** All quantitative metrics and business findings presented across `README.md`, `BUSINESS_INSIGHTS.md`, and SQL queries.  
**Execution Environment:** Python 3.13 / SQLite 3.43 / Pandas 2.2  

---

## 1. Metric-by-Metric Verification Ledger

| Metric / Finding Claimed | Documented Claim | Independently Calculated Value | SQL / Python Methodology | Audit Verdict | Necessary Correction / Interpretation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Gross Invoiced Sales** | $1,480,438,365.00 | **$1,480,438,365.00** | `SUM(gross_sales_usd)` on `fact_sales` where `net_units > 0`. | **VERIFIED** | Exact cent match across database and CSV. |
| **Return Deductions** | $2,772,950.45 | **$2,772,950.45** | `SUM(return_value_usd)` on `fact_sales`. | **VERIFIED** | Exact match. 0.22% of total order volume. |
| **Contract Discounts & Rebates** | $232,655,989.02 | **$232,655,989.02** | Independently calculated as `Units Ordered × (WAC - Net Price)`. Reconciled: `Gross - Discounts - Returns = Net`. | **VERIFIED** | 15.71% weighted discount burden. |
| **Net Recognized Sales** | $1,245,009,425.53 | **$1,245,009,425.53** | `SUM(net_sales_usd)` on `fact_sales`. | **VERIFIED** | Exact cent match. |
| **Gross-to-Net Realization Rate** | 84.10% | **84.0973% (~84.10%)** | `Net Sales / Gross Sales * 100` | **VERIFIED** | Healthy realization rate. |
| **Cost of Goods Sold (COGS)** | $220,694,220.00 | **$219,723,424.00** | `SUM(cogs_usd)` on `fact_sales`. | **CORRECTED** | Retained from source dataset; inventory credit on returns credited correctly. |
| **Commercial Gross Margin** | $1,025,286,001.53 | **$1,025,286,001.53** | `Net Sales - COGS` | **VERIFIED** | 82.35% margin profile. Reconciles to the cent ($0.00 difference). |
| **ABC Class A Revenue Share** | 64.3% (Top 4 brands) | **64.32%** | Cumulative sum over ordered product revenue. | **VERIFIED** | Top 4 products (*AmphetaDex*, *OlanzRx*, *DexMethyl*, *QuetiapMax*) drive $800.75M. Top 6 products reach 83.13%. |
| **Top 3 Distributor Concentration** | 78.0% | **69.65%** | Share of net sales from top 3 intermediaries. | **CORRECTED** | Empirical share is 69.65% ($867.1M): *Direct Pharma* (35.01%), *AmerisourceBergen* (18.30%), *Alliance* (16.33%). |
| **Sales Force Productivity** | Team Gamma ($59.04M/rep) vs Team Alpha ($47.37M/rep) | Team Alpha ($53.67M/rep) & Team Gamma ($53.14M/rep) | Headcount-normalized `Team Sales / 6 reps`. Not a complete SFE model. | **CORRECTED** | Each team has exactly 6 reps. Productivity across all teams is balanced ($48.49M to $53.67M/rep). |
| **Geographic Common-Period FY2025** | Japan & France outperform UK in 2025 run-rate | **Japan ($63.12M) & France ($53.91M) > UK ($51.20M)** | `SUM(net_sales_usd)` where `dim_date.year = 2025`. | **VERIFIED** | Fully confirmed. Unequal window normalization is essential. |
| **Forecasting Model Benchmark** | Seasonal Naive 4.08% MAPE / Holt-Winters 11.55% | **Seasonal Naive: 4.08% MAPE (0.61 MASE); HW: 11.55%** | Fixed test set (H2 2025) & rolling-origin CV. | **VERIFIED** | Seasonal Naive achieves lowest error due to synthetic Q4 channel loading; HW parameterizes trends. |
| **Institutional Accounts Analyzed** | 120 Accounts | **120 Accounts** | `COUNT(DISTINCT customer_key)`. | **VERIFIED** | Segmented into 5 business RFM tiers and 4 K-Means clusters. |

---

## 2. Business Implications of the Corrected Findings

### 2.1 Distributor Concentration Adjustment (78.0% -> 69.65%)
While the previous narrative assumed US "Big Three" domination, the empirical global data incorporates European and Japanese direct logistics:
- *Direct Pharma Logistics* accounts for $435.9M (35.01%), servicing hospital direct tenders in Europe and Canada.
- *AmerisourceBergen (Cencora)* is second at $227.9M (18.30%).
- *Alliance Healthcare* is third at $203.3M (16.33%).
- **Strategic Impact:** The risk is not purely US wholesaler fee compression, but rather managing hybrid direct-to-hospital logistics contracts across international borders.

### 2.2 Sales Force Productivity Adjustment
- Each of the 4 commercial teams consists of exactly 6 field representatives (24 reps total).
- The normalized productivity is:
  1. **Team Alpha - CNS North:** $53.67M / rep (Total: $322.0M)
  2. **Team Gamma - Specialty / Oncology:** $53.14M / rep (Total: $318.8M)
  3. **Team Delta - Commercial Accounts:** $52.21M / rep (Total: $313.3M)
  4. **Team Beta - CNS South:** $48.49M / rep (Total: $290.9M)
- **Strategic Impact:** Headcount-normalized productivity is balanced across teams, but Team Gamma achieves its $53.14M/rep from higher-value specialty orders, achieving an average transaction value of ~$37,000 in specialty oncology vs ~$15,000 in CNS, rather than relying on high transactional order volume.
