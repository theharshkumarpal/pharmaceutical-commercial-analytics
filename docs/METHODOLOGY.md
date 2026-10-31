# Pharmaceutical Commercial Analytics Methodology

**Target Role:** Life Sciences Commercial Analytics Associate / Strategy Consultant (Blue Matter Consulting)  
**Methodological Standard:** Industry-standard Gross-to-Net (GTN) Revenue Accounting, Kimball Star Schema Dimensional Modeling, and Defensible Forecasting.  

---

## 1. Data Ingestion & Quality Engineering

### 1.1 Ingestion & Idempotent Deduplication
- Raw transactions are ingested from ERP billing extracts (`data/raw/pharma_commercial_sales_raw.csv`).
- Deduplication is performed on `transaction_id`. Exactly 25 duplicate rows ($1.30M in duplicate gross sales) were identified and dropped during ingestion.
- Categorical attributes (country names, distributor names, product forms) are sanitized, stripping leading/trailing whitespace and enforcing standardized Title Case formatting.

### 1.2 Reverse Logistics & Return Mechanics
In enterprise pharmaceutical distribution, negative invoice quantities represent legitimate reverse logistics events (product recalls, near-expiry returns, cold-chain temperature excursions, and shipping damage).
- **Rule:** A record with `net_units < 0` is categorized as a commercial return.
- **Accounting Treatment:**
  - `gross_sales_usd = 0.00` (returns do not represent new invoiced sales).
  - `return_value_usd = ABS(net_units) * unit_net_price_usd` (positive financial deduction).
  - `net_sales_usd = -return_value_usd` (negative cash flow credit).
  - `cogs_usd = net_units * unit_cost` (negative inventory cost reversal).
  - `gross_margin_usd = net_sales_usd - cogs_usd` (exact margin preservation).

---

## 2. Dimensional Modeling & Star Schema

### 2.1 Fact Table Grain
The fact table `fact_sales` has a grain of **one row per commercial invoice line or credit return memo**.

### 2.2 Surrogate Key Strategy
Surrogate integer primary keys (`*_key`) are assigned across all dimension tables (`dim_date`, `dim_product`, `dim_geography`, `dim_customer`, `dim_distributor`, `dim_sales_rep`, `dim_channel`).
- Decouples analytical reporting from upstream ERP natural key churn.
- Optimizes join performance in SQLite and PostgreSQL.
- Foreign keys in `fact_sales` are strictly indexed.

---

## 3. Commercial Analytics Methodologies

### 3.1 Gross-to-Net (GTN) Waterfall Accounting
$$ \text{Gross Invoiced Sales} - \text{Return Deductions} - \text{Contract Discounts \& Rebates} = \text{Net Recognized Sales} $$
$$ \text{GTN Realization Rate (\%)} = \frac{\text{Net Recognized Sales}}{\text{Gross Invoiced Sales}} \times 100 $$

### 3.2 ABC / Pareto Portfolio Classification
Products are ranked descending by realized net sales. Cumulative percentage share is calculated using the SQL window function:
$$ \text{Cumulative Revenue \%} = \frac{\sum_{i=1}^{k} \text{Net Sales}_i}{\sum_{\text{all}} \text{Net Sales}} \times 100 $$
- **Class A:** Cumulative share $\le 80.0\%$ (Core portfolio drivers).
- **Class B:** Cumulative share between $80.1\%$ and $95.0\%$ (Secondary growth drivers).
- **Class C:** Cumulative share $> 95.0\%$ (Tail products / mature generics).

### 3.3 Geographic Common-Period Normalization
To prevent distortion from asynchronous market entry (US, DE, UK operating for 36 months vs Canada operating for 18 months):
- **All-Time Comparisons:** Documented with explicit active coverage month denominators.
- **Common-Period Benchmark (FY2025):** Evaluates all 6 markets across the identical 12-month calendar window (Jan 1, 2025 – Dec 31, 2025) when all country infrastructures were fully operational.

### 3.4 Institutional Customer RFM Segmentation
Evaluates 120 institutional healthcare accounts along three dimensions:
- **Recency ($R$):** Days elapsed between the account's last purchase and the end-of-study date (`2025-12-31`).
- **Frequency ($F$):** Total count of distinct purchasing transactions.
- **Monetary ($M$):** Total net recognized sales realized from the account.
Accounts are scored using quartile ranks ($1$ to $4$) and segmented into:
1. *Tier 1: Strategic Key Accounts (Champions)*
2. *Tier 2: Loyal Growth Accounts*
3. *Tier 3: At-Risk High-Value Accounts*
4. *Tier 4: Promising Developing Accounts*
5. *Tier 5: Low-Engagement Accounts*

---

## 4. Time-Series Revenue Forecasting

### 4.1 Temporal Validation Split
- **Total Series Length:** 36 monthly observations (2023-01 through 2025-12).
- **Training Set:** First 30 months (2023-01 through 2025-06).
- **Test Set (Out-of-Sample):** Final 6 months (2025-07 through 2025-12). Zero data leakage from the test set into model training.

### 4.2 Benchmark Model Suite
1. **Naive Persistence:** $\hat{Y}_{t+h} = Y_T$ (Baseline 1).
2. **Rolling 6-Month Moving Average:** $\hat{Y}_{t+h} = \frac{1}{6} \sum_{i=0}^5 Y_{T-i}$ (Baseline 2).
3. **SARIMAX(1,1,1):** Auto-regressive integrated moving average.
4. **Holt-Winters Exponential Smoothing:** Damped additive trend without seasonal component (`trend="add", damped_trend=True, seasonal=None`).

### 4.3 Evaluation Metrics & Test-Set Interpretation
- **Mean Absolute Error (MAE):** $\frac{1}{n} \sum |Y_t - \hat{Y}_t|$
- **Root Mean Squared Error (RMSE):** $\sqrt{\frac{1}{n} \sum (Y_t - \hat{Y}_t)^2}$
- **Mean Absolute Percentage Error (MAPE):** $\frac{100\%}{n} \sum \left| \frac{Y_t - \hat{Y}_t}{Y_t} \right|$

> **Important Analytical Note on Forecast Accuracy:** The reported **11.55% MAPE** represents an empirical backtest evaluation on a specific six-month out-of-sample test horizon (H2 2025). It is not an unconditional guarantee of future predictive accuracy, as real-world pharmaceutical demand is subject to regulatory interventions, patent expirations, loss of exclusivity (LOE), and payer formulary shifts.
