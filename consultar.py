import argparse
import json
import sys

import boto3
from botocore.config import Config

FUNCAO = "olap-duckdb"

# Espera mais que o timeout da Lambda (60 s) e não repete a chamada sozinho
cliente = boto3.client(
    "lambda",
    region_name="us-east-1",
    config=Config(read_timeout=90, retries={"max_attempts": 0}),
)


def consultar(sql):
    resposta = cliente.invoke(FunctionName=FUNCAO, Payload=json.dumps({"sql": sql}))
    retorno = json.loads(resposta["Payload"].read())

    if "FunctionError" in resposta:                   # a Lambda falhou (ex.: timeout)
        sys.exit(f"Falha na Lambda: {retorno.get('errorMessage', retorno)}")

    corpo = json.loads(retorno["body"])
    if retorno["statusCode"] != 200:                  # erro no SQL (400) ou na execução (500)
        sys.exit(f"Erro {retorno['statusCode']}: {corpo['erro']}")
    return corpo


def imprimir_tabela(dados):
    if not dados:
        print("(nenhuma linha)")
        return
    colunas = list(dados[0].keys())
    larguras = {c: max(len(c), *(len(str(linha[c])) for linha in dados)) for c in colunas}
    print("  ".join(c.ljust(larguras[c]) for c in colunas))
    print("  ".join("-" * larguras[c] for c in colunas))
    for linha in dados:
        print("  ".join(str(linha[c]).ljust(larguras[c]) for c in colunas))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consulta o lake via Lambda")
    parser.add_argument("sql", nargs="?", help="consulta SQL entre aspas")
    parser.add_argument("-f", "--arquivo", help="arquivo .sql com a consulta")
    args = parser.parse_args()

    if args.arquivo:
        sql = open(args.arquivo, encoding="utf-8").read()
    elif args.sql:
        sql = args.sql
    else:
        parser.error("informe a consulta entre aspas ou um arquivo com -f")

    resultado = consultar(sql)
    imprimir_tabela(resultado["dados"])
    aviso = " (truncado em 10.000 linhas)" if resultado["truncado"] else ""
    print(f"\n{resultado['linhas']} linhas em {resultado['tempo_ms']} ms{aviso}")