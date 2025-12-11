# DOC-01: Integración del UniverseManager

> **Prioridad**: 🔴 CRÍTICA  
> **Esfuerzo estimado**: 4-6 horas  
> **Dependencias**: Ninguna (primer paso)

## 1. Contexto y Problema

### Estado Actual
El `UniverseManager` está implementado en `src/universe/manager.py` pero **NO está siendo utilizado**. Las estrategias operan con símbolos estáticos definidos en `config/strategies.yaml`.

### Código Problemático Actual
```python
# scripts/run_strategy_lab.py (líneas 49-52)
self.runner = StrategyRunner(
    mcp_client=self.mcp_client,
    config_path="config/strategies.yaml"
    # ← FALTA: universe_manager=...
)
```

### Consecuencias
- Las estrategias siempre operan los mismos 5 símbolos (SPY, QQQ, IWM, GLD, TLT)
- No hay filtrado por liquidez/tendencia/volatilidad
- No hay adaptación al régimen de mercado
- El AI Agent no puede sugerir símbolos alternativos

---

## 2. Objetivo

Integrar el `UniverseManager` para que:
1. Se ejecute un **screening diario automático** antes de la primera operación
2. Los símbolos activos se **inyecten a todas las estrategias**
3. El AI Agent pueda **sugerir símbolos** fuera del universo filtrado
4. Todo quede **persistido** para análisis posterior

---

## 3. Arquitectura de la Solución

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUJO DE INICIALIZACIÓN                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. StrategyLab.__init__()                                     │
│     │                                                           │
│     ├─► SymbolRegistry (carga symbols.yaml)                    │
│     │                                                           │
│     ├─► MCPDataProviderAdapter (wrapper para MCP)              │
│     │                                                           │
│     ├─► UniverseManager(registry, data_provider)               │
│     │                                                           │
│     └─► StrategyRunner(..., universe_manager=universe_mgr)     │
│                                                                 │
│  2. StrategyLab.start()                                        │
│     │                                                           │
│     ├─► Obtener régimen actual                                 │
│     │                                                           │
│     ├─► universe_manager.run_daily_screening(regime)           │
│     │   • Filtrar por liquidez                                 │
│     │   • Filtrar por tendencia (según régimen)                │
│     │   • Filtrar por volatilidad                              │
│     │   • Procesar sugerencias AI pendientes                   │
│     │                                                           │
│     └─► scheduler.start() (ya con universo activo)             │
│                                                                 │
│  3. Durante el día (cada ejecución de estrategia)              │
│     │                                                           │
│     └─► StrategyRunner._inject_dependencies()                  │
│         • strategy.set_universe(universe_manager.active_symbols)│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Cambios Requeridos

### 4.1. Crear Adapter para MCP como DataProvider

El `UniverseManager` requiere un `DataProvider` que implemente el protocolo definido. Necesitamos un adapter que use el `MCPClient`.

**Archivo**: `src/universe/mcp_data_adapter.py` (NUEVO)

