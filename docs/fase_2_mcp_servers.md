# 🔌 Fase 2: MCP Servers

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 3 semanas  
**Dependencias:** Fase 0 completada  
**Docs técnicos:** Doc 3 (secciones 2, 7)

---

## 1. Objetivos de la Fase

| Objetivo | Criterio de éxito |
|----------|-------------------|
| mcp-market-data operativo | Tools `get_quote`, `get_ohlcv` responden correctamente |
| mcp-technical operativo | Tools `calculate_indicators`, `get_regime` funcionan |
| mcp-risk operativo | Tools `check_limits`, `calculate_size` validan correctamente |
| mcp-ibkr operativo | Conexión a paper trading, `get_positions` funciona |
| Tests de integración | 100% de tools pasan tests automatizados |

---

## 2. Arquitectura MCP

### 2.1 Estructura Común de Servers

Todos los MCP servers siguen la misma estructura base:

```
mcp-servers/
├── common/
│   ├── __init__.py
│   ├── base_server.py      # Clase base MCP
│   ├── config.py           # Carga de configuración
│   └── exceptions.py       # Excepciones comunes
├── market-data/
│   ├── __init__.py
│   ├── server.py           # Entry point
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── quotes.py
│   │   └── ohlcv.py
│   └── tests/
├── technical/
├── risk/
└── ibkr/
```

### 2.2 Protocolo MCP

Referencia: Doc 3, sección 2.1

Los servers exponen tools que responden a requests JSON-RPC:

```
Request:  {"method": "tools/call", "params": {"name": "tool_name", "arguments": {...}}}
Response: {"content": [{"type": "text", "text": "..."}]}
```

### 2.3 Puertos Asignados

| Server | Puerto | Función |
|--------|--------|---------|
| mcp-market-data | 3001 | Datos de mercado |
| mcp-technical | 3002 | Análisis técnico |
| mcp-risk | 3003 | Gestión de riesgo |
| mcp-ibkr | 3004 | Trading IBKR |

---

## 3. Tareas

### Tarea 2.1: Crear estructura base y clase común

**Estado:** ⬜ Pendiente

**Objetivo:** Establecer estructura de directorios y clase base reutilizable.

**Referencias:** Doc 3 sec 7

**Subtareas:**
- [ ] Crear directorios según estructura 2.1
- [ ] Implementar `BaseMCPServer` con registro de tools
- [ ] Implementar carga de configuración desde YAML
- [ ] Crear excepciones comunes

**Input:** Estructura de proyecto existente (Fase 0)

**Output:** Módulo `mcp-servers/common/` funcional

**Validación:** Import sin errores, clase instanciable

**Pseudocódigo:**
```python
# mcp-servers/common/base_server.py
from mcp.server import Server
from mcp.types import Tool

class BaseMCPServer:
    def __init__(self, name: str, config_path: str):
        self.server = Server(name)
        self.config = load_config(config_path)
        self.tools: dict[str, callable] = {}
    
    def register_tool(self, name: str, description: str, schema: dict, handler: callable):
        # 1. Crear Tool con schema JSON
        # 2. Registrar handler
        # 3. Añadir a self.tools
        pass
    
    async def handle_call(self, name: str, arguments: dict) -> str:
        # 1. Buscar handler
        # 2. Ejecutar con arguments
        # 3. Retornar resultado JSON
        pass
    
    def run(self, port: int):
        # Iniciar servidor en puerto
        pass
```

---

### Tarea 2.2: Implementar mcp-market-data

**Estado:** ⬜ Pendiente

**Objetivo:** Server que provee datos de mercado desde TimescaleDB y cache Redis.

**Referencias:** Doc 3 sec 7.2, Doc 2 sec 3.1

**Subtareas:**
- [ ] Implementar tool `get_quote` (precio actual desde Redis)
- [ ] Implementar tool `get_ohlcv` (histórico desde TimescaleDB)
- [ ] Implementar tool `get_symbols` (lista de símbolos disponibles)
- [ ] Conectar a Redis y PostgreSQL
- [ ] Tests unitarios

**Input:** Fase 1 completada (datos en BD)

**Output:** Server `mcp-market-data` desplegable

