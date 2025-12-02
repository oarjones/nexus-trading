# 🗄️ Arquitectura Técnica - Documento 2/7

## Arquitectura de Datos y Almacenamiento

**Versión:** 1.0  
**Fecha:** Diciembre 2024  
**Proyecto:** Bot de Trading Autónomo con IA

---

## 1. Visión General

### 1.1 Rol de Cada Base de Datos

| BD | Propósito | Datos | Retención |
|----|-----------|-------|-----------|
| **PostgreSQL 15+** | Transaccional, configuración | Trades, órdenes, config, audit | Indefinida |
| **TimescaleDB** | Series temporales (extensión PG) | OHLCV, indicadores calculados | 5 años completos, 10+ años comprimidos |
| **Redis 7+** | Cache, pub/sub, estado volátil | Quotes real-time, sesiones, eventos | TTL variable (1min - 24h) |
| **InfluxDB 2.x** | Métricas del sistema | Performance, latencias, health | 90 días detallado, 2 años agregado |

### 1.2 Flujo de Datos Simplificado

```
Brokers/APIs → Ingesta → Redis (cache) → TimescaleDB (persistencia)
                              ↓
                       Feature Store (Parquet + PG metadata)
                              ↓
                    Agentes IA → PostgreSQL (decisiones/trades)
                              ↓
                       InfluxDB (métricas)
```

**Principio clave:** Los datos fluyen en una dirección. Cada BD tiene un propósito claro. Sin duplicación innecesaria.

---

## 2. PostgreSQL - Esquemas Principales

### 2.1 Esquema `trading`

**Tabla: `orders`**

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | UUID | PK |
| symbol | VARCHAR(20) | Ticker/par |
| side | ENUM('buy','sell') | Dirección |
| order_type | ENUM('market','limit','stop_limit') | Tipo |
| quantity | DECIMAL(18,8) | Cantidad |
| price | DECIMAL(18,8) | Precio límite (NULL si market) |
| status | ENUM('pending','sent','partial','filled','cancelled','rejected') | Estado |
| broker | ENUM('ibkr','kraken') | Broker destino |
| broker_order_id | VARCHAR(50) | ID externo |
| strategy_id | VARCHAR(50) | Estrategia origen |
| created_at | TIMESTAMPTZ | Creación |
| updated_at | TIMESTAMPTZ | Última actualización |
| filled_at | TIMESTAMPTZ | Ejecución completa |
| filled_qty | DECIMAL(18,8) | Cantidad ejecutada |
| avg_fill_price | DECIMAL(18,8) | Precio promedio |
| commission | DECIMAL(18,8) | Comisión pagada |

**Índices:** `(symbol, created_at)`, `(status)`, `(strategy_id, created_at)`

**Tabla: `trades`** (fills ejecutados)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | UUID | PK |
| order_id | UUID | FK → orders |
| symbol | VARCHAR(20) | Ticker |
| side | ENUM('buy','sell') | Dirección |
| quantity | DECIMAL(18,8) | Cantidad del fill |
| price | DECIMAL(18,8) | Precio de ejecución |
| commission | DECIMAL(18,8) | Comisión |
| executed_at | TIMESTAMPTZ | Timestamp de ejecución |
| broker | ENUM('ibkr','kraken') | Broker |

**Tabla: `positions`** (estado actual)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| symbol | VARCHAR(20) | PK |
| quantity | DECIMAL(18,8) | Cantidad (negativo = short) |
| avg_entry_price | DECIMAL(18,8) | Precio medio de entrada |
| current_price | DECIMAL(18,8) | Último precio conocido |
| unrealized_pnl | DECIMAL(18,8) | P&L no realizado |
| realized_pnl | DECIMAL(18,8) | P&L realizado acumulado |
| opened_at | TIMESTAMPTZ | Primera entrada |
| updated_at | TIMESTAMPTZ | Última actualización |

### 2.2 Esquema `config`

**Tabla: `strategies`**

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | VARCHAR(50) | PK (ej: "momentum_eu_v1") |
| name | VARCHAR(100) | Nombre descriptivo |
| enabled | BOOLEAN | Activa/inactiva |
| params | JSONB | Parámetros configurables |
| allowed_symbols | TEXT[] | Símbolos permitidos |
| regime_filter | TEXT[] | Regímenes compatibles |
| max_positions | INTEGER | Límite de posiciones simultáneas |
| created_at | TIMESTAMPTZ | Creación |
| updated_at | TIMESTAMPTZ | Última modificación |