```python
"""
Adapter que implementa el protocolo DataProvider usando MCPClient.

Permite al UniverseManager obtener datos de mercado a través de los
servidores MCP existentes (mcp-market-data, mcp-technical).
"""

import logging
from typing import Protocol, List, Dict, Any

logger = logging.getLogger(__name__)


class MCPDataProviderAdapter:
    """
    Adapter que conecta UniverseManager con los servidores MCP.
    
    Implementa el protocolo DataProvider requerido por UniverseManager:
    - get_quote(symbol) -> dict
    - get_indicators(symbol, indicators) -> dict
    - get_historical(symbol, days) -> list[dict]
    """
    
    def __init__(self, mcp_client, servers_config):
        """
        Args:
            mcp_client: Instancia de MCPClient
            servers_config: MCPServers con URLs de los servidores
        """
        self.mcp = mcp_client
        self.servers = servers_config
        
    async def get_quote(self, symbol: str) -> dict:
        """
        Obtener cotización actual con volumen.
        
        Returns:
            {
                "symbol": "SPY",
                "price": 450.0,
                "bid": 449.95,
                "ask": 450.05,
                "volume": 50000000,
                "avg_volume_20d": 45000000,
                "change_pct": 0.5
            }
        """
        try:
            result = await self.mcp.call(
                self.servers.market_data,
                "get_quote",
                {"symbol": symbol}
            )
            
            # Normalizar respuesta al formato esperado por UniverseManager
            return {
                "symbol": symbol,
                "price": result.get("price", result.get("last", 0)),
                "bid": result.get("bid", 0),
                "ask": result.get("ask", 0),
                "volume": result.get("volume", 0),
                "avg_volume_20d": result.get("avg_volume", result.get("avgVolume", 0)),
                "change_pct": result.get("change_pct", result.get("changePercent", 0)),
            }
            
        except Exception as e:
            logger.warning(f"Error getting quote for {symbol}: {e}")
            # Retornar valores que harán que el símbolo sea filtrado
            return {
                "symbol": symbol,
                "price": 0,
                "bid": 0,
                "ask": 0,
                "volume": 0,
                "avg_volume_20d": 0,
                "change_pct": 0,
            }
    
    async def get_indicators(self, symbol: str, indicators: List[str]) -> dict:
        """
        Obtener indicadores técnicos.
        
        Args:
            symbol: Ticker del símbolo
            indicators: Lista de indicadores ["rsi_14", "sma_200", "atr_14"]
            
        Returns:
            {
                "rsi_14": 55.0,
                "sma_200": 420.0,
                "atr_14": 5.5,
                ...
            }
        """
        try:
            result = await self.mcp.call(
                self.servers.technical,
                "calculate_indicators",
                {
                    "symbol": symbol,
                    "indicators": indicators,
                    "period": 200  # Suficiente para SMA200
                }
            )
            
            # Extraer valores de la respuesta estructurada
            extracted = {}
            for ind in indicators:
                # El servidor técnico puede devolver estructuras anidadas
                # Intentamos extraer el valor de varias formas
                if ind in result:
                    val = result[ind]
                    if isinstance(val, dict):
                        extracted[ind] = val.get("value", val.get("current", 0))
                    else:
                        extracted[ind] = val
                else:
                    # Buscar por nombre alternativo (RSI vs rsi_14)
                    base_name = ind.split("_")[0].upper()
                    if base_name in result:
                        val = result[base_name]
                        extracted[ind] = val.get("value", 0) if isinstance(val, dict) else val
                    else:
                        extracted[ind] = 0
                        
            return extracted
            
        except Exception as e:
            logger.warning(f"Error getting indicators for {symbol}: {e}")
            return {ind: 0 for ind in indicators}
    
    async def get_historical(self, symbol: str, days: int) -> List[Dict[str, Any]]:
        """
        Obtener datos históricos OHLCV.
        
        Args:
            symbol: Ticker del símbolo
            days: Número de días de historia
            
        Returns:
            [
                {"date": "2024-01-01", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000000},
                ...
            ]
        """
        try:
            result = await self.mcp.call(
                self.servers.market_data,
                "get_ohlcv",
                {
                    "symbol": symbol,
                    "timeframe": "1d",
                    "limit": days
                }
            )
            
            # Convertir formato de arrays a lista de dicts
            if isinstance(result, dict) and "close" in result:
                # Formato: {"open": [...], "high": [...], ...}
                length = len(result.get("close", []))
                historical = []
                for i in range(length):
                    historical.append({
                        "date": result.get("dates", [None] * length)[i],
                        "open": result.get("open", [0] * length)[i],
                        "high": result.get("high", [0] * length)[i],
                        "low": result.get("low", [0] * length)[i],
                        "close": result.get("close", [0] * length)[i],
                        "volume": result.get("volume", [0] * length)[i],
                    })
                return historical
            
            # Si ya viene como lista de dicts
            if isinstance(result, list):
                return result
                
            return []
            
        except Exception as e:
            logger.warning(f"Error getting historical for {symbol}: {e}")
            return []
```

---

### 4.2. Modificar StrategyLab para Integrar UniverseManager

**Archivo**: `scripts/run_strategy_lab.py`

