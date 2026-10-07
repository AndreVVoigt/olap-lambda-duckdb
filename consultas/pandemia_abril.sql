-- Abril antes, durante e depois da pandemia.
-- Partition pruning: lê só 3 dos 84 arquivos.
SELECT ano,
       count(*)                          AS corridas,
       round(avg(trip_distance), 2)      AS distancia_media_milhas,
       round(avg(total_amount), 2)       AS valor_medio_usd
FROM trips_validas
WHERE mes = 4 AND ano IN (2019, 2020, 2025)
GROUP BY ano
ORDER BY ano
