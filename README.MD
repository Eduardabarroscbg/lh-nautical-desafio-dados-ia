 [![Certificado](https://img.shields.io/badge/📜_Ver_Certificado-2E86DE?style=for-the-badge)](./assets/certificado.png)

<div class="hero-image">
    <div class="frame">
        <img src="assets/cursolighthouse.png" alt="banner da indicium">
    </div>
</div>

 # LH Nautical — Desafio Lighthouse Dados e IA

Resolução completa do desafio técnico da LH Nautical: da leitura dos CSVs brutos até um painel analítico interativo, passando por schema, carga em PostgreSQL, análise exploratória, SQL avançado e dois modelos simples de dados (previsão de demanda e sistema de recomendação).

## Sumário

- [Estrutura do repositório](#estrutura-do-repositório)
- [Como rodar](#como-rodar)
- [Questão 1 — EDA](#questão-1--eda)
- [Questão 2 — Schema](#questão-2--schema)
- [Questão 3 — Carregamento](#questão-3--carregamento)
- [Questão 4 — Análise de clientes](#questão-4--análise-de-clientes)
- [Questão 5 — Dimensão de calendário](#questão-5--dimensão-de-calendário)
- [Questão 6 — Previsão de demanda](#questão-6--previsão-de-demanda)
- [Questão 7 — Sistema de recomendação](#questão-7--sistema-de-recomendação)
- [Dashboard](#dashboard)
- [Nota de qualidade de dados](#nota-de-qualidade-de-dados)


## Como rodar

**Pré-requisitos:** PostgreSQL rodando localmente, Python 3.10+.

```bash
pip install psycopg2-binary pandas scikit-learn streamlit plotly
```

**1. Gerar o schema a partir dos CSVs**
```bash
python questao2.1.py
# gera schema.sql
```

**2. Criar as tabelas no Postgres**

Rode o conteúdo de `schema.sql` no seu client SQL preferido (DBeaver, psql etc.), conectado a um banco `lhnautical` vazio.

**3. Carregar os dados**
```bash
python questao3.1.py
```

**4. Rodar as análises**

As questões 1, 4 e 5 são arquivos `.sql` — rode direto no DBeaver ou `psql`. As questões 6 e 7 são scripts Python:
```bash
python questao6.py
python questao7.py
```

**5. Subir o dashboard**
```bash
streamlit run dashboard_streamlit.py
```
Abre automaticamente em `http://localhost:8501`.

## Questão 1 — EDA

Análise exploratória da tabela `orders`, sem nenhum tratamento de dado (apenas observação/agregação), como pedido no enunciado.

| Métrica | Valor |
|---|---|
| Linhas | 48.998 |
| Período | 01/01/2020 a 31/12/2026 |
| Total (mín / méd / máx) | R$ 32,62 / R$ 28.704,99 / R$ 127.262,02 |
| Duplicatas | 0 |
| Outliers (regra do IQR) | 452 pedidos (0,92%) |
| Nulos em `salesperson_id` | 49,25% — concentrados 100% no canal e-commerce (padrão do canal, não falha de coleta) |

**Diagnóstico:** dados confiáveis para análise inicial, mas exigem cruzamento com outras tabelas (produtos, clientes) antes de decisões de negócio.

## Questão 2 — Schema

Script em Python puro (`csv`, `os`, `datetime` — sem pandas/dask/polars) que lê os 24 CSVs e infere o tipo de cada coluna (`INTEGER`, `BIGINT`, `NUMERIC`, `BOOLEAN`, `TIMESTAMP`, `TEXT`), gerando `schema.sql` com um `CREATE TABLE` por arquivo.

Cuidado principal: distinguir números de códigos disfarçados de número (CPF, CEP, chave de NF-e), que têm zero à esquerda ou tamanho incompatível com quantidade real — esses viram `TEXT`, não `INTEGER`.

## Questão 3 — Carregamento

Script Python (`psycopg2`) que insere os 24 CSVs no banco, respeitando o schema da Questão 2, sem nenhuma limpeza de dado. Inclui `TRUNCATE TABLE ... RESTART IDENTITY CASCADE` antes de cada carga, tornando o script idempotente (pode rodar várias vezes sem duplicar linhas).

**Validação:** soma de `customers + orders + order_items + payments` = **251.864** linhas.

## Questão 4 — Análise de clientes

Identifica os 10 clientes "fiéis" (maior ticket médio entre os que compraram em 13+ categorias distintas) e a categoria que esse grupo mais consome.

**Resultado:** todos os 10 clientes de elite compram em 14 categorias; a categoria com maior volume entre eles é **Hélices** (492 unidades).

## Questão 5 — Dimensão de calendário

Constrói uma dimensão de datas via `generate_series` e cruza com as vendas de loja física (`channel = 'pos'`), tratando dias sem venda como R$0 — corrigindo o erro do cenário (estagiário que ignorava dias sem venda, inflando a média de domingo).

**Resultado:** Quinta-feira tem a pior média (R$ 157.154,32); Quarta-feira, a melhor (R$ 173.605,44).

## Questão 6 — Previsão de demanda

Baseline de média móvel dos últimos 3 meses para o produto "Bússola de Bordo 702" (`product_id = 74`), prevendo o 1º trimestre de 2026. Para evitar vazamento de dado futuro, a previsão de fevereiro/março usa a **própria previsão** dos meses anteriores, nunca o valor real de 2026.

| Métrica | Valor |
|---|---|
| Soma prevista (Q1 2026) | 71 unidades |
| Soma real (Q1 2026) | 156 unidades |
| MAE | 28,33 unidades (135,2% da média histórica) |

**Limitação observada:** o erro de janeiro (salto de demanda não capturado pelo baseline) se propaga em cadeia para fevereiro e março, já que cada previsão usa a previsão anterior como insumo.

> Nota: existem dois produtos cadastrados com o nome "Bússola de Bordo 702" (`product_id` 74 e 240); usamos o 74 por ter mais histórico de vendas.

## Questão 7 — Sistema de recomendação

Matriz de interação cliente × produto (binária: comprou ou não), similaridade de cosseno produto × produto, ranking dos 5 produtos mais similares ao "Motor de Popa 1949".

**Resultado:** **Motor de Popa 5331** (similaridade 0,2566) — a maior do ranking, mas ainda baixa em termos absolutos, e em categoria diferente do item de referência, evidenciando que o método capta comportamento de compra, não intenção de venda casada por categoria.

## Dashboard

Painel em Streamlit + Plotly, conectado direto ao banco Postgres da Questão 3, com:
- KPIs gerais (receita, pedidos, ticket médio, clientes)
- Resumo das Questões 1-3 (etapas técnicas sem gráfico próprio)
- 4 achados extras: faturamento por região, top 10 produtos, cliente multi-região de maior valor, top 5 produtos em Alagoas
- Cada questão de 4 a 7 com o cenário original do desafio, gráfico/tabela e interpretação escrita dinamicamente a partir do resultado real da query

## Nota de qualidade de dados

A tabela `products` contém nomes duplicados (ex.: "Bússola de Bordo 702" e "Sonar Transducer 7193" aparecem com dois `product_id` diferentes) e ao menos 2 registros de teste (nome "asdf"). Por isso, toda agregação por produto neste projeto usa `product_id`, nunca o nome — agregar por nome nesse dataset produz resultados incorretos (ex.: o registro de teste "asdf" chegou a aparecer em 1º lugar num ranking regional antes dessa correção).