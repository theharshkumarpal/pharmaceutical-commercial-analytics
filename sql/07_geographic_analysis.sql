-- ====================================================================
-- sql/07_geographic_analysis.sql
-- Geographic Market Performance & Common-Period Normalization
-- ====================================================================

-- 1. All-Time Revenue (Note: Distorted by Unequal Launch Timing)
SELECT 
    g.country_code,
    g.country_name,
    g.region,
    g.market_launch_date,
    g.coverage_months,
    SUM(f.net_units) AS net_units,
    ROUND(SUM(f.net_sales_usd), 2) AS all_time_net_sales_usd,
    ROUND(
        SUM(f.net_sales_usd) * 100.0 / (SELECT SUM(net_sales_usd) FROM fact_sales), 2
    ) AS all_time_revenue_share_pct
FROM fact_sales f
JOIN dim_geography g ON f.geography_key = g.geography_key
GROUP BY g.country_code, g.country_name, g.region, g.market_launch_date, g.coverage_months
ORDER BY all_time_net_sales_usd DESC;

-- 2. Common-Period Comparison: Calendar Year 2025 (All Markets Fully Launched)
-- In FY2025, every single country has active, continuous commercial operations.
WITH fy2025_sales AS (
    SELECT 
        g.country_code,
        g.country_name,
        g.region,
        SUM(f.net_units) AS fy2025_net_units,
        ROUND(SUM(f.net_sales_usd), 2) AS fy2025_net_sales_usd
    FROM fact_sales f
    JOIN dim_geography g ON f.geography_key = g.geography_key
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE d.year = 2025
    GROUP BY g.country_code, g.country_name, g.region
)
SELECT 
    country_code,
    country_name,
    region,
    fy2025_net_units,
    fy2025_net_sales_usd,
    ROUND(
        fy2025_net_sales_usd * 100.0 / (SELECT SUM(fy2025_net_sales_usd) FROM fy2025_sales), 2
    ) AS fy2025_revenue_share_pct
FROM fy2025_sales
ORDER BY fy2025_net_sales_usd DESC;

-- 3. Normalized Monthly Revenue Velocity (Revenue per Active Month)
SELECT 
    g.country_code,
    g.country_name,
    g.coverage_months,
    ROUND(SUM(f.net_sales_usd), 2) AS total_net_sales_usd,
    ROUND(SUM(f.net_sales_usd) / g.coverage_months, 2) AS avg_monthly_run_rate_usd,
    ROUND(SUM(f.net_units) * 1.0 / g.coverage_months, 0) AS avg_monthly_unit_volume
FROM fact_sales f
JOIN dim_geography g ON f.geography_key = g.geography_key
GROUP BY g.country_code, g.country_name, g.coverage_months
ORDER BY avg_monthly_run_rate_usd DESC;

-- 4. Geographic YoY Growth (FY2024 vs FY2025)
WITH geo_yearly AS (
    SELECT 
        g.country_code,
        g.country_name,
        d.year,
        ROUND(SUM(f.net_sales_usd), 2) AS net_sales_usd
    FROM fact_sales f
    JOIN dim_geography g ON f.geography_key = g.geography_key
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE d.year IN (2024, 2025)
    GROUP BY g.country_code, g.country_name, d.year
)
SELECT 
    country_code,
    country_name,
    MAX(CASE WHEN year = 2024 THEN net_sales_usd END) AS fy2024_sales_usd,
    MAX(CASE WHEN year = 2025 THEN net_sales_usd END) AS fy2025_sales_usd,
    ROUND(
        (MAX(CASE WHEN year = 2025 THEN net_sales_usd END) - MAX(CASE WHEN year = 2024 THEN net_sales_usd END)) * 100.0 /
        NULLIF(MAX(CASE WHEN year = 2024 THEN net_sales_usd END), 0), 2
    ) AS yoy_growth_2024_to_2025_pct
FROM geo_yearly
GROUP BY country_code, country_name
ORDER BY fy2025_sales_usd DESC;
