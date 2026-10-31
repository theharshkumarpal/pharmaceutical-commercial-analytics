-- ====================================================================
-- sql/06_customer_analysis.sql
-- Institutional Customer RFM Segmentation & Distributor Dependency
-- ====================================================================

-- 1. Top Distributors by Net Revenue & Concentration Risk
WITH distributor_summary AS (
    SELECT 
        dst.distributor_id,
        dst.distributor_name,
        dst.distributor_tier,
        COUNT(DISTINCT f.customer_key) AS unique_accounts_served,
        COUNT(DISTINCT f.sales_fact_id) AS transactions_fulfilled,
        SUM(f.net_units) AS net_units,
        ROUND(SUM(f.net_sales_usd), 2) AS net_sales_usd
    FROM fact_sales f
    JOIN dim_distributor dst ON f.distributor_key = dst.distributor_key
    GROUP BY dst.distributor_id, dst.distributor_name, dst.distributor_tier
)
SELECT 
    distributor_id,
    distributor_name,
    distributor_tier,
    unique_accounts_served,
    transactions_fulfilled,
    net_units,
    net_sales_usd,
    ROUND(
        net_sales_usd * 100.0 / (SELECT SUM(net_sales_usd) FROM distributor_summary), 2
    ) AS distributor_share_pct,
    ROUND(
        SUM(net_sales_usd) OVER (
            ORDER BY net_sales_usd DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) * 100.0 / (SELECT SUM(net_sales_usd) FROM distributor_summary), 2
    ) AS cumulative_distributor_share_pct
FROM distributor_summary
ORDER BY net_sales_usd DESC;

-- 2. Customer Performance Summary: Net Sales, Average Order Value (AOV), Order Frequency
SELECT 
    c.customer_id,
    c.customer_name,
    c.customer_type,
    c.country_code,
    COUNT(DISTINCT f.sales_fact_id) AS total_orders,
    SUM(f.net_units) AS total_units_purchased,
    ROUND(SUM(f.net_sales_usd), 2) AS total_net_sales_usd,
    ROUND(SUM(f.net_sales_usd) / NULLIF(COUNT(DISTINCT f.sales_fact_id), 0), 2) AS average_order_value_usd,
    ROUND(
        SUM(f.net_sales_usd) * 100.0 / (SELECT SUM(net_sales_usd) FROM fact_sales), 2
    ) AS pct_of_total_revenue
FROM fact_sales f
JOIN dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.customer_id, c.customer_name, c.customer_type, c.country_code
ORDER BY total_net_sales_usd DESC
LIMIT 20;

-- 3. Customer RFM Segmentation (Recency, Frequency, Monetary)
-- Reference date: 2025-12-31 (latest transaction in dataset)
WITH customer_rfm_raw AS (
    SELECT 
        c.customer_id,
        c.customer_name,
        c.customer_type,
        c.country_code,
        -- Recency: Days between last purchase and 2025-12-31
        CAST(julianday('2025-12-31') - julianday(MAX(d.full_date)) AS INTEGER) AS recency_days,
        -- Frequency: Count of distinct purchase transactions
        COUNT(DISTINCT f.sales_fact_id) AS frequency_orders,
        -- Monetary: Total Net Sales
        ROUND(SUM(f.net_sales_usd), 2) AS monetary_value_usd
    FROM fact_sales f
    JOIN dim_customer c ON f.customer_key = c.customer_key
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.net_units > 0
    GROUP BY c.customer_id, c.customer_name, c.customer_type, c.country_code
),
rfm_scores AS (
    SELECT 
        customer_id,
        customer_name,
        customer_type,
        country_code,
        recency_days,
        frequency_orders,
        monetary_value_usd,
        NTILE(4) OVER (ORDER BY recency_days DESC) AS r_score, -- 4 is most recent
        NTILE(4) OVER (ORDER BY frequency_orders ASC) AS f_score, -- 4 is highest frequency
        NTILE(4) OVER (ORDER BY monetary_value_usd ASC) AS m_score -- 4 is highest spend
    FROM customer_rfm_raw
)
SELECT 
    customer_id,
    customer_name,
    customer_type,
    country_code,
    recency_days,
    frequency_orders,
    monetary_value_usd,
    r_score,
    f_score,
    m_score,
    CASE 
        WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Tier 1: Strategic Key Account (Champion)'
        WHEN r_score >= 3 AND f_score >= 2 THEN 'Tier 2: Loyal Growth Account'
        WHEN r_score <= 2 AND m_score >= 3 THEN 'Tier 3: At-Risk High-Value Account'
        WHEN r_score >= 3 AND f_score <= 2 THEN 'Tier 4: Promising New / Developing Account'
        ELSE 'Tier 5: Low-Engagement / Maintenance Account'
    END AS customer_rfm_segment
FROM rfm_scores
ORDER BY monetary_value_usd DESC;
