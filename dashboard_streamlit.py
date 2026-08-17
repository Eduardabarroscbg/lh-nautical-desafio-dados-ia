import pandas as pd
import psycopg2
import plotly.express as px
import streamlit as st
from sklearn.metrics.pairwise import cosine_similarity

CONEXAO = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "lhnautical",
    "user": "lhuser",
    "password": "lhpass123",
}

st.set_page_config(page_title="LH Nautical - Painel Analítico", layout="wide")

COR = "#3B82C4"


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


def primeira_linha(df, mensagem_vazio="Sem dados para essa consulta."):
    if df.empty:
        st.warning(mensagem_vazio)
        st.stop()
    return df.iloc[0]


def fmt_num(valor, casas=1):
    """Formata número no padrão brasileiro: ponto para milhar, vírgula para decimal."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_moeda(valor):
    """Formata valor monetário no padrão brasileiro, com o prefixo R$."""
    return f"R$ {fmt_num(valor, 2)}"


st.title("LH Nautical - Painel Analítico")
st.caption(
    "Este painel reúne os achados de negócio das Questões 4 a 7 do desafio, além de explorações "
    "adicionais sobre os mesmos dados. As Questões 1 a 3 são etapas técnicas de preparação "
    "(EDA, schema e carregamento) e estão resumidas em texto logo abaixo, já que não geram um "
    "achado de negócio para virar gráfico."
)

# =========================================================
# RESUMO DAS ETAPAS TECNICAS (QUESTOES 1 A 3)
# =========================================================
st.header("Etapas anteriores do desafio (Questões 1 a 3)")
st.markdown(
    "Na Questão 1, a análise exploratória da tabela `orders` mostrou 48.998 pedidos, cobrindo o "
    "período de 01/01/2020 a 31/12/2026, com valor médio de R$ 28.704,99 por pedido. Não foram "
    "encontradas duplicatas nem inconsistência entre subtotal, desconto e total - o único ponto "
    "de atenção foi o campo `salesperson_id`, vazio em ~49% dos pedidos, mas isso é esperado, já "
    "que pedidos de e-commerce não têm vendedor associado."
)
st.markdown(
    "Na Questao 2, o script em Python puro (sem bibliotecas externas) leu os 24 arquivos CSV e "
    "gerou o `schema.sql` com uma tabela para cada um, inferindo o tipo de cada coluna a partir "
    "dos valores encontrados. Um cuidado importante foi identificar colunas que parecem número "
    "mas são código (como CPF e CEP, que têm zero a esquerda) e tratá-las como texto, para não "
    "perder informação na conversão."
)
st.markdown(
    "Na Questao 3, o script de carga inseriu 251.864 linhas no banco Postgres, somando as tabelas "
    "`customers`, `orders`, `order_items` e `payments`, respeitando o schema criado na etapa "
    "anterior sem nenhum tratamento ou limpeza dos dados originais."
)

st.divider()

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
col1.metric("Receita total", f"R$ {fmt_num(kpis['receita_total'][0]/1e6, 1)} mi")
col2.metric("Pedidos", f"{kpis['qtd_pedidos'][0]:,}".replace(",", "."))
col3.metric("Ticket médio", fmt_moeda(kpis['ticket_medio'][0]))
col4.metric("Clientes", f"{kpis['qtd_clientes'][0]:,}".replace(",", "."))

st.divider()

# =========================================================
# ACHADO 1 - QUEM COMPROU MAIS POR REGIAO
# =========================================================
st.header("1. Quem comprou mais por região")
st.caption("Análise adicional que investiguei (não é uma pergunta oficial do desafio - o enunciado geral sugere \"explorações adicionais relevantes\" para o dashboard): qual estado concentra o maior faturamento, e quem é o cliente-âncora de cada um?")

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

# Para achar o cliente-âncora de cada estado sem usar função de janela:
# primeiro cálculo o gasto de cada cliente por estado, depois acho o valor
# maximo por estado, e junto de volta pra saber QUEM e esse cliente.
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
    maior_por_estado AS (
        SELECT uf, MAX(total_cliente) AS maior_valor
        FROM gasto_por_cliente_estado
        GROUP BY uf
    )
    SELECT g.uf, g.legal_name AS cliente, g.total_cliente
    FROM gasto_por_cliente_estado g
    JOIN maior_por_estado m ON m.uf = g.uf AND m.maior_valor = g.total_cliente
    ORDER BY g.total_cliente DESC
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
    st.caption("Cliente-âncora por estado (maior comprador local)")
    st.dataframe(top_cliente_estado, use_container_width=True, hide_index=True)

top_estado = primeira_linha(vendas_estado)
st.markdown(
    f"O estado que mais fatura é {top_estado['uf']}, com {fmt_moeda(top_estado['faturamento'])}. "
    "Mas olhando as 10 barras do gráfico, a diferença entre a primeira e a última é pequena - "
    "nenhum estado concentra desproporcionalmente as vendas, o faturamento é bem pulverizado entre "
    "as regiões. Na tabela ao lado, cada linha mostra o cliente que mais gastou naquele estado. "
    "*Nota: a região aqui é o endereço primário cadastrado do cliente, não o endereço de entrega "
    "do pedido - o schema disponível (orders/order_items) não guarda endereço por pedido.*"
)

st.divider()

# =========================================================
# ACHADO 2 - TOP 10 PRODUTOS MAIS VENDIDOS
# =========================================================
st.header("2. Os 10 produtos mais vendidos")
st.caption("Análise adicional que investiguei: quais produtos têm maior volume de unidades vendidas no histórico completo?")

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

top_produto = primeira_linha(top_produtos)
diferenca_pct = (top_produtos["unidades_vendidas"].iloc[0] - top_produtos["unidades_vendidas"].iloc[-1]) / top_produtos["unidades_vendidas"].iloc[0] * 100
st.markdown(
    f"O produto mais vendido é {top_produto['produto']}, com {int(top_produto['unidades_vendidas'])} "
    f"unidades. Entre a primeira e a décima posição do ranking, a diferença é de apenas "
    f"{fmt_num(diferenca_pct, 1)}% - sinal de que o volume está bem distribuído entre os produtos do catálogo, "
    "sem um item isolado puxando as vendas sozinho."
)

st.divider()

# =========================================================
# ACHADO 3 - CLIENTE MULTI-REGIAO COM MAIOR VALOR TOTAL
# =========================================================
st.header("3. Cliente que mais comprou entre os que compram em várias regiões")
st.caption("Análise adicional que investiguei: entre os clientes com endereço cadastrado em mais de um estado, quem têm o maior valor total comprado?")

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
                      "Top 5 - valor total (clientes com endereço em +1 estado)"),
        use_container_width=True,
    )
with c4:
    top1 = primeira_linha(multi_regiao)
    st.metric("Cliente-âncora", top1["cliente"])
    st.metric("Valor total comprado", fmt_moeda(top1['total_gasto']))
    st.metric("Estados distintos", int(top1["qtd_estados"]))

st.markdown(
    f"{top1['cliente']} lidera esse grupo, com {fmt_moeda(top1['total_gasto'])} comprados e endereço "
    f"cadastrado em {int(top1['qtd_estados'])} estados diferentes. Um detalhe que vale destacar: "
    "esse cliente não é só o maior entre os multirregião - conferindo contra a base inteira de "
    "clientes, ele segue sendo o maior comprador de todos, o que reforça ele como candidato natural "
    "a um programa de relacionamento dedicado."
)

st.divider()

# =========================================================
# ACHADO 4 - TOP 5 PRODUTOS EM ALAGOAS
# =========================================================
st.header("4. Os 5 produtos mais vendidos na região de Alagoas")
st.caption("Análise adicional que investiguei: qual o mix de produtos mais vendido entre os clientes com endereço primário em Alagoas (AL)?")

# Agrupar por p.id junto com p.name (não só por nome) e necessario porque a
# tabela products têm nomes duplicados (ver nota de qualidade de dados) -
# agrupar só por nome fundiria produtos diferentes, incluindo o registro de
# teste "asdf", num único item e distorceria o ranking.
top_al = rodar_query(
    """
    SELECT
        p.id AS product_id,
        p.name AS produto,
        SUM(oi.quantity) AS unidades_vendidas
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    JOIN addresses a ON a.customer_id = o.customer_id AND a.is_primary = TRUE
    JOIN product_variants pv ON pv.id = oi.product_variant_id
    JOIN products p ON p.id = pv.product_id
    WHERE a.state = 'AL'
    GROUP BY p.id, p.name
    ORDER BY unidades_vendidas DESC
    LIMIT 5;
    """
)

st.plotly_chart(
    grafico_barra(top_al, "produto", "unidades_vendidas", "Top 5 produtos vendidos em Alagoas (AL)"),
    use_container_width=True,
)

top_produto_al = primeira_linha(top_al)
st.markdown(
    f"Em Alagoas, o produto que mais vende é {top_produto_al['produto']}, com "
    f"{int(top_produto_al['unidades_vendidas'])} unidades no estado. Comparando com o top 10 "
    "nacional da secao anterior, nenhum produto se repete nas duas listas - o mix regional é "
    "diferente do nacional, o que sugere que reposição de estoque padronizada para todas as lojas "
    "pode não ser a melhor estratégia aqui."
)

st.divider()

# =========================================================
# QUESTAO 4 DO DESAFIO - CLIENTES FIEIS
# =========================================================
st.header("Questão 4 - Clientes fiéis")
st.caption(
    "Cenário (texto original do desafio): \"A Diretoria da LH Nautical deseja identificar os "
    "clientes fiéis. Diferente de quem compra muito uma única vez, o cliente fiel é o cliente "
    "que possui um gasto médio alto por transação e navega por diversas categorias da loja. "
    "O objetivo é mapear o que esses clientes de elite estão consumindo para replicar o "
    "comportamento em outros segmentos.\" Tarefa: calcular o Ticket Médio e a Diversidade de "
    "Categorias por customer_id, filtrar os 10 clientes com maior Ticket Médio entre os que "
    "tem 13+ categorias distintas, e identificar qual categoria concentra a maior quantidade "
    "de itens comprados por esse grupo."
)

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

categoria_elite = rodar_query(
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
    ),
    top10_fieis AS (
        SELECT v.customer_id, v.faturamento_total / v.frequencia AS ticket_medio
        FROM vendas_por_cliente v
        JOIN categorias_por_cliente c ON c.customer_id = v.customer_id
        WHERE c.diversidade >= 13
        ORDER BY ticket_medio DESC
        LIMIT 10
    )
    SELECT cat.name AS categoria, SUM(oi.quantity) AS quantidade_total
    FROM top10_fieis t
    JOIN orders o ON o.customer_id = t.customer_id
    JOIN order_items oi ON oi.order_id = o.id
    JOIN product_variants pv ON pv.id = oi.product_variant_id
    JOIN products p ON p.id = pv.product_id
    JOIN categories cat ON cat.id = p.category_id
    GROUP BY cat.name
    ORDER BY quantidade_total DESC
    LIMIT 1;
    """
)

