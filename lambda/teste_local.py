import json

from handler import lambda_handler


def consultar(sql, titulo):
    r = lambda_handler({"sql": sql}, None)          # mesmo formato do boto3 invoke
    corpo = json.loads(r["body"])
    print(f"\n=== {titulo} -> HTTP {r['statusCode']} ===")
    if r["statusCode"] == 200:
        extra = " (TRUNCADO)" if corpo["truncado"] else ""
        print(f"{corpo['linhas']} linhas em {corpo['tempo_ms']} ms{extra}")
        for linha in corpo["dados"][:5]:
            print("  ", linha)
    else:
        print("  ", corpo["erro"])


consultar("""
    SELECT ano, count(*) AS corridas, round(sum(total_amount) / 1e6, 1) AS receita_mi_usd
    FROM trips_validas
    GROUP BY ano ORDER BY ano
""", "Corridas e receita por ano (lake inteiro)")

consultar("""
    SELECT z.Borough AS distrito, z.Zone AS zona, count(*) AS corridas
    FROM trips_validas t JOIN zones z ON t.pu_location_id = z.LocationID
    WHERE t.ano = 2024 AND t.mes = 1
    GROUP BY ALL ORDER BY corridas DESC LIMIT 10
""", "Top 10 zonas de embarque, jan/2024")

consultar("""
    SELECT hour(tpep_pickup_datetime) AS hora, count(*) AS corridas
    FROM trips_validas
    WHERE ano = 2020 AND mes = 4
    GROUP BY 1 ORDER BY 1
""", "Corridas por hora, abril/2020")

# Comportamentos que precisam funcionar
consultar("SELEC * FROM trips", "SQL com erro de digitação (deve dar 400)")
consultar("SELECT * FROM viagens", "Tabela inexistente (deve dar 400)")
consultar("SELECT * FROM trips WHERE ano = 2024 AND mes = 1", "Resultado grande (deve truncar)")