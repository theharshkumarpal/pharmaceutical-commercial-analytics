-- ====================================================================
-- sql/01_data_quality.sql
-- Validation queries to audit data quality, missingness, and integrity
-- ====================================================================

-- 1. Check for Duplicate Transactions in Fact Table
SELECT 
    transaction_id,
    COUNT(*) AS occurrence_count
FROM fact_sales
GROUP BY transaction_id
HAVING COUNT(*) > 1;

-- 2. Verify Referential Integrity (Orphaned Foreign Keys)
SELECT 'Orphaned Date Keys' AS check_name, COUNT(*) AS violations
FROM fact_sales f LEFT JOIN dim_date d ON f.date_key = d.date_key WHERE d.date_key IS NULL
UNION ALL
SELECT 'Orphaned Product Keys', COUNT(*)
FROM fact_sales f LEFT JOIN dim_product p ON f.product_key = p.product_key WHERE p.product_key IS NULL
UNION ALL
SELECT 'Orphaned Geography Keys', COUNT(*)
FROM fact_sales f LEFT JOIN dim_geography g ON f.geography_key = g.geography_key WHERE g.geography_key IS NULL
UNION ALL
SELECT 'Orphaned Customer Keys', COUNT(*)
FROM fact_sales f LEFT JOIN dim_customer c ON f.customer_key = c.customer_key WHERE c.customer_key IS NULL
UNION ALL
SELECT 'Orphaned Distributor Keys', COUNT(*)
FROM fact_sales f LEFT JOIN dim_distributor dst ON f.distributor_key = dst.distributor_key WHERE dst.distributor_key IS NULL
UNION ALL
SELECT 'Orphaned Sales Rep Keys', COUNT(*)
FROM fact_sales f LEFT JOIN dim_sales_rep r ON f.sales_rep_key = r.sales_rep_key WHERE r.sales_rep_key IS NULL
UNION ALL
SELECT 'Orphaned Channel Keys', COUNT(*)
FROM fact_sales f LEFT JOIN dim_channel ch ON f.channel_key = ch.channel_key WHERE ch.channel_key IS NULL;

-- 3. Audit Negative vs Positive Quantities & Return Tagging
SELECT 
    CASE 
        WHEN net_units < 0 THEN 'Commercial Return / Reversal'
        WHEN net_units > 0 THEN 'Standard Sale / Shipment'
        ELSE 'Zero Quantity'
    END AS transaction_nature,
    COUNT(*) AS transaction_count,
    SUM(units_ordered) AS total_units_ordered,
    SUM(units_returned) AS total_units_returned,
    ROUND(SUM(gross_sales_usd), 2) AS total_gross_sales,
    ROUND(SUM(return_value_usd), 2) AS total_return_value,
    ROUND(SUM(net_sales_usd), 2) AS total_net_sales
FROM fact_sales
GROUP BY 1;

-- 4. Financial Reconciliation Check: Gross - Returns - Contract Discounts = Net Sales
SELECT 
    ROUND(SUM(gross_sales_usd), 2) AS total_gross_sales_usd,
    ROUND(SUM(return_value_usd), 2) AS total_return_deductions_usd,
    ROUND(SUM(net_sales_usd), 2) AS total_net_recognized_sales_usd,
    ROUND(SUM(cogs_usd), 2) AS total_cogs_usd,
    ROUND(SUM(gross_margin_usd), 2) AS total_gross_margin_usd,
    ROUND(SUM(gross_margin_usd) * 100.0 / NULLIF(SUM(net_sales_usd), 0), 2) AS gross_margin_pct
FROM fact_sales;