```python
"""
Nexus Trading - Strategy Lab Entry Point

Script principal que inicializa y ejecuta el laboratorio de estrategias.
Integra el UniverseManager para selección dinámica de activos.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from datetime import date

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.strategies.runner import StrategyRunner
from src.scheduling.scheduler import StrategyScheduler
from src.metrics.exporters.csv_reporter import CSVReporter
from src.trading.paper.portfolio import PaperPortfolioManager
from src.trading.paper.order_simulator import OrderSimulator
from src.agents.mcp_client import MCPClient, MCPServers

# NUEVOS IMPORTS para UniverseManager
from src.data.symbols import SymbolRegistry
from src.universe.manager import UniverseManager
from src.universe.mcp_data_adapter import MCPDataProviderAdapter
from src.strategies.interfaces import MarketRegime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("strategy_lab.log")
    ]
)
logger = logging.getLogger("strategy_lab")


class StrategyLab:
    """
    Orquestador principal del Strategy Lab.
    
    Responsabilidades:
    1. Inicializar todos los componentes (MCP, Portfolio, Universe, Runner)
    2. Ejecutar screening diario de universo
    3. Gestionar ciclo de vida del scheduler
    4. Manejar shutdown graceful
    """
    
    def __init__(self):
        self.running = False
        
        # =====================================================================
        # 1. INFRAESTRUCTURA BASE
        # =====================================================================
        self.mcp_client = MCPClient()
        self.mcp_servers = MCPServers.from_env()
        
        # =====================================================================
        # 2. PAPER TRADING
        # =====================================================================
        self.portfolio_manager = PaperPortfolioManager()
        self.order_simulator = OrderSimulator(
            portfolio_manager=self.portfolio_manager,
            market_data_client=self.mcp_client
        )
        
        # =====================================================================
        # 3. UNIVERSE MANAGER (NUEVO)
        # =====================================================================
        # 3.1 Cargar registro maestro de símbolos
        self.symbol_registry = SymbolRegistry(
            config_path=str(project_root / "config" / "symbols.yaml")
        )
        logger.info(f"Cargados {self.symbol_registry.count()} símbolos del universo maestro")
        
        # 3.2 Crear adapter de datos para UniverseManager
        self.data_provider = MCPDataProviderAdapter(
            mcp_client=self.mcp_client,
            servers_config=self.mcp_servers
        )
        
        # 3.3 Inicializar UniverseManager
        self.universe_manager = UniverseManager(
            symbol_registry=self.symbol_registry,
            data_provider=self.data_provider,
            db_pool=None,  # Sin persistencia BD por ahora, usa JSON
            config={
                # Filtros de liquidez
                "min_avg_volume_shares": 100_000,
                "min_avg_volume_usd": 500_000,
                "max_spread_pct": 0.5,
                
                # Filtros de precio
                "min_price": 5.0,
                "max_price": 10_000,
                
                # Filtros de volatilidad
                "min_atr_pct": 0.5,
                "max_atr_pct": 10.0,
                
                # Límites de universo activo
                "max_active_symbols": 50,
                "min_active_symbols": 10,
                
                # AI Suggestions
                "max_ai_suggestions_per_day": 10,
                "min_suggestion_confidence": 0.6,
            }
        )
        
        # =====================================================================
        # 4. REPORTER
        # =====================================================================
        self.reporter = CSVReporter()
        
        # =====================================================================
        # 5. STRATEGY RUNNER (con UniverseManager inyectado)
        # =====================================================================
        self.runner = StrategyRunner(
            mcp_client=self.mcp_client,
            config_path="config/strategies.yaml",
            universe_manager=self.universe_manager  # ← INTEGRACIÓN CLAVE
        )
        
        # Inyectar componentes adicionales al runner
        self.runner.order_simulator = self.order_simulator
        self.runner.portfolio_manager = self.portfolio_manager
        
        # =====================================================================
        # 6. SCHEDULER
        # =====================================================================
        self.scheduler = StrategyScheduler(
            runner=self.runner,
            config=self.runner.config.config
        )
        
        # Estado interno
        self._last_screening_date: date = None

    async def _run_initial_screening(self):
        """
        Ejecutar screening del universo antes de comenzar operaciones.
        
        Este método:
        1. Obtiene el régimen actual del mercado
        2. Ejecuta el screening diario del UniverseManager
        3. Loguea el resultado
        """
        logger.info("=" * 60)
        logger.info("EJECUTANDO SCREENING DIARIO DEL UNIVERSO")
        logger.info("=" * 60)
        
        try:
            # 1. Obtener régimen actual
            regime_data = await self._get_current_regime()
            regime = MarketRegime(regime_data.get("regime", "SIDEWAYS"))
            confidence = regime_data.get("confidence", 0.5)
            
            logger.info(f"Régimen detectado: {regime.value} (confianza: {confidence:.2f})")
            
            # 2. Ejecutar screening
            universe = await self.universe_manager.run_daily_screening(
                regime=regime,
                force=False  # No forzar si ya se hizo hoy
            )
            
            # 3. Loguear resultado
            logger.info(f"Screening completado:")
            logger.info(f"  - Universo maestro: {universe.master_universe_size} símbolos")
            logger.info(f"  - Pasaron liquidez: {universe.passed_liquidity}")
            logger.info(f"  - Pasaron tendencia: {universe.passed_trend}")
            logger.info(f"  - Universo activo: {len(universe.active_symbols)} símbolos")
            logger.info(f"  - Símbolos: {universe.active_symbols[:10]}...")  # Primeros 10
            
            self._last_screening_date = universe.date
            
            return universe
            
        except Exception as e:
            logger.error(f"Error en screening inicial: {e}", exc_info=True)
            # En caso de error, intentar con fallback
            logger.warning("Usando símbolos de fallback (SPY, QQQ, IWM)")
            return None
    
    async def _get_current_regime(self) -> dict:
        """Obtener régimen actual desde MCP ML Models."""
        try:
            result = await self.mcp_client.call(
                self.mcp_servers.ml_models,
                "get_regime",
                {"symbol": "SPY", "use_cache": True}
            )
            return result
        except Exception as e:
            logger.warning(f"Error obteniendo régimen: {e}. Usando SIDEWAYS por defecto.")
            return {
                "regime": "SIDEWAYS",
                "confidence": 0.5,
                "probabilities": {}
            }

    async def start(self):
        """Iniciar el Strategy Lab."""
        logger.info("=" * 60)
        logger.info("INICIANDO NEXUS TRADING STRATEGY LAB")
        logger.info("=" * 60)
        
        self.running = True
        
        # =====================================================================
        # SCREENING INICIAL (antes de arrancar el scheduler)
        # =====================================================================
        await self._run_initial_screening()
        
        # =====================================================================
        # INICIAR SCHEDULER
        # =====================================================================
        self.scheduler.start()
        
        logger.info("Strategy Lab activo. Esperando ejecuciones programadas...")
        logger.info("Presiona Ctrl+C para detener.")
        
        # Main keep-alive loop
        try:
            while self.running:
                # Verificar si necesitamos re-screening (nuevo día)
                await self._check_daily_screening()
                await asyncio.sleep(60)  # Check cada minuto
        except asyncio.CancelledError:
            logger.info("Loop principal cancelado.")
    
    async def _check_daily_screening(self):
        """Verificar si necesitamos ejecutar screening de nuevo día."""
        today = date.today()
        if self._last_screening_date and self._last_screening_date < today:
            logger.info("Nuevo día detectado. Ejecutando screening...")
            await self._run_initial_screening()
            
    async def stop(self):
        """Shutdown graceful."""
        logger.info("=" * 60)
        logger.info("DETENIENDO STRATEGY LAB")
        logger.info("=" * 60)
        
        self.running = False
        self.scheduler.stop()
        
        # Generar reporte final
        logger.info("Generando reporte diario final...")
        try:
            await self.reporter.generate_daily_report(
                portfolios=self.portfolio_manager.portfolios
            )
        except Exception as e:
            logger.error(f"Error generando reporte: {e}")
        
        # Guardar estado del portfolio
        self.portfolio_manager.save_state()
        logger.info("Estado del portfolio guardado.")
        
        # Guardar resumen del universo
        if self.universe_manager.current_universe:
            summary = self.universe_manager.get_screening_summary()
            logger.info(f"Resumen universo del día: {summary}")
        
        logger.info("Shutdown completado.")


async def main():
    lab = StrategyLab()
    
    # Crear tarea del lab
    lab_task = asyncio.create_task(lab.start())
    
    # Configurar manejo de señales
    if sys.platform != 'win32':
        loop = asyncio.get_running_loop()
        stop_signal = asyncio.Event()
        
        def signal_handler():
            logger.info("Señal de terminación recibida...")
            stop_signal.set()
            
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
            
        await stop_signal.wait()
    else:
        # Windows
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
    
    # Detener lab
    await lab.stop()
    lab_task.cancel()
    
    try:
        await lab_task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass
    else:
        asyncio.run(main())
```

