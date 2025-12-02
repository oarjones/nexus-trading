# 🏗️ Fase 0: Infraestructura Base

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 2 semanas  
**Dependencias:** Ninguna  
**Docs técnicos:** Doc 2 (secciones 1, 9), Doc 7 (sección 2)

---

## 1. Objetivos de la Fase

| Objetivo | Criterio de éxito |
|----------|-------------------|
| Docker Compose funcional | `docker-compose up` sin errores |
| PostgreSQL + TimescaleDB | Extensión activa, esquemas creados |
| Redis operativo | `PING` → `PONG` |
| InfluxDB configurado | Bucket `trading` accesible |
| Grafana básico | Dashboard de health visible |
| Estructura de proyecto | Directorios creados según Doc 1 sec 8 |

---

## 2. Prerequisitos

### 2.1 Software requerido

| Software | Versión | Verificación |
|----------|---------|--------------|
| Windows 11 | 22H2+ | `winver` |
| Docker Desktop | 4.25+ | `docker --version` |
| WSL2 | - | Docker Desktop lo habilita |
| Git | 2.40+ | `git --version` |
| Python | 3.11+ | `python --version` |

### 2.2 Recursos de sistema

- RAM disponible para Docker: 8 GB mínimo
- Disco: 20 GB libres
- Puertos libres: 5432, 6379, 8086, 3000

---

## 3. Tareas

### Tarea 0.1: Crear estructura de directorios

**Estado:** ⬜ Pendiente

**Objetivo:** Establecer la estructura base del proyecto según Doc 1 sec 8.

**Subtareas:**
- [ ] Crear directorio raíz `trading-bot`
- [ ] Crear subdirectorios de código
- [ ] Crear subdirectorios de configuración
- [ ] Crear `.gitignore`

**Input:** Estructura definida en Doc 1 sección 8

**Output:** Árbol de directorios completo

**Script PowerShell:**
```powershell
# Ejecutar desde directorio padre donde quieres el proyecto
$root = "trading-bot"

# Directorios principales
$dirs = @(
    "$root/src/core",
    "$root/src/agents",
    "$root/src/strategies",
    "$root/src/ml/models",
    "$root/src/ml/features",
    "$root/src/ml/training",
    "$root/src/trading",
    "$root/src/risk",
    "$root/src/data",
    "$root/src/regime",
    "$root/mcp-servers",
    "$root/tests/unit",
    "$root/tests/integration",
    "$root/tests/e2e",
    "$root/config",
    "$root/scripts",
    "$root/docs",
    "$root/data/features",
    "$root/data/raw",
    "$root/logs",
    "$root/init-scripts"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Path $dir -Force
}

# Crear archivos vacíos __init__.py
$pythonDirs = Get-ChildItem -Path "$root/src" -Recurse -Directory
foreach ($d in $pythonDirs) {
    New-Item -ItemType File -Path "$($d.FullName)/__init__.py" -Force
}
```

**Validación:**
```powershell
# Debe mostrar estructura completa
tree trading-bot /F
```

---

### Tarea 0.2: Configurar archivo .env

**Estado:** ⬜ Pendiente

**Objetivo:** Crear archivo de variables de entorno seguro.

**Referencias:** Doc 2 sección 9.5

**Subtareas:**
- [ ] Crear `.env` con passwords generados
- [ ] Crear `.env.example` sin secrets
- [ ] Añadir `.env` a `.gitignore`

**Input:** Template de Doc 2 sec 9.5

**Output:** Archivos `.env` y `.env.example`

**Contenido `.env`:**
```env
# === Base de datos ===
DB_PASSWORD=<generar_password_seguro>
POSTGRES_USER=trading
POSTGRES_DB=trading

# === Redis ===
REDIS_URL=redis://localhost:6379/0

# === InfluxDB ===
INFLUX_PASSWORD=<generar_password_seguro>
INFLUXDB_URL=http://localhost:8086
INFLUXDB_ORG=trading
INFLUXDB_BUCKET=trading

# === Grafana ===
GRAFANA_PASSWORD=<generar_password_seguro>

# === Paths (ajustar según tu sistema) ===
PROJECT_ROOT=C:/Users/TuUsuario/trading-bot
DATA_DIR=${PROJECT_ROOT}/data
LOGS_DIR=${PROJECT_ROOT}/logs

# === Entorno ===
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

**Contenido `.env.example`:**
```env
# Copiar a .env y rellenar valores
DB_PASSWORD=
INFLUX_PASSWORD=
GRAFANA_PASSWORD=
PROJECT_ROOT=C:/Users/TuUsuario/trading-bot
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

