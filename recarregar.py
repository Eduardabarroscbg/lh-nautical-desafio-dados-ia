import os
import csv
import psycopg2

CONEXAO = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "lhnautical",
    "user": "lhuser",
    "password": "lhpass123",
}

tabelas = ["product_suppliers", "stock_levels", "variant_attribute_values"]

conexao = psycopg2.connect(**CONEXAO)
cursor = conexao.cursor()

for nome_tabela in tabelas:
    with open(f"{nome_tabela}.csv", newline="", encoding="utf-8") as f:
        leitor = csv.reader(f)
        cabecalho = next(leitor)
        linhas = list(leitor)

    colunas = ", ".join(cabecalho)
    marcadores = ", ".join(["%s"] * len(cabecalho))
    comando = f"INSERT INTO {nome_tabela} ({colunas}) VALUES ({marcadores})"
    linhas_tratadas = [[v if v != "" else None for v in linha] for linha in linhas]

    cursor.executemany(comando, linhas_tratadas)
    conexao.commit()
    print(f"{nome_tabela}: {len(linhas_tratadas)} linhas recarregadas.")

cursor.close()
conexao.close()