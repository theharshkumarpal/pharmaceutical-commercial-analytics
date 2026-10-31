-- ====================================================================
-- sql/03_transformations.sql
-- Ingestion, staging transformations and dimensional surrogate mapping
-- ====================================================================

-- 1. Create Staging Table for Ingestion
CREATE TABLE IF NOT EXISTS stg_commercial_sales (
    transaction_id          VARCHAR(32),
    transaction_date        DATE,
    product_id              VARCHAR(20),
    product_name            VARCHAR(50),
    generic_name            VARCHAR(50),
    therapeutic_area        VARCHAR(50),
    dosage_form             VARCHAR(50),
    customer_id             VARCHAR(20),
    customer_name           VARCHAR(100),
    customer_type           VARCHAR(50),
    distributor_id          VARCHAR(20),
    distributor_name        VARCHAR(100),
    sales_rep_id            VARCHAR(20),
    sales_rep_name          VARCHAR(50),
    sales_team              VARCHAR(50),
    sales_channel_id        VARCHAR(20),
    sales_channel_name      VARCHAR(50),
    country_code            VARCHAR(5),
    country_name            VARCHAR(50),
    region                  VARCHAR(30),
    currency                VARCHAR(5),
    units_ordered           INTEGER,
    units_returned          INTEGER,
    net_units               INTEGER,
    unit_wac_price_usd      NUMERIC(10,2),
    contract_discount_pct   NUMERIC(5,2),
    unit_net_price_usd      NUMERIC(10,2),
    gross_sales_usd         NUMERIC(12,2),
    contract_discount_usd   NUMERIC(12,2),
    return_value_usd        NUMERIC(12,2),
    net_sales_usd           NUMERIC(12,2),
    cogs_usd                NUMERIC(12,2),
    gross_margin_usd                NUMERIC(12,2),
    reconciliation_status           VARCHAR(20),
    financial_reconciliation_status VARCHAR(20),
    data_quality_status             VARCHAR(20),
    anomaly_flag                    VARCHAR(50),
    cogs_source_type                VARCHAR(20),
    return_reason                   VARCHAR(100)
);

-- 2. Populate dim_date from distinct dates
INSERT OR IGNORE INTO dim_date (
    date_key, full_date, year, quarter, quarter_name,
    month, month_name, year_month, day_of_month, day_of_week, is_weekend
)
SELECT DISTINCT
    CAST(strftime('%Y%m%d', transaction_date) AS INTEGER) AS date_key,
    transaction_date AS full_date,
    CAST(strftime('%Y', transaction_date) AS INTEGER) AS year,
    CAST((strftime('%m', transaction_date) + 2) / 3 AS INTEGER) AS quarter,
    'Q' || CAST((strftime('%m', transaction_date) + 2) / 3 AS TEXT) || ' ' || strftime('%Y', transaction_date) AS quarter_name,
    CAST(strftime('%m', transaction_date) AS INTEGER) AS month,
    CASE strftime('%m', transaction_date)
        WHEN '01' THEN 'January' WHEN '02' THEN 'February' WHEN '03' THEN 'March'
        WHEN '04' THEN 'April'   WHEN '05' THEN 'May'      WHEN '06' THEN 'June'
        WHEN '07' THEN 'July'    WHEN '08' THEN 'August'   WHEN '09' THEN 'September'
        WHEN '10' THEN 'October' WHEN '11' THEN 'November' WHEN '12' THEN 'December'
    END AS month_name,
    strftime('%Y-%m', transaction_date) AS year_month,
    CAST(strftime('%d', transaction_date) AS INTEGER) AS day_of_month,
    CASE strftime('%w', transaction_date)
        WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday'
        WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' WHEN '6' THEN 'Saturday'
    END AS day_of_week,
    CASE WHEN strftime('%w', transaction_date) IN ('0', '6') THEN 1 ELSE 0 END AS is_weekend
FROM stg_commercial_sales;

-- 3. Populate dim_product
INSERT OR IGNORE INTO dim_product (
    product_id, product_name, generic_name, therapeutic_area, dosage_form, unit_wac_price_usd
)
SELECT DISTINCT
    product_id, product_name, generic_name, therapeutic_area, dosage_form, unit_wac_price_usd
