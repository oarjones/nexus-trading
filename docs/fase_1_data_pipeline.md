# 📊 Fase 1: Data Pipeline

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 3 semanas  
**Dependencias:** Fase 0 completada  
**Docs técnicos:** Doc 2 (secciones 5, 6, 7, 8)

---

## 1. Objetivos de la Fase

| Objetivo | Criterio de éxito |
|----------|-------------------|
| Conector Yahoo Finance | Descarga OHLCV de 50+ símbolos sin errores |
| Conector IBKR | Conexión a paper trading, quotes en tiempo real |
| Pipeline de ingesta | Datos en TimescaleDB, validaciones pasando |
| Feature Store | 30+ features calculados, queries < 100ms |
| Scheduler | Actualización automática diaria funcionando |
| Calidad de datos | < 1% NaN en features, alertas configuradas |

---

## 2. Arquitectura del Pipeline

```
┌─────────────────┐     ┌─────────────────┐
│  Yahoo Finance  │     │    IBKR API     │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
            ┌─────────────────┐
            │   Data Ingester │
            │  (validaciones) │
            └────────┬────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │  Redis   │ │TimescaleDB│ │  Logs   │
   │ (cache)  │ │ (OHLCV)  │ │         │
   └──────────┘ └────┬─────┘ └──────────┘
                     │
                     ▼
            ┌─────────────────┐
            │ Feature Engine  │
            └────────┬────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ Parquet  │ │ Postgres │ │  Redis   │
   │ (datos)  │ │(metadata)│ │ (cache)  │
   └──────────┘ └──────────┘ └──────────┘
```

---

## 3. Universo de Símbolos Inicial

| Mercado | Símbolos | Fuente | Prioridad |
|---------|----------|--------|-----------|
| Acciones EU | SAN, BBVA, ITX, IBE, REP, SAP, ASML, BMW | Yahoo | Alta |
| ETFs EU | EXW1, VWCE, CSPX | Yahoo | Alta |
| Forex | EURUSD=X, GBPUSD=X, USDJPY=X | Yahoo | Media |
| Crypto | BTC-EUR, ETH-EUR | Yahoo/Kraken | Media |
| US (referencia) | SPY, QQQ, AAPL, MSFT | Yahoo | Baja |

**Total inicial:** ~25 símbolos (escalable a 100+)

---

## 4. Tareas

### Tarea 1.1: Crear módulo de configuración de símbolos

**Estado:** ⬜ Pendiente

**Objetivo:** Centralizar definición de símbolos, timeframes y fuentes.

**Referencias:** Doc 2 sec 6.2 (catálogo de features)

**Subtareas:**
- [ ] Crear `src/data/symbols.py` con clase SymbolRegistry
- [ ] Definir estructura de datos para símbolo (ticker, nombre, mercado, fuente, timezone)
- [ ] Cargar desde YAML configurable
- [ ] Métodos de filtrado por mercado/tipo

**Input:** Lista de símbolos objetivo (sección 3)

**Output:** Módulo `symbols.py` + `config/symbols.yaml`

**Validación:** `SymbolRegistry.get_by_market("EU")` retorna lista correcta

**Pseudocódigo:**
```python
# src/data/symbols.py
@dataclass
class Symbol:
    ticker: str          # "SAN.MC"
    name: str            # "Banco Santander"
    market: str          # "EU", "US", "FOREX", "CRYPTO"
    source: str          # "yahoo", "ibkr", "kraken"
    timezone: str        # "Europe/Madrid"
    currency: str        # "EUR"
    
class SymbolRegistry:
    def __init__(self, config_path: str):
        # Cargar desde YAML
        pass
    
    def get_all(self) -> list[Symbol]: ...
    def get_by_market(self, market: str) -> list[Symbol]: ...
    def get_by_source(self, source: str) -> list[Symbol]: ...
```

---

### Tarea 1.2: Implementar conector Yahoo Finance

**Estado:** ⬜ Pendiente

**Objetivo:** Descargar datos OHLCV históricos y recientes de Yahoo Finance.

**Referencias:** Doc 2 sec 7.1 (pipeline de ingesta)

**Subtareas:**
- [ ] Instalar `yfinance` y añadir a requirements
- [ ] Crear `src/data/providers/yahoo.py`
- [ ] Implementar descarga histórica (5 años)
- [ ] Implementar descarga incremental (último día)
- [ ] Manejo de errores y reintentos
- [ ] Rate limiting (evitar ban)

