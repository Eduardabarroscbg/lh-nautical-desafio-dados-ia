import pandas as pd

products = pd.read_csv('products.csv')
variants = pd.read_csv('product_variants.csv')
orders = pd.read_csv('orders.csv')
order_items = pd.read_csv('order_items.csv')

PRODUCT_ID = 74  # tem outro produto com o mesmo nome (id 240), usei o 74 que tem mais historico
print(f"Produto selecionado: {products[products['id'] == PRODUCT_ID]['name'].values[0]}")

variantes_produto = variants[variants['product_id'] == PRODUCT_ID]['id'].tolist()

itens = order_items[order_items['product_variant_id'].isin(variantes_produto)]
itens = itens.merge(orders[['id', 'created_at']], left_on='order_id', right_on='id', suffixes=('', '_pedido'))
itens['created_at'] = pd.to_datetime(itens['created_at'])
itens['ano_mes'] = itens['created_at'].dt.to_period('M')

vendas_mensais = itens.groupby('ano_mes')['quantity'].sum().sort_index()

todos_meses = pd.period_range(vendas_mensais.index.min(), vendas_mensais.index.max(), freq='M')
vendas_mensais = vendas_mensais.reindex(todos_meses, fill_value=0)

meses_teste = pd.period_range('2026-01', '2026-03', freq='M')

# A janela de cada previsão usa dados reais quando disponíveis, e a
# PRÓPRIA previsão (não o valor real) para meses já dentro do período
# de teste. É o que a equipe confirmou no fórum: "use a sua própria
# previsão para janeiro e não o valor real de janeiro" ao prever fevereiro.
serie_para_janela = vendas_mensais.copy()

previsoes = {}
for mes in meses_teste:
    janela = pd.period_range(mes - 3, mes - 1, freq='M')
    previsoes[mes] = round(serie_para_janela.loc[janela].mean())
    serie_para_janela.loc[mes] = previsoes[mes]

reais = vendas_mensais.loc[meses_teste]

print("Mes       | Previsto | Real")
for mes in meses_teste:
    print(f"{mes}   | {previsoes[mes]:>8} | {reais[mes]:>4}")

soma_prevista = sum(previsoes.values())
print(f"\nSoma prevista 1 trimestre 2026: {soma_prevista}")

mae = sum(abs(previsoes[mes] - reais[mes]) for mes in meses_teste) / len(meses_teste)
media_vendas = vendas_mensais.mean()
mae_percentual = (mae / media_vendas) * 100

print(f"MAE: {mae:.2f}")
print(f"Média mensal histórica de vendas: {media_vendas:.2f}")
print(f"MAE em % da média histórica: {mae_percentual:.1f}%")
