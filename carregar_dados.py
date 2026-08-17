import os
import csv
import psycopg2

PASTA_CSVS = "."

CONEXAO = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "lhnautical",
    "user": "lhuser",
    "password": "lhpass123",
}

def carregar_csv_na_tabela(cursor, nome_tabela, caminho_csv):
    with open(caminho_csv, newline="", encoding="utf-8") as f:
        leitor = csv.reader(f)
        cabecalho = next(leitor)
        linhas = list(leitor)

    colunas = ", ".join(cabecalho)
    marcadores = ", ".join(["%s"] * len(cabecalho))
    comando = f"INSERT INTO {nome_tabela} ({colunas}) VALUES ({marcadores})"

    # "" no CSV não é NULL de verdade, é como o CSV representa célula vazia.
    # Sem essa conversão, o INSERT falharia em colunas não-texto (ex: INTEGER,
    # TIMESTAMP). Isso não é "remoção de nulo", é a forma de o nulo
    # existir no banco.
    linhas_tratadas = [
        [valor if valor != "" else None for valor in linha]
        for linha in linhas
    ]

    cursor.executemany(comando, linhas_tratadas)
    return len(linhas_tratadas)

def main():
    arquivos_csv = [f for f in os.listdir(PASTA_CSVS) if f.endswith(".csv")]
    arquivos_csv.sort()

    conexao = psycopg2.connect(**CONEXAO)
    cursor = conexao.cursor()

    total_linhas = 0
    tabelas_com_erro = []

    for nome_arquivo in arquivos_csv:
        nome_tabela = nome_arquivo.replace(".csv", "")
        caminho = os.path.join(PASTA_CSVS, nome_arquivo)

        try:

            cursor.execute(f"TRUNCATE TABLE {nome_tabela} RESTART IDENTITY CASCADE;")
            qtd = carregar_csv_na_tabela(cursor, nome_tabela, caminho)
            conexao.commit()
            total_linhas += qtd
            print(f"Tabela '{nome_tabela}': {qtd} linhas carregadas.")
        except Exception as erro:
            conexao.rollback()
            tabelas_com_erro.append(nome_tabela)
            print(f"Erro ao carregar '{nome_tabela}': {erro}")

    cursor.close()
    conexao.close()

    print(f"\nCarregamento concluído. Total de linhas inseridas: {total_linhas}")
    if tabelas_com_erro:
        print(f"Tabelas com erro ({len(tabelas_com_erro)}): {', '.join(tabelas_com_erro)}")

if __name__ == "__main__":
    main()