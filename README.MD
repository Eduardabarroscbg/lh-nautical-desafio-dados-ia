<div class="hero-image">
    <div class="frame">
        <img src="https://raw.githubusercontent.com/Eduardabarroscbg/lh-nautical-desafio-dados-ia/master/assets/cursolighthouse.png" alt="banner da indicium">
    </div>
</div>

# LH Nautical — Desafio Lighthouse Dados e IA

Resolução completa do desafio técnico da LH Nautical: da leitura dos 24 CSVs brutos até um painel analítico interativo, passando por definição de schema, carga em PostgreSQL, análise exploratória, SQL avançado e dois modelos simples de dados (previsão de demanda e sistema de recomendação).

Cada seção abaixo traz o cenário de negócio proposto, o que foi pedido, como cheguei na solução e o resultado final — na prática, o mesmo raciocínio que enviei nas respostas da plataforma, só que documentado aqui de forma corrida.

## Sumário

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

Pré-requisitos: PostgreSQL rodando localmente e Python 3.10+.

```bash
pip install psycopg2-binary pandas scikit-learn streamlit plotly
```

1. `python questao2.1.py` → gera `schema.sql` a partir dos CSVs.
2. Rode `schema.sql` no seu client SQL (DBeaver, psql...), num banco `lhnautical` vazio.
3. `python questao3.1.py` → carrega os 24 CSVs no banco.
4. Questões 1, 4 e 5 são arquivos `.sql`, rodados direto no DBeaver. Questões 6 e 7 são scripts Python (`python questao6.py`, `python questao7.py`).
5. `streamlit run dashboard_streamlit.py` → sobe o painel em `localhost:8501`.

## Questão 1 — EDA

**Cenário:** antes de qualquer modelagem, o Sr. Almir quer uma resposta simples: "posso confiar nesses dados para tomar decisões?". A missão era rodar uma análise exploratória inicial na tabela `orders`, sem nenhum tratamento (só observar, agregar e descrever), e diagnosticar a confiabilidade dos dados.

**O que fiz:** uma query única trazendo contagem de linhas, intervalo de datas (`created_at`) e estatísticas (mín/máx/média) da coluna `total`. Depois, um conjunto de queries de apoio para embasar o diagnóstico: mediana, outliers pela regra do IQR, checagem de duplicatas (`id` e `order_number`), consistência entre `subtotal`, `discount_amount` e `total`, e o percentual de nulos em cada coluna.

**Resultado:**

| Métrica | Valor |
|---|---|
| Linhas | 48.998 |
| Período | 01/01/2020 a 31/12/2026 |
| Total (mín / méd / mediana / máx) | R$ 32,62 / R$ 28.704,99 / R$ 25.917,84 / R$ 127.262,02 |
| Duplicatas (id / order_number) | 0 / 0 |
| Linhas com subtotal − desconto ≠ total | 0 |
| Outliers (regra do IQR) | 452 pedidos (0,92%) |
| Nulos em `salesperson_id` | 49,25% |

**Diagnóstico:** não encontrei duplicatas nem inconsistência entre subtotal, desconto e total. Sobre outliers: o total varia bastante, mas com a regra do IQR menos de 1% dos pedidos fica acima do limite — não interpreto isso como erro, e sim como pedidos de ticket mais alto legítimos. Sobre qualidade dos dados: o único campo com bastante nulo é `salesperson_id` (~49%), mas ao cruzar com o canal de venda, os 24.131 nulos estão 100% concentrados no e-commerce — ou seja, é um padrão esperado do canal (pedidos online não têm vendedor associado), não uma falha de coleta. Considero a tabela `orders` confiável para uma análise inicial, sem sinais de erro ou corrupção, mas não suficiente sozinha para decisões de negócio — precisa ser cruzada com outras tabelas (o que foi vendido em cada pedido, quem é o cliente) antes disso.

## Questão 2 — Schema

**Cenário:** a empresa do ERP não permite conexão direta com o banco — a única forma de obter os dados é pelos CSVs fornecidos. Antes de carregar qualquer coisa num banco, era preciso definir o schema de destino (PostgreSQL).

**O que fiz:** um script em Python puro (só `csv`, `os`, `datetime` — sem pandas/dask/polars, conforme exigido) que lê cada um dos 24 CSVs, olha os valores de cada coluna e infere o tipo mais adequado: `BOOLEAN` se só houver `TRUE`/`FALSE`, `INTEGER`/`BIGINT` se for número inteiro (dependendo do tamanho), `NUMERIC` se tiver casas decimais, `TIMESTAMP` se bater com algum formato de data conhecido, e `TEXT` como padrão.

