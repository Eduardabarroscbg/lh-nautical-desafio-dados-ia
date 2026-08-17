WITH calendario AS (
    SELECT
        d::date AS data,
        EXTRACT(ISODOW FROM d)::int AS isodow,
        CASE EXTRACT(ISODOW FROM d)
            WHEN 1 THEN 'Segunda-feira'
            WHEN 2 THEN 'Terça-feira'
            WHEN 3 THEN 'Quarta-feira'
            WHEN 4 THEN 'Quinta-feira'
            WHEN 5 THEN 'Sexta-feira'
            WHEN 6 THEN 'Sábado'
            WHEN 7 THEN 'Domingo'
        END AS dia_semana
    FROM generate_series(
        (SELECT MIN(created_at)::date FROM orders),
        (SELECT MAX(created_at)::date FROM orders),
        interval '1 day'
    ) AS d
),
vendas_diarias AS (
    SELECT
        created_at::date AS data,
        SUM(total) AS valor_venda
    FROM orders
    WHERE channel = 'pos'
    GROUP BY created_at::date
)
SELECT
    c.dia_semana,
    ROUND(AVG(COALESCE(v.valor_venda, 0)), 2) AS media_vendas
FROM calendario c
LEFT JOIN vendas_diarias v ON v.data = c.data
GROUP BY c.dia_semana, c.isodow
ORDER BY c.isodow;