**Tabla: `risk_limits`**

| Columna | Tipo | Descripción |
|---------|------|-------------|
| key | VARCHAR(50) | PK (ej: "max_position_pct") |
| value | DECIMAL(18,8) | Valor numérico |
| description | TEXT | Descripción |
| updated_at | TIMESTAMPTZ | Última modificación |
| updated_by | VARCHAR(50) | Quién lo cambió |

### 2.3 Esquema `audit`

**Tabla: `decisions`** (event sourcing de decisiones)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | UUID | PK |
| timestamp | TIMESTAMPTZ | Momento de decisión |
| decision_type | VARCHAR(50) | Tipo (entry, exit, skip, etc.) |
| symbol | VARCHAR(20) | Activo |
| signals | JSONB | Señales de entrada (snapshot) |
| risk_check | JSONB | Resultado de validación de riesgo |
| final_action | VARCHAR(50) | Acción tomada |
| reasoning | TEXT | Explicación (para debugging) |
| order_id | UUID | FK → orders (si aplica) |

**Tabla: `system_events`**

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | BIGSERIAL | PK |
| timestamp | TIMESTAMPTZ | Momento |
| event_type | VARCHAR(50) | Tipo de evento |
| severity | ENUM('info','warning','error','critical') | Severidad |
| component | VARCHAR(50) | Componente origen |
| message | TEXT | Descripción |
| metadata | JSONB | Datos adicionales |

**Política de retención:** Particionar `decisions` y `system_events` por mes. Archivar > 1 año.

---

## 3. TimescaleDB - Series Temporales

### 3.1 Hypertable Principal: `ohlcv`

```sql
CREATE TABLE market_data.ohlcv (
    time        TIMESTAMPTZ NOT NULL,
    symbol      VARCHAR(20) NOT NULL,
    timeframe   VARCHAR(10) NOT NULL,  -- '1m', '5m', '1h', '1d'
    open        DECIMAL(18,8),
    high        DECIMAL(18,8),
    low         DECIMAL(18,8),
    close       DECIMAL(18,8),
    volume      DECIMAL(24,8),
    source      VARCHAR(20),           -- 'ibkr', 'yahoo', 'kraken'
    PRIMARY KEY (time, symbol, timeframe)
);

SELECT create_hypertable('market_data.ohlcv', 'time');
```

**Políticas de retención:**

| Timeframe | Retención completa | Compresión después de |
|-----------|-------------------|----------------------|
| 1m | 6 meses | 1 mes |
| 5m | 2 años | 3 meses |
| 1h | 5 años | 6 meses |
| 1d | Indefinida | 1 año |

### 3.2 Hypertable: `indicators` (indicadores pre-calculados)

```sql
CREATE TABLE market_data.indicators (
    time        TIMESTAMPTZ NOT NULL,
    symbol      VARCHAR(20) NOT NULL,
    timeframe   VARCHAR(10) NOT NULL,
    indicator   VARCHAR(30) NOT NULL,  -- 'rsi_14', 'macd_hist', etc.
    value       DECIMAL(18,8),
    PRIMARY KEY (time, symbol, timeframe, indicator)
);

SELECT create_hypertable('market_data.indicators', 'time');
```

**Indicadores almacenados (calculados en ingesta):**

| Indicador | Descripción |
|-----------|-------------|
| sma_20, sma_50, sma_200 | Medias móviles simples |
| ema_12, ema_26 | Medias móviles exponenciales |
| rsi_14 | RSI período 14 |
| macd_line, macd_signal, macd_hist | MACD estándar |
| atr_14 | Average True Range |
| bb_upper, bb_lower, bb_middle | Bandas de Bollinger |
| adx_14 | Average Directional Index |

### 3.3 Continuous Aggregates

Para queries rápidas en dashboards:

```sql
CREATE MATERIALIZED VIEW market_data.ohlcv_1h
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) AS bucket,
    symbol,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume
FROM market_data.ohlcv
WHERE timeframe = '1m'
GROUP BY bucket, symbol;
```

---

## 4. Redis - Cache y Pub/Sub

### 4.1 Estructuras de Datos

