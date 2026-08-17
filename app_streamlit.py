import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px

CONEXAO = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "lhnautical",
    "user": "lhuser",
    "password": "lhpass123",
}

st.set_page_config(page_title="LH Nautical - Painel Analitico", layout="wide")

COR = "#3B82C4"  # uma cor só, sem esquema "1 barra destacada + resto neutro"


@st.cache_data
def rodar_query(sql):
    conexao = psycopg2.connect(**CONEXAO)
    df = pd.read_sql(sql, conexao)
    conexao.close()
    return df


def grafico_barra(df, x, y, titulo, horizontal=False):
    fig = px.bar(
        df, x=(y if horizontal else x), y=(x if horizontal else y),
        orientation="h" if horizontal else "v",
        title=titulo, template="plotly_dark",
        color_discrete_sequence=[COR],
    )
    fig.update_layout(showlegend=False, margin=dict(t=40, l=10, r=10, b=10))
    return fig


st.title("LH Nautical - Painel Analitico")
st.caption("Material complementar ao Desafio de Dados, construido sobre o banco da Questao 3.")

# =========================================================
# KPIs GERAIS
# =========================================================
kpis = rodar_query(
    """
    SELECT
        COUNT(*) AS qtd_pedidos,
        SUM(total) AS receita_total,
        ROUND(AVG(total), 2) AS ticket_medio,
        (SELECT COUNT(*) FROM customers) AS qtd_clientes
    FROM orders;
    """
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Receita total", f"R$ {kpis['receita_total'][0]/1e6:.1f} mi")
col2.metric("Pedidos", f"{kpis['qtd_pedidos'][0]:,}".replace(",", "."))
col3.metric("Ticket medio", f"R$ {kpis['ticket_medio'][0]:,.2f}")
col4.metric("Clientes", f"{kpis['qtd_clientes'][0]:,}".replace(",", "."))

st.divider()

# =========================================================
# ACHADO 1 - QUEM COMPROU MAIS POR REGIAO
# =========================================================
st.header("1. Quem comprou mais por regiao")

vendas_estado = rodar_query(
    """
    SELECT
        a.state AS uf,
        SUM(o.total) AS faturamento
    FROM orders o
    JOIN addresses a ON a.customer_id = o.customer_id AND a.is_primary = TRUE
    GROUP BY a.state
    ORDER BY faturamento DESC
    LIMIT 10;
    """
)

top_cliente_estado = rodar_query(
    """
    WITH gasto_por_cliente_estado AS (
        SELECT
            a.state AS uf,
            o.customer_id,
            c.legal_name,
            SUM(o.total) AS total_cliente
        FROM orders o
        JOIN addresses a ON a.customer_id = o.customer_id AND a.is_primary = TRUE
        JOIN customers c ON c.id = o.customer_id
        GROUP BY a.state, o.customer_id, c.legal_name
    ),
    ranking AS (
        SELECT *,
            ROW_NUMBER() OVER (PARTITION BY uf ORDER BY total_cliente DESC) AS posicao
        FROM gasto_por_cliente_estado
    )
    SELECT uf, legal_name AS cliente, total_cliente
    FROM ranking
    WHERE posicao = 1
    ORDER BY total_cliente DESC
    LIMIT 10;
    """
)

c1, c2 = st.columns([1.3, 1])
with c1:
    st.plotly_chart(
        grafico_barra(vendas_estado, "uf", "faturamento", "Faturamento total por UF (top 10)"),
        use_container_width=True,
    )
with c2:
    st.caption("Cliente-ancora por estado (maior comprador local)")
    st.dataframe(top_cliente_estado, use_container_width=True, hide_index=True)

st.divider()

# =========================================================
# ACHADO 2 - TOP 10 PRODUTOS MAIS VENDIDOS
# =========================================================
st.header("2. Os 10 produtos mais vendidos")

top_produtos = rodar_query(
    """
    SELECT
        p.id AS product_id,
        p.name AS produto,
        SUM(oi.quantity) AS unidades_vendidas
    FROM order_items oi
    JOIN product_variants pv ON pv.id = oi.product_variant_id
    JOIN products p ON p.id = pv.product_id
    GROUP BY p.id, p.name
    ORDER BY unidades_vendidas DESC
    LIMIT 10;
    """
)

st.plotly_chart(
    grafico_barra(
        top_produtos.sort_values("unidades_vendidas"),
        "produto", "unidades_vendidas",
        "Unidades vendidas por produto (top 10)", horizontal=True,
    ),
    use_container_width=True,
)

st.divider()

# =========================================================
# ACHADO 3 - CLIENTE MULTI-REGIAO COM MAIOR VALOR TOTAL
# =========================================================
st.header("3. Cliente que mais comprou entre os que compram em varias regioes")

multi_regiao = rodar_query(
    """
    WITH qtd_estados AS (
        SELECT customer_id, COUNT(DISTINCT state) AS qtd_estados
        FROM addresses
        GROUP BY customer_id
        HAVING COUNT(DISTINCT state) > 1
    ),
    gasto_cliente AS (
        SELECT customer_id, SUM(total) AS total_gasto
        FROM orders
        GROUP BY customer_id
    )
    SELECT
        g.customer_id,
        c.legal_name AS cliente,
        q.qtd_estados,
        g.total_gasto
    FROM gasto_cliente g
    JOIN qtd_estados q ON q.customer_id = g.customer_id
    JOIN customers c ON c.id = g.customer_id
    ORDER BY g.total_gasto DESC
    LIMIT 5;
    """
)

c3, c4 = st.columns([1.3, 1])
with c3:
    st.plotly_chart(
        grafico_barra(multi_regiao, "cliente", "total_gasto",
                      "Top 5 - valor total (clientes com endereco em +1 estado)"),
        use_container_width=True,
    )
with c4:
    top1 = multi_regiao.iloc[0]
    st.metric("Cliente-ancora", top1["cliente"])
    st.metric("Valor total comprado", f"R$ {top1['total_gasto']:,.2f}")
    st.metric("Estados distintos", int(top1["qtd_estados"]))

st.divider()

# =========================================================
# ACHADO 4 - TOP 5 PRODUTOS EM ALAGOAS
# =========================================================
st.header("4. Os 5 produtos mais vendidos na regiao de Alagoas")

top_al = rodar_query(
    """
    SELECT
        p.name AS produto,
        SUM(oi.quantity) AS unidades_vendidas
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    JOIN addresses a ON a.customer_id = o.customer_id AND a.is_primary = TRUE
    JOIN product_variants pv ON pv.id = oi.product_variant_id
    JOIN products p ON p.id = pv.product_id
    WHERE a.state = 'AL'
    GROUP BY p.name
    ORDER BY unidades_vendidas DESC
    LIMIT 5;
    """
)

st.plotly_chart(
    grafico_barra(top_al, "produto", "unidades_vendidas", "Top 5 produtos vendidos em Alagoas (AL)"),
    use_container_width=True,
)

st.divider()

# =========================================================
# ACHADOS DO DESAFIO (Questoes 1, 4, 5, 6, 7)
# =========================================================
st.header("Achados do desafio")
st.caption("Principais resultados das analises feitas ao longo das 7 questoes tecnicas.")

col5, col6 = st.columns(2)

with col5:
    st.subheader("Questao 5 - Pior dia para lojas fisicas")
    dias_semana = rodar_query(
        """
        WITH calendario AS (
            SELECT
                d::date AS data,
                EXTRACT(ISODOW FROM d)::int AS isodow,
                CASE EXTRACT(ISODOW FROM d)
                    WHEN 1 THEN 'Segunda-feira' WHEN 2 THEN 'Terca-feira'
                    WHEN 3 THEN 'Quarta-feira' WHEN 4 THEN 'Quinta-feira'
                    WHEN 5 THEN 'Sexta-feira' WHEN 6 THEN 'Sabado'
                    WHEN 7 THEN 'Domingo'
                END AS dia_semana
            FROM generate_series(
                (SELECT MIN(created_at)::date FROM orders),
                (SELECT MAX(created_at)::date FROM orders),
                interval '1 day'
            ) AS d
        ),
        vendas_diarias AS (
            SELECT created_at::date AS data, SUM(total) AS valor_venda
            FROM orders WHERE channel = 'pos'
            GROUP BY created_at::date
        )
        SELECT c.dia_semana, ROUND(AVG(COALESCE(v.valor_venda, 0)), 2) AS media_vendas
        FROM calendario c
        LEFT JOIN vendas_diarias v ON v.data = c.data
        GROUP BY c.dia_semana, c.isodow
        ORDER BY c.isodow;
        """
    )
    st.plotly_chart(
        grafico_barra(dias_semana, "dia_semana", "media_vendas", "Media de vendas por dia (lojas fisicas)"),
        use_container_width=True,
    )
    st.caption("Quinta-feira tem a pior media (R$ 157 mil) - considerando ate os dias sem venda registrada, evitando o erro do estagiario descrito na Questao 5.")

with col6:
    st.subheader("Questao 4 - Clientes fieis (ticket alto + diversidade)")
    clientes_fieis = rodar_query(
        """
        WITH vendas_por_cliente AS (
            SELECT o.customer_id, SUM(o.total) AS faturamento_total, COUNT(DISTINCT o.id) AS frequencia
            FROM orders o GROUP BY o.customer_id
        ),
        categorias_por_cliente AS (
            SELECT o.customer_id, COUNT(DISTINCT p.category_id) AS diversidade
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            JOIN product_variants pv ON pv.id = oi.product_variant_id
            JOIN products p ON p.id = pv.product_id
            GROUP BY o.customer_id
        )
        SELECT v.customer_id, ROUND(v.faturamento_total / v.frequencia, 2) AS ticket_medio, c.diversidade
        FROM vendas_por_cliente v
        JOIN categorias_por_cliente c ON c.customer_id = v.customer_id
        WHERE c.diversidade >= 13
        ORDER BY ticket_medio DESC
        LIMIT 10;
        """
    )
    st.dataframe(clientes_fieis, use_container_width=True, hide_index=True)
    st.caption("Os 10 clientes com maior ticket medio entre os que compraram 13+ categorias distintas. A categoria com maior volume entre eles e Helices (492 unidades).")

st.divider()

# =========================================================
# CONCLUSAO
# =========================================================
st.header("Conclusao")

top_estado = vendas_estado.iloc[0]
top_produto = top_produtos.iloc[0]
top_cliente_multi = multi_regiao.iloc[0]
top_produto_al = top_al.iloc[0]

st.markdown(f"""
- **Regiao:** {top_estado['uf']} lidera o faturamento nacional, com R$ {top_estado['faturamento']/1e6:.1f} milhoes.
- **Produto:** {top_produto['produto']} e o mais vendido do catalogo, com {int(top_produto['unidades_vendidas'])} unidades.
- **Cliente:** {top_cliente_multi['cliente']} e quem mais comprou entre os clientes com endereco em mais de um estado, somando R$ {top_cliente_multi['total_gasto']:,.2f}.
- **Alagoas:** o mix local difere do nacional - {top_produto_al['produto']} lidera as vendas no estado, mas nao aparece no top 10 geral.
- **Operacao:** quinta-feira e o pior dia de venda nas lojas fisicas (Questao 5); o modelo de previsao para "Bussola de Bordo 702" (Questao 6) errou por 16,3 unidades em media no 1º trimestre de 2026, por nao antecipar picos pontuais de demanda.

**Nota de qualidade de dados:** a tabela `products` tem nomes duplicados (ex: "Bussola de Bordo 702" e "Sonar Transducer 7193" aparecem com dois `product_id` diferentes) e ao menos 2 registros de teste (nome "asdf"). Recomenda-se sempre agregar por `product_id`, nunca por nome, e tratar esse ponto antes de qualquer decisao de compra baseada no catalogo.
""")