"""
Dashboard LH Nautical - material complementar ao Desafio de Dados
Gera um PDF com os 4 achados obrigatorios + 1 insight extra (ticket medio por estado)

Como rodar:
    pip install psycopg2-binary pandas matplotlib
    python gerar_dashboard.py

Saida: dashboard_lh_nautical.pdf
"""

import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

CONEXAO = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "lhnautical",
    "user": "lhuser",
    "password": "lhpass123",
}


def rodar_query(sql):
    conexao = psycopg2.connect(**CONEXAO)
    df = pd.read_sql(sql, conexao)
    conexao.close()
    return df


# =========================================================
# QUERIES
# =========================================================

QUERY_ACHADO1 = """
SELECT
    ad.state AS uf,
    COUNT(DISTINCT o.id) AS numero_pedidos,
    COUNT(DISTINCT o.customer_id) AS numero_clientes,
    ROUND(SUM(o.total)::numeric, 2) AS total_gasto
FROM orders o
JOIN addresses ad ON ad.customer_id = o.customer_id AND ad.is_primary = TRUE
GROUP BY ad.state
ORDER BY total_gasto DESC
LIMIT 10;
"""

QUERY_ACHADO2 = """
SELECT
    p.id,
    p.name,
    SUM(oi.quantity) AS quantidade_total,
    ROUND(SUM(oi.line_total)::numeric, 2) AS receita_total
FROM order_items oi
JOIN product_variants pv ON pv.id = oi.product_variant_id
JOIN products p ON p.id = pv.product_id
GROUP BY p.id, p.name
ORDER BY quantidade_total DESC
LIMIT 10;
"""

# Achado 3 precisa separar as duas agregações (estados distintos x valor gasto)
# em CTEs, senão o JOIN direto entre orders e addresses multiplica o total
# gasto pelo numero de enderecos do cliente.
QUERY_ACHADO3 = """
WITH estados_por_cliente AS (
    SELECT customer_id, COUNT(DISTINCT state) AS numero_estados
    FROM addresses
    GROUP BY customer_id
    HAVING COUNT(DISTINCT state) >= 2
),
gasto_por_cliente AS (
    SELECT customer_id, SUM(total) AS total_gasto
    FROM orders
    GROUP BY customer_id
)
SELECT
    g.customer_id,
    c.legal_name,
    e.numero_estados,
    ROUND(g.total_gasto::numeric, 2) AS total_gasto
FROM gasto_por_cliente g
JOIN estados_por_cliente e ON e.customer_id = g.customer_id
JOIN customers c ON c.id = g.customer_id
ORDER BY total_gasto DESC
LIMIT 5;
"""

QUERY_ACHADO4 = """
SELECT
    p.name,
    SUM(oi.quantity) AS quantidade_total,
    ROUND(SUM(oi.line_total)::numeric, 2) AS receita_total
FROM order_items oi
JOIN orders o ON o.id = oi.order_id
JOIN addresses ad ON ad.customer_id = o.customer_id AND ad.is_primary = TRUE
JOIN product_variants pv ON pv.id = oi.product_variant_id
JOIN products p ON p.id = pv.product_id
WHERE ad.state = 'AL'
GROUP BY p.name
ORDER BY quantidade_total DESC
LIMIT 5;
"""

QUERY_EXTRA_TICKET_MEDIO = """
SELECT
    ad.state AS uf,
    COUNT(o.id) AS total_pedidos,
    ROUND(AVG(o.total)::numeric, 2) AS ticket_medio
FROM orders o
JOIN addresses ad ON ad.customer_id = o.customer_id AND ad.is_primary = TRUE
GROUP BY ad.state
ORDER BY ticket_medio DESC
LIMIT 10;
"""

QUERY_KPIS = """
SELECT
    COUNT(*) AS qtd_pedidos,
    ROUND(SUM(total)::numeric, 2) AS receita_total,
    ROUND(AVG(total)::numeric, 2) AS ticket_medio,
    (SELECT COUNT(*) FROM customers) AS qtd_clientes
FROM orders;
"""