| Key Pattern | Tipo | TTL | Contenido |
|-------------|------|-----|-----------|
| `quote:{symbol}` | Hash | 60s | `{bid, ask, last, volume, timestamp}` |
| `position:{symbol}` | Hash | - | Mirror de PostgreSQL (sync cada 5s) |
| `signal:{strategy}:{symbol}` | Hash | 5min | Última señal generada |
| `regime:current` | String | 1min | Régimen detectado actual |
| `circuit:{component}` | String | - | Estado del circuit breaker |
| `session:state` | Hash | - | Estado global del sistema |

### 4.2 Canales Pub/Sub

| Canal | Publicador | Suscriptores | Mensaje |
|-------|------------|--------------|---------|
| `quotes` | Data ingester | Agentes, Dashboard | Quotes en tiempo real |
| `signals` | Agentes analistas | Orchestrator | Nuevas señales |
| `orders` | Execution agent | Portfolio, Risk | Cambios de estado de órdenes |
| `alerts` | Cualquiera | Telegram bot, Logger | Alertas del sistema |
| `regime` | Regime detector | Strategy manager, Risk | Cambios de régimen |

### 4.3 Ejemplo de Uso

```python
# Publicar quote
redis.hset("quote:AAPL", mapping={
    "bid": "185.50", "ask": "185.52", 
    "last": "185.51", "volume": "1234567",
    "timestamp": "2024-12-15T14:30:00Z"
})
redis.expire("quote:AAPL", 60)

# Suscribirse a señales
pubsub = redis.pubsub()
pubsub.subscribe("signals")
for message in pubsub.listen():
    process_signal(message)
```

---

## 5. InfluxDB - Métricas del Sistema

### 5.1 Measurements Principales

| Measurement | Tags | Fields | Descripción |
|-------------|------|--------|-------------|
| `system_health` | component | cpu_pct, mem_pct, status | Health de componentes |
| `api_latency` | endpoint, broker | latency_ms, status_code | Latencia de APIs |
| `order_execution` | symbol, broker, side | slippage_bps, fill_time_ms | Métricas de ejecución |
| `model_performance` | model_name, symbol | accuracy, calibration_error | Performance de modelos ML |
| `portfolio` | - | total_value, cash, positions_count, daily_pnl | Estado del portfolio |

### 5.2 Ejemplo de Escritura

```python
from influxdb_client import Point

point = Point("order_execution") \
    .tag("symbol", "AAPL") \
    .tag("broker", "ibkr") \
    .tag("side", "buy") \
    .field("slippage_bps", 2.5) \
    .field("fill_time_ms", 150)

write_api.write(bucket="trading", record=point)
```

### 5.3 Retención

| Bucket | Retención | Downsampling |
|--------|-----------|--------------|
| trading_raw | 7 días | - |
| trading_1h | 90 días | Agregado horario |
| trading_1d | 2 años | Agregado diario |

---

## 6. Feature Store

### 6.1 Diseño Pragmático

Para tu escala, un feature store simple basado en Parquet + metadata en PostgreSQL es suficiente.

**Estructura de archivos:**

```
data/features/
├── symbol=AAPL/
│   ├── 2024-01/features.parquet
│   ├── 2024-02/features.parquet
│   └── ...
├── symbol=EURUSD/
│   └── ...
└── _metadata/
    └── feature_catalog.json
```

**Tabla de metadata en PostgreSQL:**

```sql
CREATE TABLE features.catalog (
    feature_name    VARCHAR(50) PRIMARY KEY,
    description     TEXT,
    data_type       VARCHAR(20),
    category        VARCHAR(30),  -- 'technical', 'fundamental', 'sentiment'
    computation     TEXT,         -- Fórmula o descripción del cálculo
    dependencies    TEXT[],       -- Features de las que depende
    lookback_days   INTEGER,      -- Ventana temporal requerida
    updated_at      TIMESTAMPTZ
);
```

### 6.2 Catálogo de Features