**Input:** Lista de símbolos, rango de fechas

**Output:** DataFrame con OHLCV estandarizado

**Validación:** Descarga 5 años de SPY sin errores, columnas correctas

**Pseudocódigo:**
```python
# src/data/providers/yahoo.py
class YahooProvider:
    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit  # segundos entre requests
    
    def get_historical(
        self, 
        symbol: str, 
        start: date, 
        end: date,
        interval: str = "1d"
    ) -> pd.DataFrame:
        # 1. Llamar yfinance.download()
        # 2. Renombrar columnas a estándar (open, high, low, close, volume)
        # 3. Añadir columnas: symbol, timeframe, source
        # 4. Validar datos (no vacío, no todo NaN)
        # 5. Retornar DataFrame limpio
        pass
    
    def get_latest(self, symbol: str, days: int = 5) -> pd.DataFrame:
        # Descarga incremental para actualización diaria
        pass
```

**Estructura de DataFrame de salida:**
```
| time (index) | symbol | timeframe | open | high | low | close | volume | source |
```

---

### Tarea 1.3: Implementar conector IBKR (básico)

**Estado:** ⬜ Pendiente

**Objetivo:** Conexión básica a IBKR para quotes y datos históricos.

**Referencias:** Doc 3 sec 7.5 (mcp-ibkr tools)

**Subtareas:**
- [ ] Instalar `ib_insync` y añadir a requirements
- [ ] Crear `src/data/providers/ibkr.py`
- [ ] Implementar conexión a TWS/Gateway
- [ ] Implementar `get_quote()` para precio actual
- [ ] Implementar `get_historical()` básico
- [ ] Manejo de desconexiones

**Input:** Símbolo, credenciales IBKR (host, port, client_id)

**Output:** Quote o DataFrame OHLCV

**Validación:** Conecta a paper trading, obtiene quote de AAPL

**Pseudocódigo:**
```python
# src/data/providers/ibkr.py
class IBKRProvider:
    def __init__(self, host: str, port: int, client_id: int):
        self.ib = IB()
        self.connected = False
    
    async def connect(self) -> bool:
        # 1. Intentar conexión
        # 2. Verificar que es paper trading (safety check)
        # 3. Retornar estado
        pass
    
    async def get_quote(self, symbol: str) -> dict:
        # Retorna {bid, ask, last, volume, timestamp}
        pass
    
    async def get_historical(
        self, 
        symbol: str,
        duration: str,  # "1 Y", "6 M", etc.
        bar_size: str   # "1 day", "1 hour", etc.
    ) -> pd.DataFrame:
        pass
    
    def disconnect(self):
        pass
```

**Nota:** IBKR requiere TWS o IB Gateway corriendo. Para desarrollo inicial, Yahoo es suficiente.

---

### Tarea 1.4: Crear servicio de ingesta a TimescaleDB

**Estado:** ⬜ Pendiente

**Objetivo:** Persistir datos OHLCV en hypertable con upsert.

**Referencias:** Doc 2 sec 3.1 (hypertable ohlcv), sec 7.1 (pipeline)

**Subtareas:**
- [ ] Crear `src/data/ingestion.py`
- [ ] Implementar bulk insert eficiente
- [ ] Implementar upsert (ON CONFLICT)
- [ ] Añadir validaciones pre-insert (Doc 2 sec 8.1)
- [ ] Logging de registros insertados/actualizados

**Input:** DataFrame OHLCV estandarizado

**Output:** Registros en `market_data.ohlcv`

**Validación:** Insertar 1000 registros < 2 segundos, sin duplicados

**Pseudocódigo:**
```python
# src/data/ingestion.py
class OHLCVIngester:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
    
    def ingest(self, df: pd.DataFrame) -> dict:
        # 1. Validar DataFrame (columnas, tipos, no vacío)
        # 2. Aplicar validaciones de calidad (Doc 2 sec 8.1)
        #    - precio > 0
        #    - volumen >= 0
        #    - timestamp no futuro
        # 3. Filtrar registros inválidos (log warning)
        # 4. Bulk upsert con ON CONFLICT
        # 5. Retornar {inserted: N, updated: M, rejected: K}
        pass
    
    def _validate_row(self, row: pd.Series) -> tuple[bool, str]:
        # Retorna (is_valid, reason_if_invalid)
        pass
```

