-- ====================================================================
-- sql/02_schema.sql
-- Star Schema DDL for PostgreSQL / SQLite Commercial Data Warehouse
-- ====================================================================

-- 1. Date Dimension
CREATE TABLE IF NOT EXISTS dim_date (
    date_key        INTEGER PRIMARY KEY, -- YYYYMMDD
    full_date       DATE NOT NULL,
    year            INTEGER NOT NULL,
    quarter         INTEGER NOT NULL,
    quarter_name    VARCHAR(16) NOT NULL,
    month           INTEGER NOT NULL,
    month_name      VARCHAR(20) NOT NULL,
    year_month      VARCHAR(7) NOT NULL,
    day_of_month    INTEGER NOT NULL,
    day_of_week     VARCHAR(15) NOT NULL,
    is_weekend      INTEGER NOT NULL
);

-- 2. Product Dimension
CREATE TABLE IF NOT EXISTS dim_product (
    product_key         INTEGER PRIMARY KEY,
    product_id          VARCHAR(20) NOT NULL UNIQUE,
    product_name        VARCHAR(50) NOT NULL,
    generic_name        VARCHAR(50) NOT NULL,
    therapeutic_area    VARCHAR(50) NOT NULL,
    dosage_form         VARCHAR(50) NOT NULL,
    unit_wac_price_usd  NUMERIC(10,2) NOT NULL
);

-- 3. Geography Dimension
CREATE TABLE IF NOT EXISTS dim_geography (
    geography_key       INTEGER PRIMARY KEY,
    country_code        VARCHAR(5) NOT NULL UNIQUE,
    country_name        VARCHAR(50) NOT NULL,
    region              VARCHAR(30) NOT NULL,
    currency            VARCHAR(5) NOT NULL,
    market_launch_date  DATE NOT NULL,
    coverage_months     INTEGER NOT NULL
);

-- 4. Customer Dimension
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key    INTEGER PRIMARY KEY,
    customer_id     VARCHAR(20) NOT NULL UNIQUE,
    customer_name   VARCHAR(100) NOT NULL,
    customer_type   VARCHAR(50) NOT NULL,
    country_code    VARCHAR(5) NOT NULL
);

-- 5. Distributor Dimension
CREATE TABLE IF NOT EXISTS dim_distributor (
    distributor_key     INTEGER PRIMARY KEY,
    distributor_id      VARCHAR(20) NOT NULL UNIQUE,
    distributor_name    VARCHAR(100) NOT NULL,
    distributor_tier    VARCHAR(50) NOT NULL
);

-- 6. Sales Representative Dimension
CREATE TABLE IF NOT EXISTS dim_sales_rep (
    sales_rep_key   INTEGER PRIMARY KEY,
    sales_rep_id    VARCHAR(20) NOT NULL UNIQUE,
    sales_rep_name  VARCHAR(50) NOT NULL,
    sales_team      VARCHAR(50) NOT NULL,
    country_code    VARCHAR(5) NOT NULL
);

-- 7. Sales Channel Dimension
CREATE TABLE IF NOT EXISTS dim_channel (
    channel_key         INTEGER PRIMARY KEY,
    sales_channel_id    VARCHAR(20) NOT NULL UNIQUE,
    sales_channel_name  VARCHAR(50) NOT NULL
);

-- 8. Fact Sales Table
CREATE TABLE IF NOT EXISTS fact_sales (
    sales_fact_id           INTEGER PRIMARY KEY,
    transaction_id          VARCHAR(32) NOT NULL UNIQUE,
    date_key                INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_key             INTEGER NOT NULL REFERENCES dim_product(product_key),
    geography_key           INTEGER NOT NULL REFERENCES dim_geography(geography_key),
    customer_key            INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    distributor_key         INTEGER NOT NULL REFERENCES dim_distributor(distributor_key),
    sales_rep_key           INTEGER NOT NULL REFERENCES dim_sales_rep(sales_rep_key),
    channel_key             INTEGER NOT NULL REFERENCES dim_channel(channel_key),
    units_ordered           INTEGER NOT NULL DEFAULT 0,
    units_returned          INTEGER NOT NULL DEFAULT 0,
    net_units               INTEGER NOT NULL,
    unit_wac_price_usd      NUMERIC(10,2) NOT NULL,
    contract_discount_pct   NUMERIC(5,2) NOT NULL,
    unit_net_price_usd      NUMERIC(10,2) NOT NULL,
    gross_sales_usd         NUMERIC(12,2) NOT NULL DEFAULT 0,
    return_value_usd        NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_sales_usd           NUMERIC(12,2) NOT NULL,
    cogs_usd                NUMERIC(12,2) NOT NULL,
    gross_margin_usd        NUMERIC(12,2) NOT NULL,
    reconciliation_status   VARCHAR(20) NOT NULL DEFAULT 'PASS',
    return_reason           VARCHAR(100)
);

-- High Performance Indexes
CREATE INDEX IF NOT EXISTS idx_fact_sales_date ON fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product ON fact_sales(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_geography ON fact_sales(geography_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer ON fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_distributor ON fact_sales(distributor_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_rep ON fact_sales(sales_rep_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_channel ON fact_sales(channel_key);