| Feature | Categoría | Descripción | Lookback |
|---------|-----------|-------------|----------|
| returns_1d, returns_5d, returns_20d | Technical | Retornos en ventana | 1, 5, 20 |
| volatility_20d | Technical | Desviación estándar de retornos | 20 |
| rsi_14 | Technical | Relative Strength Index | 14 |
| macd_hist | Technical | Histograma MACD | 26 |
| volume_ratio_20d | Technical | Volumen vs media 20d | 20 |
| sma_ratio_50 | Technical | Precio / SMA(50) | 50 |
| atr_14 | Technical | Average True Range | 14 |
| bb_position | Technical | Posición dentro de Bollinger | 20 |
| adx_14 | Technical | Fuerza de tendencia | 14 |
| sector_momentum | Cross-sectional | Retorno vs sector | 20 |
| market_beta_60d | Cross-sectional | Beta rolling vs mercado | 60 |
| news_sentiment_24h | Sentiment | Sentimiento agregado noticias | 1 |
| social_volume_7d | Sentiment | Menciones en redes (si disponible) | 7 |

### 6.3 Pipeline de Generación

1. **Trigger:** Cada cierre de mercado (o cada hora para crypto)
2. **Input:** OHLCV de TimescaleDB + datos externos
3. **Cálculo:** Vectorizado con pandas/numpy
4. **Output:** Append a Parquet particionado
5. **Cache:** Features del día actual en Redis para acceso rápido

---

## 7. Data Pipelines

### 7.1 Pipeline de Ingesta de Precios

| Paso | Frecuencia | Fuente | Destino |
|------|------------|--------|---------|
| 1. Fetch quotes | 1s (mercado abierto) | IBKR/Kraken | Redis |
| 2. Agregar OHLCV 1m | Cada minuto | Redis | TimescaleDB |
| 3. Calcular indicadores | Cada 5 min | TimescaleDB | TimescaleDB (indicators) |
| 4. Generar features | Cierre de mercado | TimescaleDB | Feature Store |

### 7.2 Pipeline de Noticias/Sentiment

| Paso | Frecuencia | Fuente | Destino |
|------|------------|--------|---------|
| 1. Fetch noticias | 15 min | NewsAPI, RSS | PostgreSQL (raw_news) |
| 2. Clasificar sentiment | 15 min | FinBERT | PostgreSQL (news_sentiment) |
| 3. Agregar por símbolo | 1 hora | PostgreSQL | Feature Store |

### 7.3 Scheduling

Usar `APScheduler` (Python) para coordinación:

```python
scheduler = BackgroundScheduler()

# Quotes real-time
scheduler.add_job(fetch_quotes, 'interval', seconds=1, id='quotes')

# OHLCV agregación
scheduler.add_job(aggregate_ohlcv, 'cron', minute='*', id='ohlcv_1m')

# Indicadores
scheduler.add_job(calculate_indicators, 'cron', minute='*/5', id='indicators')

# Features diarios (después de cierre EU: 18:00 CET)
scheduler.add_job(generate_daily_features, 'cron', hour=18, minute=30, id='features')
```

---

## 8. Calidad de Datos

### 8.1 Validaciones en Ingesta

| Validación | Acción si falla |
|------------|-----------------|
| Precio > 0 | Descartar, loguear warning |
| Volumen >= 0 | Descartar, loguear warning |
| Timestamp no futuro | Descartar, loguear error |
| Gap > 10% vs último precio | Aceptar pero marcar para revisión |
| Datos duplicados | Ignorar (upsert) |

### 8.2 Reconciliación Diaria

Proceso automático post-cierre:

1. **Comparar posiciones:** PostgreSQL vs broker real (via API)
2. **Verificar trades:** Todos los fills del día están registrados
3. **Alertar discrepancias:** Telegram + log crítico si hay diferencias

### 8.3 Alertas de Calidad

| Condición | Severidad | Acción |
|-----------|-----------|--------|
| Sin datos de símbolo > 5 min | Warning | Log + revisar fuente |
| Sin datos de ningún símbolo > 2 min | Error | Circuit breaker |
| Discrepancia posiciones > 1% | Critical | Pausa + alerta humano |
| Features con NaN > 10% | Warning | Imputar o excluir símbolo |

---

## 9. Setup en Windows 11

### 9.1 Opción Recomendada: Docker Compose

