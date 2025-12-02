-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Verificar
SELECT extname, extversion FROM pg_extension 
WHERE extname IN ('timescaledb', 'uuid-ossp');
