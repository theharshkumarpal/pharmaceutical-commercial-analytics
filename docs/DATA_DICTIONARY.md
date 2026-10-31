# Data Dictionary: Pharmaceutical Commercial Performance Platform

**Domain Focus:** Life Sciences Commercial Analytics & Strategic Advisory  
**Architecture:** Star Schema OLAP Architecture  
**Database Target:** SQLite (`pharma_commercial.db`) / PostgreSQL Compatible  
**Last Updated:** October 2026  

---

## 1. Dimensional Model Overview

The analytical repository implements a Kimball-style dimensional star schema optimized for fast analytical aggregations, Gross-to-Net (GTN) waterfall accounting, customer RFM segmentation, sales-rep territory productivity, and market access penetration.

```
       ┌──────────────┐         ┌────────────────┐         ┌───────────────┐
       │   dim_date   │         │  dim_product   │         │ dim_geography │
       └──────┬───────┘         └───────┬────────┘         └───────┬───────┘
              │ date_key                │ product_key              │ geography_key
              │                         │                          │
        ┌─────┴─────────────────────────┴──────────────────────────┴─────┐
        │                           fact_sales                           │
        │  (Grain: 1 record per commercial invoice / credit return line)  │
        └─────┬─────────────────────────┬──────────────────────────┬─────┘
              │ customer_key            │ distributor_key          │ sales_rep_key / channel_key
              │                         │                          │
       ┌──────┴───────┐         ┌───────┴────────┐         ┌───────┴───────┐
       │ dim_customer │         │dim_distributor │         │ dim_sales_rep │
       │              │         │                │         │  dim_channel  │
       └──────────────┘         └────────────────┘         └───────────────┘
```

---

## 2. Fact Table: `fact_sales`

**Table Grain:** One row per individual commercial transaction (shipment invoice or reverse logistics credit return).

| Column Name | SQL Data Type | Nullable | Source / Formula | Business Meaning & Consulting Context |
| :--- | :--- | :--- | :--- | :--- |
| `sales_fact_id` | `INTEGER` | No | Auto-increment PK | Unique surrogate key for each sales transaction fact row. |
| `transaction_id` | `VARCHAR(32)` | No | ERP / Invoicing ID | Unique business identifier (`TXN-000001`). Natural key. |
| `date_key` | `INTEGER` | No | `dim_date.date_key` (FK) | Integer surrogate date key (`YYYYMMDD`). |
| `product_key` | `INTEGER` | No | `dim_product.product_key` (FK) | Surrogate reference to pharmaceutical brand. |
| `geography_key` | `INTEGER` | No | `dim_geography.geography_key` (FK) | Surrogate reference to destination market/country. |
| `customer_key` | `INTEGER` | No | `dim_customer.customer_key` (FK) | Surrogate reference to purchasing account / IDN / hospital. |
| `distributor_key` | `INTEGER` | No | `dim_distributor.distributor_key` (FK) | Surrogate reference to wholesale logistics intermediary. |
| `sales_rep_key` | `INTEGER` | No | `dim_sales_rep.sales_rep_key` (FK) | Surrogate reference to territory sales representative. |
| `channel_key` | `INTEGER` | No | `dim_channel.channel_key` (FK) | Surrogate reference to commercial delivery channel. |
| `units_ordered` | `INTEGER` | No | `units_ordered` | Quantity of drug units shipped to account. Zero on return rows. |
| `units_returned` | `INTEGER` | No | `units_returned` | Quantity of drug units returned by account due to damage/expiry. |
| `net_units` | `INTEGER` | No | `units_ordered - units_returned` | Effective net units transferred to market. Negative on returns. |
| `unit_wac_price_usd` | `NUMERIC(10,2)` | No | Wholesale Acquisition Cost | Official list price (WAC) per package/vial before contracting. |
| `contract_discount_pct` | `NUMERIC(5,2)` | No | Contract Tier % | Contracted discount / statutory rebate percentage. |
| `unit_net_price_usd` | `NUMERIC(10,2)` | No | `WAC * (1 - Discount)` | Realized net price per unit after on-invoice commercial discounts. |
| `gross_sales_usd` | `NUMERIC(12,2)` | No | `units_ordered * WAC` | Top-line invoiced sales volume before adjustments. |
| `return_value_usd` | `NUMERIC(12,2)` | No | `units_returned * Net_Price` | Total dollar value refunded for returned inventory. |
| `net_sales_usd` | `NUMERIC(12,2)` | No | `Gross - Returns - Discounts` | Realized recognized revenue adhering to GTN commercial standard. |
| `cogs_usd` | `NUMERIC(12,2)` | No | `net_units * Unit_Cost` | Cost of Goods Sold (signed: positive for sales, negative for return reversals). |
| `gross_margin_usd` | `NUMERIC(12,2)` | No | `net_sales_usd - cogs_usd` | Gross profit contribution after manufacturing costs (exact reconciliation). |
| `return_reason` | `VARCHAR(100)` | Yes | Return Reason Code | Categorical tag (e.g., `Damaged in Transit`, `Recall / Batch Expiry`). |