**Validación:** `get_ohlcv("SAN.MC", "1d", "2024-01-01", "2024-01-31")` retorna datos

**Tools a implementar:**

| Tool | Parámetros | Retorno |
|------|------------|---------|
| `get_quote` | symbol | `{bid, ask, last, volume, timestamp}` |
| `get_ohlcv` | symbol, timeframe, start, end | `[{time, o, h, l, c, v}]` |
| `get_symbols` | market (opcional) | `[{ticker, name, market}]` |

**Pseudocódigo:**
```python
# mcp-servers/market-data/tools/ohlcv.py
class OHLCVTool:
    def __init__(self, db_engine, redis_client):
        self.db = db_engine
        self.redis = redis_client
    
    async def get_ohlcv(self, symbol: str, timeframe: str, start: str, end: str) -> list[dict]:
        # 1. Validar parámetros
        # 2. Query a market_data.ohlcv
        # 3. Formatear respuesta
        # 4. Retornar lista de barras
        query = """
            SELECT time, open, high, low, close, volume
            FROM market_data.ohlcv
            WHERE symbol = %s AND timeframe = %s
              AND time BETWEEN %s AND %s
            ORDER BY time
        """
        pass
    
    async def get_quote(self, symbol: str) -> dict:
        # 1. Buscar en Redis cache
        # 2. Si no existe, retornar último OHLCV
        quote = self.redis.hgetall(f"quote:{symbol}")
        if not quote:
            # Fallback a último cierre
            pass
        return quote
```

---

### Tarea 2.3: Implementar mcp-technical

**Estado:** ⬜ Pendiente

**Objetivo:** Server que calcula indicadores técnicos y detecta régimen.

**Referencias:** Doc 3 sec 7.3, Doc 2 sec 6.2

**Subtareas:**
- [ ] Implementar tool `calculate_indicators` (usa IndicatorEngine de Fase 1)
- [ ] Implementar tool `get_regime` (consulta HMM o reglas simples inicialmente)
- [ ] Implementar tool `find_sr_levels` (soportes/resistencias)
- [ ] Conectar a Feature Store
- [ ] Tests unitarios

**Input:** Feature Store operativo (Fase 1), mcp-market-data

**Output:** Server `mcp-technical` desplegable

**Validación:** `calculate_indicators("AAPL", ["RSI", "MACD"], "1d")` retorna valores correctos

**Tools a implementar:**

| Tool | Parámetros | Retorno |
|------|------------|---------|
| `calculate_indicators` | symbol, indicators[], timeframe | `{indicator: value}` |
| `get_regime` | symbol (opcional) | `{regime, probability, since}` |
| `find_sr_levels` | symbol, lookback | `{support: [], resistance: []}` |

**Pseudocódigo:**
```python
# mcp-servers/technical/tools/indicators.py
class IndicatorsTool:
    def __init__(self, feature_store, market_data_client):
        self.features = feature_store
        self.market = market_data_client
    
    async def calculate_indicators(self, symbol: str, indicators: list[str], timeframe: str) -> dict:
        # 1. Obtener OHLCV reciente (vía mcp-market-data o directo)
        # 2. Calcular cada indicador solicitado
        # 3. Retornar dict con valores actuales
        result = {}
        for ind in indicators:
            result[ind] = self._calculate_single(symbol, ind, timeframe)
        return result

# mcp-servers/technical/tools/regime.py
class RegimeTool:
    REGIMES = ["trending_bull", "trending_bear", "range_bound", "high_volatility"]
    
    async def get_regime(self, symbol: str = None) -> dict:
        # Fase inicial: reglas simples basadas en ADX y SMA
        # Fase 5: usar modelo HMM
        # 1. Obtener ADX, precio vs SMA200, volatilidad
        # 2. Clasificar según reglas
        # 3. Retornar régimen con probabilidad
        pass
```

**Reglas simples para régimen (hasta Fase 5):**

| Condición | Régimen |
|-----------|---------|
| ADX > 25 AND precio > SMA200 | trending_bull |
| ADX > 25 AND precio < SMA200 | trending_bear |
| ADX < 20 | range_bound |
| Volatilidad > 2x media | high_volatility |

---

