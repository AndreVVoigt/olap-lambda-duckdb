-- Corridas e receita por ano, no lake inteiro (2019-2025)
SELECT ano,
       count(*)                           AS corridas,
       round(sum(total_amount) / 1e6, 1)  AS receita_mi_usd
FROM trips_validas
GROUP BY ano
ORDER BY ano