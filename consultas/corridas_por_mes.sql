-- Corridas por mês, de 2019 a 2025 (84 linhas).
-- Mostra a queda da pandemia em 2020 e a recuperação depois.
-- Lê só a coluna is_suspeita: ano e mes vêm do nome das pastas.
SELECT ano, mes, count(*) AS corridas
FROM trips_validas
GROUP BY ano, mes
ORDER BY ano, mes
