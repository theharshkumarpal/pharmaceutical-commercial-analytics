# Pharmaceutical Commercial Analytics Methodology

**Domain Focus:** Life Sciences Commercial Analytics & Strategic Advisory  
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

### 3.4 Institutional Customer Segmentation: Business RFM Tiers vs. K-Means Clusters
The platform implements two complementary customer segmentation methodologies:
1. **Five Business RFM Tiers (Rule-Based Scored Quartiles):**
   - *Tier 1: Strategic Key Accounts (Champions, 37 accounts):* Top-quartile frequency and spend; core relationship partners.
   - *Tier 2: Loyal Growth Accounts (20 accounts):* Consistent ordering cadence with expanding volume.
   - *Tier 3: At-Risk High-Value Accounts (18 accounts):* High historical monetary spend with recency gaps > 45 days.
   - *Tier 4: Promising Developing Accounts (12 accounts):* Recent purchasers with moderate transaction volume.
   - *Tier 5: Low-Engagement Accounts (33 accounts):* Low frequency, low volume purchasing accounts.
2. **Four Unsupervised K-Means Clusters (`src/customer_segmentation.py`):**
   - Accounts are log-transformed (`log1p`) and standardized using `StandardScaler` on Recency, Frequency, and Monetary features before K-Means clustering ($k=4$).
   - K-Means clusters identify empirical behavioral archetypes: High-Volume Institutional Champions, Mid-Tier Regional Hospitals, Specialized Infusion Clinics, and Infrequent Long-Tail Facilities.

### 3.5 Sales Team Headcount-Normalized Productivity
- **Methodology:** Total recognized net sales per commercial team is normalized by active sales representative headcount:
  $$ \text{Productivity per Representative} = \frac{\sum \text{Team Net Sales}}{\text{Team Active Headcount}} $$
- **Scope & Modeling Boundary:** This metric provides headcount-normalized commercial productivity across the 4 specialized business teams (6 reps per team). It is an exploratory productivity benchmark, **not** a complete Sales Force Effectiveness (SFE) model; it does not model physician detailing call frequency, local disease epidemiology, territory market access potential, or quota attainment.

---

## 4. Time-Series Revenue Forecasting

### 4.1 Temporal Validation Split & Series Integrity
- **Total Series Length:** 36 continuous monthly observations (2023-01 through 2025-12).
- **Monthly Continuity Check:** Validates that no calendar months are omitted between start and end dates.
- **Fixed Training Set:** First 30 months (2023-01 through 2025-06).
- **Fixed Test Set (Out-of-Sample):** Final 6 months (2025-07 through 2025-12). Zero future data leakage into model training or feature preparation.

### 4.2 Benchmark & Statistical Model Suite
1. **Seasonal Naive Benchmark (12-Month Lag):** $\hat{Y}_{t+h} = Y_{t+h-12}$ (Baseline 1).
2. **Holt-Winters Exponential Smoothing:** Damped additive trend without seasonal component (`trend="add", damped_trend=True, seasonal=None`).
3. **SARIMAX(1,1,1):** Auto-regressive integrated moving average with exogenous parameterization.
4. **Rolling 6-Month Moving Average:** $\hat{Y}_{t+h} = \frac{1}{6} \sum_{i=0}^5 Y_{T-i}$ (Baseline 2).
5. **Naive Persistence:** $\hat{Y}_{t+h} = Y_T$ (Baseline 3).

### 4.3 Evaluation Metrics & MASE Formulation
- **Mean Absolute Error (MAE):** $\frac{1}{n} \sum |Y_t - \hat{Y}_t|$
- **Root Mean Squared Error (RMSE):** $\sqrt{\frac{1}{n} \sum (Y_t - \hat{Y}_t)^2}$
- **Mean Absolute Percentage Error (MAPE):** $\frac{100\%}{n} \sum \left| \frac{Y_t - \hat{Y}_t}{Y_t} \right|$
- **Mean Absolute Scaled Error (MASE, Hyndman & Koehler, 2006):**
  $$ \text{MASE} = \frac{\text{MAE}_{\text{test}}}{\frac{1}{T-1} \sum_{t=2}^{T} |Y_t - Y_{t-1}|} $$
  The scaling denominator is computed **strictly in-sample on the training series**, measuring whether the evaluated model outperforms a one-step naive forecast on the training data ($\text{MASE} < 1.0$ indicates superior performance).

### 4.4 Symmetric Rolling-Origin Cross-Validation
To verify performance stability across multiple economic regimes:
- **Design:** Evaluates all 5 models over 6 expanding historical origins ($N=6$) with an identical 3-month forecast horizon ($H=3$).
- **Fit Failure Tracking:** Explicitly records `fit_success_count` and `fit_failure_count` per candidate; convergence warnings or fit errors are logged rather than silently replaced.

### 4.5 Qualified Model Evaluation & Synthetic Seasonality Finding
- **Empirical Results:** On this dataset, **Baseline Seasonal Naive achieves the lowest error** on both the fixed test horizon (**4.08% MAPE | 0.61 MASE | RMSE $2.13M**) and in rolling-origin cross-validation (**4.94% Avg MAPE | 0.75 Avg MASE | Avg RMSE $2.32M**).
- **Synthetic Data Nuance:** The data generator deliberately introduces a Q4 commercial purchasing surge (15%–35% volume increase simulating year-end hospital/wholesaler channel loading). Because the synthetic dataset exhibits strong 12-month periodicity, Seasonal Naive empirically outperforms trend-extrapolation models over a 12-month historical lookback.
- **Role of Statistical Models:** While Seasonal Naive is empirically superior for 12-month lookbacks, parameterized models (Holt-Winters at 11.55% test MAPE and SARIMAX at 11.86% test MAPE) remain essential for forward projections beyond historical data where lag lookups cannot project secular growth or patent transitions.