FROM stg_commercial_sales;

-- 4. Populate dim_geography
INSERT OR IGNORE INTO dim_geography (
    country_code, country_name, region, currency, market_launch_date, coverage_months
)
SELECT DISTINCT
    country_code, country_name, region, currency,
    CASE country_code
        WHEN 'US' THEN '2023-01-01' WHEN 'DE' THEN '2023-01-01' WHEN 'UK' THEN '2023-01-01'
        WHEN 'FR' THEN '2023-07-01' WHEN 'JP' THEN '2024-01-01' WHEN 'CA' THEN '2024-06-01'
    END AS market_launch_date,
    CASE country_code
        WHEN 'US' THEN 36 WHEN 'DE' THEN 36 WHEN 'UK' THEN 36
        WHEN 'FR' THEN 30 WHEN 'JP' THEN 24 WHEN 'CA' THEN 18
    END AS coverage_months
FROM stg_commercial_sales;

-- 5. Populate dim_customer
INSERT OR IGNORE INTO dim_customer (
    customer_id, customer_name, customer_type, country_code
)
SELECT DISTINCT
    customer_id, customer_name, customer_type, country_code
FROM stg_commercial_sales;

-- 6. Populate dim_distributor
INSERT OR IGNORE INTO dim_distributor (
    distributor_id, distributor_name, distributor_tier
)
SELECT DISTINCT
    distributor_id, distributor_name,
    CASE 
        WHEN distributor_name LIKE '%McKesson%' OR distributor_name LIKE '%AmerisourceBergen%' OR distributor_name LIKE '%Cardinal%' THEN 'Tier 1 National / Global'
        ELSE 'Tier 2 Regional / Specialty'
    END AS distributor_tier
FROM stg_commercial_sales;

-- 7. Populate dim_sales_rep
INSERT OR IGNORE INTO dim_sales_rep (
    sales_rep_id, sales_rep_name, sales_team, country_code
)
SELECT DISTINCT
    sales_rep_id, sales_rep_name, sales_team, country_code
FROM stg_commercial_sales;

-- 8. Populate dim_channel
INSERT OR IGNORE INTO dim_channel (
    sales_channel_id, sales_channel_name
)
SELECT DISTINCT
    sales_channel_id, sales_channel_name
FROM stg_commercial_sales;

-- 9. Insert fact_sales mapping all surrogate keys
INSERT INTO fact_sales (
    transaction_id, date_key, product_key, geography_key,
    customer_key, distributor_key, sales_rep_key, channel_key,
    units_ordered, units_returned, net_units,
    unit_wac_price_usd, contract_discount_pct, unit_net_price_usd,
    gross_sales_usd, contract_discount_usd, return_value_usd, net_sales_usd,
    cogs_usd, gross_margin_usd, reconciliation_status, financial_reconciliation_status,
    data_quality_status, anomaly_flag, cogs_source_type, return_reason
)
SELECT 
    s.transaction_id,
    d.date_key,
    p.product_key,
    g.geography_key,
    c.customer_key,
    dst.distributor_key,
    r.sales_rep_key,
    ch.channel_key,
    s.units_ordered,
    s.units_returned,
    s.net_units,
    s.unit_wac_price_usd,
    s.contract_discount_pct,
    s.unit_net_price_usd,
    s.gross_sales_usd,
    s.contract_discount_usd,
    s.return_value_usd,
    s.net_sales_usd,
    s.cogs_usd,
    s.gross_margin_usd,
    s.reconciliation_status,
    s.financial_reconciliation_status,
    s.data_quality_status,
    s.anomaly_flag,
    s.cogs_source_type,
    s.return_reason
FROM stg_commercial_sales s
JOIN dim_date d ON strftime('%Y%m%d', s.transaction_date) = CAST(d.date_key AS TEXT)
JOIN dim_product p ON s.product_id = p.product_id
JOIN dim_geography g ON s.country_code = g.country_code
JOIN dim_customer c ON s.customer_id = c.customer_id
JOIN dim_distributor dst ON s.distributor_id = dst.distributor_id
JOIN dim_sales_rep r ON s.sales_rep_id = r.sales_rep_id
JOIN dim_channel ch ON s.sales_channel_id = ch.sales_channel_id;