**Validación:** `.env` existe y no está en git (`git status` no lo muestra)

---

### Tarea 0.3: Crear docker-compose.yml

**Estado:** ✅ Completado

**Objetivo:** Definir servicios de infraestructura en Docker Compose.

**Referencias:** Doc 2 sección 9.1

**Subtareas:**
- [ ] Crear `docker-compose.yml` con 4 servicios
- [ ] Configurar volúmenes persistentes
- [ ] Configurar healthchecks
- [ ] Mapear puertos

**Input:** Configuración de Doc 2 sec 9.1

**Output:** `docker-compose.yml` funcional

**Contenido `docker-compose.yml`:**
```yaml
version: '3.8'

services:
  # PostgreSQL + TimescaleDB
  postgres:
    image: timescale/timescaledb:latest-pg15
    container_name: trading_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-trading}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-trading}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U trading -d trading"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis
  redis:
    image: redis:7-alpine
    container_name: trading_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # InfluxDB
  influxdb:
    image: influxdb:2.7
    container_name: trading_influxdb
    environment:
      DOCKER_INFLUXDB_INIT_MODE: setup
      DOCKER_INFLUXDB_INIT_USERNAME: admin
      DOCKER_INFLUXDB_INIT_PASSWORD: ${INFLUX_PASSWORD}
      DOCKER_INFLUXDB_INIT_ORG: ${INFLUXDB_ORG:-trading}
      DOCKER_INFLUXDB_INIT_BUCKET: ${INFLUXDB_BUCKET:-trading}
    ports:
      - "8086:8086"
    volumes:
      - influx_data:/var/lib/influxdb2
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8086/ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Grafana
  grafana:
    image: grafana/grafana:latest
    container_name: trading_grafana
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana/provisioning:/etc/grafana/provisioning:ro
    depends_on:
      - postgres
      - influxdb
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  influx_data:
  grafana_data:
```

**Validación:**
```powershell
docker-compose config  # Debe parsear sin errores
```

---

### Tarea 0.4: Crear scripts de inicialización de BD

**Estado:** ✅ Completado

**Objetivo:** Scripts SQL para crear esquemas y tablas base.

**Referencias:** Doc 2 secciones 2, 3, 9.4

**Subtareas:**
- [ ] Crear `01_extensions.sql` (extensiones)
- [ ] Crear `02_schemas.sql` (esquemas y tipos ENUM)
- [ ] Crear `03_tables_trading.sql` (tablas trading)
- [ ] Crear `04_tables_config.sql` (tablas config)
- [ ] Crear `05_tables_audit.sql` (tablas audit)
- [ ] Crear `06_tables_market_data.sql` (hypertables)

**Input:** Esquemas de Doc 2 secciones 2 y 3

**Output:** Scripts SQL en `init-scripts/`

**Archivo `init-scripts/01_extensions.sql`:**
```sql
-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Verificar
SELECT extname, extversion FROM pg_extension 
WHERE extname IN ('timescaledb', 'uuid-ossp');
```

**Archivo `init-scripts/02_schemas.sql`:**
```sql
-- Esquemas
CREATE SCHEMA IF NOT EXISTS trading;
CREATE SCHEMA IF NOT EXISTS market_data;
CREATE SCHEMA IF NOT EXISTS config;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS features;

-- Tipos ENUM
DO $$ BEGIN
    CREATE TYPE trading.order_status AS ENUM 
        ('pending', 'sent', 'partial', 'filled', 'cancelled', 'rejected');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE trading.order_side AS ENUM ('buy', 'sell');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE trading.broker_type AS ENUM ('ibkr', 'kraken');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE audit.severity_level AS ENUM ('info', 'warning', 'error', 'critical');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
```

