import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

products = pd.read_csv('products.csv')
variants = pd.read_csv('product_variants.csv')
orders = pd.read_csv('orders.csv')
order_items = pd.read_csv('order_items.csv')

itens = order_items.merge(variants[['id', 'product_id']], left_on='product_variant_id', right_on='id', suffixes=('', '_variant'))
itens = itens.merge(orders[['id', 'customer_id']], left_on='order_id', right_on='id', suffixes=('', '_pedido'))

interacoes = itens[['customer_id', 'product_id']].drop_duplicates()

matriz = interacoes.assign(valor=1).pivot_table(index='customer_id', columns='product_id', values='valor', fill_value=0)

PRODUTO_REFERENCIA = 180  # Motor de Popa 1949

sim = cosine_similarity(matriz.T)
sim_df = pd.DataFrame(sim, index=matriz.columns, columns=matriz.columns)

similares = sim_df[PRODUTO_REFERENCIA].drop(PRODUTO_REFERENCIA).sort_values(ascending=False).head(5)

print("Top 5 similares ao Motor de Popa 1949:")
for pid, score in similares.items():
    nome = products.loc[products['id'] == pid, 'name'].values[0]
    print(f"{nome} - similaridade {score:.4f}")
