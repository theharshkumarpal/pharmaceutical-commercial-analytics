# Power BI Commercial Dashboard Architecture & Implementation Guide

**Dashboard Suite:** Global Pharmaceutical Commercial Performance & Market Analytics
**Implementation Status:** DAX Measures Library (`dashboards/powerbi/dax_measures.txt`) and 6-Page Executive Wireframe Specification.
**Deliverables Notice:** **No binary Power BI (`.pbix`) file is included in this repository.** This guide provides the complete blueprint and measures for loading the Star Schema into Power BI Desktop.
**Target User Persona:** VP of Commercial Strategy, Franchise Brand Leads, Commercial Operations Analysts
**Layout Standard:** 16:9 widescreen (1920 × 1080 px), Slate Navy & Life Sciences Teal consulting palette.
**Data Source:** Star Schema connection to `data/processed/pharma_commercial.db` or PostgreSQL data warehouse.

---

## 1. Dimensional Model Setup in Power BI

Establish 1-to-Many (`1:*`), Single-Direction relationships from Dimension tables to `fact_sales`:
- `dim_date[date_key]` (1) ───< `fact_sales[date_key]` (*)
- `dim_product[product_key]` (1) ───< `fact_sales[product_key]` (*)
- `dim_geography[geography_key]` (1) ───< `fact_sales[geography_key]` (*)
- `dim_customer[customer_key]` (1) ───< `fact_sales[customer_key]` (*)
- `dim_distributor[distributor_key]` (1) ───< `fact_sales[distributor_key]` (*)
- `dim_sales_rep[sales_rep_key]` (1) ───< `fact_sales[sales_rep_key]` (*)
- `dim_channel[channel_key]` (1) ───< `fact_sales[channel_key]` (*)

---

## 2. 6-Page Executive Dashboard Specifications

### Page 1: Executive Commercial Overview
- **Header KPIs (Card Visuals):**
  - **Net Sales:** `$1.25B` (Format: Currency Millions, `$#,##0.0M`)
  - **Gross Sales:** `$1.48B`
  - **Returns & Deductions:** `$2.77M`
  - **Gross-to-Net Realization:** `84.1%`
  - **Total Net Units:** `4.90M Units`
  - **Gross Margin %:** `82.4%`
- **Visual 1 (Area + Line Chart):** Monthly Net Revenue Velocity & MoM Growth % (X-axis: `dim_date[year_month]`, Y-axis: `[Net Sales]`, Secondary Y: `[MoM Sales Growth %]`).
- **Visual 2 (Donut Chart):** Revenue Contribution by Therapeutic Area (*CNS / Psychiatry* 78.3%, *Oncology* 18.8%, *Immunology* 2.9%).
- **Visual 3 (Ranked Bar Chart):** Country Revenue Contribution with drill-through to Geography page.
- **Visual 4 (Table Visual):** Top 5 Brands by Net Sales, Gross Margin %, and Units Sold.

### Page 2: Product Portfolio & ABC / Pareto Intelligence
- **Header KPIs:**
  - **Active Portfolio Assets:** `9 Brands`
  - **Class A Core Assets:** `4 Brands ($800.8M, 64.3%)`
  - **Average Realized Unit Price:** `$254.16 / Unit`
  - **Portfolio Return Rate:** `0.22%`
- **Visual 1 (Combined Column + Line Pareto Chart):** Products sorted descending by Net Sales; Line visual showing `[Product Revenue Cumulative %]` with threshold line at `80%`.
- **Visual 2 (Scatter Plot - Volume vs Value Contribution):** X-axis: `[Total Net Units]`, Y-axis: `[Net Sales]`, Bubble Size: `[Gross Margin %]`, Legend: `dim_product[therapeutic_area]`. Identifies high-volume low-margin assets (*AlprazPlus*) vs low-volume high-margin assets (*OncoShield*, *ImmunoPax*).
- **Visual 3 (Matrix Grid):** Product Return Rates and Primary Return Reasons (*Damaged in Transit*, *Batch Expiry*, etc.).

### Page 3: Geographic Performance & Common-Period Normalization
- **Header Callout Alert Box:** *"Caution: Country launch dates range from Jan 2023 (US, DE, UK) to June 2024 (CA). Common-period benchmark (FY2025) avoids unequal window bias."*
- **Visual 1 (Side-by-Side Horizontal Bar Chart):**
  - Left: All-Time Net Sales (US $551.6M, DE $200.2M, UK $157.0M, FR $137.4M, JP $122.7M, CA $76.1M).
  - Right: FY2025 Common-Period Benchmark (Reveals Japan and France outperforming UK in annualized velocity).
- **Visual 2 (Map Visual):** Market bubble size driven by `[Normalized Monthly Revenue Velocity]`.
- **Visual 3 (Clustered Column Chart):** Year-over-Year Growth (FY2024 vs FY2025) per country.

### Page 4: Customer RFM & Distributor Dependency
- **Header KPIs:**
  - **Institutional Accounts:** `120 Accounts`
  - **Top 3 Wholesaler Concentration:** `69.65%` (Direct Pharma Logistics, AmerisourceBergen, Alliance Healthcare)
  - **Tier 1 Strategic Key Accounts:** `37 Accounts`
  - **Tier 3 At-Risk Accounts:** `18 Accounts`
- **Visual 1 (Treemap):** Distributor Volume Share (`Direct Pharma Logistics` 35.01%, `AmerisourceBergen` 18.30%, `Alliance Healthcare` 16.33%, `McKesson Corp` 14.30%, `Cardinal Health` 11.24%, `Medipal` 4.81%).
- **Visual 2 (Scatter Plot - RFM Profile):** X-axis: `Recency Days`, Y-axis: `Monetary Net Spend ($)`, Bubble Size: `Order Frequency`, Colored by `Customer RFM Segment`.
- **Visual 3 (Detail Table with Conditional Formatting):** Top 20 Institutional Accounts with AOV, Order Count, and Segment Tag.

### Page 5: Sales Force Effectiveness (SFE)
- **Header KPIs:**
  - **Total Field Force:** `24 Representatives`
  - **Commercial Teams:** `4 Business Units (6 reps each)`
  - **Average Productivity:** `$51.88M / Rep`
  - **Top Team Productivity:** `Team Alpha ($53.67M / Rep) & Team Gamma ($53.14M / Rep)`
- **Visual 1 (Horizontal Bar Chart):** Headcount-Normalized Revenue per Representative by Commercial Team.
- **Visual 2 (Leaderboard Table):** Representative Ranking, Territory Country, Total Accounts Covered, Average Deal Size, Firm Contribution %.
- **Visual 3 (Line Chart):** Quarterly Team Sales Trends (Tracking detailing momentum).

### Page 6: Commercial Channel Dynamics
- **Header KPIs:**
  - **Primary Route to Market:** `Wholesale Distributor ($501.8M, 40.3%)`
  - **Direct Hospital Tender:** `$370.8M (29.8%)`
  - **Retail Pharmacy Chain:** `$261.7M (21.0%)`
  - **Specialty Mail Order:** `$110.6M (8.9%)`
- **Visual 1 (100% Stacked Bar):** Therapeutic Area Mix within each Channel.
- **Visual 2 (Bar Chart):** Average Contract Discount % by Channel (*Hospital Tender 22.1%*, *Wholesale 15.0%*, *Retail 9.9%*, *Specialty 8.0%*).
- **Visual 3 (Card KPI):** Average Transaction Value by Channel (Specialty Mail Order leads at $97,000+ per shipment).