**Archivo `init-scripts/03_tables_trading.sql`:**
```sql
-- Tabla: orders
CREATE TABLE IF NOT EXISTS trading.orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    side trading.order_side NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8),
    status trading.order_status NOT NULL DEFAULT 'pending',
    broker trading.broker_type NOT NULL,
    broker_order_id VARCHAR(50),
    strategy_id VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    filled_at TIMESTAMPTZ,
    filled_qty DECIMAL(18,8) DEFAULT 0,
    avg_fill_price DECIMAL(18,8),
    commission DECIMAL(18,8) DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_orders_symbol_created 
    ON trading.orders(symbol, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_status 
    ON trading.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_strategy 
    ON trading.orders(strategy_id, created_at);

-- Tabla: trades (fills)
CREATE TABLE IF NOT EXISTS trading.trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES trading.orders(id),
    symbol VARCHAR(20) NOT NULL,
    side trading.order_side NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    commission DECIMAL(18,8) DEFAULT 0,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    broker trading.broker_type NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_order 
    ON trading.trades(order_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_executed 
    ON trading.trades(symbol, executed_at);

-- Tabla: positions
CREATE TABLE IF NOT EXISTS trading.positions (
    symbol VARCHAR(20) PRIMARY KEY,
    quantity DECIMAL(18,8) NOT NULL DEFAULT 0,
    avg_entry_price DECIMAL(18,8),
    current_price DECIMAL(18,8),
    unrealized_pnl DECIMAL(18,8) DEFAULT 0,
    realized_pnl DECIMAL(18,8) DEFAULT 0,
    opened_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Archivo `init-scripts/04_tables_config.sql`:**
```sql
-- Tabla: strategies
CREATE TABLE IF NOT EXISTS config.strategies (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT false,
    params JSONB NOT NULL DEFAULT '{}',
    allowed_symbols TEXT[],
    regime_filter TEXT[],
    max_positions INTEGER DEFAULT 5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tabla: risk_limits
CREATE TABLE IF NOT EXISTS config.risk_limits (
    key VARCHAR(50) PRIMARY KEY,
    value DECIMAL(18,8) NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(50)
);

-- Insertar límites por defecto (Doc 6 sec 2)
INSERT INTO config.risk_limits (key, value, description) VALUES
    ('max_position_pct', 0.20, 'Máximo % por posición individual'),
    ('max_sector_pct', 0.40, 'Máximo % por sector'),
    ('max_correlation', 0.70, 'Máxima correlación entre posiciones'),
    ('max_drawdown', 0.15, 'Drawdown máximo antes de STOP'),
    ('min_cash_pct', 0.10, 'Mínimo % en cash'),
    ('max_daily_loss', 0.03, 'Pérdida máxima diaria'),
    ('max_weekly_loss', 0.05, 'Pérdida máxima semanal')
ON CONFLICT (key) DO NOTHING;
```

**Archivo `init-scripts/05_tables_audit.sql`:**
```sql
-- Tabla: decisions
CREATE TABLE IF NOT EXISTS audit.decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decision_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    signals JSONB,
    risk_check JSONB,
    final_action VARCHAR(50),
    reasoning TEXT,
    order_id UUID REFERENCES trading.orders(id)
);

CREATE INDEX IF NOT EXISTS idx_decisions_timestamp 
    ON audit.decisions(timestamp);
CREATE INDEX IF NOT EXISTS idx_decisions_symbol 
    ON audit.decisions(symbol, timestamp);

