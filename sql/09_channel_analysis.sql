-- ====================================================================
-- sql/09_channel_analysis.sql
-- Commercial Channel Performance, Product Mix & Discount Dynamics
-- ====================================================================

-- 1. Sales Channel Commercial Summary & Realization
SELECT 
    ch.sales_channel_id,
    ch.sales_channel_name,
    COUNT(DISTINCT f.sales_fact_id)                                  AS transaction_volume,
    COUNT(DISTINCT f.customer_key)                                  AS unique_accounts_reached,
    SUM(f.net_units)                                                AS total_net_units,
    ROUND(SUM(f.gross_sales_usd), 2)                                AS gross_sales_usd,
    ROUND(SUM(f.return_value_usd), 2)                               AS returns_refunded_usd,
    ROUND(SUM(f.net_sales_usd), 2)                                  AS net_sales_usd,
    ROUND(AVG(f.contract_discount_pct), 2)                          AS avg_contract_discount_pct,
    ROUND(SUM(f.net_sales_usd) / NULLIF(COUNT(DISTINCT f.sales_fact_id), 0), 2) AS avg_transaction_value_usd,
    ROUND(
        SUM(f.net_sales_usd) * 100.0 / (SELECT SUM(net_sales_usd) FROM fact_sales), 2
    ) AS channel_revenue_share_pct
FROM fact_sales f
JOIN dim_channel ch ON f.channel_key = ch.channel_key
GROUP BY ch.sales_channel_id, ch.sales_channel_name
ORDER BY net_sales_usd DESC;

-- 2. Channel-Level Product Mix (Therapeutic Area Distribution per Channel)
SELECT 
    ch.sales_channel_name,
    p.therapeutic_area,
    SUM(f.net_units) AS net_units,
    ROUND(SUM(f.net_sales_usd), 2) AS net_sales_usd,
    ROUND(
        SUM(f.net_sales_usd) * 100.0 / SUM(SUM(f.net_sales_usd)) OVER (PARTITION BY ch.sales_channel_name), 2
    ) AS therapeutic_mix_within_channel_pct
FROM fact_sales f
JOIN dim_channel ch ON f.channel_key = ch.channel_key
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY ch.sales_channel_name, p.therapeutic_area
ORDER BY ch.sales_channel_name, net_sales_usd DESC;

-- 3. Channel Performance by Geographic Region
SELECT 
    g.region,
    ch.sales_channel_name,
    COUNT(DISTINCT f.sales_fact_id) AS transactions,
    SUM(f.net_units) AS net_units,
    ROUND(SUM(f.net_sales_usd), 2) AS net_sales_usd
FROM fact_sales f
JOIN dim_geography g ON f.geography_key = g.geography_key
JOIN dim_channel ch ON f.channel_key = ch.channel_key
GROUP BY g.region, ch.sales_channel_name
ORDER BY g.region, net_sales_usd DESC;