O ponto mais delicado foi identificar colunas que **parecem** número mas na verdade são código — CPF, CEP, chave de NF-e, SKU — onde o zero à esquerda tem significado (ex: `"06351-685"`) ou o valor é longo demais para ser quantidade. Criei uma função (`eh_codigo_disfarcado_de_numero`) que detecta esses casos antes de qualquer outra inferência e força `TEXT`, evitando perder informação na conversão.

**Resultado:** `schema.sql` com 24 comandos `CREATE TABLE`, um por CSV, com coluna `id` sempre como `PRIMARY KEY`. Validei manualmente colunas de risco como `employees.cpf` (virou `BIGINT`, número grande demais para `INTEGER`), `customers.tax_id`, `addresses.postal_code`, `fiscal_invoices.nfe_access_key` e `product_variants.barcode_ean` (todas viraram `TEXT` corretamente).

## Questão 3 — Carregamento

**Cenário:** com o schema definido, o próximo passo era carregar os dados brutos no banco, sem nenhum tratamento (sem remover nulo, sem corrigir caractere especial), para viabilizar as análises seguintes.

**O que fiz:** script Python com `psycopg2` que lê cada CSV e faz `INSERT` respeitando o schema da Questão 2. A única "conversão" aplicada é transformar string vazia (`""`) em `None` — isso não é limpeza de dado, é a única forma de uma célula vazia do CSV virar de fato um `NULL` no banco (sem isso, o `INSERT` falha em colunas não-texto). Antes de cada carga, rodo `TRUNCATE TABLE ... RESTART IDENTITY CASCADE`, o que torna o script idempotente: pode ser executado várias vezes sem duplicar linha nenhuma.

**Resultado:** 24 tabelas carregadas. Como validação, a soma de linhas de `customers + orders + order_items + payments` = **251.864**, conferida tanto no terminal (saída do script) quanto rodando a contagem direto no banco via DBeaver.

## Questão 4 — Análise de clientes

**Cenário:** a Diretoria quer identificar os clientes fiéis — diferente de quem compra muito uma vez só, o cliente fiel tem gasto médio alto por transação **e** navega por várias categorias da loja. O objetivo é mapear o que esse grupo de elite consome, para replicar o comportamento em outros segmentos.

**Regras dadas:** Ticket Médio = Faturamento Total / Frequência (nº de pedidos distintos); Diversidade = nº de `category_id` distintos comprados; filtro de elite = só entram clientes com 13+ categorias distintas; desempate por `customer_id` crescente.

**O que fiz:** uma cadeia de CTEs em SQL — `vendas_por_cliente` (faturamento e frequência), `categorias_por_cliente` (diversidade, via join até `products`), `metricas_cliente` (junta as duas e calcula ticket médio) e `top_10_fieis` (filtra diversidade ≥ 13, ordena por ticket médio decrescente, limita a 10). Numa segunda consulta, reuso esse mesmo grupo de 10 clientes como filtro para somar a quantidade comprada por categoria entre eles, achando a categoria campeã.

**Resultado:** os 10 clientes de elite compraram, todos, em exatamente 14 categorias distintas (acima do mínimo de 13). A categoria que mais concentra volume entre eles é **Hélices**, com 492 unidades — à frente de Coletes Salva-Vidas (393) e Eletrônica Náutica (392).

## Questão 5 — Dimensão de calendário

**Cenário:** o Sr. Almir quer saber qual dia da semana tem a pior média de vendas nas lojas físicas, para decidir se vale fechar a loja nesses dias. Um estagiário tinha feito um `GROUP BY` direto na tabela `orders` e concluído (errado) que Domingo era ótimo — porque os domingos em que a loja abriu e vendeu R$0 simplesmente não existem na tabela `orders`, então foram ignorados na média, inflando o resultado.

**O que fiz:** construí uma dimensão de datas com `generate_series`, cobrindo cada dia entre a menor e a maior data presente no arquivo, com o dia da semana calculado via `EXTRACT(ISODOW ...)` e traduzido para português num `CASE`. Depois, um `LEFT JOIN` dessa dimensão com as vendas agregadas por dia (`channel = 'pos'`), tratando com `COALESCE(..., 0)` os dias sem venda registrada como R$0 — em vez de eles simplesmente sumirem da média, como no erro do estagiário.

**Resultado:** Quinta-feira tem a pior média (R$ 157.154,32), Quarta-feira a melhor (R$ 173.605,44) — nada parecido com o "Domingo ótimo" que o estagiário tinha calculado errado. Quanto mais dias vazios um dia da semana tiver, mais distorcida (otimista) fica a média calculada sem o calendário — é exatamente essa distorção que a dimensão de datas corrige.

## Questão 6 — Previsão de demanda

**Cenário:** no último verão, o estoque de "Coletes Salva-Vidas" acabou em 3 meses (venda perdida), enquanto "Âncoras" foram compradas demais e estão enferrujando no galpão. O Tech Lead não quer mais confiar em "feeling" — pediu um modelo preditivo simples para o produto "Bússola de Bordo 702".