### Tarea 2.4: Implementar mcp-risk

**Estado:** ⬜ Pendiente

**Objetivo:** Server que valida operaciones contra límites de riesgo.

**Referencias:** Doc 3 sec 7.7, Doc 6 sec 2-3

**Subtareas:**
- [ ] Implementar tool `check_limits` (validación pre-trade)
- [ ] Implementar tool `calculate_size` (position sizing)
- [ ] Implementar tool `get_exposure` (exposiciones actuales)
- [ ] Cargar límites desde config.risk_limits
- [ ] Tests unitarios

**Input:** Esquema config.risk_limits (Fase 0), posiciones en trading.positions

**Output:** Server `mcp-risk` desplegable

**Validación:** `check_limits({symbol: "AAPL", size: 1000, ...})` retorna aprobación/rechazo correcto

**Tools a implementar:**

| Tool | Parámetros | Retorno |
|------|------------|---------|
| `check_limits` | proposed_trade | `{approved, adjustments, warnings}` |
| `calculate_size` | signal, capital | `{shares, value, risk_amount}` |
| `get_exposure` | - | `{by_sector, by_currency, total}` |

**Pseudocódigo:**
```python
# mcp-servers/risk/tools/limits.py
class LimitsTool:
    # Límites hardcoded (Doc 6 sec 2.1)
    HARD_LIMITS = {
        "max_position_pct": 0.20,
        "max_sector_pct": 0.40,
        "max_correlation": 0.70,
        "max_drawdown": 0.15,
        "min_cash_pct": 0.10,
    }
    
    def __init__(self, db_engine):
        self.db = db_engine
        self.soft_limits = self._load_soft_limits()
    
    async def check_limits(self, trade: dict) -> dict:
        # trade: {symbol, side, size, price, strategy_id}
        # 1. Obtener portfolio actual
        # 2. Simular trade
        # 3. Verificar cada límite
        # 4. Retornar resultado
        
        warnings = []
        adjustments = []
        
        # Check max position
        if self._exceeds_max_position(trade):
            return {"approved": False, "reason": "Exceeds max position 20%"}
        
        # Check correlation
        corr = self._calculate_correlation(trade["symbol"])
        if corr > 0.5:
            adjustments.append({"reason": "high_correlation", "factor": 0.7})
        
        return {
            "approved": True,
            "original_size": trade["size"],
            "adjusted_size": trade["size"] * self._get_adjustment_factor(adjustments),
            "adjustments": adjustments,
            "warnings": warnings
        }

# mcp-servers/risk/tools/sizing.py
class SizingTool:
    async def calculate_size(self, signal: dict, capital: float) -> dict:
        # signal: {symbol, direction, confidence, entry_price, stop_loss}
        # Implementar Kelly fraccional (Doc 6 sec 3.1)
        
        base_risk = 0.01  # 1% del capital
        confidence_factor = signal["confidence"]
        
        risk_amount = capital * base_risk * confidence_factor
        distance_to_stop = abs(signal["entry_price"] - signal["stop_loss"])
        
        shares = int(risk_amount / distance_to_stop)
        value = shares * signal["entry_price"]
        
        # Aplicar límite máximo
        max_value = capital * 0.20
        if value > max_value:
            shares = int(max_value / signal["entry_price"])
            value = shares * signal["entry_price"]
        
        return {
            "shares": shares,
            "value": value,
            "risk_amount": risk_amount
        }
```

---

### Tarea 2.5: Implementar mcp-ibkr

**Estado:** ⬜ Pendiente

**Objetivo:** Server que conecta con IBKR para consultas y ejecución (paper trading).

**Referencias:** Doc 3 sec 7.5-7.6

**Subtareas:**
- [ ] Implementar conexión a TWS/Gateway (usar ib_insync)
- [ ] Implementar tool `get_account` (balance, buying power)
- [ ] Implementar tool `get_positions` (posiciones actuales)
- [ ] Implementar tool `place_order` (enviar orden)
- [ ] Implementar tool `get_order_status` (estado de orden)
- [ ] Safety check: solo paper trading
- [ ] Tests de integración con TWS paper

**Input:** TWS/Gateway corriendo en paper trading

