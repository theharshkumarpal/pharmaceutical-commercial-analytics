-- ====================================================================
-- sql/08_sales_force_analysis.sql
-- Sales Force Effectiveness (SFE), Headcount Normalization & Team Productivity
-- ====================================================================

-- 1. Sales Representative Individual Scorecard
SELECT 
    r.sales_rep_id,
    r.sales_rep_name,
    r.sales_team,
    r.country_code,
    COUNT(DISTINCT f.sales_fact_id)                                  AS transaction_count,
    COUNT(DISTINCT f.customer_key)                                  AS active_accounts_serviced,
    SUM(f.net_units)                                                AS net_units_sold,
    ROUND(SUM(f.net_sales_usd), 2)                                  AS total_net_sales_usd,
    ROUND(SUM(f.net_sales_usd) / NULLIF(COUNT(DISTINCT f.sales_fact_id), 0), 2) AS avg_deal_size_usd,
    ROUND(
        SUM(f.net_sales_usd) * 100.0 / (SELECT SUM(net_sales_usd) FROM fact_sales), 2
    ) AS contribution_to_firm_sales_pct,
    DENSE_RANK() OVER (ORDER BY SUM(f.net_sales_usd) DESC)          AS overall_revenue_rank
FROM fact_sales f
JOIN dim_sales_rep r ON f.sales_rep_key = r.sales_rep_key
GROUP BY r.sales_rep_id, r.sales_rep_name, r.sales_team, r.country_code
ORDER BY total_net_sales_usd DESC;

-- 2. Commercial Team Performance with Headcount Normalization
-- Normalizing team comparisons by representative count ensures fair benchmarking
WITH team_metrics AS (
    SELECT 
        r.sales_team,
        COUNT(DISTINCT r.sales_rep_id) AS team_headcount,
        COUNT(DISTINCT f.customer_key) AS total_accounts_covered,
        COUNT(DISTINCT f.sales_fact_id) AS total_orders_booked,
        SUM(f.net_units) AS total_net_units,
        ROUND(SUM(f.net_sales_usd), 2) AS total_team_net_sales_usd
    FROM fact_sales f
    JOIN dim_sales_rep r ON f.sales_rep_key = r.sales_rep_key
    GROUP BY r.sales_team
)
SELECT 
    sales_team,
    team_headcount,
    total_accounts_covered,
    total_orders_booked,
    total_net_units,
    total_team_net_sales_usd,
    ROUND(total_team_net_sales_usd / team_headcount, 2) AS productivity_revenue_per_rep_usd,
    ROUND(total_net_units * 1.0 / team_headcount, 0) AS units_per_rep,
    ROUND(
        total_team_net_sales_usd * 100.0 / (SELECT SUM(total_team_net_sales_usd) FROM team_metrics), 2
    ) AS team_revenue_share_pct
FROM team_metrics
ORDER BY productivity_revenue_per_rep_usd DESC;

-- 3. Sales Force Quarterly Revenue Trend
SELECT 
    r.sales_team,
    d.quarter_name,
    ROUND(SUM(f.net_sales_usd), 2) AS quarterly_net_sales_usd,
    SUM(f.net_units) AS quarterly_net_units
FROM fact_sales f
JOIN dim_sales_rep r ON f.sales_rep_key = r.sales_rep_key
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY r.sales_team, d.quarter_name
ORDER BY r.sales_team, d.quarter_name;