**SQL de upsert:**
```sql
INSERT INTO market_data.ohlcv (time, symbol, timeframe, open, high, low, close, volume, source)
VALUES (...)
ON CONFLICT (time, symbol, timeframe) 
DO UPDATE SET open=EXCLUDED.open, high=EXCLUDED.high, ...
```

---

### Tarea 1.5: Implementar cálculo de indicadores técnicos

**Estado:** ⬜ Pendiente

**Objetivo:** Calcular indicadores técnicos sobre OHLCV y persistir.

**Referencias:** Doc 2 sec 3.2 (hypertable indicators), sec 6.2 (catálogo)

**Subtareas:**
- [ ] Instalar `ta-lib` o `pandas-ta` y añadir a requirements
- [ ] Crear `src/data/indicators.py`
- [ ] Implementar cálculo de indicadores base (tabla abajo)
- [ ] Persistir en `market_data.indicators`
- [ ] Optimizar para cálculo vectorizado

**Input:** OHLCV de TimescaleDB para un símbolo

**Output:** Indicadores en `market_data.indicators`

**Validación:** RSI(14) de SPY calculado correctamente (comparar con TradingView)

**Indicadores a implementar (Fase 1):**

| Indicador | Función | Parámetros |
|-----------|---------|------------|
| SMA | Media móvil simple | 20, 50, 200 |
| EMA | Media móvil exponencial | 12, 26 |
| RSI | Relative Strength Index | 14 |
| MACD | Moving Average Convergence | 12, 26, 9 |
| ATR | Average True Range | 14 |
| BB | Bandas de Bollinger | 20, 2 |
| ADX | Average Directional Index | 14 |

**Pseudocódigo:**
```python
# src/data/indicators.py
class IndicatorEngine:
    INDICATORS = {
        'sma_20': lambda df: df['close'].rolling(20).mean(),
        'sma_50': lambda df: df['close'].rolling(50).mean(),
        'rsi_14': lambda df: ta.rsi(df['close'], 14),
        'macd_hist': lambda df: ta.macd(df['close'])['histogram'],
        # ... resto de indicadores
    }
    
    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        # 1. Verificar datos suficientes (min 200 rows para SMA200)
        # 2. Calcular cada indicador
        # 3. Retornar DataFrame con columnas: time, symbol, timeframe, indicator, value
        pass
    
    def calculate_single(self, df: pd.DataFrame, indicator: str) -> pd.Series:
        pass
```

---

### Tarea 1.6: Implementar Feature Store

**Estado:** ⬜ Pendiente

**Objetivo:** Generar y almacenar features para ML y estrategias.

**Referencias:** Doc 2 sec 6 (Feature Store completo)

**Subtareas:**
- [ ] Crear estructura de directorios para Parquet
- [ ] Crear `src/data/feature_store.py`
- [ ] Implementar generación de features (catálogo Doc 2 sec 6.2)
- [ ] Implementar tabla de metadata en PostgreSQL
- [ ] Implementar lectura eficiente por símbolo/rango
- [ ] Cache en Redis para features del día actual

**Input:** OHLCV + Indicadores de TimescaleDB

**Output:** Archivos Parquet + metadata en PostgreSQL + cache Redis

**Validación:** Cargar features de AAPL últimos 30 días < 50ms

**Estructura de directorios:**
```
data/features/
├── symbol=SAN.MC/
│   ├── 2024-01/features.parquet
│   ├── 2024-02/features.parquet
│   └── ...
└── symbol=EURUSD=X/
    └── ...
```

**Features a generar (30+):**

| Categoría | Features |
|-----------|----------|
| Momentum | returns_1d, returns_5d, returns_20d, rsi_14, macd_hist |
| Volatilidad | volatility_20d, atr_14, bb_width, bb_position |
| Volumen | volume_ratio_20d, obv_slope |
| Tendencia | sma_ratio_50, sma_ratio_200, adx_14, trend_strength |
| Derivados | rsi_slope, macd_slope, momentum_5d |

