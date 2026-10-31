-- ====================================================================
-- sql/05_product_analysis.sql
-- Pharmaceutical Portfolio ABC / Pareto Analysis & Product Mix
-- ====================================================================

-- 1. Product Portfolio Ranking, Volume vs Revenue & Return Rates
SELECT 
    p.product_id,
    p.product_name,
    p.generic_name,
    p.therapeutic_area,
    p.dosage_form,
    p.unit_wac_price_usd,
    SUM(f.units_ordered)                                              AS total_gross_units,
    SUM(f.units_returned)                                             AS total_returned_units,
    SUM(f.net_units)                                                  AS net_units_sold,
    ROUND(SUM(f.units_returned) * 100.0 / NULLIF(SUM(f.units_ordered), 0), 2) AS return_rate_pct,
    ROUND(SUM(f.gross_sales_usd), 2)                                  AS gross_sales_usd,
    ROUND(SUM(f.return_value_usd), 2)                                 AS returns_usd,
    ROUND(SUM(f.net_sales_usd), 2)                                    AS net_sales_usd,
    ROUND(SUM(f.gross_margin_usd), 2)                                 AS gross_margin_usd,
    ROUND(SUM(f.gross_margin_usd) * 100.0 / NULLIF(SUM(f.net_sales_usd), 0), 2) AS gross_margin_pct,
    ROUND(
        SUM(f.net_sales_usd) * 100.0 / (SELECT SUM(net_sales_usd) FROM fact_sales), 2
    ) AS revenue_contribution_pct
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.product_id, p.product_name, p.generic_name, p.therapeutic_area, p.dosage_form, p.unit_wac_price_usd
ORDER BY net_sales_usd DESC;

-- 2. Formal ABC / Pareto Classification by Cumulative Revenue Contribution
WITH product_revenue AS (
    SELECT 
        p.product_id,
        p.product_name,
        p.therapeutic_area,
        p.unit_wac_price_usd,
        SUM(f.net_units) AS net_units,
        ROUND(SUM(f.net_sales_usd), 2) AS net_sales_usd
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.product_id, p.product_name, p.therapeutic_area, p.unit_wac_price_usd
),
ranked_products AS (
    SELECT 
        product_id,
        product_name,
        therapeutic_area,
        unit_wac_price_usd,
        net_units,
        net_sales_usd,
        ROUND(net_sales_usd * 100.0 / (SELECT SUM(net_sales_usd) FROM product_revenue), 2) AS individual_pct,
        ROUND(
            SUM(net_sales_usd) OVER (
                ORDER BY net_sales_usd DESC 
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) * 100.0 / (SELECT SUM(net_sales_usd) FROM product_revenue), 2
        ) AS cumulative_revenue_pct
    FROM product_revenue
)
SELECT 
    product_id,
    product_name,
    therapeutic_area,
    unit_wac_price_usd,
    net_units,
    net_sales_usd,
    individual_pct,
    cumulative_revenue_pct,
    CASE 
        WHEN cumulative_revenue_pct <= 80.0 THEN 'Class A (Core 80% Value Driver)'
        WHEN cumulative_revenue_pct <= 95.0 THEN 'Class B (Next 15% Secondary Driver)'
        ELSE 'Class C (Remaining 5% Tail)'
    END AS pareto_class
FROM ranked_products
ORDER BY net_sales_usd DESC;

-- 3. Product Performance Breakdown across Geographic Markets (Product Mix)
SELECT 
    g.country_name,
    p.product_name,
    p.therapeutic_area,
    SUM(f.net_units) AS net_units,
    ROUND(SUM(f.net_sales_usd), 2) AS net_sales_usd,
    ROUND(
        SUM(f.net_sales_usd) * 100.0 / SUM(SUM(f.net_sales_usd)) OVER (PARTITION BY g.country_name), 2
    ) AS country_product_mix_pct
FROM fact_sales f
JOIN dim_geography g ON f.geography_key = g.geography_key
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY g.country_name, p.product_name, p.therapeutic_area
ORDER BY g.country_name, net_sales_usd DESC;