---

### 4.3. Verificar que SymbolRegistry carga correctamente

**Archivo**: `src/data/symbols.py`

Verificar que existe y funciona. Si no, aquí está la implementación necesaria:

```python
# Pseudo-código - verificar implementación existente

class SymbolRegistry:
    """
    Registro del universo maestro de símbolos.
    Carga desde config/symbols.yaml
    """
    
    def __init__(self, config_path: str):
        # Cargar YAML
        # Parsear lista de símbolos
        # Crear índices por ticker, mercado, asset_type
        pass
    
    def count(self) -> int:
        """Número total de símbolos."""
        pass
    
    def get_all(self) -> List[Symbol]:
        """Todos los símbolos."""
        pass
    
    def get_by_ticker(self, ticker: str) -> Optional[Symbol]:
        """Buscar por ticker."""
        pass
    
    def get_by_market(self, market: str) -> List[Symbol]:
        """Filtrar por mercado (US, EU, etc)."""
        pass
    
    def get_by_asset_type(self, asset_type: str) -> List[Symbol]:
        """Filtrar por tipo (etf, stock, etc)."""
        pass
```

---

### 4.4. Ajustar StrategyRunner para usar universo inyectado

El código actual en `src/strategies/runner.py` ya tiene soporte parcial. Verificar estas secciones:

