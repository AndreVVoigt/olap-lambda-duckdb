-- Corridas por dia da semana e hora em março de 2025 (168 linhas: 7 dias × 24 horas).
-- Bom para um mapa de calor: picos de rush e madrugadas de sexta e sábado.
-- dia_semana: 0 = domingo, 6 = sábado.
SELECT dayofweek(tpep_pickup_datetime) AS dia_semana,
       hour(tpep_pickup_datetime)      AS hora,
       count(*)                        AS corridas
FROM trips_validas
WHERE ano = 2025 AND mes = 3
GROUP BY ALL
ORDER BY dia_semana, hora