**Pseudocódigo:**
```python
# src/data/feature_store.py
class FeatureStore:
    def __init__(self, base_path: str, db_url: str, redis_url: str):
        self.base_path = Path(base_path)
        self.engine = create_engine(db_url)
        self.redis = Redis.from_url(redis_url)
    
    def generate_features(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        # 1. Cargar OHLCV + indicadores de TimescaleDB
        # 2. Calcular features derivados
        # 3. Aplicar transformaciones (z-score rolling, winsorization)
        # 4. Retornar DataFrame de features
        pass
    
    def save(self, symbol: str, df: pd.DataFrame):
        # 1. Particionar por mes
        # 2. Guardar Parquet
        # 3. Actualizar metadata en PostgreSQL
        # 4. Cache día actual en Redis
        pass
    
    def load(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        # 1. Verificar cache Redis para hoy
        # 2. Cargar Parquet necesarios
        # 3. Filtrar por rango
        pass
    
    def _apply_transforms(self, df: pd.DataFrame) -> pd.DataFrame:
        # Z-score rolling (60 días), winsorization 1-99%
        pass
```

**Tabla metadata (Doc 2 sec 6.1):**
```sql
-- Ya definida en fase 0, verificar que existe
SELECT * FROM features.catalog LIMIT 1;
```

---

### Tarea 1.7: Crear scheduler de actualización

**Estado:** ⬜ Pendiente

**Objetivo:** Automatizar descarga diaria y generación de features.

**Referencias:** Doc 2 sec 7.3 (scheduling)

**Subtareas:**
- [ ] Instalar APScheduler y añadir a requirements
- [ ] Crear `src/data/scheduler.py`
- [ ] Job: Actualización OHLCV post-cierre mercado EU (18:30 CET)
- [ ] Job: Cálculo de indicadores (18:35 CET)
- [ ] Job: Generación de features (18:45 CET)
- [ ] Logging de ejecución y errores

**Input:** Configuración de jobs en YAML

**Output:** Scheduler corriendo, datos actualizados diariamente

**Validación:** Ejecutar manualmente, verificar datos en BD

**Pseudocódigo:**
```python
# src/data/scheduler.py
class DataScheduler:
    def __init__(self, config_path: str):
        self.scheduler = BackgroundScheduler()
        self.config = load_config(config_path)
    
    def setup_jobs(self):
        # Actualización OHLCV (después de cierre EU)
        self.scheduler.add_job(
            self.job_update_ohlcv,
            'cron', hour=18, minute=30, timezone='Europe/Madrid',
            id='ohlcv_daily'
        )
        
        # Cálculo de indicadores
        self.scheduler.add_job(
            self.job_calculate_indicators,
            'cron', hour=18, minute=35, timezone='Europe/Madrid',
            id='indicators_daily'
        )
        
        # Generación de features
        self.scheduler.add_job(
            self.job_generate_features,
            'cron', hour=18, minute=45, timezone='Europe/Madrid',
            id='features_daily'
        )
    
    def job_update_ohlcv(self):
        # 1. Obtener lista de símbolos activos
        # 2. Para cada símbolo: descargar últimos 5 días
        # 3. Ingestar a TimescaleDB
        # 4. Log resultado
        pass
    
    def job_calculate_indicators(self):
        # 1. Para cada símbolo con datos nuevos
        # 2. Recalcular indicadores (últimos 250 días para ventanas largas)
        # 3. Persistir
        pass
    
    def job_generate_features(self):
        # 1. Para cada símbolo
        # 2. Generar features del día
        # 3. Guardar en Feature Store
        pass
    
    def start(self):
        self.scheduler.start()
    
    def shutdown(self):
        self.scheduler.shutdown()
```

**Config `config/scheduler.yaml`:**
```yaml
jobs:
  ohlcv_update:
    enabled: true
    hour: 18
    minute: 30
    timezone: Europe/Madrid
    
  indicators:
    enabled: true
    hour: 18
    minute: 35
    
  features:
    enabled: true
    hour: 18
    minute: 45
```

---

### Tarea 1.8: Implementar validaciones y alertas de calidad

**Estado:** ⬜ Pendiente

**Objetivo:** Detectar problemas de datos y alertar.

**Referencias:** Doc 2 sec 8 (calidad de datos)

**Subtareas:**
- [ ] Crear `src/data/quality.py`
- [ ] Implementar validaciones de Doc 2 sec 8.1
- [ ] Implementar checks de completitud (gaps)
- [ ] Alertas a log (Telegram en fase posterior)
- [ ] Dashboard panel de calidad en Grafana