**Output:** Server `mcp-ibkr` desplegable

**Validación:** `get_positions()` retorna posiciones del paper account

**Tools a implementar:**

| Tool | Parámetros | Retorno |
|------|------------|---------|
| `get_account` | - | `{balance, buying_power, currency}` |
| `get_positions` | - | `[{symbol, qty, avg_price, pnl}]` |
| `place_order` | order_spec | `{order_id, status}` |
| `cancel_order` | order_id | `{success, message}` |
| `get_order_status` | order_id | `{status, filled_qty, avg_price}` |

**Pseudocódigo:**
```python
# mcp-servers/ibkr/server.py
from ib_insync import IB, Stock, MarketOrder, LimitOrder

class IBKRServer(BaseMCPServer):
    def __init__(self, config_path: str):
        super().__init__("mcp-ibkr", config_path)
        self.ib = IB()
        self.connected = False
    
    async def connect(self):
        # 1. Conectar a TWS/Gateway
        # 2. IMPORTANTE: Verificar que es paper trading
        await self.ib.connectAsync(
            host=self.config["ibkr"]["host"],
            port=self.config["ibkr"]["port"],
            clientId=self.config["ibkr"]["client_id"]
        )
        
        # Safety check
        if not self._is_paper_trading():
            await self.ib.disconnect()
            raise RuntimeError("SAFETY: Only paper trading allowed!")
        
        self.connected = True
    
    def _is_paper_trading(self) -> bool:
        # Paper accounts tienen prefijo "DU" o puerto 7497
        account = self.ib.managedAccounts()[0]
        return account.startswith("DU") or self.config["ibkr"]["port"] == 7497

# mcp-servers/ibkr/tools/orders.py
class OrdersTool:
    def __init__(self, ib: IB):
        self.ib = ib
    
    async def place_order(self, order_spec: dict) -> dict:
        # order_spec: {symbol, side, quantity, order_type, price}
        # 1. Crear contrato
        contract = Stock(order_spec["symbol"], "SMART", "USD")
        
        # 2. Crear orden según tipo
        if order_spec["order_type"] == "market":
            order = MarketOrder(order_spec["side"], order_spec["quantity"])
        else:
            order = LimitOrder(order_spec["side"], order_spec["quantity"], order_spec["price"])
        
        # 3. Enviar
        trade = self.ib.placeOrder(contract, order)
        
        return {
            "order_id": trade.order.orderId,
            "status": trade.orderStatus.status
        }
```

**Configuración `config/ibkr.yaml`:**
```yaml
ibkr:
  host: "127.0.0.1"
  port: 7497  # 7497 = paper, 7496 = live
  client_id: 1
  timeout: 30
```

---

### Tarea 2.6: Crear tests de integración

**Estado:** ⬜ Pendiente

**Objetivo:** Suite de tests que valida todos los tools de todos los servers.

**Referencias:** Doc 3 sec 7 (tools disponibles)

**Subtareas:**
- [ ] Crear fixtures de datos de prueba
- [ ] Tests para mcp-market-data (3 tools)
- [ ] Tests para mcp-technical (3 tools)
- [ ] Tests para mcp-risk (3 tools)
- [ ] Tests para mcp-ibkr (5 tools, requiere TWS)
- [ ] Script de ejecución de suite completa

**Input:** Servers implementados, datos de Fase 1

**Output:** Suite pytest pasando

**Validación:** `pytest mcp-servers/tests/ -v` → 100% pass

**Estructura de tests:**
```
mcp-servers/tests/
├── conftest.py           # Fixtures comunes
├── test_market_data.py
├── test_technical.py
├── test_risk.py
└── test_ibkr.py          # Marcado @pytest.mark.ibkr (requiere TWS)
```

