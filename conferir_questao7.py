import pandas as pd
import numpy as np

products = pd.read_csv('products.csv')
variants = pd.read_csv('product_variants.csv')
orders = pd.read_csv('orders.csv')
order_items = pd.read_csv('order_items.csv')

itens = order_items.merge(variants[['id', 'product_id']], left_on='product_variant_id', right_on='id', suffixes=('', '_variant'))
itens = itens.merge(orders[['id', 'customer_id']], left_on='order_id', right_on='id', suffixes=('', '_pedido'))
interacoes = itens[['customer_id', 'product_id']].drop_duplicates()

PRODUTO_A = 180  # Motor de Popa 1949
PRODUTO_B = 389  # produto que o questao7.py apontou como mais similar

clientes_a = set(interacoes[interacoes['product_id'] == PRODUTO_A]['customer_id'])
clientes_b = set(interacoes[interacoes['product_id'] == PRODUTO_B]['customer_id'])

intersecao = clientes_a & clientes_b
print(f"Clientes que compraram o produto {PRODUTO_A}: {len(clientes_a)}")
print(f"Clientes que compraram o produto {PRODUTO_B}: {len(clientes_b)}")
print(f"Clientes que compraram os DOIS: {len(intersecao)}")

cosseno_manual = len(intersecao) / (np.sqrt(len(clientes_a)) * np.sqrt(len(clientes_b)))
print(f"\nCosseno calculado na mao: {cosseno_manual:.4f}")