**Prerequisitos:**
1. Instalar [Docker Desktop para Windows](https://www.docker.com/products/docker-desktop/)
2. Habilitar WSL2 (Docker Desktop lo guía)
3. Asignar al menos 8 GB RAM a Docker (Settings → Resources)

**docker-compose.yml:**

```yaml
version: '3.8'

services:
  postgres:
    image: timescale/timescaledb:latest-pg15
    container_name: trading_db
    environment:
      POSTGRES_USER: trading
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: trading
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: trading_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  influxdb:
    image: influxdb:2.7
    container_name: trading_influx
    environment:
      DOCKER_INFLUXDB_INIT_MODE: setup
      DOCKER_INFLUXDB_INIT_USERNAME: admin
      DOCKER_INFLUXDB_INIT_PASSWORD: ${INFLUX_PASSWORD}
      DOCKER_INFLUXDB_INIT_ORG: trading
      DOCKER_INFLUXDB_INIT_BUCKET: trading
    ports:
      - "8086:8086"
    volumes:
      - influx_data:/var/lib/influxdb2
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: trading_grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  influx_data:
  grafana_data:
```

**Archivo `.env`:**

```env
DB_PASSWORD=tu_password_seguro
INFLUX_PASSWORD=tu_password_influx
```

**Comandos de inicio:**

```powershell
# Desde PowerShell, en el directorio del proyecto
docker-compose up -d

# Verificar que todo está corriendo
docker-compose ps

# Ver logs
docker-compose logs -f postgres
```

### 9.2 Opción Alternativa: Instalación Nativa

Si prefieres no usar Docker:

| Componente | Instalador | Notas |
|------------|------------|-------|
| PostgreSQL 15 | [EDB Installer](https://www.postgresql.org/download/windows/) | Incluir pgAdmin |
| TimescaleDB | [Instrucciones](https://docs.timescale.com/install/latest/self-hosted/installation-windows/) | Extensión para PG existente |
| Redis | [Memurai](https://www.memurai.com/) o [WSL2](https://redis.io/docs/install/install-redis/install-redis-on-windows/) | Redis no tiene build oficial Windows |
| InfluxDB | [Descarga oficial](https://portal.influxdata.com/downloads/) | Versión Windows disponible |

### 9.3 Verificación del Setup

```powershell
# PostgreSQL + TimescaleDB
psql -h localhost -U trading -d trading -c "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"

# Redis
redis-cli ping
# Respuesta esperada: PONG

# InfluxDB (abrir en navegador)
# http://localhost:8086

# Grafana (abrir en navegador)
# http://localhost:3000 (admin/admin inicial)
```

### 9.4 Script de Inicialización de Esquemas

Crear `init-scripts/01_init_schemas.sql`:

```sql
-- Extensiones
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Esquemas
CREATE SCHEMA IF NOT EXISTS trading;
CREATE SCHEMA IF NOT EXISTS market_data;
CREATE SCHEMA IF NOT EXISTS config;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS features;

-- Tipos ENUM
CREATE TYPE trading.order_status AS ENUM 
    ('pending', 'sent', 'partial', 'filled', 'cancelled', 'rejected');
CREATE TYPE trading.order_side AS ENUM ('buy', 'sell');
CREATE TYPE trading.broker_type AS ENUM ('ibkr', 'kraken');
CREATE TYPE audit.severity_level AS ENUM ('info', 'warning', 'error', 'critical');
```

### 9.5 Variables de Entorno para Python

Crear archivo `.env` en raíz del proyecto:

```env
# Base de datos
DATABASE_URL=postgresql://trading:${DB_PASSWORD}@localhost:5432/trading
REDIS_URL=redis://localhost:6379/0
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=tu_token_aqui
INFLUXDB_ORG=trading
INFLUXDB_BUCKET=trading

# Paths (Windows)
DATA_DIR=C:\Users\TuUsuario\trading-bot\data
FEATURES_DIR=C:\Users\TuUsuario\trading-bot\data\features
LOGS_DIR=C:\Users\TuUsuario\trading-bot\logs
```

---

## 10. Referencias Cruzadas

| Tema | Documento |
|------|-----------|
| Stack tecnológico completo | Doc 1, Sección 7 |
| Flujo de datos alto nivel | Doc 1, Sección 6 |
| Circuit breakers y modos | Doc 1, Sección 5 |
| Estructura del proyecto | Doc 1, Sección 8 |
| Detalle de agentes MCP | Doc 3 (pendiente) |
| Pipeline de features ML | Doc 5 (pendiente) |

---

*Documento 2 de 7 - Arquitectura Técnica del Bot de Trading*  
*Versión 1.0*