**Input:** Datos recién ingestados

**Output:** Alertas si problemas, métricas a InfluxDB

**Validación:** Insertar datos con NaN, verificar alerta generada

**Validaciones (Doc 2 sec 8.1):**

| Validación | Severidad | Acción |
|------------|-----------|--------|
| Precio ≤ 0 | Error | Descartar registro |
| Volumen < 0 | Error | Descartar registro |
| Timestamp futuro | Error | Descartar registro |
| Gap > 10% vs anterior | Warning | Aceptar, marcar para revisión |
| Sin datos > 5 días | Warning | Alertar |
| NaN > 5% en features | Warning | Alertar |

**Pseudocódigo:**
```python
# src/data/quality.py
class DataQualityChecker:
    def __init__(self, influx_client, alert_handler):
        self.influx = influx_client
        self.alerter = alert_handler
    
    def check_ohlcv(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
        # 1. Aplicar validaciones
        # 2. Separar válidos de inválidos
        # 3. Generar lista de issues
        # 4. Retornar (df_valid, issues)
        pass
    
    def check_features(self, df: pd.DataFrame) -> list[dict]:
        # 1. Contar NaN por columna
        # 2. Si > 5% en alguna columna -> warning
        # 3. Retornar issues
        pass
    
    def check_completeness(self, symbol: str, expected_days: int = 5) -> list[dict]:
        # 1. Query últimos N días de mercado
        # 2. Verificar que hay datos para cada día
        # 3. Retornar gaps encontrados
        pass
    
    def report_metrics(self, metrics: dict):
        # Escribir a InfluxDB para dashboard
        pass
```

---

### Tarea 1.9: Crear script de carga histórica inicial

**Estado:** ⬜ Pendiente

**Objetivo:** Script para poblar BD con datos históricos (5 años).

**Subtareas:**
- [ ] Crear `scripts/load_historical.py`
- [ ] Descargar 5 años de cada símbolo
- [ ] Calcular todos los indicadores
- [ ] Generar features históricos
- [ ] Progreso y logging

**Input:** Lista de símbolos, fecha inicio (2019-01-01)

**Output:** BD poblada con datos históricos

**Validación:** Query de 5 años de SPY retorna ~1250 registros

**Pseudocódigo:**
```python
# scripts/load_historical.py
def main():
    registry = SymbolRegistry('config/symbols.yaml')
    yahoo = YahooProvider()
    ingester = OHLCVIngester(db_url)
    indicator_engine = IndicatorEngine()
    feature_store = FeatureStore(...)
    
    symbols = registry.get_all()
    start_date = date(2019, 1, 1)
    end_date = date.today()
    
    for symbol in tqdm(symbols):
        logger.info(f"Procesando {symbol.ticker}...")
        
        # 1. Descargar histórico
        df = yahoo.get_historical(symbol.ticker, start_date, end_date)
        
        # 2. Ingestar OHLCV
        result = ingester.ingest(df)
        logger.info(f"  OHLCV: {result}")
        
        # 3. Calcular indicadores
        indicators = indicator_engine.calculate_all(df)
        # Persistir indicadores...
        
        # 4. Generar features
        features = feature_store.generate_features(symbol.ticker, start_date, end_date)
        feature_store.save(symbol.ticker, features)
        
        # Rate limiting
        time.sleep(1)
    
    logger.info("Carga histórica completada")

if __name__ == "__main__":
    main()
```

---

### Tarea 1.10: Crear script de verificación de pipeline

**Estado:** ⬜ Pendiente

**Objetivo:** Script que valida todo el pipeline de datos.

**Subtareas:**
- [ ] Crear `scripts/verify_data_pipeline.py`
- [ ] Verificar conexión a fuentes
- [ ] Verificar datos en TimescaleDB
- [ ] Verificar indicadores calculados
- [ ] Verificar Feature Store
- [ ] Verificar scheduler configurado

**Input:** Ninguno (usa configuración existente)

**Output:** Reporte de estado del pipeline

**Validación:** Ejecutar después de carga histórica, todo ✅

