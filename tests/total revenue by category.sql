SELECT p.category, ROUND(SUM(f.line_revenue), 2) AS total_revenue
FROM gold.fact_orders f
JOIN gold.dim_product p ON f.product_key = p.product_key
GROUP BY p.category
ORDER BY total_revenue DESC;