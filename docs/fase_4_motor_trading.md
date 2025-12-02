# ⚙️ Fase 4: Motor de Trading

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 4 semanas  
**Dependencias:** Fase 3 completada  
**Docs técnicos:** Doc 4 (secciones 1-6), Doc 1 (sec 4.6, 4.8)

---

## 1. Objetivos de la Fase

| Objetivo | Criterio de éxito |
|----------|-------------------|
| Strategy Registry operativo | Estrategias registradas en PostgreSQL con estado en Redis |
| `swing_momentum_eu` implementada | Genera señales correctas en backtest |
| `mean_reversion_pairs` implementada | Detecta z-score y genera señales de pares |
| Framework backtesting funcional | Ejecuta backtest con costes realistas |
| Modelo de costes calibrado | Comisiones + spread + slippage aplicados |
| Execution Agent en paper | Órdenes ejecutadas en IBKR paper trading |
| Métricas de evaluación | Sharpe, MaxDD, Win Rate calculados |

---

## 2. Arquitectura del Motor

### 2.1 Componentes Principales

Referencia: Doc 4, sección 2

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Strategy     │     │    Backtest     │     │   Execution     │
│    Registry     │     │     Engine      │     │     Agent       │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────┬───────────┴───────────────────────┘
                     ▼
              ┌─────────────┐
              │  Cost Model │
              └─────────────┘
```

### 2.2 Estados de Estrategia

| Estado | Puede operar | Transiciones válidas |
|--------|--------------|---------------------|
| `active` | Sí | → paused, regime_disabled, drawdown_disabled |
| `paused` | No | → active |
| `regime_disabled` | No | → active (automático al cambiar régimen) |
| `drawdown_disabled` | No | → active (manual tras revisión) |
| `paper_only` | No (solo señales) | → active |

### 2.3 Activación por Régimen

Referencia: Doc 1, sección 4.6

| Régimen | Estrategias Activas |
|---------|---------------------|
| Trending Bull | `swing_momentum_eu` |
| Range-bound | `mean_reversion_pairs` |
| High Volatility | Ninguna nueva entrada |
| Crisis | Solo cierres |

### 2.4 Estructura de Directorios

```
src/trading/
├── __init__.py
├── registry.py          # Strategy Registry
├── strategies/
│   ├── __init__.py
│   ├── base.py          # Clase base Strategy
│   ├── swing_momentum.py
│   └── mean_reversion.py
├── backtest/
│   ├── __init__.py
│   ├── engine.py        # Motor de backtesting
│   ├── costs.py         # Modelo de costes
│   └── metrics.py       # Cálculo de métricas
├── execution/
│   ├── __init__.py
│   ├── agent.py         # Execution Agent
│   └── orders.py        # Gestión de órdenes
└── config.py

