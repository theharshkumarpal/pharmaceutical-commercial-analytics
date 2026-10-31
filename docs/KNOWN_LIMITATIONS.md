# Known Limitations & Data Assumptions

**Auditor / Consultant:** Pharmaceutical Commercial Analytics Specialist  
**Domain Focus:** Life Sciences Commercial Analytics & Strategic Advisory  
**Date:** October 2026  

---

## 1. Data Provenance & Real-World Generalizability

### 1.1 Synthetic Generation vs. Audited Secondary Data
- **Limitation:** The commercial sales dataset (`data/raw/pharma_commercial_sales_raw.csv`) is **algorithmically generated** using Python (NumPy/Pandas with fixed seed `42`).
- **Consulting Distinction:** It simulates authentic transaction mechanics (pricing tiers, channel discounts, reverse logistics, and distributor flows), but is **not** real-world proprietary secondary data sourced from IQVIA (NPA, MIDAS, DDD) or Symphony Health (PHAST).
- **Analytical Framing:** This is an enterprise-grade synthetic commercial dataset created to model real-world pharmaceutical distribution challenges, rather than proprietary client audit data.

---

## 2. Commercial Analytics & Modeling Limitations

### 2.1 Time-Series Horizon for Forecasting
- **Limitation:** The dataset spans 36 monthly aggregations (2023–2025).
- **Impact:** While 36 months is sufficient for a 6-month out-of-sample backtest and classical statistical methods (Holt-Winters Exponential Smoothing, SARIMAX), it is insufficient for multi-year deep learning architectures (e.g., LSTMs, Transformers) which require hundreds of seasonal cycles to avoid overfitting.
- **Defensibility:** We deliberately restricted forecasting to interpretable exponential smoothing and autoregressive baselines, reporting an out-of-sample MAPE of 11.55%.

### 2.2 Customer & Account Level Behavioral Grain
- **Limitation:** The customer base consists of 120 institutional healthcare accounts (IDNs, Academic Medical Centers, Retail Chains).
- **Impact:** In commercial pharma, institutional purchasing behavior is governed by multi-year master service agreements (MSAs) and formulary tier placements. While our RFM segmentation accurately captures purchasing recency and order frequency, it does not include qualitative contracting negotiations, 340B ceiling price eligibility, or formulary exclusion lists.

### 2.3 Sales Force Territory Potential
- **Limitation:** The sales force effectiveness module normalizes performance by headcount (revenue per representative), but territory geographic land area and underlying disease prevalence per territory are not explicitly modeled in the raw transaction tables.
- **Consulting Caveat:** While revenue per rep provides a substantially better benchmark than raw team sales, full territory realignment in consulting practice also incorporates local patient epidemiology and physician detailing call-frequency metrics.

---

## 3. Technology & Dashboard Environment Constraints

### 3.1 Power BI Desktop Headless Environment
- **Limitation:** Power BI Desktop (`.pbix` authoring tool) requires a Windows desktop environment with a graphical user interface and is not natively executable in this headless macOS / Linux terminal environment.
- **Mitigation:** We implemented:
  1. A complete, production-ready DAX measures library in [dashboards/powerbi/dax_measures.txt](../dashboards/powerbi/dax_measures.txt).
  2. A comprehensive 6-page visual specification, wireframe layout, and slicer configuration guide in [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md).
  3. Matplotlib/Seaborn visualization scripts in [src/visualizations.py](../src/visualizations.py) generating presentation-grade static visual equivalents in `outputs/figures/`.
