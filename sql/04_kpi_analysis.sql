-- ====================================================================
-- sql/04_kpi_analysis.sql
-- Executive Commercial Performance & Gross-to-Net (GTN) Accounting
-- ====================================================================

-- 1. High-Level Executive Commercial Summary
SELECT 
    COUNT(DISTINCT f.sales_fact_id)                                  AS total_transactions,
    SUM(f.units_ordered)                                            AS total_gross_units_sold,
    SUM(f.units_returned)                                           AS total_units_returned,
    SUM(f.net_units)                                                AS total_net_units,
    ROUND(SUM(f.gross_sales_usd), 2)                                AS total_gross_sales_usd,
    ROUND(SUM(f.return_value_usd), 2)                               AS total_returns_usd,
    ROUND(SUM(f.net_sales_usd), 2)                                  AS total_net_sales_usd,
    ROUND(SUM(f.cogs_usd), 2)                                       AS total_cogs_usd,
    ROUND(SUM(f.gross_margin_usd), 2)                               AS total_gross_margin_usd,
    ROUND(SUM(f.net_sales_usd) / NULLIF(COUNT(DISTINCT f.sales_fact_id), 0), 2) AS average_order_value_usd,
    ROUND(SUM(f.net_sales_usd) * 100.0 / NULLIF(SUM(f.gross_sales_usd), 0), 2) AS gross_to_net_realization_pct,
    ROUND(SUM(f.gross_margin_usd) * 100.0 / NULLIF(SUM(f.net_sales_usd), 0), 2) AS gross_margin_pct
FROM fact_sales f;

-- 2. Monthly Revenue Trend with Month-over-Month (MoM) Growth
WITH monthly_sales AS (
    SELECT 
        d.year,
        d.month,
        d.year_month,
        ROUND(SUM(f.gross_sales_usd), 2) AS gross_sales_usd,
        ROUND(SUM(f.return_value_usd), 2) AS return_value_usd,
        ROUND(SUM(f.net_sales_usd), 2) AS net_sales_usd,
        SUM(f.net_units) AS net_units,
        COUNT(DISTINCT f.sales_fact_id) AS transaction_count
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year, d.month, d.year_month
)
SELECT 
    year_month,
    net_units,
    gross_sales_usd,
    return_value_usd,
    net_sales_usd,
    LAG(net_sales_usd, 1) OVER (ORDER BY year_month) AS prior_month_net_sales,
    ROUND(
        (net_sales_usd - LAG(net_sales_usd, 1) OVER (ORDER BY year_month)) * 100.0 /
        NULLIF(LAG(net_sales_usd, 1) OVER (ORDER BY year_month), 0), 2
    ) AS mom_growth_pct
FROM monthly_sales
ORDER BY year_month;

-- 3. Year-over-Year (YoY) Growth by Calendar Year
WITH yearly_summary AS (
    SELECT 
        d.year,
        ROUND(SUM(f.net_sales_usd), 2) AS net_sales_usd,
        SUM(f.net_units) AS net_units,
        COUNT(DISTINCT f.sales_fact_id) AS transactions
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year
)
SELECT 
    year,
    net_units,
    transactions,
    net_sales_usd,
    LAG(net_sales_usd, 1) OVER (ORDER BY year) AS prior_year_net_sales,
    ROUND(
        (net_sales_usd - LAG(net_sales_usd, 1) OVER (ORDER BY year)) * 100.0 /
        NULLIF(LAG(net_sales_usd, 1) OVER (ORDER BY year), 0), 2
    ) AS yoy_growth_pct
FROM yearly_summary
ORDER BY year;

-- 4. Revenue Contribution Breakdown by Geography
SELECT 
    g.country_code,
    g.country_name,
    g.region,
    g.coverage_months,
    SUM(f.net_units) AS net_units,
    ROUND(SUM(f.net_sales_usd), 2) AS net_sales_usd,
    ROUND(
        SUM(f.net_sales_usd) * 100.0 / (SELECT SUM(net_sales_usd) FROM fact_sales), 2
    ) AS pct_of_global_revenue
FROM fact_sales f
JOIN dim_geography g ON f.geography_key = g.geography_key
GROUP BY g.country_code, g.country_name, g.region, g.coverage_months
ORDER BY net_sales_usd DESC;