def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    print("Rodando queries no banco...")
    kpis = rodar_query(QUERY_KPIS).iloc[0]
    achado1 = rodar_query(QUERY_ACHADO1)
    achado2 = rodar_query(QUERY_ACHADO2)
    achado3 = rodar_query(QUERY_ACHADO3)
    achado4 = rodar_query(QUERY_ACHADO4)
    extra = rodar_query(QUERY_EXTRA_TICKET_MEDIO)

    print("Gerando PDF...")
    with PdfPages("dashboard_lh_nautical.pdf") as pdf:

        # ---------- PAGINA 1: CAPA ----------
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.1, 0.75, "LH Nautical", fontsize=32, weight="bold")
        fig.text(0.1, 0.68, "Painel Analitico - Material Complementar", fontsize=16)
        fig.text(0.1, 0.60, "Desafio de Dados | Base: orders, order_items, customers,\n"
                             "addresses, products, product_variants (2020-2026)",
                 fontsize=11, color="gray")

        kpi_texto = (
            f"Receita total: {formatar_moeda(kpis['receita_total'])}\n"
            f"Pedidos: {int(kpis['qtd_pedidos']):,}".replace(",", ".") + "\n"
            f"Ticket medio: {formatar_moeda(kpis['ticket_medio'])}\n"
            f"Clientes: {int(kpis['qtd_clientes']):,}".replace(",", ".")
        )
        fig.text(0.1, 0.30, kpi_texto, fontsize=13, va="top")
        plt.axis("off")
        pdf.savefig(fig)
        plt.close(fig)

        # ---------- PAGINA 2: ACHADO 1 ----------
        fig, ax = plt.subplots(figsize=(11, 8.5))
        dados = achado1.sort_values("total_gasto")
        ax.barh(dados["uf"], dados["total_gasto"] / 1e6, color="#2c6e91")
        ax.set_xlabel("Faturamento (R$ milhoes)")
        ax.set_title("Achado 1 - Quem comprou mais por regiao (top 10 estados)", fontsize=14, weight="bold")
        top_estado = achado1.iloc[0]
        ax.text(0.98, 0.02,
                f"Lider: {top_estado['uf']} - {formatar_moeda(top_estado['total_gasto'])} "
                f"({int(top_estado['numero_pedidos'])} pedidos, {int(top_estado['numero_clientes'])} clientes)",
                transform=ax.transAxes, ha="right", fontsize=9, color="gray")
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # ---------- PAGINA 3: ACHADO 2 ----------
        fig, ax = plt.subplots(figsize=(11, 8.5))
        dados = achado2.sort_values("quantidade_total")
        ax.barh(dados["name"], dados["quantidade_total"], color="#3d8361")
        ax.set_xlabel("Unidades vendidas")
        ax.set_title("Achado 2 - Os 10 produtos mais vendidos", fontsize=14, weight="bold")
        top_produto = achado2.iloc[0]
        ax.text(0.98, 0.02,
                f"Campeao: {top_produto['name']} - {int(top_produto['quantidade_total'])} unidades vendidas",
                transform=ax.transAxes, ha="right", fontsize=9, color="gray")
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # ---------- PAGINA 4: ACHADO 3 ----------
        fig = plt.figure(figsize=(11, 8.5))
        top_cliente = achado3.iloc[0]
        fig.text(0.1, 0.85, "Achado 3", fontsize=14, weight="bold")
        fig.text(0.1, 0.80, "Cliente que mais comprou entre os que possuem enderecos em varias regioes",
                 fontsize=11, color="gray")

        fig.text(0.1, 0.65, top_cliente["legal_name"], fontsize=26, weight="bold")
        fig.text(0.1, 0.58, formatar_moeda(top_cliente["total_gasto"]), fontsize=20, color="#2c6e91")
        fig.text(0.1, 0.52, f"Presente em {int(top_cliente['numero_estados'])} estados distintos", fontsize=12)

        ax = fig.add_axes([0.1, 0.10, 0.8, 0.32])
        ax.axis("off")
        tabela = ax.table(
            cellText=achado3[["legal_name", "numero_estados", "total_gasto"]].values,
            colLabels=["Cliente", "Nº estados", "Total gasto (R$)"],
            loc="center",
            cellLoc="left",
        )
        tabela.auto_set_font_size(False)
        tabela.set_fontsize(9)
        tabela.scale(1, 1.6)
        pdf.savefig(fig)
        plt.close(fig)

        # ---------- PAGINA 5: ACHADO 4 ----------
        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.axis("off")
        ax.set_title("Achado 4 - Os 5 produtos mais vendidos na regiao de Alagoas (AL)",
                     fontsize=14, weight="bold", loc="left", pad=20)
        tabela = ax.table(
            cellText=achado4[["name", "quantidade_total", "receita_total"]].values,
            colLabels=["Produto", "Unidades vendidas", "Receita (R$)"],
            loc="upper center",
            cellLoc="left",
        )
        tabela.auto_set_font_size(False)
        tabela.set_fontsize(10)
        tabela.scale(1, 2.2)
        pdf.savefig(fig)
        plt.close(fig)

        # ---------- PAGINA 6: EXTRA ----------
        fig, ax = plt.subplots(figsize=(11, 8.5))
        dados = extra.sort_values("ticket_medio")
        ax.barh(dados["uf"], dados["ticket_medio"], color="#b3541e")
        ax.set_xlabel("Ticket medio (R$)")
        ax.set_title("Extra - Ticket medio por estado (top 10)", fontsize=14, weight="bold")
        ax.text(0.02, -0.12,
                "Complementa o Achado 1: mostra que o estado com mais faturamento total\n"
                "nao e necessariamente o de maior ticket medio por pedido.",
                transform=ax.transAxes, fontsize=9, color="gray")
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # ---------- PAGINA 7: CONCLUSAO ----------
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.1, 0.85, "Conclusao", fontsize=18, weight="bold")
        texto = (
            f"1. Regiao: {achado1.iloc[0]['uf']} lidera o faturamento nacional "
            f"({formatar_moeda(achado1.iloc[0]['total_gasto'])}).\n\n"
            f"2. Produto: {achado2.iloc[0]['name']} e o mais vendido "
            f"({int(achado2.iloc[0]['quantidade_total'])} unidades).\n\n"
            f"3. Cliente: {achado3.iloc[0]['legal_name']} e quem mais comprou entre os clientes "
            f"presentes em multiplas regioes ({formatar_moeda(achado3.iloc[0]['total_gasto'])}).\n\n"
            f"4. Alagoas: {achado4.iloc[0]['name']} lidera as vendas no estado "
            f"({int(achado4.iloc[0]['quantidade_total'])} unidades) - "
            f"mix diferente do ranking nacional.\n\n"
            "Nota de qualidade de dados: a tabela products possui nomes duplicados "
            "(ex.: 'Bussola de Bordo 702' e 'Sonar Transducer 7193' aparecem com dois "
            "product_id diferentes) e registros de teste (nome 'asdf'). Recomenda-se "
            "sempre agregar por product_id, nunca por nome."
        )
        fig.text(0.1, 0.75, texto, fontsize=11, va="top", wrap=True)
        plt.axis("off")
        pdf.savefig(fig)
        plt.close(fig)

    print("Pronto! Arquivo gerado: dashboard_lh_nautical.pdf")


if __name__ == "__main__":
    main()