**Pseudocódigo:**
```python
# mcp-servers/tests/conftest.py
import pytest

@pytest.fixture
def market_data_client():
    # Cliente para llamar a mcp-market-data
    return MCPClient("localhost", 3001)

@pytest.fixture
def sample_trade():
    return {
        "symbol": "SAN.MC",
        "side": "buy",
        "size": 100,
        "price": 4.50,
        "strategy_id": "test_strategy"
    }

# mcp-servers/tests/test_market_data.py
class TestMarketData:
    def test_get_quote_existing_symbol(self, market_data_client):
        result = market_data_client.call("get_quote", {"symbol": "SAN.MC"})
        assert "last" in result
        assert result["last"] > 0
    
    def test_get_ohlcv_valid_range(self, market_data_client):
        result = market_data_client.call("get_ohlcv", {
            "symbol": "SAN.MC",
            "timeframe": "1d",
            "start": "2024-01-01",
            "end": "2024-01-31"
        })
        assert len(result) > 0
        assert all(k in result[0] for k in ["time", "open", "high", "low", "close"])

# mcp-servers/tests/test_risk.py
class TestRisk:
    def test_check_limits_valid_trade(self, risk_client, sample_trade):
        result = risk_client.call("check_limits", sample_trade)
        assert "approved" in result
    
    def test_check_limits_exceeds_max_position(self, risk_client):
        huge_trade = {"symbol": "AAPL", "size": 100000, ...}
        result = risk_client.call("check_limits", huge_trade)
        assert result["approved"] == False
```

---

### Tarea 2.7: Crear script de verificación de fase

**Estado:** ⬜ Pendiente

**Objetivo:** Script que valida todos los servers están operativos.

**Subtareas:**
- [ ] Crear `scripts/verify_mcp_servers.py`
- [ ] Verificar cada server responde a health check
- [ ] Verificar cada tool responde correctamente
- [ ] Output claro de estado

**Input:** Servers corriendo

**Output:** Script ejecutable

**Validación:** Ejecutar después de levantar servers, todo ✅

**Pseudocódigo:**
```python
# scripts/verify_mcp_servers.py
SERVERS = [
    ("mcp-market-data", 3001, ["get_quote", "get_ohlcv", "get_symbols"]),
    ("mcp-technical", 3002, ["calculate_indicators", "get_regime", "find_sr_levels"]),
    ("mcp-risk", 3003, ["check_limits", "calculate_size", "get_exposure"]),
    ("mcp-ibkr", 3004, ["get_account", "get_positions"]),  # Solo read-only para verify
]

def check_server(name: str, port: int, tools: list[str]) -> tuple[bool, str]:
    try:
        client = MCPClient("localhost", port)
        
        # Health check
        if not client.ping():
            return False, "No responde"
        
        # Verificar cada tool
        for tool in tools:
            try:
                client.call(tool, get_test_params(tool))
            except Exception as e:
                return False, f"Tool {tool} falló: {e}"
        
        return True, f"{len(tools)} tools OK"
    except Exception as e:
        return False, str(e)

def main():
    print("VERIFICACIÓN MCP SERVERS - FASE 2")
    print("=" * 50)
    
    all_ok = True
    for name, port, tools in SERVERS:
        ok, msg = check_server(name, port, tools)
        status = "✅" if ok else "❌"
        print(f"{status} {name}:{port} - {msg}")
        if not ok:
            all_ok = False
    
    return 0 if all_ok else 1
```

---

### Tarea 2.8: Configurar Docker para MCP servers

**Estado:** ⬜ Pendiente

**Objetivo:** Añadir MCP servers al docker-compose para deployment.

**Referencias:** Doc 7 sec 2.2

**Subtareas:**
- [ ] Crear Dockerfile para servers Python
- [ ] Añadir servicios a docker-compose.yml
- [ ] Configurar networking entre servers y BD
- [ ] Variables de entorno para conexiones

**Input:** docker-compose.yml de Fase 0

**Output:** Servers desplegables con `docker-compose up`

**Validación:** `docker-compose up mcp-market-data` levanta y responde

**Dockerfile:**
```dockerfile
# mcp-servers/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ ./common/
COPY ${SERVER_NAME}/ ./${SERVER_NAME}/

ENV PYTHONPATH=/app

CMD ["python", "-m", "${SERVER_NAME}.server"]
```