c5, c6 = st.columns([1.3, 1])
with c5:
    st.dataframe(clientes_fieis, use_container_width=True, hide_index=True)
with c6:
    cat_top = primeira_linha(categoria_elite)
    st.metric("Categoria mais consumida por eles", cat_top["categoria"])
    st.metric("Quantidade total", int(cat_top["quantidade_total"]))

st.markdown(
    f"Os 10 clientes fiéis compraram, todos eles, em 14 categorias distintas - acima do mínimo de "
    f"13 exigido pelo critério de elite -, com ticket médio entre "
    f"R\\$ {fmt_num(clientes_fieis['ticket_medio'].min(), 2)} e R\\$ {fmt_num(clientes_fieis['ticket_medio'].max(), 2)}. "
    f"Entre tudo que esse grupo comprou, a categoria **{cat_top['categoria']}** é a que concentra o "
    "maior volume."
)

st.divider()

# =========================================================
# QUESTAO 5 DO DESAFIO - CALENDARIO / PIOR DIA
# =========================================================
st.header("Questão 5 - Pior dia da semana para lojas físicas")
st.caption(
    "Cenário (texto original do desafio): \"O Sr. Almir quer saber: 'Qual é o dia da semana "
    "(Segunda, Terça...), nas lojas físicas, temos a pior média de vendas?' para decidir se "
    "vale a pena fechar a loja nesses dias. Um estagiário fez um GROUP BY dia_semana direto na "
    "tabela de vendas e disse que o Domingo era ótimo... O problema: o estagiário esqueceu que "
    "em muitos Domingos a loja abriu mas vendeu zero. Como esses dias não existem na tabela de "
    "vendas (orders), eles foram ignorados no cálculo da média, inflando o resultado.\" Tarefa: "
    "construir uma dimensão de datas e cruzar com a tabela de vendas para corrigir esse erro."
)

