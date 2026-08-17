import csv
import os
from datetime import datetime

PASTA_CSVS = "."
ARQUIVO_SAIDA = "schema.sql"

FORMATOS_DATA = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
]


def eh_inteiro(valor):
    try:
        int(valor)
        return True
    except ValueError:
        return False


def eh_decimal(valor):
    try:
        float(valor)
        return True
    except ValueError:
        return False


def eh_booleano(valor):
    return valor.upper() in ("TRUE", "FALSE")


def eh_data(valor):
    for formato in FORMATOS_DATA:
        try:
            datetime.strptime(valor, formato)
            return True
        except ValueError:
            continue
    return False


def eh_codigo_disfarcado_de_numero(valor):

    if len(valor) > 1 and valor.startswith("0") and valor[1].isdigit():
        return True

    if eh_inteiro(valor) and len(valor) > 15:
        return True
    return False


def inferir_tipo_coluna(valores, nome_coluna=None):
    valores_preenchidos = [v for v in valores if v not in ("", None)]

    if not valores_preenchidos:
        return "TEXT"

    valores_que_parecem_codigo = [v for v in valores_preenchidos if eh_codigo_disfarcado_de_numero(v)]
    if valores_que_parecem_codigo:
        exemplo = valores_que_parecem_codigo[0]
        print(
            f"  -> Coluna '{nome_coluna}': tratada como TEXT (não INTEGER), "
            f"pois os valores parecem código (ex: '{exemplo}') e não quantidade "
            f"— provavelmente CPF, CEP ou SKU, onde o zero à esquerda tem significado."
        )
        return "TEXT"

    if all(eh_booleano(v) for v in valores_preenchidos):
        return "BOOLEAN"

    if all(eh_inteiro(v) for v in valores_preenchidos):
        maior_valor = max(abs(int(v)) for v in valores_preenchidos)
        if maior_valor <= 2_147_483_647:
            return "INTEGER"
        return "BIGINT"

    if all(eh_decimal(v) for v in valores_preenchidos):
        return "NUMERIC"

    if all(eh_data(v) for v in valores_preenchidos):
        return "TIMESTAMP"

    return "TEXT"


def ler_csv(caminho_arquivo):

    with open(caminho_arquivo, newline="", encoding="utf-8") as f:
        leitor = csv.reader(f)
        cabecalho = next(leitor)
        linhas = list(leitor)
    return cabecalho, linhas


def gerar_create_table(nome_tabela, cabecalho, linhas):
    colunas_sql = []

    for indice, nome_coluna in enumerate(cabecalho):
        valores_coluna = [linha[indice] for linha in linhas if indice < len(linha)]
        tipo = inferir_tipo_coluna(valores_coluna, nome_coluna=nome_coluna)

        if nome_coluna.lower() == "id":
            colunas_sql.append(f"    {nome_coluna} {tipo} PRIMARY KEY")
        else:
            colunas_sql.append(f"    {nome_coluna} {tipo}")

    corpo = ",\n".join(colunas_sql)
    return f"CREATE TABLE {nome_tabela} (\n{corpo}\n);"


def main():
    arquivos_csv = [f for f in os.listdir(PASTA_CSVS) if f.endswith(".csv")]
    arquivos_csv.sort()

    comandos = []

    for nome_arquivo in arquivos_csv:
        caminho = os.path.join(PASTA_CSVS, nome_arquivo)
        nome_tabela = nome_arquivo.replace(".csv", "")

        cabecalho, linhas = ler_csv(caminho)
        comando = gerar_create_table(nome_tabela, cabecalho, linhas)
        comandos.append(comando)

        print(f"Tabela '{nome_tabela}' processada ({len(cabecalho)} colunas, {len(linhas)} linhas).")

    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        f.write("\n\n".join(comandos))
        f.write("\n")

    print(f"\nArquivo '{ARQUIVO_SAIDA}' gerado com {len(arquivos_csv)} tabelas.")


if __name__ == "__main__":
    main()