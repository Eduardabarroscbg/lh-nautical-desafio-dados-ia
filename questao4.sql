WITH vendas_por_cliente AS (
    SELECT
        o.customer_id,
        SUM(o.total) AS faturamento_total,
        COUNT(DISTINCT o.id) AS frequencia
    FROM orders o
    GROUP BY o.customer_id
),
categorias_por_cliente AS (
    SELECT
        o.customer_id,
        COUNT(DISTINCT p.category_id) AS diversidade_categorias
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.id
    JOIN product_variants pv ON pv.id = oi.product_variant_id
    JOIN products p ON p.id = pv.product_id
    GROUP BY o.customer_id
),
metricas_cliente AS (
    SELECT
        v.customer_id,
        v.faturamento_total,
        v.frequencia,
        v.faturamento_total / v.frequencia AS ticket_medio,
        c.diversidade_categorias
    FROM vendas_por_cliente v
    JOIN categorias_por_cliente c ON c.customer_id = v.customer_id
),
top_10_fieis AS (
    SELECT customer_id, faturamento_total, frequencia, ticket_medio, diversidade_categorias
    FROM metricas_cliente
    WHERE diversidade_categorias >= 13
    ORDER BY ticket_medio DESC, customer_id ASC
    LIMIT 10
)
SELECT
    customer_id,
    faturamento_total,
    frequencia,
    ROUND(ticket_medio, 2) AS ticket_medio,
    diversidade_categorias
FROM top_10_fieis;


WITH vendas_por_cliente AS (
    SELECT
        o.customer_id,
        SUM(o.total) AS faturamento_total,
        COUNT(DISTINCT o.id) AS frequencia
    FROM orders o
    GROUP BY o.customer_id
),
categorias_por_cliente AS (
    SELECT
        o.customer_id,
        COUNT(DISTINCT p.category_id) AS diversidade_categorias
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.id
    JOIN product_variants pv ON pv.id = oi.product_variant_id
    JOIN products p ON p.id = pv.product_id
    GROUP BY o.customer_id
),
metricas_cliente AS (
    SELECT
        v.customer_id,
        v.faturamento_total / v.frequencia AS ticket_medio,
        c.diversidade_categorias
    FROM vendas_por_cliente v
    JOIN categorias_por_cliente c ON c.customer_id = v.customer_id
),
top_10_fieis AS (
    SELECT customer_id
    FROM metricas_cliente
    WHERE diversidade_categorias >= 13
    ORDER BY ticket_medio DESC, customer_id ASC
    LIMIT 10
)
SELECT
    p.category_id,
    cat.name AS nome_categoria,
    SUM(oi.quantity) AS quantidade_total
FROM top_10_fieis t
JOIN orders o ON o.customer_id = t.customer_id
JOIN order_items oi ON oi.order_id = o.id
JOIN product_variants pv ON pv.id = oi.product_variant_id
JOIN products p ON p.id = pv.product_id
JOIN categories cat ON cat.id = p.category_id
GROUP BY p.category_id, cat.name
ORDER BY quantidade_total DESC
LIMIT 1;