**Pseudocódigo:**
```python
# scripts/verify_data_pipeline.py
def check_yahoo_connection():
    # Intentar descargar 1 día de SPY
    pass

def check_timescale_data():
    # Contar registros en market_data.ohlcv
    # Verificar rango de fechas
    # Verificar símbolos presentes
    pass

def check_indicators():
    # Verificar que hay indicadores para símbolos con OHLCV
    # Verificar que no hay NaN excesivos
    pass

def check_feature_store():
    # Verificar que existen archivos Parquet
    # Verificar metadata en PostgreSQL
    # Test de lectura
    pass

def check_scheduler():
    # Verificar que config existe
    # Verificar que jobs están definidos
    pass

def main():
    checks = [
        ("Yahoo Finance", check_yahoo_connection),
        ("TimescaleDB OHLCV", check_timescale_data),
        ("Indicadores", check_indicators),
        ("Feature Store", check_feature_store),
        ("Scheduler Config", check_scheduler),
    ]
    
    for name, check_fn in checks:
        ok, msg = check_fn()
        status = "✅" if ok else "❌"
        print(f"{status} {name}: {msg}")
```

---

## 5. Dependencias Python Adicionales

Añadir a `requirements.txt`:

```
# Data providers
yfinance>=0.2.33
ib_insync>=0.9.86

# Technical analysis
pandas-ta>=0.3.14b
# o ta-lib (requiere instalación sistema)

# Scheduling
apscheduler>=3.10.4

# Progress bars
tqdm>=4.66.0

# Parquet
pyarrow>=14.0.0
```

---

## 6. Checklist de Finalización

```
Fase 1: Data Pipeline
══════════════════════════════

[ ] Tarea 1.1: Módulo de símbolos
[ ] Tarea 1.2: Conector Yahoo Finance
[ ] Tarea 1.3: Conector IBKR (básico)
[ ] Tarea 1.4: Ingesta a TimescaleDB
[ ] Tarea 1.5: Cálculo de indicadores
[ ] Tarea 1.6: Feature Store
[ ] Tarea 1.7: Scheduler de actualización
[ ] Tarea 1.8: Validaciones y alertas
[ ] Tarea 1.9: Carga histórica inicial
[ ] Tarea 1.10: Script de verificación

Gate de avance:
[ ] verify_data_pipeline.py pasa 100%
[ ] 5 años de datos para 20+ símbolos
[ ] Features sin NaN > 5%
[ ] Scheduler ejecuta sin errores
```

---

## 7. Troubleshooting

### Yahoo Finance rate limit

```python
# Si obtienes errores 429, aumentar delay entre requests
yahoo = YahooProvider(rate_limit=2.0)  # 2 segundos entre requests
```

### TimescaleDB hypertable no existe

```sql
-- Verificar que se creó en Fase 0
SELECT * FROM timescaledb_information.hypertables;

-- Si no existe, ejecutar init script manualmente
\i init-scripts/06_tables_market_data.sql
```

### Indicadores con NaN al inicio

Es normal: SMA(200) requiere 200 datos previos. El Feature Store debe manejar esto:
```python
# Eliminar primeras N filas donde hay NaN por ventana
df = df.dropna()
```

### IBKR no conecta

1. Verificar que TWS/Gateway está corriendo
2. Verificar que API está habilitada en TWS: File → Global Configuration → API
3. Verificar puerto (7497 paper, 7496 live)
4. Verificar que `client_id` no está en uso

---

## 8. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Esquema OHLCV | Doc 2 | 3.1 |
| Esquema indicadores | Doc 2 | 3.2 |
| Feature Store diseño | Doc 2 | 6 |
| Catálogo de features | Doc 2 | 6.2 |
| Pipeline de ingesta | Doc 2 | 7.1 |
| Validaciones calidad | Doc 2 | 8.1 |
| Scheduling | Doc 2 | 7.3 |
| Infraestructura Docker | Fase 0 | - |

---

## 9. Siguiente Fase

Una vez completada la Fase 1:
- **Verificar:** Script `verify_data_pipeline.py` pasa al 100%
- **Verificar:** Datos históricos cargados (5 años, 20+ símbolos)
- **Siguiente:** `fase_2_mcp_servers.md`
- **Paralelo posible:** Fase 2 puede comenzar antes si Fase 0 está completa

---

*Fase 1 - Data Pipeline*  
*Bot de Trading Autónomo con IA*