**O que fiz:** unifiquei `orders`, `order_items` e `product_variants` para obter a série mensal de vendas do produto (havia dois `product_id` cadastrados com esse nome — usei o 74, por ter mais histórico: 330 registros contra 142 do outro). O baseline é uma média móvel dos 3 meses anteriores. Para evitar vazamento de dado futuro (data leakage), a previsão de fevereiro e março usa a **própria previsão** dos meses anteriores como entrada da janela — nunca o valor real de 2026, já que na vida real, ao prever fevereiro, o valor real de janeiro ainda não existiria.

**Resultado:**

| Métrica | Valor |
|---|---|
| Previsto (jan / fev / mar 2026) | 25 / 25 / 21 unidades |
| Real (jan / fev / mar 2026) | 69 / 42 / 45 unidades |
| Soma prevista / Soma real | 71 / 156 unidades |
| MAE | 28,33 unidades (135,2% da média histórica) |

**Limitação:** o baseline não é adequado para esse produto. Janeiro/2026 teve um salto de demanda (69 unidades, bem acima da média recente de ~25) que o modelo não conseguiu antecipar, porque só repete o padrão dos meses anteriores. Como a previsão em cadeia usa a própria previsão (errada) de janeiro para calcular fevereiro, e a de fevereiro para calcular março, o erro se propaga e se acumula em vez de se corrigir sozinho — é a limitação mais séria desse tipo de baseline simples.

## Questão 7 — Sistema de recomendação

**Cenário:** a Marina percebeu que clientes que compram lanchas quase sempre esquecem a defesa (proteção lateral) e quer uma vitrine de "quem comprou isso, também levou..." no site — sem ferramentas caras de Big Data.

**O que fiz:** construí uma matriz de interação cliente × produto (2.000 × 500), com 1 se o cliente comprou o produto ao menos uma vez, 0 caso contrário (ignorando quantidade). A partir dela, calculei a similaridade de cosseno produto × produto (transpondo a matriz) e rankeei os 5 produtos mais similares ao "Motor de Popa 1949", desconsiderando o próprio motor.

**Resultado:** o produto recomendado é **Motor de Popa 5331**, com similaridade de 0,2566 — a maior do ranking, mas o valor absoluto é baixo (as 5 posições ficaram entre 0,23 e 0,26, nenhuma se destacou de verdade). A matriz tem só 13,55% de densidade, o que já limita o quanto qualquer similaridade consegue ser "forte".

**Limitação:** o método não usa categoria nem preço, só comportamento de compra puro — o "Motor de Popa 1949" é da categoria 13, e o produto recomendado é da categoria 8. Ou seja, o modelo aponta um produto porque os mesmos clientes compraram os dois, não porque faz sentido de venda casada. O que a Marina esperava (algo tipo defesa/proteção lateral) nem existe no catálogo — por isso o resultado real acabou sendo outro motor, não o acessório que faria mais sentido comercial.

## Dashboard

Painel em Streamlit + Plotly, conectado direto ao banco Postgres da Questão 3. Cada seção traz o cenário original do desafio (ou a pergunta de negócio, no caso das explorações extras), o gráfico/tabela correspondente e uma interpretação escrita **dinamicamente** a partir do resultado real da query — não é texto fixo.

Estrutura do painel: KPIs gerais no topo → resumo em texto das Questões 1-3 (etapas técnicas sem gráfico de negócio próprio) → 4 explorações extras (faturamento por região, top 10 produtos, cliente multi-região de maior valor, top 5 produtos em Alagoas) → Questões 4 a 7 com cenário, gráfico e conclusão → conclusão geral.

![Visão geral do painel](https://raw.githubusercontent.com/Eduardabarroscbg/lh-nautical-desafio-dados-ia/master/assets/01_dashboard_visao_geral.png)

![Questão 6 — Previsão de demanda](https://raw.githubusercontent.com/Eduardabarroscbg/lh-nautical-desafio-dados-ia/master/assets/02_questao6_previsao.png)

![Questão 7 — Sistema de recomendação](https://raw.githubusercontent.com/Eduardabarroscbg/lh-nautical-desafio-dados-ia/master/assets/03_questao7_recomendacao.png)

## Nota de qualidade de dados

A tabela `products` contém nomes duplicados — por exemplo, "Bússola de Bordo 702" e "Sonar Transducer 7193" aparecem cada um com dois `product_id` diferentes — e ao menos 2 registros de teste (nome literal "asdf"). Esse detalhe é mais do que um comentário lateral: ao testar uma agregação por nome de produto (em vez de `product_id`) no ranking de vendas de Alagoas, o registro "asdf" chegou a aparecer em 1º lugar, distorcendo o resultado real. Por isso, toda agregação por produto neste projeto usa `product_id`, nunca o nome.