tests/trading/
├── __init__.py
├── test_registry.py
├── test_strategies.py
├── test_backtest.py
├── test_execution.py
└── test_integration.py
```

---

## 3. Tareas

### Tarea 4.1: Strategy Registry

**Estado:** ⬜ Pendiente

**Objetivo:** Sistema de registro y gestión de estrategias.

**Referencias:** Doc 4 sec 2.1-2.3

**Subtareas:**
- [ ] Crear tabla `config.strategies` en PostgreSQL
- [ ] Implementar `StrategyRegistry` con CRUD
- [ ] Gestión de estados en Redis
- [ ] Lógica de activación por régimen
- [ ] Asignación dinámica de pesos

**Input:** PostgreSQL + Redis operativos (Fase 0)

**Output:** Módulo `registry.py` funcional

**Validación:** Estrategia registrada, cambio de estado persiste, peso calculado

**Esquema PostgreSQL:**
```sql
-- Añadir a migrations/
CREATE TABLE IF NOT EXISTS config.strategies (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    markets TEXT[] NOT NULL,
    regime_filter TEXT[] NOT NULL,
    params JSONB NOT NULL,
    risk_params JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_strategies_enabled ON config.strategies(enabled);
CREATE INDEX idx_strategies_markets ON config.strategies USING GIN(markets);
```

**Pseudocódigo:**
```python
# src/trading/registry.py
from dataclasses import dataclass
from enum import Enum
import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

class StrategyState(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    REGIME_DISABLED = "regime_disabled"
    DRAWDOWN_DISABLED = "drawdown_disabled"
    PAPER_ONLY = "paper_only"

@dataclass
class StrategyConfig:
    id: str
    name: str
    markets: list[str]
    regime_filter: list[str]
    params: dict
    risk_params: dict

class StrategyRegistry:
    def __init__(self, db: Session, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client
        self._strategies: dict[str, StrategyConfig] = {}
    
    def load_strategies(self):
        """Cargar estrategias habilitadas de PostgreSQL"""
        # 1. Query config.strategies WHERE enabled = true
        # 2. Poblar self._strategies
        # 3. Inicializar estado en Redis si no existe
        pass
    
    def get_state(self, strategy_id: str) -> StrategyState:
        """Obtener estado actual de Redis"""
        state = self.redis.hget(f"strategy:{strategy_id}", "state")
        return StrategyState(state.decode()) if state else StrategyState.PAUSED
    
    def set_state(self, strategy_id: str, state: StrategyState, reason: str = ""):
        """Cambiar estado con logging"""
        # 1. Validar transición permitida
        # 2. Actualizar Redis hash
        # 3. Log en audit
        self.redis.hset(f"strategy:{strategy_id}", mapping={
            "state": state.value,
            "updated_at": datetime.utcnow().isoformat(),
            "reason": reason
        })
    
    def get_active_for_regime(self, regime: str) -> list[StrategyConfig]:
        """Estrategias activas para régimen actual"""
        active = []
        for sid, config in self._strategies.items():
            if self.get_state(sid) == StrategyState.ACTIVE:
                if regime in config.regime_filter:
                    active.append(config)
        return active
    
    def calculate_weights(self, active_strategies: list[str], 
                          performance: dict[str, dict]) -> dict[str, float]:
        """Asignar pesos basado en performance"""
        # Referencia: Doc 4 sec 2.3
        # peso_raw = sharpe_3m * (1 - dd_actual / dd_max)
        # Normalizar para que sumen 1.0
        # Aplicar límites: min 10%, max 50%
        weights = {}
        total_raw = 0.0
        
        for sid in active_strategies:
            perf = performance.get(sid, {})
            sharpe = perf.get("sharpe_3m", 0.5)
            dd_actual = perf.get("drawdown", 0.0)
            dd_max = self._strategies[sid].risk_params.get("max_drawdown", 0.15)
            
            raw = max(0, sharpe * (1 - dd_actual / dd_max))
            weights[sid] = raw
            total_raw += raw
        
        # Normalizar y aplicar límites
        for sid in weights:
            weights[sid] = max(0.10, min(0.50, weights[sid] / total_raw))
        
        # Re-normalizar tras límites
        total = sum(weights.values())
        return {sid: w / total for sid, w in weights.items()}
```

---

### Tarea 4.2: Clase Base Strategy

**Estado:** ⬜ Pendiente

**Objetivo:** Clase abstracta que define interfaz de estrategias.

**Referencias:** Doc 4 sec 1

**Subtareas:**
- [ ] Definir `BaseStrategy` con métodos abstractos
- [ ] Implementar gestión de parámetros
- [ ] Sistema de generación de señales
- [ ] Integración con Feature Store

**Input:** Feature Store operativo (Fase 1)

**Output:** Módulo `strategies/base.py`

**Validación:** Estrategia heredada compila y genera señal mock

**Pseudocódigo:**
```python
# src/trading/strategies/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Signal:
    strategy_id: str
    symbol: str
    direction: str  # "long", "short", "close"
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: Optional[float]
    timestamp: datetime
    metadata: dict

class BaseStrategy(ABC):
    def __init__(self, config: dict, feature_store):
        self.id = config["id"]
        self.name = config["name"]
        self.params = config["params"]
        self.risk_params = config["risk_params"]
        self.markets = config["markets"]
        self.feature_store = feature_store
    
    @abstractmethod
    def generate_signals(self, symbols: list[str], 
                         timestamp: datetime) -> list[Signal]:
        """Generar señales para símbolos dados"""
        pass
    
    @abstractmethod
    def validate_entry(self, symbol: str, direction: str) -> bool:
        """Validar condiciones adicionales de entrada"""
        pass
    
    def get_features(self, symbol: str, lookback: int = 100) -> dict:
        """Obtener features del Feature Store"""
        return self.feature_store.get_features(
            symbol=symbol,
            features=self._required_features(),
            lookback=lookback
        )
    
    @abstractmethod
    def _required_features(self) -> list[str]:
        """Lista de features requeridos por la estrategia"""
        pass
    
    def calculate_levels(self, entry: float, atr: float, 
                         direction: str) -> tuple[float, float]:
        """Calcular stop loss y take profit"""
        stop_mult = self.params.get("atr_stop_mult", 2.0)
        rr_ratio = self.params.get("risk_reward", 3.0)
        
        if direction == "long":
            stop = entry - (atr * stop_mult)
            target = entry + (atr * stop_mult * rr_ratio)
        else:
            stop = entry + (atr * stop_mult)
            target = entry - (atr * stop_mult * rr_ratio)
        
        return stop, target
```

---

### Tarea 4.3: Estrategia swing_momentum_eu

**Estado:** ⬜ Pendiente

**Objetivo:** Implementar estrategia de momentum para acciones europeas.

**Referencias:** Doc 4 sec 1.2

**Subtareas:**
- [ ] Implementar lógica de señal (RSI + MACD + SMA + volumen)
- [ ] Cálculo de confianza con ajustes
- [ ] Stop loss y take profit basados en ATR
- [ ] Tests unitarios con datos históricos

**Input:** Feature Store con RSI, MACD, SMA, volumen, ATR

**Output:** Módulo `strategies/swing_momentum.py`

**Validación:** Backtest en datos 2023 genera señales coherentes

**Parámetros:**

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| rsi_oversold | 35 | Entrada long si RSI < valor |
| rsi_overbought | 65 | Salida si RSI > valor |
| sma_filter | 50 | Precio > SMA(n) para longs |
| volume_mult | 1.5 | Volumen > n × media 20d |
| atr_stop_mult | 2.0 | Stop = entrada - n × ATR(14) |
| risk_reward | 3.0 | TP = entrada + n × riesgo |

**Pseudocódigo:**
```python
# src/trading/strategies/swing_momentum.py
from trading.strategies.base import BaseStrategy, Signal

class SwingMomentumEU(BaseStrategy):
    """
    Estrategia de momentum para mercados europeos.
    Timeframe: 1d | Holding: 3-10 días | Max posiciones: 5
    """
    
    def _required_features(self) -> list[str]:
        return [
            "rsi_14", "macd_line", "macd_signal", "macd_hist",
            "sma_50", "sma_200", "volume", "volume_sma_20",
            "atr_14", "close", "adx_14"
        ]
    
    def generate_signals(self, symbols: list[str], 
                         timestamp: datetime) -> list[Signal]:
        signals = []
        
        for symbol in symbols:
            features = self.get_features(symbol, lookback=5)
            if not self._has_valid_data(features):
                continue
            
            signal = self._evaluate_symbol(symbol, features, timestamp)
            if signal:
                signals.append(signal)
        
        return signals
    
    def _evaluate_symbol(self, symbol: str, features: dict, 
                         timestamp: datetime) -> Optional[Signal]:
        # Últimos valores
        rsi = features["rsi_14"][-1]
        macd_hist = features["macd_hist"][-1]
        macd_hist_prev = features["macd_hist"][-2]
        close = features["close"][-1]
        sma_50 = features["sma_50"][-1]
        volume = features["volume"][-1]
        vol_avg = features["volume_sma_20"][-1]
        atr = features["atr_14"][-1]
        adx = features["adx_14"][-1]
        
        direction = None
        confidence = 0.0
        
        # Condición LONG
        if (rsi < self.params["rsi_oversold"] and 
            close > sma_50 and 
            volume > self.params["volume_mult"] * vol_avg):
            
            if macd_hist > macd_hist_prev:  # MACD mejorando
                direction = "long"
                confidence = 0.60
        
        # Condición SHORT (si permitido)
        elif (rsi > self.params["rsi_overbought"] and 
              close < sma_50 and 
              volume > self.params["volume_mult"] * vol_avg):
            
            if macd_hist < macd_hist_prev:
                direction = "short"
                confidence = 0.55  # Menor confianza en shorts
        
        if direction is None:
            return None
        
        # Ajustes de confianza
        if volume > 2.0 * vol_avg:
            confidence += 0.05
        if adx > 25:
            confidence += 0.05
        
        confidence = min(confidence, 0.95)
        
        # Calcular niveles
        stop_loss, take_profit = self.calculate_levels(close, atr, direction)
        
        return Signal(
            strategy_id=self.id,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=close,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=timestamp,
            metadata={
                "rsi": rsi,
                "macd_hist": macd_hist,
                "volume_ratio": volume / vol_avg,
                "adx": adx
            }
        )
    
    def validate_entry(self, symbol: str, direction: str) -> bool:
        """Validaciones adicionales antes de ejecutar"""
        # 1. No entrar si ya hay posición abierta en símbolo
        # 2. Verificar horario de mercado
        # 3. Verificar que no hay earnings próximos (opcional)
        return True
```

---

### Tarea 4.4: Estrategia mean_reversion_pairs

**Estado:** ⬜ Pendiente

**Objetivo:** Implementar estrategia de reversión a la media en pares cointegrados.

**Referencias:** Doc 4 sec 1.3

**Subtareas:**
- [ ] Implementar cálculo de z-score del spread
- [ ] Verificación de cointegración (test ADF)
- [ ] Señales de entrada/salida basadas en z-score
- [ ] Cálculo dinámico de hedge ratio
- [ ] Tests con pares SAN/BBVA

**Input:** Feature Store con precios de pares

**Output:** Módulo `strategies/mean_reversion.py`

**Validación:** Z-score calculado correctamente, señales en umbrales

**Parámetros:**

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| zscore_entry | 2.0 | Entrada si \|z-score\| > valor |
| zscore_exit | 0.5 | Salida si \|z-score\| < valor |
| lookback | 60 | Ventana para spread |
| max_holding_days | 5 | Cierre forzado |
| coint_pvalue | 0.05 | Umbral cointegración |

**Pseudocódigo:**
```python
# src/trading/strategies/mean_reversion.py
from trading.strategies.base import BaseStrategy, Signal
from statsmodels.tsa.stattools import adfuller
import numpy as np

class MeanReversionPairs(BaseStrategy):
    """
    Pairs trading basado en cointegración.
    Timeframe: 1h | Holding: 1-5 días
    Pares: SAN.MC/BBVA.MC, SAP.DE/ASML.AS
    """
    
    def __init__(self, config: dict, feature_store):
        super().__init__(config, feature_store)
        self.pairs = config.get("pairs", [])  # [(sym1, sym2), ...]
        self._hedge_ratios = {}
        self._last_coint_check = {}
    
    def _required_features(self) -> list[str]:
        return ["close", "volume"]
    
    def generate_signals(self, symbols: list[str], 
                         timestamp: datetime) -> list[Signal]:
        signals = []
        
        for sym1, sym2 in self.pairs:
            # Verificar cointegración periódicamente
            if self._should_check_cointegration(sym1, sym2):
                if not self._check_cointegration(sym1, sym2):
                    continue  # Par no cointegrado, skip
            
            signal = self._evaluate_pair(sym1, sym2, timestamp)
            if signal:
                signals.extend(signal)  # Retorna 2 señales (long/short)
        
        return signals
    
    def _check_cointegration(self, sym1: str, sym2: str) -> bool:
        """Verificar cointegración con test ADF en spread"""
        lookback = self.params.get("coint_lookback", 252)  # 1 año
        
        prices1 = self.get_features(sym1, lookback)["close"]
        prices2 = self.get_features(sym2, lookback)["close"]
        
        # Calcular hedge ratio por OLS
        hedge_ratio = self._calculate_hedge_ratio(prices1, prices2)
        self._hedge_ratios[(sym1, sym2)] = hedge_ratio
        
        # Calcular spread
        spread = prices1 - hedge_ratio * prices2
        
        # Test ADF
        adf_result = adfuller(spread, maxlag=1)
        pvalue = adf_result[1]
        
        self._last_coint_check[(sym1, sym2)] = datetime.utcnow()
        
        return pvalue < self.params["coint_pvalue"]
    
    def _calculate_hedge_ratio(self, prices1: np.ndarray, 
                                prices2: np.ndarray) -> float:
        """OLS regression para hedge ratio"""
        # y = prices1, x = prices2
        # hedge_ratio = cov(y, x) / var(x)
        cov = np.cov(prices1, prices2)[0, 1]
        var = np.var(prices2)
        return cov / var
    
    def _evaluate_pair(self, sym1: str, sym2: str, 
                       timestamp: datetime) -> list[Signal]:
        lookback = self.params["lookback"]
        
        prices1 = self.get_features(sym1, lookback)["close"]
        prices2 = self.get_features(sym2, lookback)["close"]
        
        hedge_ratio = self._hedge_ratios.get((sym1, sym2), 1.0)
        
        # Calcular spread y z-score
        spread = prices1 - hedge_ratio * prices2
        zscore = (spread[-1] - np.mean(spread)) / np.std(spread)
        
        signals = []
        
        # Z-score alto: spread se contraerá
        # → Short sym1, Long sym2
        if zscore > self.params["zscore_entry"]:
            signals.append(self._create_signal(
                sym1, "short", abs(zscore), prices1[-1], timestamp
            ))
            signals.append(self._create_signal(
                sym2, "long", abs(zscore), prices2[-1], timestamp,
                size_multiplier=hedge_ratio
            ))
        
        # Z-score bajo: spread se expandirá
        # → Long sym1, Short sym2
        elif zscore < -self.params["zscore_entry"]:
            signals.append(self._create_signal(
                sym1, "long", abs(zscore), prices1[-1], timestamp
            ))
            signals.append(self._create_signal(
                sym2, "short", abs(zscore), prices2[-1], timestamp,
                size_multiplier=hedge_ratio
            ))
        
        return signals
    
    def _create_signal(self, symbol: str, direction: str, 
                       zscore: float, price: float,
                       timestamp: datetime,
                       size_multiplier: float = 1.0) -> Signal:
        # Confianza basada en z-score
        confidence = min(0.50 + (zscore - 2.0) * 0.10, 0.80)
        
        # Stop más amplio para pairs (basado en spread, no precio)
        atr = self.get_features(symbol, 20)["atr_14"][-1] if "atr_14" in self._required_features() else price * 0.02
        stop_loss, take_profit = self.calculate_levels(price, atr, direction)
        
        return Signal(
            strategy_id=self.id,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=None,  # Exit por z-score, no TP fijo
            timestamp=timestamp,
            metadata={
                "zscore": zscore,
                "pair_trade": True,
                "size_multiplier": size_multiplier
            }
        )
    
    def validate_entry(self, symbol: str, direction: str) -> bool:
        return True
    
    def _should_check_cointegration(self, sym1: str, sym2: str) -> bool:
        """Re-verificar cointegración cada semana"""
        last_check = self._last_coint_check.get((sym1, sym2))
        if last_check is None:
            return True
        return (datetime.utcnow() - last_check).days >= 7
```

---

### Tarea 4.5: Framework de Backtesting

**Estado:** ⬜ Pendiente

**Objetivo:** Motor de backtesting con costes realistas y validación temporal.

**Referencias:** Doc 4 sec 3

**Subtareas:**
- [ ] Implementar `BacktestEngine` con simulación de órdenes
- [ ] Modelo de costes (comisiones, spread, slippage)
- [ ] División temporal train/val/test con embargo
- [ ] Walk-forward optimization
- [ ] Cálculo de métricas (Sharpe, MaxDD, Win Rate, etc.)
- [ ] Generación de reportes

**Input:** Estrategia + datos históricos

**Output:** Módulos `backtest/engine.py`, `backtest/costs.py`, `backtest/metrics.py`

**Validación:** Backtest de SMA crossover reproduce resultados conocidos

**Pseudocódigo:**
```python
# src/trading/backtest/costs.py
from dataclasses import dataclass

@dataclass
class CostModel:
    """Modelo de costes para backtesting realista"""
    commission_pct: float = 0.0005  # 0.05% IBKR EU
    spread_pct: float = 0.0002      # 0.02% estimado
    slippage_base: float = 0.0001   # 0.01% base
    market_impact_threshold: float = 0.01  # 1% del volumen diario
    
    def calculate_entry_cost(self, price: float, quantity: int,
                             daily_volume: int, volatility: float) -> float:
        """Coste total de entrada"""
        notional = price * quantity
        
        # Comisión
        commission = notional * self.commission_pct
        
        # Spread
        spread = notional * self.spread_pct
        
        # Slippage (aumenta con volatilidad)
        slippage = notional * self.slippage_base * (1 + volatility * 0.5)
        
        # Market impact (si orden grande)
        order_pct = quantity / daily_volume if daily_volume > 0 else 0
        if order_pct > self.market_impact_threshold:
            impact = notional * 0.001 * (order_pct / self.market_impact_threshold)
        else:
            impact = 0
        
        return commission + spread + slippage + impact
    
    def calculate_exit_cost(self, price: float, quantity: int,
                            daily_volume: int, volatility: float) -> float:
        """Coste de salida (similar a entrada)"""
        return self.calculate_entry_cost(price, quantity, daily_volume, volatility)

# src/trading/backtest/engine.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import pandas as pd

@dataclass
class Trade:
    symbol: str
    direction: str
    entry_price: float
    entry_time: datetime
    quantity: int
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    costs: float = 0.0
    status: str = "open"

@dataclass
class BacktestResult:
    trades: list[Trade]
    equity_curve: pd.Series
    metrics: dict
    signals_generated: int
    signals_executed: int

class BacktestEngine:
    def __init__(self, strategy, data: pd.DataFrame, 
                 cost_model: CostModel, initial_capital: float = 10000):
        self.strategy = strategy
        self.data = data
        self.costs = cost_model
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: dict[str, Trade] = {}
        self.trades: list[Trade] = []
        self.equity_history: list[tuple[datetime, float]] = []
    
    def run(self, start_date: datetime, end_date: datetime) -> BacktestResult:
        """Ejecutar backtest en rango de fechas"""
        signals_generated = 0
        signals_executed = 0
        
        # Filtrar datos por rango
        mask = (self.data.index >= start_date) & (self.data.index <= end_date)
        test_data = self.data[mask]
        
        for timestamp, row in test_data.iterrows():
            # 1. Actualizar posiciones abiertas (stops, targets)
            self._update_positions(timestamp, row)
            
            # 2. Generar señales
            symbols = self._get_tradeable_symbols(row)
            signals = self.strategy.generate_signals(symbols, timestamp)
            signals_generated += len(signals)
            
            # 3. Procesar señales
            for signal in signals:
                if self._can_execute(signal):
                    self._execute_signal(signal, row)
                    signals_executed += 1
            
            # 4. Registrar equity
            equity = self._calculate_equity(row)
            self.equity_history.append((timestamp, equity))
        
        # Cerrar posiciones abiertas al final
        self._close_all_positions(test_data.iloc[-1])
        
        # Calcular métricas
        equity_curve = pd.Series(
            [e[1] for e in self.equity_history],
            index=[e[0] for e in self.equity_history]
        )
        metrics = calculate_metrics(equity_curve, self.trades)
        
        return BacktestResult(
            trades=self.trades,
            equity_curve=equity_curve,
            metrics=metrics,
            signals_generated=signals_generated,
            signals_executed=signals_executed
        )
    
    def _execute_signal(self, signal, row):
        """Ejecutar señal con costes"""
        # Calcular tamaño basado en risk
        quantity = self._calculate_position_size(signal)
        
        # Aplicar slippage a precio de entrada
        volatility = row.get(f"{signal.symbol}_volatility", 0.02)
        volume = row.get(f"{signal.symbol}_volume", 1000000)
        
        slipped_price = self._apply_slippage(
            signal.entry_price, signal.direction, volatility
        )
        
        # Calcular costes
        entry_cost = self.costs.calculate_entry_cost(
            slipped_price, quantity, volume, volatility
        )
        
        # Crear trade
        trade = Trade(
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=slipped_price,
            entry_time=signal.timestamp,
            quantity=quantity,
            costs=entry_cost
        )
        
        self.positions[signal.symbol] = trade
        self.capital -= entry_cost
    
    def _calculate_position_size(self, signal) -> int:
        """Position sizing basado en riesgo"""
        risk_per_trade = self.capital * 0.01  # 1% por trade
        risk_per_share = abs(signal.entry_price - signal.stop_loss)
        
        if risk_per_share <= 0:
            return 0
        
        shares = int(risk_per_trade / risk_per_share)
        
        # Límite máximo por posición (15% del capital)
        max_shares = int((self.capital * 0.15) / signal.entry_price)
        
        return min(shares, max_shares)
    
    def _apply_slippage(self, price: float, direction: str, 
                        volatility: float) -> float:
        """Aplicar slippage realista"""
        slippage_pct = 0.0001 * (1 + volatility * 0.5)
        
        if direction == "long":
            return price * (1 + slippage_pct)
        else:
            return price * (1 - slippage_pct)

# src/trading/backtest/metrics.py
import numpy as np
import pandas as pd

def calculate_metrics(equity_curve: pd.Series, 
                      trades: list) -> dict:
    """Calcular métricas de performance"""
    
    returns = equity_curve.pct_change().dropna()
    
    # Sharpe Ratio (asumiendo rf = 0)
    sharpe = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0
    
    # Max Drawdown
    rolling_max = equity_curve.expanding().max()
    drawdown = (equity_curve - rolling_max) / rolling_max
    max_dd = drawdown.min()
    
    # Sortino (solo downside)
    downside = returns[returns < 0]
    sortino = np.sqrt(252) * returns.mean() / downside.std() if len(downside) > 0 else 0
    
    # Trade metrics
    winning_trades = [t for t in trades if t.pnl > 0]
    losing_trades = [t for t in trades if t.pnl <= 0]
    
    win_rate = len(winning_trades) / len(trades) if trades else 0
    
    gross_profit = sum(t.pnl for t in winning_trades)
    gross_loss = abs(sum(t.pnl for t in losing_trades))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    avg_trade = sum(t.pnl for t in trades) / len(trades) if trades else 0
    
    # CAGR
    days = (equity_curve.index[-1] - equity_curve.index[0]).days
    years = days / 365.25
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
    cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    
    # Calmar
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0
    
    return {
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "max_drawdown": round(max_dd * 100, 2),  # Porcentaje
        "calmar": round(calmar, 2),
        "win_rate": round(win_rate * 100, 1),  # Porcentaje
        "profit_factor": round(profit_factor, 2),
        "avg_trade_pct": round(avg_trade * 100, 3),  # Porcentaje
        "total_trades": len(trades),
        "cagr": round(cagr * 100, 2),  # Porcentaje
        "total_return": round(total_return * 100, 2)
    }
```

---

### Tarea 4.6: Execution Agent

**Estado:** ⬜ Pendiente

**Objetivo:** Agente que ejecuta órdenes en IBKR paper trading.

**Referencias:** Doc 4 sec 4, Doc 3 sec 7.5

**Subtareas:**
- [ ] Implementar `ExecutionAgent` heredando de `BaseAgent`
- [ ] Conectar a mcp-ibkr para envío de órdenes
- [ ] Gestión de estados de orden (pending → sent → filled)
- [ ] Manejo de fills parciales
- [ ] Reconciliación con posiciones en BD

**Input:** Decisiones del Orchestrator (Fase 3), mcp-ibkr operativo (Fase 2)

**Output:** Módulo `execution/agent.py`

**Validación:** Orden enviada a IBKR paper, fill recibido y registrado

**Pseudocódigo:**
```python
# src/trading/execution/agent.py
from agents.base import BaseAgent
from agents.schemas import TradingDecision
from dataclasses import dataclass
from enum import Enum
import asyncio

class OrderStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    PARTIAL = "partial"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

@dataclass
class Order:
    id: str
    symbol: str
    direction: str
    quantity: int
    order_type: str  # "market", "limit"
    limit_price: float | None
    status: OrderStatus
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    created_at: datetime = None
    updated_at: datetime = None

class ExecutionAgent(BaseAgent):
    def __init__(self, config: dict, message_bus, mcp_client, db):
        super().__init__("execution", config, message_bus)
        self.mcp = mcp_client
        self.db = db
        self.pending_orders: dict[str, Order] = {}
        self.order_timeout = config.get("order_timeout_seconds", 300)
    
    async def setup(self):
        # Suscribirse a decisiones
        self.bus.subscribe("decisions", self._handle_decision)
        
        # Verificar conexión a IBKR
        status = await self.mcp.call("mcp-ibkr", "get_connection_status", {})
        if not status.get("connected"):
            raise RuntimeError("IBKR not connected")
    
    async def process(self):
        # 1. Monitorear órdenes pendientes
        await self._check_pending_orders()
        
        # 2. Manejar timeouts
        await self._handle_timeouts()
        
        await asyncio.sleep(1)  # Poll cada segundo
    
    async def _handle_decision(self, decision: dict):
        """Procesar decisión del Orchestrator"""
        if decision["action"] not in ["open_long", "open_short", "close"]:
            return
        
        # Crear orden
        order = Order(
            id=str(uuid.uuid4()),
            symbol=decision["symbol"],
            direction="buy" if "long" in decision["action"] else "sell",
            quantity=decision["size"],
            order_type="limit",  # Preferir limit orders
            limit_price=self._calculate_limit_price(decision),
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        # Enviar a broker
        await self._submit_order(order)
    
    async def _submit_order(self, order: Order):
        """Enviar orden a IBKR via MCP"""
        try:
            result = await self.mcp.call("mcp-ibkr", "place_order", {
                "symbol": order.symbol,
                "action": order.direction.upper(),
                "quantity": order.quantity,
                "order_type": order.order_type.upper(),
                "limit_price": order.limit_price
            })
            
            if result.get("order_id"):
                order.status = OrderStatus.SENT
                order.updated_at = datetime.utcnow()
                self.pending_orders[result["order_id"]] = order
                
                # Guardar en BD
                self._save_order_to_db(order)
            else:
                order.status = OrderStatus.REJECTED
                self._log_rejection(order, result.get("error"))
                
        except Exception as e:
            order.status = OrderStatus.REJECTED
            self._log_rejection(order, str(e))
    
    async def _check_pending_orders(self):
        """Consultar estado de órdenes pendientes"""
        for broker_id, order in list(self.pending_orders.items()):
            status = await self.mcp.call("mcp-ibkr", "get_order_status", {
                "order_id": broker_id
            })
            
            if status["status"] == "filled":
                order.status = OrderStatus.FILLED
                order.filled_qty = status["filled_qty"]
                order.avg_fill_price = status["avg_price"]
                order.updated_at = datetime.utcnow()
                
                # Actualizar posición
                await self._update_position(order)
                
                # Remover de pendientes
                del self.pending_orders[broker_id]
                
            elif status["status"] == "partial":
                order.status = OrderStatus.PARTIAL
                order.filled_qty = status["filled_qty"]
                order.updated_at = datetime.utcnow()
    
    async def _handle_timeouts(self):
        """Manejar órdenes que exceden timeout"""
        now = datetime.utcnow()
        
        for broker_id, order in list(self.pending_orders.items()):
            elapsed = (now - order.created_at).total_seconds()
            
            if elapsed > self.order_timeout:
                if order.status == OrderStatus.SENT:
                    # Cancelar y reintentar como market
                    await self._cancel_order(broker_id)
                    await self._convert_to_market(order)
                    
                elif order.status == OrderStatus.PARTIAL:
                    # Completar resto como market
                    remaining = order.quantity - order.filled_qty
                    if remaining > 0:
                        await self._submit_market_order(order.symbol, 
                                                        order.direction, 
                                                        remaining)
    
    def _calculate_limit_price(self, decision: dict) -> float:
        """Calcular precio límite con pequeño margen"""
        entry = decision["entry_price"]
        
        if "long" in decision["action"]:
            # Comprar ligeramente por encima
            return entry * 1.001
        else:
            # Vender ligeramente por debajo
            return entry * 0.999
    
    async def _update_position(self, order: Order):
        """Actualizar posición en BD tras fill"""
        # Insertar en trading.trades
        # Actualizar trading.positions
        # Log en audit
        pass
    
    def _save_order_to_db(self, order: Order):
        """Persistir orden en PostgreSQL"""
        # INSERT INTO trading.orders
        pass
```

---

### Tarea 4.7: Tests de Integración

**Estado:** ⬜ Pendiente

**Objetivo:** Validar flujo completo estrategia → señal → backtest → ejecución.

**Referencias:** Doc 4 sec 7

**Subtareas:**
- [ ] Test de Strategy Registry CRUD
- [ ] Test de generación de señales por estrategia
- [ ] Test de backtest con datos mock
- [ ] Test de Execution Agent con IBKR paper
- [ ] Test end-to-end: señal → decisión → orden

**Input:** Componentes de Fase 4 implementados

**Output:** Suite de tests en `tests/trading/`

**Validación:** `pytest tests/trading/ -v` pasa 100%

**Pseudocódigo:**
```python
# tests/trading/test_integration.py
import pytest
from datetime import datetime, timedelta

@pytest.fixture
def strategy_registry(db_session, redis_client):
    registry = StrategyRegistry(db_session, redis_client)
    registry.load_strategies()
    return registry

@pytest.fixture
def swing_strategy(feature_store_mock):
    config = {
        "id": "swing_momentum_eu",
        "name": "Test Swing",
        "markets": ["BME"],
        "regime_filter": ["trending_bull"],
        "params": {
            "rsi_oversold": 35,
            "rsi_overbought": 65,
            "sma_filter": 50,
            "volume_mult": 1.5,
            "atr_stop_mult": 2.0,
            "risk_reward": 3.0
        },
        "risk_params": {"max_positions": 5}
    }
    return SwingMomentumEU(config, feature_store_mock)

class TestStrategyRegistry:
    def test_load_strategies(self, strategy_registry):
        """Estrategias se cargan de BD"""
        assert len(strategy_registry._strategies) > 0
    
    def test_state_transitions(self, strategy_registry):
        """Estados cambian correctamente"""
        sid = "swing_momentum_eu"
        
        strategy_registry.set_state(sid, StrategyState.ACTIVE)
        assert strategy_registry.get_state(sid) == StrategyState.ACTIVE
        
        strategy_registry.set_state(sid, StrategyState.PAUSED)
        assert strategy_registry.get_state(sid) == StrategyState.PAUSED
    
    def test_regime_filtering(self, strategy_registry):
        """Solo retorna estrategias compatibles con régimen"""
        active = strategy_registry.get_active_for_regime("trending_bull")
        for s in active:
            assert "trending_bull" in s.regime_filter

class TestSwingMomentum:
    def test_long_signal_conditions(self, swing_strategy, feature_store_mock):
        """Genera LONG cuando RSI < 35 + MACD mejorando + precio > SMA50"""
        # Mock features con condiciones de long
        feature_store_mock.set_features("TEST.MC", {
            "rsi_14": [40, 38, 33],  # Oversold
            "macd_hist": [-0.5, -0.3, -0.1],  # Mejorando
            "close": [100, 101, 102],
            "sma_50": [95, 95, 95],  # Precio > SMA
            "volume": [1000000, 1500000, 2000000],
            "volume_sma_20": [1000000, 1000000, 1000000],
            "atr_14": [2.0, 2.0, 2.0],
            "adx_14": [30, 30, 30]
        })
        
        signals = swing_strategy.generate_signals(
            ["TEST.MC"], 
            datetime.utcnow()
        )
        
        assert len(signals) == 1
        assert signals[0].direction == "long"
        assert signals[0].confidence >= 0.60
    
    def test_no_signal_neutral(self, swing_strategy, feature_store_mock):
        """No genera señal cuando condiciones neutras"""
        feature_store_mock.set_features("TEST.MC", {
            "rsi_14": [50, 50, 50],  # Neutral
            "macd_hist": [0.1, 0.1, 0.1],
            "close": [100, 100, 100],
            "sma_50": [100, 100, 100],
            "volume": [1000000, 1000000, 1000000],
            "volume_sma_20": [1000000, 1000000, 1000000],
            "atr_14": [2.0, 2.0, 2.0],
            "adx_14": [20, 20, 20]
        })
        
        signals = swing_strategy.generate_signals(
            ["TEST.MC"], 
            datetime.utcnow()
        )
        
        assert len(signals) == 0

class TestBacktestEngine:
    def test_backtest_with_costs(self, backtest_data):
        """Backtest aplica costes correctamente"""
        strategy = MockStrategy()
        cost_model = CostModel(commission_pct=0.001)
        engine = BacktestEngine(strategy, backtest_data, cost_model)
        
        result = engine.run(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31)
        )
        
        # Verificar que hay trades
        assert result.total_trades > 0
        
        # Verificar que costes se aplicaron
        total_costs = sum(t.costs for t in result.trades)
        assert total_costs > 0
    
    def test_metrics_calculation(self, backtest_data):
        """Métricas se calculan correctamente"""
        # ... similar setup
        result = engine.run(...)
        
        assert "sharpe" in result.metrics
        assert "max_drawdown" in result.metrics
        assert result.metrics["max_drawdown"] <= 0  # DD es negativo

class TestExecutionAgent:
    @pytest.mark.asyncio
    async def test_order_submission(self, execution_agent, mock_mcp):
        """Orden se envía correctamente a IBKR"""
        mock_mcp.set_response("place_order", {"order_id": "12345"})
        
        decision = {
            "action": "open_long",
            "symbol": "SAN.MC",
            "size": 100,
            "entry_price": 3.50
        }
        
        await execution_agent._handle_decision(decision)
        
        assert len(execution_agent.pending_orders) == 1
        assert "12345" in execution_agent.pending_orders
    
    @pytest.mark.asyncio
    async def test_fill_processing(self, execution_agent, mock_mcp):
        """Fill actualiza posición correctamente"""
        # Setup orden pendiente
        execution_agent.pending_orders["12345"] = Order(
            id="test",
            symbol="SAN.MC",
            direction="buy",
            quantity=100,
            order_type="limit",
            limit_price=3.50,
            status=OrderStatus.SENT
        )
        
        mock_mcp.set_response("get_order_status", {
            "status": "filled",
            "filled_qty": 100,
            "avg_price": 3.51
        })
        
        await execution_agent._check_pending_orders()
        
        assert len(execution_agent.pending_orders) == 0
```

---

### Tarea 4.8: Script de verificación de fase

**Estado:** ⬜ Pendiente

**Objetivo:** Script que valida todos los componentes de la fase funcionan.

**Subtareas:**
- [ ] Crear `scripts/verify_trading.py`
- [ ] Verificar Strategy Registry
- [ ] Verificar generación de señales
- [ ] Ejecutar backtest de prueba
- [ ] Verificar conexión a IBKR paper

**Input:** Componentes de Fase 4 implementados

**Output:** Script ejecutable con resultado claro

**Validación:** Ejecutar script, todo ✅

**Pseudocódigo:**
```python
# scripts/verify_trading.py
import asyncio
from datetime import datetime, timedelta

CHECKS = [
    ("PostgreSQL strategies table", check_strategies_table),
    ("Redis strategy states", check_redis_states),
    ("Strategy Registry load", check_registry_load),
    ("Swing Momentum signals", check_swing_signals),
    ("Mean Reversion signals", check_pairs_signals),
    ("Backtest engine", check_backtest),
    ("Cost model", check_cost_model),
    ("IBKR paper connection", check_ibkr_connection),
    ("Execution Agent health", check_execution_health),
]

async def check_strategies_table():
    """Verificar tabla config.strategies existe y tiene datos"""
    db = get_db_connection()
    result = db.execute("SELECT COUNT(*) FROM config.strategies WHERE enabled = true")
    count = result.scalar()
    
    if count >= 2:
        return True, f"{count} strategies registered"
    return False, f"Only {count} strategies (need >= 2)"

async def check_swing_signals():
    """Verificar que swing_momentum genera señales con datos de prueba"""
    registry = StrategyRegistry(db, redis)
    strategy = registry.get_strategy("swing_momentum_eu")
    
    # Usar datos históricos conocidos
    signals = strategy.generate_signals(
        ["SAN.MC", "BBVA.MC"],
        datetime.utcnow()
    )
    
    # Puede generar 0 señales si mercado neutral, verificar que no hay error
    return True, f"Generated {len(signals)} signals (OK if 0)"

async def check_backtest():
    """Ejecutar backtest corto de prueba"""
    strategy = SwingMomentumEU(test_config, feature_store)
    data = load_test_data("2023-06-01", "2023-06-30")
    
    engine = BacktestEngine(strategy, data, CostModel())
    result = engine.run(
        start_date=datetime(2023, 6, 1),
        end_date=datetime(2023, 6, 30)
    )
    
    if "sharpe" in result.metrics:
        return True, f"Backtest OK: {result.total_trades} trades, Sharpe={result.metrics['sharpe']}"
    return False, "Backtest failed to produce metrics"

async def check_ibkr_connection():
    """Verificar conexión a IBKR paper trading"""
    mcp = get_mcp_client("mcp-ibkr")
    
    try:
        status = await mcp.call("get_connection_status", {})
        if status.get("connected") and status.get("account_type") == "paper":
            return True, f"Connected to {status.get('account_id')}"
        return False, f"Not connected or not paper: {status}"
    except Exception as e:
        return False, f"Connection error: {e}"

async def main():
    print("VERIFICACIÓN MOTOR TRADING - FASE 4")
    print("=" * 50)
    
    all_ok = True
    for name, check_fn in CHECKS:
        try:
            ok, msg = await check_fn()
            status = "✅" if ok else "❌"
            print(f"{status} {name}: {msg}")
            if not ok:
                all_ok = False
        except Exception as e:
            print(f"❌ {name}: Error - {e}")
            all_ok = False
    
    print("=" * 50)
    if all_ok:
        print("✅ FASE 4 VERIFICADA CORRECTAMENTE")
    else:
        print("❌ FASE 4 TIENE ERRORES")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    exit(asyncio.run(main()))
```

---

## 4. Configuración de Estrategias

**Archivo:** `config/strategies/swing_momentum_eu.yaml`

```yaml
id: swing_momentum_eu
name: "Momentum Swing EU"
enabled: true
markets:
  - BME    # Madrid
  - XETRA  # Frankfurt
regime_filter:
  - trending_bull
timeframe: "1d"
holding_days:
  min: 3
  max: 10
params:
  rsi_oversold: 35
  rsi_overbought: 65
  sma_filter: 50
  volume_mult: 1.5
  atr_stop_mult: 2.0
  risk_reward: 3.0
risk_params:
  max_positions: 5
  max_pct_per_position: 0.15
  max_correlation: 0.7
```

**Archivo:** `config/strategies/mean_reversion_pairs.yaml`

```yaml
id: mean_reversion_pairs
name: "Pairs Mean Reversion"
enabled: true
markets:
  - BME
  - XETRA
regime_filter:
  - range_bound
timeframe: "1h"
pairs:
  - ["SAN.MC", "BBVA.MC"]
  - ["SAP.DE", "ASML.AS"]
params:
  zscore_entry: 2.0
  zscore_exit: 0.5
  lookback: 60
  max_holding_days: 5
  coint_pvalue: 0.05
  coint_lookback: 252
risk_params:
  max_pairs: 2
  max_pct_per_pair: 0.20
```

---

## 5. Dependencias Python Adicionales

Añadir a `requirements.txt`:

```
# Estadísticas
statsmodels>=0.14.0
scipy>=1.11.0

# Backtesting
pandas>=2.0.0
numpy>=1.24.0

# Visualización reportes
matplotlib>=3.7.0
seaborn>=0.12.0

# YAML config
pyyaml>=6.0

# Testing adicional
pytest-cov>=4.1.0
hypothesis>=6.82.0  # Property-based testing
```

---

## 6. Checklist de Finalización

```
Fase 4: Motor de Trading
═══════════════════════════════════════

[ ] Tarea 4.1: Strategy Registry
[ ] Tarea 4.2: Clase Base Strategy
[ ] Tarea 4.3: swing_momentum_eu
[ ] Tarea 4.4: mean_reversion_pairs
[ ] Tarea 4.5: Framework Backtesting
[ ] Tarea 4.6: Execution Agent
[ ] Tarea 4.7: Tests de integración
[ ] Tarea 4.8: Script de verificación

Gate de avance:
[ ] verify_trading.py pasa 100%
[ ] pytest tests/trading/ pasa 100%
[ ] Backtest swing_momentum: Sharpe > 0 en 2023
[ ] Backtest mean_reversion: Sharpe > 0 en 2023
[ ] Orden ejecutada en IBKR paper
[ ] Posición actualizada en BD tras fill
```

---

## 7. Troubleshooting

### Estrategia no genera señales

```python
# Verificar que hay datos en Feature Store
redis-cli HGETALL "features:SAN.MC:1d"

# Verificar que indicadores tienen valores
SELECT * FROM market_data.features 
WHERE symbol = 'SAN.MC' 
ORDER BY timestamp DESC LIMIT 5;

# Verificar régimen actual
redis-cli GET "regime:current"
```

### Backtest da Sharpe negativo

1. Verificar modelo de costes no es excesivo
2. Verificar parámetros de estrategia
3. Revisar período de test (puede ser desfavorable)
4. Ejecutar walk-forward para validar robustez

```python
# Backtest sin costes para aislar problema
engine = BacktestEngine(strategy, data, CostModel(
    commission_pct=0, spread_pct=0, slippage_base=0
))
```

### Órdenes no se ejecutan en IBKR

```python
# Verificar conexión
curl http://localhost:5000/mcp-ibkr/health

# Verificar modo paper
redis-cli GET "ibkr:account_type"  # Debe ser "paper"

# Ver log de órdenes
SELECT * FROM trading.orders 
WHERE status != 'filled' 
ORDER BY created_at DESC;
```

### Error de cointegración en pairs

```python
# Verificar que pares tienen suficiente historia
SELECT COUNT(*) FROM market_data.ohlcv 
WHERE symbol IN ('SAN.MC', 'BBVA.MC') 
AND timeframe = '1h';

# Test manual de cointegración
from statsmodels.tsa.stattools import adfuller
spread = prices_san - hedge_ratio * prices_bbva
print(adfuller(spread))  # p-value < 0.05
```

### Position size siempre 0

1. Verificar capital disponible
2. Verificar stop loss no está en precio de entrada
3. Verificar ATR tiene valor > 0

```python
# Debug sizing
risk = capital * 0.01
risk_per_share = abs(entry - stop)
print(f"Risk budget: {risk}, Risk/share: {risk_per_share}")
print(f"Max shares: {risk / risk_per_share}")
```

---

## 8. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Catálogo de estrategias | Doc 4 | 1 |
| Strategy Registry | Doc 4 | 2 |
| Backtesting framework | Doc 4 | 3 |
| Order lifecycle | Doc 4 | 4 |
| Gestión de señales | Doc 4 | 5 |
| Paper → Live | Doc 4 | 6 |
| Régimen detection | Doc 1 | 4.6 |
| Cost model | Doc 1 | 4.8 |
| mcp-ibkr tools | Doc 3 | 7.5 |
| Risk validation | Doc 6 | 2-4 |
| Feature Store | Doc 2 | 6 |

---

## 9. Siguiente Fase

Una vez completada la Fase 4:
- **Verificar:** `verify_trading.py` pasa 100%
- **Verificar:** Backtest de ambas estrategias con Sharpe > 0
- **Verificar:** Al menos 1 orden ejecutada en IBKR paper
- **Siguiente:** `fase_5_ml_pipeline.md`
- **Contenido Fase 5:** HMM para régimen, pipeline de training, mcp-ml-models, monitoreo de calibración

---

*Fase 4 - Motor de Trading*  
*Bot de Trading Autónomo con IA*