---

## 3. Dimension Tables

### 3.1 `dim_date`
Provides multi-level calendar attributes for time-series forecasting, quarterly earnings reporting, and common-period filtering.
- `date_key` (`INT`, PK): Format `YYYYMMDD`.
- `full_date` (`DATE`): Calendar date (`YYYY-MM-DD`).
- `year` (`INT`): 2023, 2024, 2025.
- `quarter` (`INT`): 1, 2, 3, 4.
- `quarter_name` (`VARCHAR(16)`): e.g., `Q1 2024`.
- `month` (`INT`): 1 to 12.
- `month_name` (`VARCHAR(20)`): e.g., `January`.
- `year_month` (`VARCHAR(7)`): e.g., `2024-03`.
- `day_of_month` (`INT`): 1 to 31.
- `day_of_week` (`VARCHAR(15)`): Monday through Sunday.
- `is_weekend` (`INT`): 1 if Saturday/Sunday, else 0.

### 3.2 `dim_product`
Contains pharmaceutical brand hierarchy, generic chemical classification, and therapeutic area.
- `product_key` (`INT`, PK): Surrogate product identifier.
- `product_id` (`VARCHAR(20)`, Natural Key): e.g., `PRD-CNS-001`, `PRD-ONC-007`.
- `product_name` (`VARCHAR(50)`): Proprietary trade brand name (*AmphetaDex*, *OncoShield*, etc.).
- `generic_name` (`VARCHAR(50)`): Active Pharmaceutical Ingredient (API).
- `therapeutic_area` (`VARCHAR(50)`): Disease portfolio (*CNS / Psychiatry*, *Oncology*, *Immunology*).
- `dosage_form` (`VARCHAR(50)`): Formulation (*Capsule*, *Vial Injection*, *Auto-injector Pen*).
- `unit_wac_price_usd` (`NUMERIC(10,2)`): Baseline catalog list price.

### 3.3 `dim_geography`
Documents global commercial launch territories, currency, and market access coverage.
- `geography_key` (`INT`, PK): Surrogate geography identifier.
- `country_code` (`VARCHAR(5)`, Natural Key): ISO alpha-2 (`US`, `DE`, `UK`, `FR`, `JP`, `CA`).
- `country_name` (`VARCHAR(50)`): Formal country name.
- `region` (`VARCHAR(30)`): `North America`, `Europe`, `Asia-Pacific`.
- `currency` (`VARCHAR(5)`): Reporting currency (`USD`, `EUR`, `GBP`, `JPY`, `CAD`).
- `market_launch_date` (`DATE`): Commercial market authorization / reimbursement date.
- `coverage_months` (`INT`): Total months of active commercial sales in dataset.

### 3.4 `dim_customer`
Institutional health system and retail accounts purchasing therapies.
- `customer_key` (`INT`, PK): Surrogate customer identifier.
- `customer_id` (`VARCHAR(20)`, Natural Key): Institutional account code (`CUST-0001`).
- `customer_name` (`VARCHAR(100)`): Hospital / IDN name.
- `customer_type` (`VARCHAR(50)`): `Academic Medical Center`, `Integrated Delivery Network (IDN)`, `Community Hospital`, `National Retail Pharmacy`, `Specialty Oncology Clinic`.
- `country_code` (`VARCHAR(5)`): Territory location.

### 3.5 `dim_distributor`
Logistics and wholesale intermediaries managing commercial inventory.
- `distributor_key` (`INT`, PK): Surrogate distributor identifier.
- `distributor_id` (`VARCHAR(20)`, Natural Key): e.g., `DST-001`.
- `distributor_name` (`VARCHAR(100)`): e.g., *McKesson Corp*, *AmerisourceBergen (Cencora)*, *Cardinal Health*.
- `distributor_tier` (`VARCHAR(50)`): `Tier 1 National / Global` vs `Tier 2 Regional / Specialty`.

### 3.6 `dim_sales_rep`
Field commercial force driving detailing, formulary placement, and volume growth.
- `sales_rep_key` (`INT`, PK): Surrogate representative key.
- `sales_rep_id` (`VARCHAR(20)`, Natural Key): e.g., `REP-001`.
- `sales_rep_name` (`VARCHAR(50)`): Representative name.
- `sales_team` (`VARCHAR(50)`): Assigned commercial business unit (`Team Alpha - CNS North`, etc.).
- `country_code` (`VARCHAR(5)`): Home territory.

### 3.7 `dim_channel`
Commercial route to market.
- `channel_key` (`INT`, PK): Surrogate channel key.
- `sales_channel_id` (`VARCHAR(20)`, Natural Key): `CHN-01` through `CHN-04`.
- `sales_channel_name` (`VARCHAR(50)`): `Hospital Direct Tender`, `Wholesale Distributor`, `Retail Pharmacy Chain`, `Specialty Mail Order`.
