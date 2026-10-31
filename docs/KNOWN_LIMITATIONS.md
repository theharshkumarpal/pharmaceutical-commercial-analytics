# Known Limitations & Data Assumptions

**Auditor / Consultant:** Pharmaceutical Commercial Analytics Specialist
**Domain Focus:** Life Sciences Commercial Analytics & Strategic Advisory
**Date:** October 2026

---

## 1. Data Provenance & Real-World Generalizability

### 1.1 Synthetic Generation vs. Audited Secondary Data
- **Limitation:** The commercial sales dataset (`data/raw/pharma_commercial_sales_raw.csv`) is **algorithmically generated** using Python (NumPy/Pandas with fixed seed `42`).
- **Consulting Distinction:** It simulates authentic transaction mechanics (pricing tiers, channel discounts, reverse logistics, and distributor flows), but is **not** real-world proprietary secondary data sourced from IQVIA (NPA, MIDAS, DDD) or Symphony Health (PHAST).
- **Analytical Framing:** This is a modeled synthetic commercial dataset created to reflect pharmaceutical distribution dynamics, rather than proprietary client audit data.

---

## 2. Commercial Analytics & Modeling Limitations

### 2.1 Time-Series Horizon for Forecasting
- **Limitation:** The dataset spans 36 monthly aggregations (2023–2025).
- **Impact:** While 36 months is sufficient for a 6-month out-of-sample backtest and statistical time-series methods, it is insufficient for multi-year deep learning architectures which require hundreds of seasonal cycles to avoid overfitting.
- **Defensibility:** We evaluated multiple classical baselines and statistical models. A 12-month seasonal naive benchmark achieved the lowest error (4.08% MAPE, 0.61 MASE) due to recurring annual purchasing cycles, while Holt-Winters (11.55% MAPE) and SARIMAX (11.86% MAPE) provide trend parameterization for forward projections.

### 2.2 Customer & Account Level Behavioral Grain
- **Limitation:** The customer base consists of 120 institutional healthcare accounts (IDNs, Academic Medical Centers, Retail Chains).
- **Impact:** In commercial pharma, institutional purchasing behavior is governed by multi-year master service agreements (MSAs) and formulary tier placements. While our RFM segmentation accurately captures purchasing recency and order frequency, it does not include qualitative contracting negotiations, 340B ceiling price eligibility, or formulary exclusion lists.

### 2.3 Sales Force Productivity Normalization
- **Limitation:** The commercial team productivity module normalizes performance by headcount (revenue per representative), but territory geographic land area and underlying disease prevalence per territory are not explicitly modeled in the raw transaction tables.
- **Consulting Caveat:** While revenue per rep provides a substantially better benchmark than raw team sales, territory realignment in advisory practice also incorporates local patient epidemiology and physician detailing call-frequency metrics.

### 2.4 Cost of Goods Sold (COGS) & Gross Margin Accounting
- **Preservation from Source Data:** In the validation and preprocessing pipeline (`src/data_validation.py`), Cost of Goods Sold (`cogs_usd`) is **retained directly from the source dataset** (`cogs_usd_original`) rather than independently reconstructed for each individual transaction. In real-world enterprise architectures, product-level standard unit manufacturing costs reside in separate enterprise resource planning (ERP) master cost tables; the transactional sales feed does not include real-time manufacturing bill-of-materials lookups.
- **15% WAC Fallback Assumption:** If `cogs_usd` is absent or completely unpopulated in an ingested dataset, the validation module applies an industry-standard heuristic fallback:
  $$\text{expected\_cogs} = \text{units\_ordered} \times \text{unit\_wac\_price\_usd} \times 0.15$$
  This 15% proxy reflects typical pharmaceutical manufacturing, packaging, and supply-chain cost ratios (10%–20% of list price) for branded specialty therapies. Gross margin is then verified as $\text{expected\_margin} = \text{expected\_net} - \text{expected\_cogs}$.

### 2.5 Synthetic-Data Accounting Assumptions for Reverse Logistics
- **Return-Credit Valuation at Net Contract Price:** In the synthetic dataset generator (`src/generate_commercial_data.py`), customer return records represent discrete reverse logistics credit memos issued at the customer channel's **contract net price** ($\text{unit\_net\_price\_usd} = \text{WAC} \times (1 - \text{discount})$) rather than list WAC. In commercial practice, credit memos reflect the net price invoiced on the originating order. In this synthetic dataset, returns are generated with channel-specific contract discount rates rather than dynamically joining against historical parent invoice IDs.
- **Inventory Restocking & COGS Reversal Assumption:** When a return transaction occurs ($\text{net\_units} < 0$), COGS is credited back ($\text{cogs\_usd} = \text{net\_units} \times \text{base\_cost} < 0$), reducing total COGS and increasing gross margin. This embodies the operational assumption that returned units (e.g. overstock or undamaged returns) are restocked into available inventory or credited by the supply chain, rather than written off as a 100% destruction/disposal expense.

---

## 3. Technology & Dashboard Environment Constraints

### 3.1 Power BI Desktop Headless Environment & File Deliverables
- **Limitation & Disclosure:** **No binary Power BI (`.pbix`) file is included in this repository.** Authoring binary `.pbix` files requires a Windows desktop environment with a graphical user interface and is not natively executable in this headless macOS / Linux terminal environment.
- **Delivered Assets:**
  1. A complete DAX measures library in [dashboards/powerbi/dax_measures.txt](../dashboards/powerbi/dax_measures.txt) (17 production measures).
  2. A comprehensive 6-page visual specification, wireframe layout, and slicer configuration guide in [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md).
  3. Matplotlib/Seaborn visualization scripts in [src/visualizations.py](../src/visualizations.py) generating presentation-grade static visual equivalents in `outputs/figures/`.
