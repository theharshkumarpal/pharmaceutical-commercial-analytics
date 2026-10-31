# Pharmaceutical Commercial Business Insights & Strategic Recommendations

**Target Audience:** Commercial Leadership, VP of Market Access, Franchise Brand Leads, Commercial Analytics Teams
**Analytical Basis:** Executed SQL & Python analytics on 28,500 commercial transactions ($1.245 Billion Net Recognized Sales)
**Date:** October 2026 (Audited & Verified)

---

## Executive Scorecard

| Commercial Metric | Observed Value | Strategic Interpretation |
| :--- | :--- | :--- |
| **Gross Invoiced Sales** | **$1,480,438,365.00** | Top-line aggregate portfolio demand across 6 target markets. |
| **Reverse Logistics Returns** | **$2,772,950.45** | 0.22% portfolio return rate (well controlled within pharma industry standard < 1.5%). |
| **Contract Discounts & Rebates** | **$232,655,989.02** | 15.71% weighted gross-to-net discount burden across institutional contracts. |
| **Net Recognized Revenue** | **$1,245,009,425.53** | Simulated net sales realized (`Gross - Returns - Discounts`). |
| **Gross-to-Net (GTN) Realization** | **84.10%** | Healthy net realization; hospital tender shows deepest statutory discounting (22.1%). |
| **Cost of Goods Sold (COGS)** | **$219,723,424.00** | Direct API formulation, sterile manufacturing, and packaging costs. |
| **Commercial Gross Margin** | **$1,025,286,001.53 (82.35%)** | Strong margin profile typical of high-value CNS and specialty oncology assets. |
| **Total Net Volume** | **4,898,450 Units** | Distributed across 120 key institutional healthcare accounts. |

---

## Module 1: Product Portfolio ABC / Pareto Strategy

### 1. Business Question
*Which brands represent the core value drivers of the business, and are there brand concentration risks or "volume-heavy, margin-light" distortions?*

### 2. Analytical Methodology
Executed SQL cumulative contribution analysis (`sql/05_product_analysis.sql`) sorting all 9 commercial products by net sales, calculating cumulative revenue percentages, and segmenting into Pareto Class A (first 80%), Class B (next 15%), and Class C (tail 5%).

### 3. Empirical Results
- **Class A Brands (Core Value Drivers, Top 4 Brands generate 64.32% | Top 6 Brands reach 83.13%):**
  1. **AmphetaDex (CNS):** $292.97M (23.53% share | 1,220,557 units sold)
  2. **OlanzRx (CNS):** $193.59M (15.55% share | 546,823 units sold)
  3. **DexMethyl (CNS):** $161.38M (12.96% share | 982,845 units sold)
  4. **QuetiapMax (CNS):** $152.81M (12.27% share | 476,308 units sold)
  *Subtotal Top 4 (Class A Core): $800.75M (64.32% of portfolio revenue)*
- **Class B Brands (Specialty High-Value & Mature Drivers, 26.35% of revenue):**
  5. **ImmunoPax (Oncology mAb):** $119.98M (9.64% share | 26,286 units sold)
  6. **OncoShield (Oncology):** $114.29M (9.18% share | 35,267 units sold)
  7. **EscitaloPro (CNS):** $93.86M (7.54% share | 768,383 units sold)
- **Class C Brands (Mature / Secondary Tail, 9.33% of revenue):**
  8. **AlprazPlus (CNS):** $79.68M (6.40% share | 821,837 units sold)
  9. **RheumaCure (Immunology Biosimilar):** $36.45M (2.93% share | 20,144 units sold)

### 4. Interpretation & Strategic Implications
- **High-Volume vs High-Value Divergence:** *ImmunoPax* and *OncoShield* generate $234.3M in net revenue from 61,553 units combined (~$3,806 USD net price/unit), whereas *AlprazPlus* moves 821,837 units to yield only $79.7M (~$97 USD net price/unit).
- **Consulting Recommendation:** Commercial leadership must rebalance field focus away from low-margin mature CNS volume (*AlprazPlus*) where transaction values are low, shifting commercial resources toward institutional formulary access for specialty oncology assets.

---

## Module 2: Geographic Market Access & Common-Period Normalization

### 1. Business Question
*What are the true market growth dynamics across global territories, and how does unequal market launch timing distort market-level resource allocation?*

### 2. Analytical Methodology
Evaluated all-time net revenue versus normalized **FY2025 Common-Period Revenue** where all 6 countries had full 12-month commercial operations (`sql/07_geographic_analysis.sql`).