-- Tabla: system_events
CREATE TABLE IF NOT EXISTS audit.system_events (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    severity audit.severity_level NOT NULL DEFAULT 'info',
    component VARCHAR(50),
    message TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp 
    ON audit.system_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_severity 
    ON audit.system_events(severity);
```

**Archivo `init-scripts/06_tables_market_data.sql`:**
```sql
-- Hypertable: ohlcv
CREATE TABLE IF NOT EXISTS market_data.ohlcv (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open DECIMAL(18,8),
    high DECIMAL(18,8),
    low DECIMAL(18,8),
    close DECIMAL(18,8),
    volume DECIMAL(24,8),
    source VARCHAR(20),
    PRIMARY KEY (time, symbol, timeframe)
);

-- Convertir a hypertable (TimescaleDB)
SELECT create_hypertable(
    'market_data.ohlcv', 
    'time',
    if_not_exists => TRUE
);

-- Hypertable: indicators
CREATE TABLE IF NOT EXISTS market_data.indicators (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    indicator VARCHAR(30) NOT NULL,
    value DECIMAL(18,8),
    PRIMARY KEY (time, symbol, timeframe, indicator)
);

SELECT create_hypertable(
    'market_data.indicators', 
    'time',
    if_not_exists => TRUE
);

-- Índices adicionales
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol 
    ON market_data.ohlcv(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_indicators_symbol 
    ON market_data.indicators(symbol, indicator, time DESC);
```

**Validación:** Los scripts se ejecutan sin errores al iniciar el contenedor.

---

### Tarea 0.5: Levantar infraestructura Docker

**Estado:** ✅ Completado

**Objetivo:** Iniciar todos los servicios y verificar health.

**Subtareas:**
- [ ] Ejecutar `docker-compose up -d`
- [ ] Verificar health de todos los servicios
- [ ] Verificar logs sin errores
- [ ] Verificar esquemas creados en PostgreSQL

**Input:** `docker-compose.yml` y scripts de init

**Output:** Todos los servicios running y healthy

**Comandos:**
```powershell
# Navegar al directorio del proyecto
cd trading-bot

# Levantar servicios
docker-compose up -d

# Esperar 30 segundos para inicialización
Start-Sleep -Seconds 30

# Verificar estado
docker-compose ps

# Ver logs de postgres (buscar errores)
docker-compose logs postgres | Select-String -Pattern "ERROR" -Context 0,2

# Verificar TimescaleDB
docker exec trading_postgres psql -U trading -d trading -c "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"

# Verificar esquemas
docker exec trading_postgres psql -U trading -d trading -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('trading', 'market_data', 'config', 'audit', 'features');"

# Verificar Redis
docker exec trading_redis redis-cli ping

# Verificar InfluxDB (abrir en navegador)
# http://localhost:8086
```

**Validación:**
```powershell
# Todos los servicios deben mostrar "Up" y "(healthy)"
docker-compose ps

# Resultado esperado:
# NAME                STATUS              PORTS
# trading_grafana     Up                  0.0.0.0:3000->3000/tcp
# trading_influxdb    Up (healthy)        0.0.0.0:8086->8086/tcp
# trading_postgres    Up (healthy)        0.0.0.0:5432->5432/tcp
# trading_redis       Up (healthy)        0.0.0.0:6379->6379/tcp
```

---

### Tarea 0.6: Configurar Grafana básico

**Estado:** ✅ Completado

**Objetivo:** Dashboard inicial de health del sistema.

**Subtareas:**
- [ ] Crear directorio de provisioning
- [ ] Configurar datasource PostgreSQL
- [ ] Configurar datasource InfluxDB
- [ ] Crear dashboard de health básico

**Input:** Grafana running en puerto 3000

**Output:** Dashboard accesible con métricas de health

**Estructura de directorios:**
```
config/grafana/provisioning/
├── datasources/
│   └── datasources.yml
└── dashboards/
    ├── dashboards.yml
    └── health.json
```

**Archivo `config/grafana/provisioning/datasources/datasources.yml`:**
```yaml
apiVersion: 1

datasources:
  - name: PostgreSQL
    type: postgres
    url: trading_postgres:5432
    database: trading
    user: trading
    secureJsonData:
      password: ${DB_PASSWORD}
    jsonData:
      sslmode: disable
      maxOpenConns: 5
      maxIdleConns: 2

  - name: InfluxDB
    type: influxdb
    url: http://trading_influxdb:8086
    jsonData:
      version: Flux
      organization: trading
      defaultBucket: trading
    secureJsonData:
      token: ${INFLUX_TOKEN}
```

**Archivo `config/grafana/provisioning/dashboards/dashboards.yml`:**
```yaml
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
```

**Dashboard básico (crear manualmente primero):**
1. Acceder a http://localhost:3000 (admin / password de .env)
2. Crear nuevo dashboard
3. Añadir panel "PostgreSQL Connections"
4. Añadir panel "Redis Memory"
5. Exportar JSON y guardar en `config/grafana/provisioning/dashboards/health.json`

**Validación:** Dashboard visible en http://localhost:3000 con paneles de health.

---

### Tarea 0.7: Crear script de verificación

**Estado:** ✅ Completado

**Objetivo:** Script que valida toda la infraestructura.

**Subtareas:**
- [ ] Crear `scripts/verify_infra.py`
- [ ] Verificar conexión a cada servicio
- [ ] Verificar esquemas y tablas
- [ ] Output claro de estado

**Input:** Servicios Docker running

**Output:** Script Python ejecutable

**Archivo `scripts/verify_infra.py`:**
```python
#!/usr/bin/env python3
"""
Verificación de infraestructura - Fase 0
Ejecutar: python scripts/verify_infra.py
"""

import sys
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def check_postgres():
    """Verificar PostgreSQL + TimescaleDB"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="trading",
            user="trading",
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor()
        
        # Verificar TimescaleDB
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
        result = cur.fetchone()
        if not result:
            return False, "TimescaleDB no instalado"
        
        # Verificar esquemas
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata 
            WHERE schema_name IN ('trading', 'market_data', 'config', 'audit', 'features')
        """)
        schemas = [r[0] for r in cur.fetchall()]
        expected = {'trading', 'market_data', 'config', 'audit', 'features'}
        if set(schemas) != expected:
            return False, f"Esquemas faltantes: {expected - set(schemas)}"
        
        # Verificar tablas críticas
        cur.execute("""
            SELECT table_schema || '.' || table_name 
            FROM information_schema.tables 
            WHERE table_schema IN ('trading', 'config', 'audit', 'market_data')
        """)
        tables = [r[0] for r in cur.fetchall()]
        
        required_tables = [
            'trading.orders', 'trading.trades', 'trading.positions',
            'config.strategies', 'config.risk_limits',
            'audit.decisions', 'audit.system_events',
            'market_data.ohlcv', 'market_data.indicators'
        ]
        missing = [t for t in required_tables if t not in tables]
        if missing:
            return False, f"Tablas faltantes: {missing}"
        
        conn.close()
        return True, f"TimescaleDB {result[0]}, {len(tables)} tablas OK"
    
    except Exception as e:
        return False, str(e)


def check_redis():
    """Verificar Redis"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        if r.ping():
            info = r.info()
            return True, f"Redis {info['redis_version']}, memoria: {info['used_memory_human']}"
        return False, "PING falló"
    except Exception as e:
        return False, str(e)


def check_influxdb():
    """Verificar InfluxDB"""
    try:
        from influxdb_client import InfluxDBClient
        client = InfluxDBClient(
            url=os.getenv("INFLUXDB_URL", "http://localhost:8086"),
            token=os.getenv("INFLUX_TOKEN", ""),
            org=os.getenv("INFLUXDB_ORG", "trading")
        )
        health = client.health()
        if health.status == "pass":
            return True, f"InfluxDB {health.version}"
        return False, f"Status: {health.status}"
    except Exception as e:
        return False, str(e)


def check_grafana():
    """Verificar Grafana"""
    try:
        import requests
        resp = requests.get("http://localhost:3000/api/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return True, f"Grafana: {data.get('database', 'OK')}"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 50)
    print("VERIFICACIÓN DE INFRAESTRUCTURA - FASE 0")
    print("=" * 50)
    print()
    
    checks = [
        ("PostgreSQL + TimescaleDB", check_postgres),
        ("Redis", check_redis),
        ("InfluxDB", check_influxdb),
        ("Grafana", check_grafana),
    ]
    
    all_ok = True
    for name, check_fn in checks:
        ok, msg = check_fn()
        status = "✅" if ok else "❌"
        print(f"{status} {name}: {msg}")
        if not ok:
            all_ok = False
    
    print()
    print("=" * 50)
    if all_ok:
        print("✅ INFRAESTRUCTURA OK - Fase 0 completada")
        return 0
    else:
        print("❌ ERRORES DETECTADOS - Revisar antes de continuar")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Dependencias (añadir a `requirements.txt`):**
```
psycopg2-binary>=2.9.9
redis>=5.0.0
influxdb-client>=1.38.0
python-dotenv>=1.0.0
requests>=2.31.0
```

**Validación:**
```powershell
pip install -r requirements.txt
python scripts/verify_infra.py

# Output esperado:
# ✅ PostgreSQL + TimescaleDB: TimescaleDB 2.x.x, 9 tablas OK
# ✅ Redis: Redis 7.x.x, memoria: 1.5M
# ✅ InfluxDB: InfluxDB 2.7.x
# ✅ Grafana: Grafana: OK
# ✅ INFRAESTRUCTURA OK - Fase 0 completada
```

---

### Tarea 0.8: Crear requirements.txt base

**Estado:** ✅ Completado

**Objetivo:** Dependencias Python para todo el proyecto.

**Subtareas:**
- [ ] Crear `requirements.txt` con dependencias core
- [ ] Crear `requirements-dev.txt` para desarrollo
- [ ] Verificar instalación en entorno virtual

**Output:** Archivos de requirements

**Archivo `requirements.txt`:**
```
# Core
python-dotenv>=1.0.0

# Base de datos
psycopg2-binary>=2.9.9
redis>=5.0.0
influxdb-client>=1.38.0
sqlalchemy>=2.0.0

# Data
pandas>=2.1.0
numpy>=1.26.0

# HTTP
requests>=2.31.0
httpx>=0.25.0

# Scheduling
apscheduler>=3.10.0

# Logging
structlog>=23.2.0

# Configuración
pydantic>=2.5.0
pydantic-settings>=2.1.0
pyyaml>=6.0.1
```

**Archivo `requirements-dev.txt`:**
```
-r requirements.txt

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0

# Linting
ruff>=0.1.0
mypy>=1.7.0

# Notebooks
jupyter>=1.0.0
ipykernel>=6.27.0
```

**Validación:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip list  # Verificar instalación
```

---

## 4. Checklist de Finalización

```
Fase 0: Infraestructura Base
════════════════════════════

[X ] Tarea 0.1: Estructura de directorios
[X ] Tarea 0.2: Archivo .env configurado
[X ] Tarea 0.3: docker-compose.yml creado
[X ] Tarea 0.4: Scripts SQL de inicialización
[X ] Tarea 0.5: Servicios Docker running
[X ] Tarea 0.6: Grafana con dashboard básico
[X ] Tarea 0.7: Script de verificación pasa
[X ] Tarea 0.8: Requirements instalados

Gate de avance: Todos los items ✅
```

---

## 5. Troubleshooting

### PostgreSQL no inicia

```powershell
# Ver logs
docker-compose logs postgres

# Causas comunes:
# - Puerto 5432 ocupado → netstat -ano | findstr 5432
# - Password vacío en .env → verificar DB_PASSWORD
# - Volumen corrupto → docker volume rm trading-bot_postgres_data
```

### TimescaleDB no se activa

```sql
-- Ejecutar manualmente dentro del contenedor
docker exec -it trading_postgres psql -U trading -d trading
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
```

### Redis connection refused

```powershell
# Verificar que el contenedor está corriendo
docker ps | findstr redis

# Verificar puerto
Test-NetConnection -ComputerName localhost -Port 6379
```

### Grafana no muestra datos

- Verificar que el datasource tiene las credenciales correctas
- El token de InfluxDB debe generarse manualmente en la UI de InfluxDB

---

## 6. Referencias

| Tema | Documento | Sección |
|------|-----------|---------|
| Esquemas PostgreSQL | Doc 2 | 2 |
| Hypertables TimescaleDB | Doc 2 | 3 |
| Docker Compose | Doc 2 | 9.1 |
| Variables de entorno | Doc 2 | 9.5 |
| Estructura proyecto | Doc 1 | 8 |
| Stack tecnológico | Doc 1 | 7 |

---

## 7. Siguiente Fase

Una vez completada la Fase 0:
- **Verificar:** Script `verify_infra.py` pasa al 100%
- **Siguiente:** `fase_1_data_pipeline.md`
- **Dependencia:** Esta fase es prerequisito para Fase 1 y Fase 2

---

*Fase 0 - Infraestructura Base*  
*Bot de Trading Autónomo con IA*
