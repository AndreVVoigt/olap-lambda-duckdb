import base64
import json
import os
import time

import duckdb

LAKE = os.environ.get("LAKE_URI", "data/lake")
MAX_LINHAS = 10_000     # a resposta de uma Lambda síncrona tem limite de tamanho

VIEWS = f"""
CREATE OR REPLACE VIEW trips AS
    SELECT * FROM read_parquet('{LAKE}/trips/*/*/*.parquet', hive_partitioning = true);

CREATE OR REPLACE VIEW zones AS
    SELECT * FROM read_parquet('{LAKE}/zones/zones.parquet');

CREATE OR REPLACE VIEW trips_validas AS
    SELECT * FROM trips WHERE NOT is_suspeita;
"""

# Fora do handler: roda uma vez por ambiente (cold start) e é reaproveitado
# em todas as invocações seguintes enquanto o ambiente estiver "quente".
con = duckdb.connect()
if LAKE.startswith("s3://"):
    con.sql("CREATE SECRET (TYPE s3, PROVIDER credential_chain, REGION 'us-east-1')")
con.sql(VIEWS)

# Erros causados pelo SQL enviado (sintaxe, tabela/coluna inexistente, tipo errado)
ERROS_DO_SQL = (
    duckdb.ParserException,
    duckdb.BinderException,
    duckdb.CatalogException,
    duckdb.ConversionException,
    duckdb.InvalidInputException,
)


def resposta(status, corpo):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(corpo, ensure_ascii=False, default=str),
    }


def ler_pedido(event):
    """Aceita invocação direta (boto3/CLI) e chamada HTTP (body em texto)."""
    if "sql" in event:
        return event
    corpo = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        corpo = base64.b64decode(corpo).decode("utf-8")
    return json.loads(corpo)


def lambda_handler(event, context):
    try:
        sql = ler_pedido(event).get("sql")
        if not sql:
            raise ValueError('envie {"sql": "..."}')
    except (ValueError, TypeError, AttributeError) as erro:
        return resposta(400, {"erro": str(erro)})

    inicio = time.perf_counter()
    try:
        resultado = con.sql(sql)
        if resultado is None:                       # comando sem retorno (ex.: SET)
            return resposta(200, {"tempo_ms": 0, "linhas": 0, "dados": []})
        colunas = resultado.columns
        linhas = resultado.fetchmany(MAX_LINHAS + 1)
    except ERROS_DO_SQL as erro:
        return resposta(400, {"erro": str(erro)})   # erro no SQL: devolve a mensagem para corrigir
    except Exception as erro:
        print(f"ERRO sql={sql!r}: {erro}")          # vai para o CloudWatch na AWS
        return resposta(500, {"erro": str(erro)})

    truncado = len(linhas) > MAX_LINHAS
    dados = [dict(zip(colunas, linha)) for linha in linhas[:MAX_LINHAS]]
    return resposta(200, {
        "tempo_ms": round((time.perf_counter() - inicio) * 1000),
        "linhas": len(dados),
        "truncado": truncado,
        "dados": dados,
    })