### 3. Empirical Results
- **All-Time Revenue (Distorted by 36m vs 18m coverage):**
  - United States (36m): $551.60M (44.31%)
  - Germany (36m): $200.19M (16.08%)
  - United Kingdom (36m): $157.02M (12.61%)
  - France (30m): $137.38M (11.03%)
  - Japan (24m): $122.72M (9.86%)
  - Canada (18m): $76.10M (6.11%)
- **Normalized FY2025 Common-Period Benchmark (All 6 Markets Active):**
  - United States: $181.45M (39.2%)
  - Germany: $65.42M (14.1%)
  - **Japan: $63.12M (13.6%) — Outperformed the UK!**
  - **France: $53.91M (11.6%) — Outperformed the UK!**
  - United Kingdom: $51.20M (11.1%)
  - Canada: $47.22M (10.2%) — *Generated 62% of its all-time revenue in 2025 alone!*

### 4. Strategic Implications & Pitfall Avoidance
- **The Analytical Trap:** Reviewing all-time cumulative sales makes Canada look like a minor 6.1% territory and Japan smaller than the UK.
- **The Consulting Reality:** In FY2025, Japan and France generated higher annualized revenues ($63.12M and $53.91M respectively) than the mature UK market ($51.20M).
- **Recommendation:** Rebalance European commercial headcount to bolster French hospital detailing and deepen distribution agreements with Medipal Holdings in Japan.

---

## Module 3: Customer RFM Segmentation & Distributor Concentration

### 1. Business Question
*Are revenues overly vulnerable to wholesale distributor consolidation, and which institutional accounts warrant dedicated Key Account Managers (KAMs)?*

### 2. Analytical Methodology
Aggregated distributor volume concentration (`sql/06_customer_analysis.sql`) and performed statistical RFM segmentation classifying 120 key institutional accounts into 5 tiers.

### 3. Empirical Results
- **Distributor Concentration:**
  - **Top 3 Intermediaries:** Direct Pharma Logistics ($435.9M, 35.01%), AmerisourceBergen/Cencora ($227.9M, 18.30%), Alliance Healthcare ($203.3M, 16.33%).
  - **Top 3 Wholesaler Share:** **69.65% of total commercial volume** routes through the top 3 logistics partners ($867.1M).
- **Customer Segmentation Breakdown (120 Accounts):**
  - **Tier 1 Strategic Key Accounts (Champions):** 37 Accounts (30.8%) | High frequency, high spend. Dedicated Key Account Managers assigned.
  - **Tier 2 Loyal Growth Accounts:** 20 Accounts (16.7%) | Steady re-order velocity.
  - **Tier 3 At-Risk High-Value Accounts:** 18 Accounts (15.0%) | High historical spend, but recency gap > 45 days.
  - **Tier 4 Developing Accounts:** 12 Accounts (10.0%) | Emerging community clinics.
  - **Tier 5 Low-Engagement Accounts:** 33 Accounts (27.5%) | Serviced via digital channels.

### 4. Strategic Recommendations
- **Wholesale Mitigation:** Establish direct distribution agreements with major integrated delivery networks (IDNs) for specialty biologics to reduce margin erosion.
- **KAM Retention Program:** Deploy field medical science liaisons (MSLs) and commercial KAMs specifically to the 18 **Tier 3 At-Risk Accounts** to investigate whether order delays stem from formulary switching or local supply chain bottlenecks.

---

## Module 4: Headcount-Normalized Commercial Team Productivity

### 1. Business Question
*Are the sales teams genuinely differentiated in productivity, or does revenue simply follow territory headcount?*

### 2. Analytical Methodology
Evaluated raw team sales vs **Headcount-Normalized Revenue per Representative** across 24 reps organized into 4 teams of 6 reps each (`sql/08_sales_force_analysis.sql`).

### 3. Empirical Results
- **Team Alpha - CNS North (6 Reps):** Total Sales: $322.00M | **Productivity: $53.67M / Rep**
- **Team Gamma - Specialty / Oncology (6 Reps):** Total Sales: $318.82M | **Productivity: $53.14M / Rep**
- **Team Delta - Commercial Accounts (6 Reps):** Total Sales: $313.27M | **Productivity: $52.21M / Rep**
- **Team Beta - CNS South (6 Reps):** Total Sales: $290.92M | **Productivity: $48.49M / Rep**

### 4. Strategic Implications
- While Team Alpha leads slightly in total net sales ($322.00M vs $318.82M), Team Gamma achieves comparable productivity ($53.14M/rep) from fewer, higher-value transactions (average transaction value of ~$37,000 in specialty oncology vs ~$15,000 in CNS).
- **Recommendation:** Rather than focusing purely on transaction volume, commercial strategy should recognize the higher revenue-per-transaction realization in specialty oncology and structure sales incentives accordingly.