```python
# En run_single_strategy (líneas ~123-127):
# Verificar que esta lógica funciona correctamente

if self.universe_manager and hasattr(strategy, 'set_universe'):
    symbols = self.universe_manager.active_symbols
    strategy.set_universe(symbols)
```

**Mejora sugerida** - añadir logging:

```python
if self.universe_manager and hasattr(strategy, 'set_universe'):
    symbols = self.universe_manager.active_symbols
    if symbols:
        strategy.set_universe(symbols)
        logger.info(f"Inyectados {len(symbols)} símbolos del universo a {strategy.strategy_id}")
    else:
        logger.warning(f"Universo vacío para {strategy.strategy_id}, usando símbolos default")
```

---

## 5. Configuración Necesaria

### 5.1. Verificar variables de entorno

Asegurar que `.env` tiene las URLs de los servidores MCP:

```bash
# .env
MCP_MARKET_DATA_URL=http://localhost:8001
MCP_TECHNICAL_URL=http://localhost:8002
MCP_ML_MODELS_URL=http://localhost:8003
MCP_RISK_URL=http://localhost:8004
MCP_IBKR_URL=http://localhost:8005
```

### 5.2. Configuración del UniverseManager

Opcionalmente, crear `config/universe.yaml` para configuración externa:

```yaml
# config/universe.yaml (OPCIONAL - los valores también están en código)

screening:
  # Filtros de liquidez
  min_avg_volume_shares: 100000
  min_avg_volume_usd: 500000
  max_spread_pct: 0.5
  
  # Filtros de precio
  min_price: 5.0
  max_price: 10000
  
  # Filtros de volatilidad  
  min_atr_pct: 0.5
  max_atr_pct: 10.0
  
  # Tendencia por régimen
  trend_sma_period: 200

limits:
  max_active_symbols: 50
  min_active_symbols: 10

ai_suggestions:
  max_per_day: 10
  min_confidence: 0.6
```

---

## 6. Testing

### 6.1. Test unitario para MCPDataProviderAdapter

```python
# tests/universe/test_mcp_adapter.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.universe.mcp_data_adapter import MCPDataProviderAdapter


@pytest.fixture
def mock_mcp_client():
    client = MagicMock()
    client.call = AsyncMock()
    return client


@pytest.fixture
def mock_servers():
    servers = MagicMock()
    servers.market_data = "http://localhost:8001"
    servers.technical = "http://localhost:8002"
    return servers


@pytest.mark.asyncio
async def test_get_quote_success(mock_mcp_client, mock_servers):
    """Test que get_quote normaliza la respuesta correctamente."""
    mock_mcp_client.call.return_value = {
        "price": 450.0,
        "bid": 449.95,
        "ask": 450.05,
        "volume": 50000000,
        "avgVolume": 45000000,
        "changePercent": 0.5
    }
    
    adapter = MCPDataProviderAdapter(mock_mcp_client, mock_servers)
    result = await adapter.get_quote("SPY")
    
    assert result["symbol"] == "SPY"
    assert result["price"] == 450.0
    assert result["avg_volume_20d"] == 45000000


@pytest.mark.asyncio
async def test_get_quote_error_returns_zeros(mock_mcp_client, mock_servers):
    """Test que errores retornan valores que filtran el símbolo."""
    mock_mcp_client.call.side_effect = Exception("Connection error")
    
    adapter = MCPDataProviderAdapter(mock_mcp_client, mock_servers)
    result = await adapter.get_quote("SPY")
    
    assert result["price"] == 0
    assert result["avg_volume_20d"] == 0
```

