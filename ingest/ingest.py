
import csv
import duckdb
import pathlib
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


RAW = pathlib.Path("data/raw")
LAKE = pathlib.Path("data/lake/trips")
RELATORIO = pathlib.Path("data/ingest_report.csv")
URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{ano}-{mes:02d}.parquet"
URL_ZONAS = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"

MESES = [(ano, mes) for ano in range(2019, 2026) for mes in range(1, 13)]
WORKERS_DOWNLOAD = 4      # downloads em paralelo (I/O: threads ajudam)
REFAZER = False           # True = retransforma meses que já estão no lake

# ---------------------------------------------------------------------------
# Regras da proposta em SQL
# ---------------------------------------------------------------------------
SQL = """
SELECT
    tpep_pickup_datetime,
    tpep_dropoff_datetime,
    CAST(PULocationID AS INTEGER)               AS pu_location_id,
    CAST(DOLocationID AS INTEGER)               AS do_location_id,
    CAST(NULLIF(passenger_count, 0) AS INTEGER) AS passenger_count,
    trip_distance,
    CAST(RatecodeID AS INTEGER)                 AS ratecode_id,
    CAST(payment_type AS INTEGER)               AS payment_type,
    fare_amount,
    tip_amount,
    tolls_amount,
    total_amount,
    congestion_surcharge,
    CAST(airport_fee AS DOUBLE)                 AS airport_fee,
    {cbd}                                       AS cbd_congestion_fee,
    (trip_distance <= 0 OR trip_distance > 100
     OR total_amount > 1000)                    AS is_suspeita
FROM read_parquet('{arquivo}')
WHERE tpep_pickup_datetime >= make_date({ano}, {mes}, 1)
  AND tpep_pickup_datetime <  make_date({ano}, {mes}, 1) + INTERVAL 1 MONTH
ORDER BY tpep_pickup_datetime
"""


def caminho_raw(ano, mes):
    return RAW / f"yellow_tripdata_{ano}-{mes:02d}.parquet"


def caminho_lake(ano, mes):
    return LAKE / f"ano={ano}" / f"mes={mes}" / "trips.parquet"


# ---------------------------------------------------------------------------
# Download: idempotente, atômico e com novas tentativas
# ---------------------------------------------------------------------------
def baixar_mes(ano, mes):
    destino = caminho_raw(ano, mes)
    if destino.exists():
        return destino

    RAW.mkdir(parents=True, exist_ok=True)
    temp = destino.with_suffix(".part")
    with requests.get(URL.format(ano=ano, mes=mes), stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(temp, "wb") as f:
            for bloco in r.iter_content(chunk_size=1 << 20):
                f.write(bloco)
    temp.rename(destino)
    return destino


def baixar_com_retry(ano, mes, tentativas=3):
    for tentativa in range(1, tentativas + 1):
        try:
            return baixar_mes(ano, mes)
        except requests.RequestException:
            if tentativa == tentativas:
                raise
            time.sleep(2 ** tentativa)     # espera 2s, depois 4s (backoff)


def baixar_todos(meses):
    """Fase 1: baixa tudo em paralelo. Devolve {(ano, mes): erro} das falhas."""
    falhas = {}
    with ThreadPoolExecutor(max_workers=WORKERS_DOWNLOAD) as executor:
        futuros = {executor.submit(baixar_com_retry, a, m): (a, m) for a, m in meses}
        for futuro in as_completed(futuros):
            ano, mes = futuros[futuro]
            try:
                futuro.result()
                print(f"[download] {ano}-{mes:02d} ok")
            except Exception as erro:
                falhas[(ano, mes)] = str(erro)
                print(f"[download] {ano}-{mes:02d} FALHOU: {erro}")
    return falhas


# ---------------------------------------------------------------------------
# Transformação: aplica o molde SQL a um mês e grava no lake (atômico)
# ---------------------------------------------------------------------------
def transformar_mes(con, arquivo, ano, mes):
    caminho = arquivo.as_posix()

    colunas = {c.lower() for c in con.sql(f"SELECT * FROM read_parquet('{caminho}') LIMIT 0").columns}
    if "cbd_congestion_fee" in colunas:
        cbd = "CAST(cbd_congestion_fee AS DOUBLE)"
    else:
        cbd = "CAST(NULL AS DOUBLE)"

    final = caminho_lake(ano, mes)
    final.parent.mkdir(parents=True, exist_ok=True)
    temp = final.with_suffix(".tmp")

    consulta = SQL.format(arquivo=caminho, ano=ano, mes=mes, cbd=cbd)
    con.sql(f"COPY ({consulta}) TO '{temp.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
    temp.replace(final)                    # só vira trips.parquet se terminou
    return final.as_posix()


def relatorio(con, arquivo, saida):
    lidas = con.sql(
        f"SELECT num_rows FROM parquet_file_metadata('{arquivo.as_posix()}')"
    ).fetchone()[0]
    gravadas, suspeitas = con.sql(
        f"SELECT count(*), count(*) FILTER (WHERE is_suspeita) FROM '{saida}'"
    ).fetchone()
    return {"lidas": lidas, "gravadas": gravadas,
            "descartadas": lidas - gravadas, "suspeitas": suspeitas}


def processar_todos(con, meses, falhas_download):
    """Fase 2: transforma mês a mês. Uma falha não derruba os outros meses."""
    linhas = []
    for ano, mes in meses:
        inicio = time.perf_counter()
        linha = {"ano": ano, "mes": mes, "status": "", "lidas": None, "gravadas": None,
                 "descartadas": None, "suspeitas": None, "segundos": None, "erro": ""}

        if (ano, mes) in falhas_download:
            linha.update(status="falha_download", erro=falhas_download[(ano, mes)])
        else:
            arquivo = caminho_raw(ano, mes)
            try:
                if caminho_lake(ano, mes).exists() and not REFAZER:
                    saida, status = caminho_lake(ano, mes).as_posix(), "pulado"
                else:
                    saida, status = transformar_mes(con, arquivo, ano, mes), "ok"
                linha.update(relatorio(con, arquivo, saida), status=status)
            except Exception as erro:
                linha.update(status="falha_transformacao", erro=str(erro))

        linha["segundos"] = round(time.perf_counter() - inicio, 1)
        print(f"[lake] {ano}-{mes:02d} {linha['status']} {linha['gravadas']} linhas {linha['segundos']}s")
        linhas.append(linha)
    return linhas


def salvar_relatorio(linhas):
    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    with open(RELATORIO, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=linhas[0].keys())
        writer.writeheader()
        writer.writerows(linhas)

def ingerir_zonas(con):
    destino = LAKE.parent / "zones" / "zones.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    con.sql(f"COPY (SELECT * FROM read_csv('{URL_ZONAS}')) TO '{destino.as_posix()}' (FORMAT parquet)")
    print("[lake] zonas ok")

# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    con = duckdb.connect()
    ingerir_zonas(con)
    inicio = time.perf_counter()

    falhas = baixar_todos(MESES)
    linhas = processar_todos(con, MESES, falhas)
    salvar_relatorio(linhas)

    ok = sum(l["status"] in ("ok", "pulado") for l in linhas)
    total_min = (time.perf_counter() - inicio) / 60
    print(f"\n{ok}/{len(linhas)} meses no lake em {total_min:.1f} min. Relatório: {RELATORIO}")