-- Embarques nos três aeroportos por ano.
-- Usa a dimensão de zonas pelo nome, sem depender dos IDs.
SELECT t.ano,
       z.Zone                         AS aeroporto,
       count(*)                       AS embarques,
       round(avg(t.total_amount), 2)  AS valor_medio_usd
FROM trips_validas t
JOIN zones z ON t.pu_location_id = z.LocationID
WHERE z.Zone IN ('JFK Airport', 'LaGuardia Airport', 'Newark Airport')
GROUP BY ALL
ORDER BY t.ano, embarques DESC