**Añadir a docker-compose.yml:**
```yaml
  mcp-market-data:
    build:
      context: ./mcp-servers
      args:
        SERVER_NAME: market-data
    environment:
      DATABASE_URL: postgresql://trading:${DB_PASSWORD}@postgres:5432/trading
      REDIS_URL: redis://redis:6379/0
    ports:
      - "3001:3001"
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  mcp-technical:
    build:
      context: ./mcp-servers
      args:
        SERVER_NAME: technical
    ports:
      - "3002:3002"
    depends_on:
      - mcp-market-data
    restart: unless-stopped

  mcp-risk:
    build:
      context: ./mcp-servers
      args:
        SERVER_NAME: risk
    environment:
      DATABASE_URL: postgresql://trading:${DB_PASSWORD}@postgres:5432/trading
    ports:
      - "3003:3003"
    depends_on:
      - postgres
    restart: unless-stopped

  mcp-ibkr:
    build:
      context: ./mcp-servers
      args:
        SERVER_NAME: ibkr
    environment:
      IBKR_HOST: host.docker.internal  # Para conectar a TWS en Windows
      IBKR_PORT: 7497
    ports:
      - "3004:3004"
    restart: unless-stopped
```

---

## 4. Dependencias Python Adicionales

Añadir a `mcp-servers/requirements.txt`:

```
# MCP SDK
mcp>=0.1.0

# Base (heredar de requirements.txt principal)
psycopg2-binary>=2.9.9
redis>=5.0.0
pandas>=2.1.0
pydantic>=2.5.0
pyyaml>=6.0.1

# IBKR
ib_insync>=0.9.86

# Technical analysis (para mcp-technical)
pandas-ta>=0.3.14b

# HTTP client (para comunicación entre servers)
httpx>=0.25.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

---

## 5. Checklist de Finalización

```
Fase 2: MCP Servers
═══════════════════════════════

[ ] Tarea 2.1: Estructura base y clase común
[ ] Tarea 2.2: mcp-market-data
[ ] Tarea 2.3: mcp-technical
[ ] Tarea 2.4: mcp-risk
[ ] Tarea 2.5: mcp-ibkr
[ ] Tarea 2.6: Tests de integración
[ ] Tarea 2.7: Script de verificación
[ ] Tarea 2.8: Docker para MCP servers

Gate de avance:
[ ] verify_mcp_servers.py pasa 100%
[ ] pytest mcp-servers/tests/ pasa 100%
[ ] docker-compose up levanta todos los servers
[ ] mcp-ibkr conecta a paper trading
```

---

## 6. Troubleshooting

### Server no responde en puerto

```powershell
# Verificar que el puerto no está ocupado
netstat -ano | findstr :3001

# Verificar logs del contenedor
docker-compose logs mcp-market-data
```

### Error de conexión a PostgreSQL desde container

```yaml
# Verificar que el service name es correcto en DATABASE_URL
DATABASE_URL: postgresql://trading:${DB_PASSWORD}@postgres:5432/trading
#                                                 ^^^^^^^^ nombre del service
```

### mcp-ibkr no conecta a TWS

1. Verificar TWS/Gateway está corriendo
2. Verificar API habilitada: File → Global Configuration → API → Enable ActiveX and Socket Clients
3. En Docker, usar `host.docker.internal` como host (Windows/Mac)
4. Verificar puerto 7497 (paper) no 7496 (live)

### Tests de ibkr fallan

```python
# Marcar tests que requieren TWS
@pytest.mark.ibkr
def test_get_positions():
    ...

# Ejecutar sin tests IBKR
pytest mcp-servers/tests/ -v -m "not ibkr"
```

---

## 7. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Tools por server | Doc 3 | 7.2-7.7 |
| Protocolo MCP | Doc 3 | 2.1-2.2 |
| Límites de riesgo | Doc 6 | 2.1 |
| Position sizing | Doc 6 | 3.1 |
| Régimen detection | Doc 1 | 4.6 |
| Feature Store | Doc 2 | 6 |
| Docker setup | Doc 2 | 9.1 |

---

## 8. Siguiente Fase

Una vez completada la Fase 2:
- **Verificar:** `verify_mcp_servers.py` pasa 100%
- **Verificar:** Tests de integración pasan
- **Siguiente:** `fase_3_agentes_core.md`
- **Dependencia:** Fase 3 requiere Fase 1 y Fase 2 completadas

---

*Fase 2 - MCP Servers*  
*Bot de Trading Autónomo con IA*
