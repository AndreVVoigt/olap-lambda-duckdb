-- As 10 zonas com mais embarques em janeiro de 2024.
-- JOIN entre a tabela de corridas e a dimensão de zonas.
SELECT z.Borough AS distrito,
       z.Zone    AS zona,
       count(*)  AS corridas
FROM trips_validas t
JOIN zones z ON t.pu_location_id = z.LocationID
WHERE t.ano = 2024 AND t.mes = 1
GROUP BY ALL
ORDER BY corridas DESC
LIMIT 10