### 6.2. Test de integración del screening

```python
# tests/universe/test_screening_integration.py

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.universe.manager import UniverseManager, DailyUniverse
from src.strategies.interfaces import MarketRegime


@pytest.fixture
def mock_registry():
    """Registry con símbolos de prueba."""
    registry = MagicMock()
    
    # Simular 10 símbolos
    mock_symbols = [
        MagicMock(ticker=f"SYM{i}", market="US", asset_type="etf")
        for i in range(10)
    ]
    registry.get_all.return_value = mock_symbols
    registry.count.return_value = 10
    
    return registry


@pytest.fixture
def mock_data_provider():
    """Data provider que pasa todos los filtros."""
    provider = MagicMock()
    
    async def mock_quote(symbol):
        return {
            "price": 100.0,
            "avg_volume_20d": 1000000,  # Pasa filtro
            "bid": 99.95,
            "ask": 100.05,
        }
    
    async def mock_indicators(symbol, indicators):
        return {
            "sma_200": 95.0,  # Precio > SMA200 (alcista)
            "atr_14": 2.0,    # ATR 2% (dentro de rango)
        }
    
    provider.get_quote = AsyncMock(side_effect=mock_quote)
    provider.get_indicators = AsyncMock(side_effect=mock_indicators)
    
    return provider


@pytest.mark.asyncio
async def test_daily_screening_bull_regime(mock_registry, mock_data_provider):
    """Test screening en régimen BULL."""
    manager = UniverseManager(
        symbol_registry=mock_registry,
        data_provider=mock_data_provider,
        config={"max_active_symbols": 50, "min_active_symbols": 5}
    )
    
    universe = await manager.run_daily_screening(MarketRegime.BULL)
    
    assert isinstance(universe, DailyUniverse)
    assert universe.date == date.today()
    assert universe.regime_at_screening == MarketRegime.BULL
    assert len(universe.active_symbols) > 0
```

---

## 7. Checklist de Implementación

- [ ] Crear `src/universe/mcp_data_adapter.py`
- [ ] Modificar `scripts/run_strategy_lab.py` según especificación
- [ ] Verificar que `src/data/symbols.py` tiene `SymbolRegistry` funcional
- [ ] Verificar que `src/universe/manager.py` no tiene bugs
- [ ] Añadir logging mejorado en `StrategyRunner._inject_dependencies()`
- [ ] Crear tests unitarios para el adapter
- [ ] Crear test de integración del screening
- [ ] Probar manualmente el flujo completo
- [ ] Verificar que las estrategias reciben símbolos dinámicos

---

## 8. Notas Importantes

### Fallback de Seguridad
Si el screening falla por cualquier motivo (MCP caído, error de datos), las estrategias deben seguir funcionando con sus símbolos default configurados en `strategies.yaml`.

### Persistencia
El `UniverseManager` puede persistir en PostgreSQL si se le pasa `db_pool`, pero para el MVP inicial funcionará sin BD, solo en memoria. El estado se pierde al reiniciar pero se reconstruye con el screening inicial.

### Performance
El screening de ~150 símbolos puede tomar 2-5 minutos si se hacen llamadas secuenciales. Considerar paralelizar las llamadas MCP con `asyncio.gather()` para reducir a <1 minuto.

```python
# Ejemplo de paralelización en _filter_by_liquidity:
async def _filter_by_liquidity_parallel(self, symbols: list[str]) -> list[str]:
    tasks = [self.data_provider.get_quote(s) for s in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    passed = []
    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            continue
        if result.get("avg_volume_20d", 0) >= self.config["min_avg_volume_shares"]:
            passed.append(symbol)
    
    return passed
```