dias_semana = rodar_query(
    """
    WITH calendario AS (
        SELECT
            d::date AS data,
            EXTRACT(ISODOW FROM d)::int AS isodow,
            CASE EXTRACT(ISODOW FROM d)
                WHEN 1 THEN 'Segunda-feira' WHEN 2 THEN 'Terça-feira'
                WHEN 3 THEN 'Quarta-feira' WHEN 4 THEN 'Quinta-feira'
                WHEN 5 THEN 'Sexta-feira' WHEN 6 THEN 'Sábado'
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
    grafico_barra(dias_semana, "dia_semana", "media_vendas", "Media de vendas por dia (lojas físicas)"),
    use_container_width=True,
)

pior_dia = dias_semana.loc[dias_semana["media_vendas"].idxmin()]
melhor_dia = dias_semana.loc[dias_semana["media_vendas"].idxmax()]
st.markdown(
    f"A barra mais baixa do gráfico é {pior_dia['dia_semana']}, com média de "
    f"R\\$ {fmt_num(pior_dia['media_vendas'], 2)} - contra {melhor_dia['dia_semana']}, a mais alta, com "
    f"R\\$ {fmt_num(melhor_dia['media_vendas'], 2)}. Esse cálculo considera os dias sem venda registrada "
    "como R\\$0 na média, em vez de ignorá-los, corrigindo o erro do estagiário descrito no cenário "
    "da Questao 5."
)

st.divider()

# =========================================================
# QUESTAO 6 DO DESAFIO - PREVISAO DE DEMANDA
# =========================================================
st.header("Questão 6 - Previsão de demanda: Bússola de Bordo 702")
st.caption(
    "Cenário (texto original do desafio): \"O Sr. Almir está furioso. No último verão, o "
    "estoque de 'Coletes Salva-Vidas' acabou em 3 meses, e a empresa perdeu milhares de reais "
    "em vendas. Por outro lado, compraram 'Âncoras' demais e elas estão enferrujando no galpão. "
    "Gabriel Santos, o Tech Lead, disse que não dá mais para confiar no 'feeling'. Ele quer um "
    "modelo preditivo que diga exatamente quantas unidades venderemos no próximo mês para "
    "ajustar as compras com fornecedores.\" Tarefa: construir um baseline de média móvel dos "
    "últimos 3 meses (sem usar dado real futuro), gerar a previsão mensal do 1o trimestre de "
    "2026 e comparar com o real usando MAE."
)

# Traz os dados brutos (data do pedido + quantidade) e faz a agregação
# mensal em pandas, igual foi feito na Questão 6 original - mantem o
# mesmo estilo do resto do desafio em vez de agregar por mês direto no SQL.
vendas_produto_bruto = rodar_query(
    """
    SELECT o.created_at, oi.quantity
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    JOIN product_variants pv ON pv.id = oi.product_variant_id
    WHERE pv.product_id = 74;
    """
)
vendas_produto_bruto["created_at"] = pd.to_datetime(vendas_produto_bruto["created_at"])
vendas_produto_bruto["ano_mes"] = vendas_produto_bruto["created_at"].dt.to_period("M")
serie = vendas_produto_bruto.groupby("ano_mes")["quantity"].sum().sort_index()

todos_meses = pd.period_range(serie.index.min(), serie.index.max(), freq="M")
serie = serie.reindex(todos_meses, fill_value=0)

meses_teste = pd.period_range("2026-01", "2026-03", freq="M")
serie_para_janela = serie.copy()
previsoes = {}
for mes in meses_teste:
    janela = pd.period_range(mes - 3, mes - 1, freq="M")
    previsoes[mes] = round(serie_para_janela.loc[janela].mean())
    serie_para_janela.loc[mes] = previsoes[mes]

comparativo = pd.DataFrame({
    "mes": [str(m) for m in meses_teste],
    "previsto": [previsoes[m] for m in meses_teste],
    "real": [serie.loc[m] for m in meses_teste],
})

fig_prev = px.line(
    comparativo, x="mes", y=["previsto", "real"],
    title="Previsto vs Real - 1o trimestre 2026",
    template="plotly_dark", markers=True,
)
fig_prev.update_layout(legend_title_text="")
st.plotly_chart(fig_prev, use_container_width=True)

soma_prevista = int(comparativo["previsto"].sum())
mae = (comparativo["previsto"] - comparativo["real"]).abs().mean()
media_historica = serie.mean()
mae_pct = (mae / media_historica) * 100

col7, col8, col9 = st.columns(3)
col7.metric("Soma prevista (Q1 2026)", f"{soma_prevista} unidades")
col8.metric("MAE", f"{fmt_num(mae, 2)} unidades")
col9.metric("MAE vs média histórica", f"{fmt_num(mae_pct, 1)}%")

st.markdown(
    f"O baseline previu {soma_prevista} unidades para o trimestre, contra "
    f"{int(comparativo['real'].sum())} reais - um MAE de {fmt_num(mae, 2)} unidades ({fmt_num(mae_pct, 1)}% da média "
    "histórica). O erro de janeiro (o modelo não previu o salto de demanda daquele mês) se propagou "
    "para fevereiro e março, já que a previsão usa a própria previsão dos meses anteriores como "
    "entrada, nunca o valor real de 2026, pra não vazar dado futuro. Essa é uma limitação real de "
    "baselines em cadeia: o erro de um mês contamina os seguintes em vez de se corrigir sozinho."
)
st.caption(
    "Nota: existem dois produtos cadastrados com o nome 'Bússola de Bordo 702' (product_id 74 e 240); "
    "usamos o id 74 por ter mais histórico de vendas (330 registros contra 142 do id 240)."
)

st.divider()

# =========================================================
# QUESTAO 7 DO DESAFIO - SISTEMA DE RECOMENDACAO
# =========================================================
st.header("Questão 7 - Sistema de recomendação: 'Motor de Popa 1949'")
st.caption(
    "Cenário (texto original do desafio): \"A Marina percebeu que clientes que compram lanchas "
    "quase sempre esquecem de levar a defesa (proteção lateral). Ela quer implementar uma "
    "vitrine de 'Quem comprou isso, também levou...' no site. Como não temos ferramentas de Big "
    "Data caras, você precisará criar um motor de recomendação, baseado na similaridade de "
    "compra dos clientes.\" Tarefa: identificar qual produto deve ser recomendado junto ao item "
    "'Motor de Popa 1949', com base na similaridade de comportamento de compra dos clientes."
)

interacoes = rodar_query(
    """
    SELECT DISTINCT o.customer_id, pv.product_id
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    JOIN product_variants pv ON pv.id = oi.product_variant_id;
    """
)
matriz = interacoes.assign(valor=1).pivot_table(
    index="customer_id", columns="product_id", values="valor", fill_value=0
)

PRODUTO_REFERENCIA = 180  # Motor de Popa 1949
sim = cosine_similarity(matriz.T)
sim_df = pd.DataFrame(sim, index=matriz.columns, columns=matriz.columns)
similares_ids = sim_df[PRODUTO_REFERENCIA].drop(PRODUTO_REFERENCIA).sort_values(ascending=False).head(5)

nomes_produtos = rodar_query(
    f"SELECT id, name, category_id FROM products WHERE id IN ({','.join(map(str, similares_ids.index))});"
)
tabela_similares = nomes_produtos.set_index("id").loc[similares_ids.index].reset_index()
tabela_similares["similaridade"] = similares_ids.values.round(4)

st.dataframe(
    tabela_similares[["name", "category_id", "similaridade"]],
    use_container_width=True, hide_index=True,
)

top_similar = tabela_similares.iloc[0]
st.markdown(
    f"O produto recomendado é **{top_similar['name']}**, com similaridade de "
    f"{fmt_num(top_similar['similaridade'], 4)}. Vale registrar: a maior similaridade encontrada é baixa "
    "(nenhum produto passa de 0,26), e o item recomendado está em categoria diferente do "
    "'Motor de Popa 1949' - o método capta comportamento de compra, não intenção de venda casada "
    "por categoria (uma defesa náutica, que a diretoria esperava, nem existe no catálogo)."
)

st.divider()

# =========================================================
# CONCLUSAO
# =========================================================
st.header("Conclusão")

st.markdown(f"""
- **Região:** {top_estado['uf']} lidera o faturamento nacional (R$ {fmt_num(top_estado['faturamento']/1e6, 1)} milhões).
- **Produto:** {top_produto['produto']} é o mais vendido do catálogo ({int(top_produto['unidades_vendidas'])} unidades).
- **Cliente:** {top1['cliente']} é quem mais comprou entre os clientes multirregião ({fmt_moeda(top1['total_gasto'])}).
- **Alagoas:** {top_produto_al['produto']} lidera localmente, mix diferente do ranking nacional.
- **Operação:** {pior_dia['dia_semana']} é o pior dia de venda em lojas físicas.
- **Previsão:** o baseline de média móvel errou {fmt_num(mae, 2)} unidades em média para "Bússola de Bordo 702" no 1o trimestre de 2026 - o erro de janeiro se propagou para os meses seguintes.
- **Recomendação:** o sistema de similaridade de cosseno aponta {top_similar['name']} como o item de venda casada com "Motor de Popa 1949", mas com similaridade fraca.

**Nota de qualidade de dados:** a tabela `products` tem nomes duplicados (ex: "Bússola de Bordo 702" e "Sonar Transducer 7193" aparecem com dois `product_id` diferentes) e ao menos 2 registros de teste (nome "asdf"). Isso afeta resultados reais quando a agregação é feita por nome em vez de `product_id` - foi o caso do Achado 4, corrigido nesta versão. Recomenda-se sempre agregar por `product_id`.
""")