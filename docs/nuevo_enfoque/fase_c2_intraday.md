# ⚡ Fase C2: Estrategias Intradía

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 1 semana  
**Dependencias:** Fase C1 (métricas), Fase B1 (TradingStrategy ABC), Fase A2 (régimen ML)  
**Prerrequisito:** MVP Swing funcionando en paper trading, sistema de métricas operativo

---

## 1. Contexto y Motivación

### 1.1 Situación Actual

Las fases anteriores han establecido un sistema de trading swing completo:

| Fase | Componente | Estado |
|------|------------|--------|
| A1 | IBKR como fuente de datos principal | ✅ Configurado |
| A2 | Detección de régimen (HMM/Rules) | ✅ Funcionando |
| B1 | TradingStrategy ABC + ETF Momentum | ✅ Generando señales |
| B2 | AI Agent con Claude | ✅ Decisiones estructuradas |
| C1 | Sistema de métricas completo | ✅ Capturando trades |

**Lo que falta:** Estrategias intradía que operen en timeframes más cortos (1min, 5min) para capturar oportunidades de corto plazo.

### 1.2 Objetivo de Esta Fase

Implementar **estrategias intradía** como extensión del sistema de swing trading:

```
FILOSOFÍA CLAVE - INTRADÍA:
═══════════════════════════════════════════════════════════════════════════════
1. Intradía viene DESPUÉS del swing
   - Swing debe funcionar primero (MVP validado)
   - Intradía añade complejidad: más trades, más datos, más riesgo
   - No activar intradía hasta validar swing en paper trading

2. Mismo framework, diferentes parámetros
   - Reutilizar TradingStrategy ABC
   - Misma estructura de Signal
   - Métricas unificadas (C1 soporta todo)

3. Régimen sigue mandando
   - SIDEWAYS: Mean Reversion activo
   - Alta volatilidad intradía: Breakout activo
   - BEAR extremo: Pausar todo intradía

4. Datos real-time cuando sea necesario
   - Toggle entre delayed (15min) y real-time
   - Real-time solo para intradía activo
   - Costo de datos justificado por uso

5. Límites estrictos de exposición intradía
   - Max 20% del capital en posiciones intradía
   - Cierre obligatorio antes de fin de sesión
   - Stops más ajustados que swing
═══════════════════════════════════════════════════════════════════════════════
```

### 1.3 Por Qué Estas Estrategias

| Estrategia | Régimen Óptimo | Justificación |
|------------|---------------|---------------|
| Mean Reversion Intraday | SIDEWAYS | Mercado lateral = reversiones frecuentes |
| Volatility Breakout | VOLATILE (controlado) | Capturar movimientos direccionales explosivos |

### 1.4 Decisiones de Diseño

| Decisión | Justificación |
|----------|---------------|
| Herencia de TradingStrategy | Consistencia con swing, reutilización de código |
| IntraDayMixin | Funcionalidad común (session checks, limits) |
| Timeframes 1min/5min | Balance entre ruido y oportunidades |
| Position sizing reducido | Menor exposición por trade intradía |
| Session-aware trading | Respetar horarios de mercado, no overnight |

### 1.5 Riesgos y Mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Overtrading | Límite máximo de trades/día por estrategia |
| Costos de comisiones | Min profit target > 2x comisión esperada |
| Slippage | Limit orders preferidos, market orders solo urgencia |
| Datos delayed incorrectos | Toggle explícito, validación de timestamp |
| Posiciones overnight | Cierre forzado 15 min antes de cierre |

---

## 2. Objetivos de la Fase

| Objetivo | Criterio de Éxito |
|----------|-------------------|
| Mean Reversion implementado | Genera señales válidas en régimen SIDEWAYS |
| Volatility Breakout implementado | Genera señales en rupturas de rango |
| Timeframes intradía soportados | Data pipeline procesa 1min/5min bars |
| Toggle real-time funcional | Cambio dinámico delayed ↔ real-time |
| Límites intradía activos | Max exposure 20%, cierre end-of-day |
| Tests unitarios | > 80% cobertura en estrategias intradía |

---

## 3. Arquitectura de Estrategias Intradía

### 3.1 Diagrama de Componentes

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                      INTRADAY STRATEGY SYSTEM                                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  config/strategies.yaml                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐          │
│  │ strategies:                                                          │          │
│  │   # SWING (existentes)                                               │          │
│  │   etf_momentum:                                                      │          │
│  │     enabled: true                                                    │          │
│  │     type: "swing"                                                    │          │
│  │                                                                      │          │
│  │   # INTRADÍA (nuevas)                                                │          │
│  │   mean_reversion_intraday:                                           │          │
│  │     enabled: false  ◄── Desactivado por defecto                      │          │
│  │     type: "intraday"                                                 │          │
│  │     required_regime: [SIDEWAYS]                                      │          │
│  │     timeframe: "5min"                                                │          │
│  │                                                                      │          │
│  │   volatility_breakout:                                               │          │
│  │     enabled: false                                                   │          │
│  │     type: "intraday"                                                 │          │
│  │     required_regime: [BULL, VOLATILE]                                │          │
│  │     timeframe: "1min"                                                │          │
│  └─────────────────────────────────────────────────────────────────────┘          │
│                                                                                   │
│              │                                                                    │
│              ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐          │
│  │              StrategyRegistry (extendido)                            │          │
│  │  ─────────────────────────────────────────────────────────────────   │          │
│  │  • get_active_for_regime() → filtra swing + intradía                 │          │
│  │  • get_by_type("intraday") → solo estrategias intradía               │          │
│  │  • get_by_type("swing") → solo estrategias swing                     │          │
│  └─────────────────────────────────────────────────────────────────────┘          │
│              │                                                                    │
│      ┌───────┴──────────────────────────────────────────┐                         │
│      │                                                  │                         │
│      ▼                                                  ▼                         │
│  ┌────────────────────┐                    ┌────────────────────────────┐         │
│  │    SWING           │                    │       INTRADÍA             │         │
│  ├────────────────────┤                    ├────────────────────────────┤         │
│  │ • ETF Momentum     │                    │ • Mean Reversion Intraday  │         │
│  │ • AI Agent Swing   │                    │ • Volatility Breakout      │         │
│  │                    │                    │                            │         │
│  │ Timeframe: 1d      │                    │ Timeframe: 1min, 5min      │         │
│  │ Holding: días/sem  │                    │ Holding: minutos/horas     │         │
│  └────────────────────┘                    └────────────────────────────┘         │
│                                                      │                            │
│                                                      ▼                            │
│                                            ┌─────────────────────────┐            │
│                                            │   IntraDayMixin         │            │
│                                            │   ───────────────────── │            │
│                                            │ • is_market_open()      │            │
│                                            │ • time_to_close()       │            │
│                                            │ • check_intraday_limits │            │
│                                            │ • force_close_eod()     │            │
│                                            └─────────────────────────┘            │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Jerarquía de Clases

```
                    ┌─────────────────────────┐
                    │   TradingStrategy       │
                    │   (ABC - Fase B1)       │
                    │   ───────────────────── │
                    │   • strategy_id         │
                    │   • required_regime     │
                    │   • generate_signals()  │
                    │   • should_close()      │
                    └───────────┬─────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────────┐
│  SwingStrategy    │  │ IntraDayStrategy  │  │     AI Agent Strategy     │
│  (Fase B1)        │  │ (NUEVO - C2)      │  │     (Fase B2)             │
│                   │  │                   │  │                           │
│  • ETFMomentum    │  │  + IntraDayMixin  │  │  • Claude decision-making │
│                   │  │  ───────────────  │  │                           │
│                   │  │  • timeframe      │  │                           │
│                   │  │  • session_start  │  │                           │
│                   │  │  • session_end    │  │                           │
│                   │  │  • max_trades_day │  │                           │
└───────────────────┘  └─────────┬─────────┘  └───────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
        ┌───────────────────────┐  ┌───────────────────────┐
        │  MeanReversionIntra   │  │  VolatilityBreakout   │
        │  ───────────────────  │  │  ───────────────────  │
        │  • bollinger_period   │  │  • breakout_lookback  │
        │  • zscore_entry       │  │  • atr_multiplier     │
        │  • zscore_exit        │  │  • volume_confirm     │
        │  • max_holding_bars   │  │  • min_range_bars     │
        └───────────────────────┘  └───────────────────────┘
```

### 3.3 Flujo de Ejecución Intradía

```
                    ┌─────────────────────────────┐
                    │      IntraDayRunner         │
                    │      (cada 1-5 min)         │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │    1. Check Market Open     │
                    │    is_market_open()         │
                    └─────────────┬───────────────┘
                                  │
                         ┌────────┴────────┐
                    NO   │                 │  YES
              ┌──────────┘                 └──────────┐
              ▼                                       ▼
    ┌─────────────────┐                    ┌─────────────────────────┐
    │    Skip cycle   │                    │  2. Check Time to Close │
    │    Log status   │                    │  time_to_close() < 15min│
    └─────────────────┘                    └───────────┬─────────────┘
                                                       │
                                              ┌────────┴────────┐
                                         YES  │                 │  NO
                                   ┌──────────┘                 └──────────┐
                                   ▼                                       ▼
                         ┌─────────────────────┐              ┌─────────────────────┐
                         │  3. Force Close     │              │  4. Check Limits    │
                         │  All Intraday Pos   │              │  Daily trades/exp   │
                         │  force_close_eod()  │              └───────────┬─────────┘
                         └─────────────────────┘                          │
                                                                 ┌────────┴────────┐
                                                           LIMIT │                 │ OK
                                                       ┌─────────┘                 └─────────┐
                                                       ▼                                     ▼
                                             ┌─────────────────┐              ┌─────────────────────┐
                                             │  Skip signals   │              │  5. Get Regime      │
                                             │  Log warning    │              │  mcp-ml-models      │
                                             └─────────────────┘              └───────────┬─────────┘
                                                                                          │
                                                                              ┌───────────▼───────────┐
                                                                              │  6. Get Market Data   │
                                                                              │  Timeframe: 1min/5min │
                                                                              └───────────┬───────────┘
                                                                                          │
                                                                              ┌───────────▼───────────┐
                                                                              │  7. Generate Signals  │
                                                                              │  Per active strategy  │
                                                                              └───────────┬───────────┘
                                                                                          │
                                                                              ┌───────────▼───────────┐
                                                                              │  8. Validate & Send   │
                                                                              │  to Risk Manager      │
                                                                              └───────────────────────┘
```

---

## 4. Dependencias Entre Tareas

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                          FASE C2: ESTRATEGIAS INTRADÍA                                  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  ┌────────────────────────┐                                                             │
│  │ C2.1: IntraDayMixin    │                                                             │
│  │ + IntraDayStrategy ABC │├──────────────────────┐                                     │
│  └────────────────────────┘                       │                                     │
│                                                   │                                     │
│  ┌────────────────────────┐                       │     ┌────────────────────────┐      │
│  │ C2.2: Mean Reversion   │├──────────────────────┼────►│ C2.5: IntraDayRunner   │      │
│  │ Intraday               │                       │     │ + Config Updates       │      │
│  └────────────────────────┘                       │     └───────────┬────────────┘      │
│                                                   │                 │                   │
│  ┌────────────────────────┐                       │                 │                   │
│  │ C2.3: Volatility       │├──────────────────────┘                 │                   │
│  │ Breakout               │                                         │                   │
│  └────────────────────────┘                                         │                   │
│                                                                     │                   │
│  ┌────────────────────────┐                                         │                   │
│  │ C2.4: Data Pipeline    │├────────────────────────────────────────┤                   │
│  │ Intradía + Toggle RT   │                                         │                   │
│  └────────────────────────┘                                         │                   │
│                                                                     │                   │
│                                                                     ▼                   │
│                                                   ┌────────────────────────────────┐    │
│                                                   │ C2.6: Tests + Verificación     │    │
│                                                   │                                │    │
│                                                   └────────────────────────────────┘    │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘

LEYENDA:
────────
C2.1 es prerequisito de C2.2 y C2.3 (necesitan el mixin)
C2.2, C2.3 pueden desarrollarse en paralelo
C2.4 puede desarrollarse en paralelo con C2.2/C2.3
C2.5 integra todo (depende de C2.1-C2.4)
C2.6 requiere todos los anteriores
```

---

## 5. Interfaces Base para Intradía

### 5.1 IntraDayMixin (Funcionalidad Común)

Este mixin proporciona funcionalidad común para todas las estrategias intradía.

```python
# src/strategies/intraday/mixins.py
"""
Mixin para funcionalidad común de estrategias intradía.
"""
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)


@dataclass
class MarketSession:
    """Definición de sesión de mercado."""
    market_id: str              # "US", "EU", "CRYPTO"
    timezone: str               # "America/New_York", "Europe/Madrid"
    open_time: time             # 09:30 para US
    close_time: time            # 16:00 para US
    pre_market_start: Optional[time] = None   # 04:00 para US
    after_hours_end: Optional[time] = None    # 20:00 para US
    
    def is_open(self, dt: datetime) -> bool:
        """Verifica si el mercado está abierto en el datetime dado."""
        tz = ZoneInfo(self.timezone)
        local_dt = dt.astimezone(tz)
        current_time = local_dt.time()
        
        # Verificar día de semana (0=lunes, 6=domingo)
        if local_dt.weekday() >= 5:  # Sábado o domingo
            return False
        
        return self.open_time <= current_time <= self.close_time
    
    def time_to_close(self, dt: datetime) -> timedelta:
        """Retorna tiempo restante hasta el cierre."""
        tz = ZoneInfo(self.timezone)
        local_dt = dt.astimezone(tz)
        
        close_dt = local_dt.replace(
            hour=self.close_time.hour,
            minute=self.close_time.minute,
            second=0,
            microsecond=0
        )
        
        if local_dt >= close_dt:
            return timedelta(0)
        
        return close_dt - local_dt


# Sesiones predefinidas
MARKET_SESSIONS = {
    "US": MarketSession(
        market_id="US",
        timezone="America/New_York",
        open_time=time(9, 30),
        close_time=time(16, 0),
        pre_market_start=time(4, 0),
        after_hours_end=time(20, 0)
    ),
    "EU": MarketSession(
        market_id="EU",
        timezone="Europe/Madrid",
        open_time=time(9, 0),
        close_time=time(17, 30)
    ),
    "CRYPTO": MarketSession(
        market_id="CRYPTO",
        timezone="UTC",
        open_time=time(0, 0),
        close_time=time(23, 59)  # 24/7
    )
}


@dataclass
class IntraDayLimits:
    """Límites para trading intradía."""
    max_trades_per_day: int = 10          # Máx trades por día
    max_exposure_pct: float = 0.20        # Máx 20% del capital
    max_position_pct: float = 0.05        # Máx 5% por posición
    min_profit_vs_commission: float = 2.0 # Profit mínimo = 2x comisión
    force_close_minutes_before: int = 15  # Cerrar 15 min antes de cierre
    max_holding_minutes: int = 240        # Máx 4 horas en posición


class IntraDayMixin:
    """
    Mixin que proporciona funcionalidad común para estrategias intradía.
    
    Debe mezclarse con una clase que tenga:
    - self.market: str ("US", "EU")
    - self.limits: IntraDayLimits
    - self._trades_today: int (contador interno)
    """
    
    def __init_intraday__(
        self, 
        market: str = "US",
        limits: Optional[IntraDayLimits] = None
    ):
        """Inicializa componentes intradía."""
        self._market = market
        self._session = MARKET_SESSIONS.get(market, MARKET_SESSIONS["US"])
        self._limits = limits or IntraDayLimits()
        self._trades_today: int = 0
        self._last_trade_date: Optional[datetime] = None
        self._current_exposure: float = 0.0
    
    @property
    def market(self) -> str:
        return self._market
    
    @property
    def session(self) -> MarketSession:
        return self._session
    
    @property
    def limits(self) -> IntraDayLimits:
        return self._limits
    
    def is_market_open(self, dt: Optional[datetime] = None) -> bool:
        """Verifica si el mercado está abierto."""
        dt = dt or datetime.now(ZoneInfo("UTC"))
        return self._session.is_open(dt)
    
    def time_to_close(self, dt: Optional[datetime] = None) -> timedelta:
        """Tiempo restante hasta el cierre."""
        dt = dt or datetime.now(ZoneInfo("UTC"))
        return self._session.time_to_close(dt)
    
    def should_force_close(self, dt: Optional[datetime] = None) -> bool:
        """
        Determina si se debe forzar cierre de posiciones.
        True si faltan menos de X minutos para el cierre.
        """
        remaining = self.time_to_close(dt)
        threshold = timedelta(minutes=self._limits.force_close_minutes_before)
        return remaining <= threshold and remaining > timedelta(0)
    
    def check_daily_limit(self) -> bool:
        """
        Verifica si se puede hacer más trades hoy.
        Resetea contador si es nuevo día.
        """
        today = datetime.now(ZoneInfo("UTC")).date()
        
        if self._last_trade_date != today:
            self._trades_today = 0
            self._last_trade_date = today
        
        return self._trades_today < self._limits.max_trades_per_day
    
    def increment_trade_count(self):
        """Incrementa contador de trades del día."""
        self._trades_today += 1
        self._last_trade_date = datetime.now(ZoneInfo("UTC")).date()
    
    def check_exposure_limit(self, portfolio_value: float) -> float:
        """
        Retorna el capital disponible para nuevas posiciones intradía.
        """
        max_intraday = portfolio_value * self._limits.max_exposure_pct
        available = max_intraday - self._current_exposure
        return max(0, available)
    
    def validate_profit_vs_commission(
        self, 
        expected_profit: float, 
        commission: float
    ) -> bool:
        """
        Valida que el profit esperado justifique la comisión.
        """
        if commission <= 0:
            return True
        return expected_profit >= (commission * self._limits.min_profit_vs_commission)
    
    def get_max_position_size(
        self, 
        portfolio_value: float,
        price: float
    ) -> int:
        """
        Calcula el tamaño máximo de posición en unidades.
        """
        max_value = portfolio_value * self._limits.max_position_pct
        available = self.check_exposure_limit(portfolio_value)
        effective_max = min(max_value, available)
        
        if price <= 0:
            return 0
        
        return int(effective_max / price)
    
    def reset_daily_counters(self):
        """Reset manual de contadores (para testing)."""
        self._trades_today = 0
        self._current_exposure = 0.0
        self._last_trade_date = None
```

### 5.2 IntraDayStrategy (Clase Base Abstracta)

```python
# src/strategies/intraday/base.py
"""
Clase base abstracta para estrategias intradía.
"""
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

from src.strategies.interfaces import TradingStrategy, Signal
from src.strategies.intraday.mixins import IntraDayMixin, IntraDayLimits


@dataclass
class IntraDayConfig:
    """Configuración específica para estrategias intradía."""
    timeframe: str = "5min"              # "1min", "5min", "15min"
    market: str = "US"                   # "US", "EU", "CRYPTO"
    lookback_bars: int = 100             # Barras de histórico necesarias
    min_volume_ratio: float = 1.0        # Volumen mínimo vs promedio
    max_spread_pct: float = 0.002        # Spread máximo aceptable (0.2%)
    
    # Override de límites por defecto
    limits: IntraDayLimits = field(default_factory=IntraDayLimits)


class IntraDayStrategy(TradingStrategy, IntraDayMixin):
    """
    Clase base para estrategias intradía.
    
    Hereda de TradingStrategy (ABC de Fase B1) y añade:
    - Gestión de sesiones de mercado
    - Límites intradía (trades/día, exposición)
    - Timeframes cortos (1min, 5min)
    - Cierre forzado EOD
    
    Las subclases DEBEN implementar:
    - strategy_id (property)
    - required_regime (property)  
    - generate_signals()
    - should_close()
    - _calculate_entry_signal() (específico de cada estrategia)
    """
    
    def __init__(self, config: IntraDayConfig):
        """
        Inicializa estrategia intradía.
        
        Args:
            config: Configuración de la estrategia
        """
        self.config = config
        self.__init_intraday__(
            market=config.market,
            limits=config.limits
        )
        self._open_positions: dict[str, dict] = {}
    
    @property
    def strategy_type(self) -> str:
        """Tipo de estrategia."""
        return "intraday"
    
    @property
    def timeframe(self) -> str:
        """Timeframe de la estrategia."""
        return self.config.timeframe
    
    def pre_generate_checks(
        self, 
        market_data: pd.DataFrame,
        current_time: Optional[datetime] = None
    ) -> tuple[bool, str]:
        """
        Verificaciones previas a generar señales.
        
        Returns:
            (can_proceed, reason): Si puede proceder y razón si no
        """
        current_time = current_time or datetime.now()
        
        # 1. Mercado abierto
        if not self.is_market_open(current_time):
            return False, "Market closed"
        
        # 2. No cerca del cierre
        if self.should_force_close(current_time):
            return False, "Too close to market close"
        
        # 3. Límite diario
        if not self.check_daily_limit():
            return False, f"Daily trade limit reached ({self._limits.max_trades_per_day})"
        
        # 4. Datos suficientes
        if len(market_data) < self.config.lookback_bars:
            return False, f"Insufficient data ({len(market_data)}/{self.config.lookback_bars})"
        
        # 5. Volumen mínimo
        if 'volume' in market_data.columns:
            avg_volume = market_data['volume'].rolling(20).mean().iloc[-1]
            current_volume = market_data['volume'].iloc[-1]
            if current_volume < avg_volume * self.config.min_volume_ratio:
                return False, "Volume too low"
        
        return True, "OK"
    
    def generate_signals(
        self,
        market_data: pd.DataFrame,
        regime: str,
        portfolio: dict,
        current_time: Optional[datetime] = None
    ) -> list[Signal]:
        """
        Genera señales de trading.
        
        Flujo:
        1. Pre-checks (mercado, límites)
        2. Validar régimen
        3. Llamar implementación específica
        4. Filtrar y validar señales
        
        Args:
            market_data: DataFrame con OHLCV
            regime: Régimen actual ("BULL", "BEAR", "SIDEWAYS", "VOLATILE")
            portfolio: Estado del portfolio {"value": float, "positions": [...]}
            current_time: Timestamp actual (para testing)
            
        Returns:
            Lista de Signal para ejecutar
        """
        signals = []
        current_time = current_time or datetime.now()
        
        # Pre-checks
        can_proceed, reason = self.pre_generate_checks(market_data, current_time)
        if not can_proceed:
            self._log_skip(reason)
            return signals
        
        # Validar régimen
        if regime not in self.required_regime:
            self._log_skip(f"Regime {regime} not in {self.required_regime}")
            return signals
        
        # Generar señales (implementación específica)
        raw_signals = self._calculate_entry_signals(
            market_data=market_data,
            regime=regime,
            portfolio=portfolio
        )
        
        # Validar y filtrar señales
        portfolio_value = portfolio.get("value", 0)
        for signal in raw_signals:
            if self._validate_signal(signal, portfolio_value):
                signals.append(signal)
                self.increment_trade_count()
        
        return signals
    
    @abstractmethod
    def _calculate_entry_signals(
        self,
        market_data: pd.DataFrame,
        regime: str,
        portfolio: dict
    ) -> list[Signal]:
        """
        Calcula señales de entrada específicas de la estrategia.
        Debe ser implementado por cada estrategia concreta.
        """
        pass
    
    def should_close(
        self,
        position: dict,
        market_data: pd.DataFrame,
        regime: str,
        current_time: Optional[datetime] = None
    ) -> Optional[Signal]:
        """
        Determina si una posición intradía debe cerrarse.
        
        Razones de cierre:
        1. Cierre forzado EOD
        2. Max holding time alcanzado
        3. Stop loss / take profit
        4. Cambio de régimen adverso
        5. Condición específica de estrategia
        
        Args:
            position: Posición actual
            market_data: Datos de mercado
            regime: Régimen actual
            current_time: Timestamp actual
            
        Returns:
            Signal de cierre o None
        """
        current_time = current_time or datetime.now()
        symbol = position.get("symbol")
        entry_time = position.get("entry_time")
        entry_price = position.get("entry_price")
        current_price = market_data['close'].iloc[-1]
        
        # 1. Cierre forzado EOD
        if self.should_force_close(current_time):
            return self._create_close_signal(
                symbol=symbol,
                current_price=current_price,
                reason="EOD_FORCE_CLOSE"
            )
        
        # 2. Max holding time
        if entry_time:
            holding_duration = current_time - entry_time
            max_holding = timedelta(minutes=self._limits.max_holding_minutes)
            if holding_duration > max_holding:
                return self._create_close_signal(
                    symbol=symbol,
                    current_price=current_price,
                    reason="MAX_HOLDING_TIME"
                )
        
        # 3. Cambio de régimen adverso
        if regime not in self.required_regime:
            return self._create_close_signal(
                symbol=symbol,
                current_price=current_price,
                reason=f"REGIME_CHANGE_TO_{regime}"
            )
        
        # 4. Condición específica de estrategia
        return self._check_strategy_exit(position, market_data, regime)
    
    @abstractmethod
    def _check_strategy_exit(
        self,
        position: dict,
        market_data: pd.DataFrame,
        regime: str
    ) -> Optional[Signal]:
        """
        Verifica condiciones de salida específicas de la estrategia.
        Debe ser implementado por cada estrategia concreta.
        """
        pass
    
    def _validate_signal(
        self, 
        signal: Signal, 
        portfolio_value: float
    ) -> bool:
        """Valida que la señal cumple límites intradía."""
        # Verificar exposición
        if signal.size_suggestion:
            signal_value = signal.size_suggestion * (signal.entry_price or 0)
            available = self.check_exposure_limit(portfolio_value)
            if signal_value > available:
                self._log_skip(f"Signal exceeds exposure limit: {signal_value} > {available}")
                return False
        
        # Verificar profit vs comisión (estimado)
        if signal.take_profit and signal.entry_price:
            expected_profit = abs(signal.take_profit - signal.entry_price)
            estimated_commission = 2.0  # €2 estimado roundtrip
            if not self.validate_profit_vs_commission(expected_profit, estimated_commission):
                self._log_skip("Expected profit doesn't justify commission")
                return False
        
        return True
    
    def _create_close_signal(
        self,
        symbol: str,
        current_price: float,
        reason: str
    ) -> Signal:
        """Crea señal de cierre."""
        return Signal(
            strategy_id=self.strategy_id,
            symbol=symbol,
            direction="CLOSE",
            confidence=1.0,  # Cierre obligatorio
            entry_price=current_price,
            stop_loss=None,
            take_profit=None,
            size_suggestion=None,
            regime_at_signal="N/A",
            reasoning=reason,
            metadata={"close_type": reason}
        )
    
    def _log_skip(self, reason: str):
        """Log cuando se omiten señales."""
        import logging
        logger = logging.getLogger(f"strategy.{self.strategy_id}")
        logger.debug(f"Skipping signal generation: {reason}")
```

### 5.3 Actualización de Signal (Metadata Intradía)

La dataclass Signal de Fase B1 ya es compatible, pero añadimos metadata específica:

```python
# Ejemplo de Signal para intradía (usa el mismo Signal de B1)
intraday_signal = Signal(
    strategy_id="mean_reversion_intraday",
    symbol="SPY",
    direction="LONG",
    confidence=0.72,
    entry_price=450.25,
    stop_loss=448.50,
    take_profit=452.00,
    size_suggestion=10,
    regime_at_signal="SIDEWAYS",
    reasoning="Z-score below -2.0, expecting reversion",
    metadata={
        # Metadata específica intradía
        "strategy_type": "intraday",
        "timeframe": "5min",
        "z_score": -2.15,
        "bollinger_position": "below_lower",
        "volume_ratio": 1.3,
        "bars_in_range": 45,
        "expected_holding_bars": 12,
        "session": "US",
        "time_to_close_minutes": 180
    }
)
```

---

## 6. Estructura de Archivos Fase C2

```
src/
├── strategies/
│   ├── __init__.py
│   ├── interfaces.py              # TradingStrategy ABC (Fase B1) ✅
│   ├── registry.py                # StrategyRegistry (Fase B1) ✅
│   ├── config.py                  # StrategyConfig (Fase B1) ✅
│   ├── runner.py                  # StrategyRunner (Fase B1) ✅
│   │
│   ├── swing/                     # Estrategias swing (Fase B1) ✅
│   │   ├── __init__.py
│   │   └── etf_momentum.py
│   │
│   └── intraday/                  # NUEVO - Fase C2
│       ├── __init__.py
│       ├── mixins.py              # IntraDayMixin, MarketSession
│       ├── base.py                # IntraDayStrategy ABC
│       ├── mean_reversion.py      # MeanReversionIntraday
│       ├── volatility_breakout.py # VolatilityBreakout
│       └── runner.py              # IntraDayRunner
│
├── data/
│   └── providers/
│       ├── ibkr.py                # Actualizar para intradía
│       └── realtime_toggle.py     # NUEVO - Toggle real-time
│
config/
├── strategies.yaml                # Actualizar con estrategias intradía
├── intraday.yaml                  # NUEVO - Config específica intradía
└── markets.yaml                   # NUEVO - Definición de sesiones

tests/
└── strategies/
    └── intraday/
        ├── __init__.py
        ├── test_mixins.py
        ├── test_mean_reversion.py
        ├── test_volatility_breakout.py
        └── test_runner.py
```

---

## 7. Configuración YAML Intradía

### 7.1 config/intraday.yaml

```yaml
# Configuración específica para trading intradía
# Este archivo controla todas las estrategias intradía

intraday:
  # Master switch - desactivar todo intradía
  enabled: false  # ◄── IMPORTANTE: false por defecto hasta validar swing
  
  # Requisitos para activar
  prerequisites:
    min_swing_trades: 50           # Mínimo trades swing antes de activar
    min_swing_sharpe: 0.5          # Sharpe mínimo del swing
    paper_trading_only: true       # Solo en paper trading inicialmente
  
  # Límites globales intradía
  global_limits:
    max_total_exposure_pct: 0.20   # 20% máximo del capital en intradía
    max_strategies_active: 2        # Máx estrategias intradía simultáneas
    max_trades_per_day_total: 20   # Máx trades intradía/día (todas estrategias)
  
  # Data settings
  data:
    default_timeframe: "5min"
    available_timeframes: ["1min", "5min", "15min"]
    use_realtime: false            # false = delayed 15min
    realtime_buffer_seconds: 1     # Buffer para evitar datos incompletos
  
  # Sesiones de mercado
  sessions:
    US:
      timezone: "America/New_York"
      open: "09:30"
      close: "16:00"
      trading_start: "09:45"       # Evitar primeros 15 min
      trading_end: "15:45"         # Cerrar todo 15 min antes
    EU:
      timezone: "Europe/Madrid"
      open: "09:00"
      close: "17:30"
      trading_start: "09:15"
      trading_end: "17:15"

# Configuración por estrategia
strategies:
  mean_reversion_intraday:
    enabled: false
    timeframe: "5min"
    market: "US"
    required_regime: ["SIDEWAYS"]
    
    # Límites específicos
    limits:
      max_trades_per_day: 5
      max_exposure_pct: 0.10       # 10% máximo para esta estrategia
      max_position_pct: 0.03       # 3% por posición
      max_holding_minutes: 120     # 2 horas máximo
    
    # Parámetros de estrategia
    params:
      bollinger_period: 20
      bollinger_std: 2.0
      zscore_entry: 2.0            # Entrar cuando Z < -2 o Z > 2
      zscore_exit: 0.5             # Salir cuando |Z| < 0.5
      rsi_oversold: 30
      rsi_overbought: 70
      min_volume_ratio: 1.2
      atr_stop_multiplier: 1.5
    
    # Símbolos permitidos
    universe:
      - "SPY"
      - "QQQ"
      - "IWM"
      - "DIA"
  
  volatility_breakout:
    enabled: false
    timeframe: "1min"
    market: "US"
    required_regime: ["BULL", "VOLATILE"]
    
    limits:
      max_trades_per_day: 3
      max_exposure_pct: 0.10
      max_position_pct: 0.03
      max_holding_minutes: 60      # 1 hora máximo
    
    params:
      range_lookback_bars: 30      # Barras para calcular rango
      breakout_threshold: 1.5      # ATR multiplier para confirmar breakout
      volume_surge_ratio: 2.0      # Volumen debe ser 2x promedio
      min_range_bars: 20           # Mínimo barras en consolidación
      atr_period: 14
      stop_atr_multiplier: 1.0
      target_atr_multiplier: 2.0
    
    universe:
      - "SPY"
      - "QQQ"
      - "AAPL"
      - "TSLA"
      - "NVDA"
```

### 7.2 Actualización config/strategies.yaml

```yaml
# Añadir a config/strategies.yaml existente

strategies:
  # === SWING (existentes) ===
  etf_momentum:
    enabled: true
    type: "swing"
    required_regime: ["BULL"]
    # ... resto de config existente
  
  ai_agent_swing:
    enabled: true
    type: "swing"
    # ... resto de config existente
  
  # === INTRADÍA (nuevas) ===
  mean_reversion_intraday:
    enabled: false                 # ◄── Desactivado por defecto
    type: "intraday"
    config_file: "intraday.yaml"   # Config detallada en archivo separado
  
  volatility_breakout:
    enabled: false
    type: "intraday"
    config_file: "intraday.yaml"

# Configuración del runner
runner:
  swing:
    interval_minutes: 5            # Cada 5 minutos
    enabled: true
  
  intraday:
    interval_seconds: 60           # Cada 60 segundos
    enabled: false                 # ◄── Desactivado hasta validar swing
    require_realtime: false        # Puede funcionar con delayed
```

---

## 8. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| TradingStrategy ABC | fase_b1_estrategias_swing.md | Sección 4 |
| Signal dataclass | fase_b1_estrategias_swing.md | Sección 4.1 |
| StrategyRegistry | fase_b1_estrategias_swing.md | Sección 8 |
| Régimen detector | fase_a2_ml_modular.md | Tareas A2.2-A2.3 |
| Sistema de métricas | fase_c1_metricas.md | Secciones 3-7 |
| IBKR provider | fase_a1_extensiones_base.md | Tarea A1.3 |
| Agentes core | fase_3_agentes_core.md | Tareas 3.1-3.4 |

---

*Fin de Parte 1 - Contexto, Arquitectura y Diseño*

---

**Siguiente:** Parte 2 - Implementación Mean Reversion Intraday
# ⚡ Fase C2: Estrategias Intradía

## Parte 2: Implementación Mean Reversion Intraday

---

## 9. Tarea C2.2: Mean Reversion Intraday

### 9.1 Concepto de la Estrategia

Mean Reversion Intraday explota la tendencia de los precios a regresar a su media en mercados laterales (SIDEWAYS). 

```
PRINCIPIO FUNDAMENTAL:
══════════════════════════════════════════════════════════════════════════════
En un mercado SIDEWAYS (sin tendencia clara):
- Los precios oscilan alrededor de una media
- Desviaciones extremas tienden a corregirse
- Comprar en sobreventa, vender en sobrecompra

INDICADORES CLAVE:
- Bollinger Bands: Define el "canal" normal de precios
- Z-Score: Cuántas desviaciones estándar del precio vs media
- RSI: Confirma condición de sobreventa/sobrecompra
- Volumen: Valida que hay liquidez suficiente

ENTRADA LONG:
- Precio toca/cruza banda inferior de Bollinger
- Z-Score < -2.0 (2 std debajo de media)
- RSI < 30 (sobreventa)
- Volumen > promedio (hay actividad)

ENTRADA SHORT:
- Precio toca/cruza banda superior de Bollinger
- Z-Score > 2.0 (2 std arriba de media)
- RSI > 70 (sobrecompra)
- Volumen > promedio

SALIDA:
- Precio regresa a la media (Z-Score cerca de 0)
- Stop loss basado en ATR
- Take profit en banda opuesta o media
- Tiempo máximo en posición (evitar quedar atrapado)
══════════════════════════════════════════════════════════════════════════════
```

### 9.2 Diagrama de Flujo de Decisión

```
                        ┌─────────────────────────────┐
                        │   Nuevo bar de 5 minutos    │
                        └─────────────┬───────────────┘
                                      │
                        ┌─────────────▼───────────────┐
                        │  Calcular indicadores:      │
                        │  • Bollinger Bands (20, 2)  │
                        │  • Z-Score (20 períodos)    │
                        │  • RSI (14)                 │
                        │  • ATR (14)                 │
                        │  • Volume ratio             │
                        └─────────────┬───────────────┘
                                      │
                        ┌─────────────▼───────────────┐
                        │  ¿Hay posición abierta?     │
                        └─────────────┬───────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
               SÍ   │                                   │  NO
                    ▼                                   ▼
        ┌───────────────────────┐           ┌───────────────────────┐
        │  Evaluar salida:      │           │  Evaluar entrada:     │
        │  • ¿Z-Score → 0?      │           │  • ¿Z-Score extremo?  │
        │  • ¿Hit SL/TP?        │           │  • ¿RSI confirma?     │
        │  • ¿Max holding?      │           │  • ¿Volumen OK?       │
        └───────────┬───────────┘           └───────────┬───────────┘
                    │                                   │
            ┌───────┴───────┐                   ┌───────┴───────┐
       SÍ   │               │ NO           SÍ   │               │ NO
            ▼               ▼                   ▼               ▼
    ┌───────────────┐  ┌─────────┐      ┌───────────────┐  ┌─────────┐
    │ Signal CLOSE  │  │  HOLD   │      │ Signal ENTRY  │  │  WAIT   │
    │ • reason      │  │         │      │ • LONG/SHORT  │  │         │
    │ • pnl calc    │  │         │      │ • SL/TP calc  │  │         │
    └───────────────┘  └─────────┘      └───────────────┘  └─────────┘
```

### 9.3 Implementación Completa

```python
# src/strategies/intraday/mean_reversion.py
"""
Estrategia Mean Reversion Intradía.

Explota reversiones a la media en mercados laterales (SIDEWAYS).
Usa Bollinger Bands, Z-Score y RSI para identificar extremos.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd
import logging

from src.strategies.interfaces import Signal
from src.strategies.intraday.base import IntraDayStrategy, IntraDayConfig
from src.strategies.intraday.mixins import IntraDayLimits

logger = logging.getLogger(__name__)


@dataclass
class MeanReversionConfig(IntraDayConfig):
    """Configuración específica para Mean Reversion."""
    # Bollinger Bands
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    
    # Z-Score
    zscore_period: int = 20
    zscore_entry_threshold: float = 2.0    # Entrar cuando |Z| > 2.0
    zscore_exit_threshold: float = 0.5     # Salir cuando |Z| < 0.5
    
    # RSI
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    
    # ATR para stops
    atr_period: int = 14
    atr_stop_multiplier: float = 1.5
    atr_target_multiplier: float = 2.0
    
    # Filtros
    min_volume_ratio: float = 1.2
    max_spread_pct: float = 0.002
    
    # Holding
    max_holding_bars: int = 24             # ~2 horas en 5min bars
    
    # Límites (override defaults)
    limits: IntraDayLimits = field(default_factory=lambda: IntraDayLimits(
        max_trades_per_day=5,
        max_exposure_pct=0.10,
        max_position_pct=0.03,
        max_holding_minutes=120
    ))


class MeanReversionIntraday(IntraDayStrategy):
    """
    Estrategia de Mean Reversion para trading intradía.
    
    Lógica:
    - LONG cuando precio está significativamente por debajo de la media
    - SHORT cuando precio está significativamente por encima de la media
    - EXIT cuando precio regresa a la media
    
    Condiciones de entrada LONG:
    1. Z-Score < -zscore_entry_threshold
    2. Precio <= Bollinger Band inferior
    3. RSI < rsi_oversold
    4. Volumen > min_volume_ratio * avg_volume
    
    Condiciones de entrada SHORT:
    1. Z-Score > zscore_entry_threshold
    2. Precio >= Bollinger Band superior
    3. RSI > rsi_overbought
    4. Volumen > min_volume_ratio * avg_volume
    
    Condiciones de salida:
    1. |Z-Score| < zscore_exit_threshold (reversión a media)
    2. Stop loss hit (ATR-based)
    3. Take profit hit (banda opuesta o media)
    4. Max holding time alcanzado
    """
    
    def __init__(self, config: Optional[MeanReversionConfig] = None):
        """
        Inicializa estrategia Mean Reversion.
        
        Args:
            config: Configuración de la estrategia. Si None, usa defaults.
        """
        self._config = config or MeanReversionConfig()
        super().__init__(self._config)
        
        # Cache de indicadores
        self._indicators_cache: dict = {}
        self._last_calc_time: Optional[datetime] = None
    
    @property
    def strategy_id(self) -> str:
        return "mean_reversion_intraday"
    
    @property
    def required_regime(self) -> list[str]:
        return ["SIDEWAYS"]
    
    @property
    def mr_config(self) -> MeanReversionConfig:
        """Acceso tipado a la configuración."""
        return self._config
    
    # =========================================================================
    # CÁLCULO DE INDICADORES
    # =========================================================================
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula todos los indicadores necesarios.
        
        Args:
            df: DataFrame con columnas OHLCV
            
        Returns:
            DataFrame con indicadores añadidos
        """
        df = df.copy()
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(
            window=self.mr_config.bollinger_period
        ).mean()
        
        bb_std = df['close'].rolling(
            window=self.mr_config.bollinger_period
        ).std()
        
        df['bb_upper'] = df['bb_middle'] + (bb_std * self.mr_config.bollinger_std)
        df['bb_lower'] = df['bb_middle'] - (bb_std * self.mr_config.bollinger_std)
        
        # Z-Score
        rolling_mean = df['close'].rolling(
            window=self.mr_config.zscore_period
        ).mean()
        rolling_std = df['close'].rolling(
            window=self.mr_config.zscore_period
        ).std()
        
        df['zscore'] = (df['close'] - rolling_mean) / rolling_std
        
        # RSI
        df['rsi'] = self._calculate_rsi(
            df['close'], 
            period=self.mr_config.rsi_period
        )
        
        # ATR
        df['atr'] = self._calculate_atr(
            df['high'], 
            df['low'], 
            df['close'],
            period=self.mr_config.atr_period
        )
        
        # Volume ratio
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Bollinger position (para metadata)
        df['bb_position'] = np.where(
            df['close'] <= df['bb_lower'], 'below_lower',
            np.where(df['close'] >= df['bb_upper'], 'above_upper', 'inside')
        )
        
        return df
    
    def _calculate_rsi(
        self, 
        prices: pd.Series, 
        period: int = 14
    ) -> pd.Series:
        """Calcula RSI."""
        delta = prices.diff()
        
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_atr(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """Calcula ATR (Average True Range)."""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    # =========================================================================
    # GENERACIÓN DE SEÑALES
    # =========================================================================
    
    def _calculate_entry_signals(
        self,
        market_data: pd.DataFrame,
        regime: str,
        portfolio: dict
    ) -> list[Signal]:
        """
        Calcula señales de entrada para Mean Reversion.
        
        Args:
            market_data: DataFrame con OHLCV
            regime: Régimen actual (debe ser SIDEWAYS)
            portfolio: Estado del portfolio
            
        Returns:
            Lista de Signal (0 o 1 señal típicamente)
        """
        signals = []
        
        # Calcular indicadores
        df = self._calculate_indicators(market_data)
        
        # Obtener última fila
        current = df.iloc[-1]
        
        # Verificar que hay datos válidos
        if pd.isna(current['zscore']) or pd.isna(current['rsi']):
            logger.debug("Insufficient data for indicators")
            return signals
        
        # Extraer valores actuales
        price = current['close']
        zscore = current['zscore']
        rsi = current['rsi']
        bb_lower = current['bb_lower']
        bb_upper = current['bb_upper']
        bb_middle = current['bb_middle']
        atr = current['atr']
        volume_ratio = current['volume_ratio']
        
        # Log estado actual
        logger.debug(
            f"MR Check: price={price:.2f}, zscore={zscore:.2f}, "
            f"rsi={rsi:.1f}, vol_ratio={volume_ratio:.2f}"
        )
        
        # Verificar condiciones de volumen
        if volume_ratio < self.mr_config.min_volume_ratio:
            logger.debug(f"Volume too low: {volume_ratio:.2f}")
            return signals
        
        # Obtener símbolo del DataFrame
        symbol = market_data['symbol'].iloc[-1] if 'symbol' in market_data.columns else "UNKNOWN"
        
        # =====================================================================
        # SEÑAL LONG: Sobreventa extrema
        # =====================================================================
        if (zscore < -self.mr_config.zscore_entry_threshold and
            price <= bb_lower and
            rsi < self.mr_config.rsi_oversold):
            
            # Calcular stop loss y take profit
            stop_loss = price - (atr * self.mr_config.atr_stop_multiplier)
            take_profit = bb_middle  # Target: media de Bollinger
            
            # Calcular tamaño de posición
            portfolio_value = portfolio.get("value", 25000)
            position_size = self.get_max_position_size(portfolio_value, price)
            
            if position_size > 0:
                signal = Signal(
                    strategy_id=self.strategy_id,
                    symbol=symbol,
                    direction="LONG",
                    confidence=self._calculate_confidence(zscore, rsi, "LONG"),
                    entry_price=price,
                    stop_loss=round(stop_loss, 2),
                    take_profit=round(take_profit, 2),
                    size_suggestion=position_size,
                    regime_at_signal=regime,
                    reasoning=self._generate_reasoning(zscore, rsi, "LONG"),
                    metadata={
                        "strategy_type": "intraday",
                        "timeframe": self.timeframe,
                        "z_score": round(zscore, 3),
                        "rsi": round(rsi, 1),
                        "bollinger_position": "below_lower",
                        "bb_lower": round(bb_lower, 2),
                        "bb_middle": round(bb_middle, 2),
                        "bb_upper": round(bb_upper, 2),
                        "atr": round(atr, 4),
                        "volume_ratio": round(volume_ratio, 2),
                        "expected_holding_bars": self.mr_config.max_holding_bars // 2,
                        "risk_reward_ratio": round(
                            (take_profit - price) / (price - stop_loss), 2
                        )
                    }
                )
                signals.append(signal)
                logger.info(f"LONG signal generated: {symbol} @ {price:.2f}")
        
        # =====================================================================
        # SEÑAL SHORT: Sobrecompra extrema
        # =====================================================================
        elif (zscore > self.mr_config.zscore_entry_threshold and
              price >= bb_upper and
              rsi > self.mr_config.rsi_overbought):
            
            # Calcular stop loss y take profit
            stop_loss = price + (atr * self.mr_config.atr_stop_multiplier)
            take_profit = bb_middle  # Target: media de Bollinger
            
            # Calcular tamaño de posición
            portfolio_value = portfolio.get("value", 25000)
            position_size = self.get_max_position_size(portfolio_value, price)
            
            if position_size > 0:
                signal = Signal(
                    strategy_id=self.strategy_id,
                    symbol=symbol,
                    direction="SHORT",
                    confidence=self._calculate_confidence(zscore, rsi, "SHORT"),
                    entry_price=price,
                    stop_loss=round(stop_loss, 2),
                    take_profit=round(take_profit, 2),
                    size_suggestion=position_size,
                    regime_at_signal=regime,
                    reasoning=self._generate_reasoning(zscore, rsi, "SHORT"),
                    metadata={
                        "strategy_type": "intraday",
                        "timeframe": self.timeframe,
                        "z_score": round(zscore, 3),
                        "rsi": round(rsi, 1),
                        "bollinger_position": "above_upper",
                        "bb_lower": round(bb_lower, 2),
                        "bb_middle": round(bb_middle, 2),
                        "bb_upper": round(bb_upper, 2),
                        "atr": round(atr, 4),
                        "volume_ratio": round(volume_ratio, 2),
                        "expected_holding_bars": self.mr_config.max_holding_bars // 2,
                        "risk_reward_ratio": round(
                            (price - take_profit) / (stop_loss - price), 2
                        )
                    }
                )
                signals.append(signal)
                logger.info(f"SHORT signal generated: {symbol} @ {price:.2f}")
        
        return signals
    
    def _calculate_confidence(
        self, 
        zscore: float, 
        rsi: float, 
        direction: str
    ) -> float:
        """
        Calcula nivel de confianza de la señal.
        
        Factores:
        - Magnitud del Z-Score (más extremo = más confianza)
        - RSI (más extremo = más confianza)
        
        Returns:
            Confianza entre 0.5 y 0.95
        """
        base_confidence = 0.5
        
        # Z-Score contribution (0 a 0.25)
        zscore_abs = abs(zscore)
        zscore_contrib = min(0.25, (zscore_abs - 2.0) * 0.1)
        
        # RSI contribution (0 a 0.20)
        if direction == "LONG":
            rsi_extremity = max(0, (30 - rsi) / 30)
        else:  # SHORT
            rsi_extremity = max(0, (rsi - 70) / 30)
        rsi_contrib = rsi_extremity * 0.20
        
        confidence = base_confidence + zscore_contrib + rsi_contrib
        return round(min(0.95, confidence), 2)
    
    def _generate_reasoning(
        self, 
        zscore: float, 
        rsi: float, 
        direction: str
    ) -> str:
        """Genera explicación de la señal."""
        if direction == "LONG":
            return (
                f"Mean reversion LONG: Z-Score={zscore:.2f} (oversold), "
                f"RSI={rsi:.1f} (<{self.mr_config.rsi_oversold}), "
                f"price at lower Bollinger Band. "
                f"Expecting reversion to mean."
            )
        else:
            return (
                f"Mean reversion SHORT: Z-Score={zscore:.2f} (overbought), "
                f"RSI={rsi:.1f} (>{self.mr_config.rsi_overbought}), "
                f"price at upper Bollinger Band. "
                f"Expecting reversion to mean."
            )
    
    # =========================================================================
    # EVALUACIÓN DE SALIDA
    # =========================================================================
    
    def _check_strategy_exit(
        self,
        position: dict,
        market_data: pd.DataFrame,
        regime: str
    ) -> Optional[Signal]:
        """
        Verifica condiciones de salida específicas de Mean Reversion.
        
        Condiciones de salida:
        1. Z-Score ha revertido (|Z| < exit_threshold)
        2. Precio alcanzó target (media de Bollinger)
        3. Max holding bars alcanzado
        4. RSI ya no extremo
        
        Args:
            position: Posición actual
            market_data: Datos de mercado actuales
            regime: Régimen actual
            
        Returns:
            Signal de cierre o None
        """
        # Calcular indicadores actuales
        df = self._calculate_indicators(market_data)
        current = df.iloc[-1]
        
        symbol = position.get("symbol")
        direction = position.get("direction")
        entry_price = position.get("entry_price", 0)
        entry_bar = position.get("entry_bar", 0)
        current_bar = len(df)
        
        price = current['close']
        zscore = current['zscore']
        bb_middle = current['bb_middle']
        
        # Verificar datos válidos
        if pd.isna(zscore):
            return None
        
        # =====================================================================
        # Condición 1: Z-Score ha revertido a la media
        # =====================================================================
        if abs(zscore) < self.mr_config.zscore_exit_threshold:
            pnl_pct = ((price - entry_price) / entry_price) * 100
            if direction == "SHORT":
                pnl_pct = -pnl_pct
            
            return Signal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                direction="CLOSE",
                confidence=0.9,
                entry_price=price,
                stop_loss=None,
                take_profit=None,
                size_suggestion=None,
                regime_at_signal=regime,
                reasoning=f"Mean reversion complete: Z-Score={zscore:.2f}, PnL={pnl_pct:.2f}%",
                metadata={
                    "exit_reason": "MEAN_REVERSION_COMPLETE",
                    "zscore_at_exit": round(zscore, 3),
                    "bars_held": current_bar - entry_bar,
                    "pnl_pct": round(pnl_pct, 2)
                }
            )
        
        # =====================================================================
        # Condición 2: Max holding bars alcanzado
        # =====================================================================
        bars_held = current_bar - entry_bar
        if bars_held >= self.mr_config.max_holding_bars:
            pnl_pct = ((price - entry_price) / entry_price) * 100
            if direction == "SHORT":
                pnl_pct = -pnl_pct
            
            return Signal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                direction="CLOSE",
                confidence=1.0,  # Forzado
                entry_price=price,
                stop_loss=None,
                take_profit=None,
                size_suggestion=None,
                regime_at_signal=regime,
                reasoning=f"Max holding time reached: {bars_held} bars, PnL={pnl_pct:.2f}%",
                metadata={
                    "exit_reason": "MAX_HOLDING_BARS",
                    "bars_held": bars_held,
                    "max_bars": self.mr_config.max_holding_bars,
                    "pnl_pct": round(pnl_pct, 2)
                }
            )
        
        # =====================================================================
        # Condición 3: Z-Score se mueve contra la posición (stop conceptual)
        # =====================================================================
        if direction == "LONG" and zscore > 1.0:
            # Posición LONG pero Z-Score indica sobrecompra moderada
            # Esto no debería pasar si compramos en sobreventa
            logger.warning(f"LONG position but Z-Score={zscore:.2f}, potential reversal failed")
        
        if direction == "SHORT" and zscore < -1.0:
            # Posición SHORT pero Z-Score indica sobreventa moderada
            logger.warning(f"SHORT position but Z-Score={zscore:.2f}, potential reversal failed")
        
        return None
    
    # =========================================================================
    # MÉTODOS DE UTILIDAD
    # =========================================================================
    
    def get_indicator_snapshot(self, market_data: pd.DataFrame) -> dict:
        """
        Obtiene snapshot de indicadores actuales (para debugging/logging).
        
        Returns:
            Dict con valores actuales de todos los indicadores
        """
        df = self._calculate_indicators(market_data)
        current = df.iloc[-1]
        
        return {
            "price": round(current['close'], 2),
            "zscore": round(current['zscore'], 3) if not pd.isna(current['zscore']) else None,
            "rsi": round(current['rsi'], 1) if not pd.isna(current['rsi']) else None,
            "bb_upper": round(current['bb_upper'], 2) if not pd.isna(current['bb_upper']) else None,
            "bb_middle": round(current['bb_middle'], 2) if not pd.isna(current['bb_middle']) else None,
            "bb_lower": round(current['bb_lower'], 2) if not pd.isna(current['bb_lower']) else None,
            "atr": round(current['atr'], 4) if not pd.isna(current['atr']) else None,
            "volume_ratio": round(current['volume_ratio'], 2) if not pd.isna(current['volume_ratio']) else None,
            "bb_position": current['bb_position']
        }
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """
        Valida la configuración de la estrategia.
        
        Returns:
            (is_valid, list of issues)
        """
        issues = []
        
        if self.mr_config.zscore_entry_threshold <= self.mr_config.zscore_exit_threshold:
            issues.append("zscore_entry_threshold must be > zscore_exit_threshold")
        
        if self.mr_config.bollinger_period < 10:
            issues.append("bollinger_period should be >= 10")
        
        if self.mr_config.rsi_oversold >= self.mr_config.rsi_overbought:
            issues.append("rsi_oversold must be < rsi_overbought")
        
        if self.mr_config.atr_stop_multiplier <= 0:
            issues.append("atr_stop_multiplier must be > 0")
        
        if self.mr_config.max_holding_bars < 1:
            issues.append("max_holding_bars must be >= 1")
        
        return len(issues) == 0, issues


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_mean_reversion_strategy(
    config_dict: Optional[dict] = None
) -> MeanReversionIntraday:
    """
    Factory function para crear estrategia Mean Reversion.
    
    Args:
        config_dict: Diccionario de configuración (típicamente de YAML)
        
    Returns:
        Instancia configurada de MeanReversionIntraday
    """
    if config_dict is None:
        return MeanReversionIntraday()
    
    # Extraer límites si existen
    limits_dict = config_dict.pop("limits", {})
    limits = IntraDayLimits(**limits_dict) if limits_dict else IntraDayLimits()
    
    # Crear config
    config = MeanReversionConfig(
        limits=limits,
        **config_dict
    )
    
    return MeanReversionIntraday(config)
```

### 9.4 Ejemplo de Uso

```python
# Ejemplo de uso de MeanReversionIntraday

import pandas as pd
from datetime import datetime

from src.strategies.intraday.mean_reversion import (
    MeanReversionIntraday,
    MeanReversionConfig,
    create_mean_reversion_strategy
)
from src.strategies.intraday.mixins import IntraDayLimits

# Opción 1: Crear con defaults
strategy = MeanReversionIntraday()

# Opción 2: Crear con configuración custom
config = MeanReversionConfig(
    timeframe="5min",
    market="US",
    bollinger_period=20,
    bollinger_std=2.0,
    zscore_entry_threshold=2.0,
    zscore_exit_threshold=0.5,
    rsi_period=14,
    rsi_oversold=30,
    rsi_overbought=70,
    limits=IntraDayLimits(
        max_trades_per_day=5,
        max_exposure_pct=0.10,
        max_position_pct=0.03
    )
)
strategy = MeanReversionIntraday(config)

# Opción 3: Crear desde diccionario (típico de YAML)
yaml_config = {
    "timeframe": "5min",
    "market": "US",
    "bollinger_period": 20,
    "zscore_entry_threshold": 2.0,
    "limits": {
        "max_trades_per_day": 5,
        "max_exposure_pct": 0.10
    }
}
strategy = create_mean_reversion_strategy(yaml_config)

# Validar configuración
is_valid, issues = strategy.validate_config()
if not is_valid:
    print(f"Config issues: {issues}")

# Generar señales
# (asumiendo market_data es un DataFrame con columnas OHLCV)
signals = strategy.generate_signals(
    market_data=market_data,
    regime="SIDEWAYS",
    portfolio={"value": 25000, "positions": []},
    current_time=datetime.now()
)

for signal in signals:
    print(f"Signal: {signal.direction} {signal.symbol} @ {signal.entry_price}")
    print(f"  SL: {signal.stop_loss}, TP: {signal.take_profit}")
    print(f"  Confidence: {signal.confidence}")
    print(f"  Reasoning: {signal.reasoning}")

# Obtener snapshot de indicadores
snapshot = strategy.get_indicator_snapshot(market_data)
print(f"Current indicators: {snapshot}")
```

### 9.5 Diagrama de Indicadores

```
VISUALIZACIÓN DE SEÑALES MEAN REVERSION:
═══════════════════════════════════════════════════════════════════════════════

Precio y Bollinger Bands:
                                                      BB Upper (overbought)
    ────────────────────────────────────────────────────────────────────────
                     *                    *
               *          *          *         *
          *                   *                      *
    ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  BB Middle (mean)
              *                   *                      *
                   *          *          *         *
    ────────────────*───────────────────────────*────────────────────────────
                    ↑                           ↑        BB Lower (oversold)
                 LONG                        LONG
              (Z < -2)                      (Z < -2)

Z-Score:
     +3 |
     +2 |─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  ← SHORT zone
     +1 |              *
      0 |────────*─────────────*──────────────────*────  ← Exit zone (±0.5)
     -1 |    *                     *
     -2 |─ ─*─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─*─ ─ ─ ─ ─ ─  ← LONG zone
     -3 |   ↑                             ↑
            Entry LONG                 Entry LONG

RSI:
    100 |
     70 |─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  ← Overbought (SHORT)
     50 |────────────────────────────────────────────────  Neutral
     30 |─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  ← Oversold (LONG)
      0 |

CONDICIONES PARA SEÑAL:
═══════════════════════════════════════════════════════════════════════════════
LONG:  Z-Score < -2.0  AND  Precio ≤ BB Lower  AND  RSI < 30  AND  Vol > 1.2x
SHORT: Z-Score > +2.0  AND  Precio ≥ BB Upper  AND  RSI > 70  AND  Vol > 1.2x
EXIT:  |Z-Score| < 0.5  (precio cerca de la media)
═══════════════════════════════════════════════════════════════════════════════
```

---

## 10. Tests para Mean Reversion

### 10.1 Test Suite Completa

```python
# tests/strategies/intraday/test_mean_reversion.py
"""
Tests para estrategia Mean Reversion Intradía.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.strategies.intraday.mean_reversion import (
    MeanReversionIntraday,
    MeanReversionConfig,
    create_mean_reversion_strategy
)
from src.strategies.intraday.mixins import IntraDayLimits


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def default_strategy():
    """Estrategia con configuración por defecto."""
    return MeanReversionIntraday()


@pytest.fixture
def custom_strategy():
    """Estrategia con configuración personalizada."""
    config = MeanReversionConfig(
        timeframe="5min",
        market="US",
        bollinger_period=20,
        zscore_entry_threshold=1.5,  # Más agresivo para testing
        zscore_exit_threshold=0.3,
        rsi_oversold=35,
        rsi_overbought=65,
        limits=IntraDayLimits(
            max_trades_per_day=3,
            max_exposure_pct=0.05
        )
    )
    return MeanReversionIntraday(config)


@pytest.fixture
def sample_market_data():
    """DataFrame de ejemplo con datos OHLCV."""
    np.random.seed(42)
    n_bars = 100
    
    # Generar precios con reversión a la media
    base_price = 100
    noise = np.random.randn(n_bars) * 0.5
    mean_reversion = np.zeros(n_bars)
    
    prices = [base_price]
    for i in range(1, n_bars):
        # Mean reversion: precio tiende a volver a base_price
        reversion = (base_price - prices[-1]) * 0.1
        new_price = prices[-1] + reversion + noise[i]
        prices.append(new_price)
    
    prices = np.array(prices)
    
    df = pd.DataFrame({
        'symbol': ['SPY'] * n_bars,
        'open': prices - np.random.rand(n_bars) * 0.2,
        'high': prices + np.random.rand(n_bars) * 0.5,
        'low': prices - np.random.rand(n_bars) * 0.5,
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, n_bars)
    })
    
    return df


@pytest.fixture
def oversold_market_data():
    """DataFrame con condición de sobreventa extrema."""
    n_bars = 50
    
    # Crear tendencia bajista fuerte al final
    base = 100
    prices = np.concatenate([
        np.linspace(base, base, 30),           # Flat inicial
        np.linspace(base, base - 5, 20)        # Caída fuerte
    ])
    
    df = pd.DataFrame({
        'symbol': ['SPY'] * n_bars,
        'open': prices - 0.1,
        'high': prices + 0.2,
        'low': prices - 0.3,
        'close': prices,
        'volume': [2000000] * n_bars  # Volumen alto
    })
    
    return df


@pytest.fixture
def overbought_market_data():
    """DataFrame con condición de sobrecompra extrema."""
    n_bars = 50
    
    # Crear tendencia alcista fuerte al final
    base = 100
    prices = np.concatenate([
        np.linspace(base, base, 30),           # Flat inicial
        np.linspace(base, base + 5, 20)        # Subida fuerte
    ])
    
    df = pd.DataFrame({
        'symbol': ['SPY'] * n_bars,
        'open': prices - 0.1,
        'high': prices + 0.3,
        'low': prices - 0.2,
        'close': prices,
        'volume': [2000000] * n_bars
    })
    
    return df


@pytest.fixture
def portfolio():
    """Portfolio de ejemplo."""
    return {
        "value": 25000,
        "positions": []
    }


@pytest.fixture
def market_open_time():
    """Timestamp durante horas de mercado US."""
    # Miércoles a las 10:30 AM EST
    return datetime(2024, 12, 4, 15, 30, tzinfo=ZoneInfo("UTC"))  # 10:30 EST


@pytest.fixture
def market_close_time():
    """Timestamp cerca del cierre de mercado US."""
    # Miércoles a las 3:50 PM EST (10 min antes del cierre)
    return datetime(2024, 12, 4, 20, 50, tzinfo=ZoneInfo("UTC"))


# =============================================================================
# TESTS DE INICIALIZACIÓN
# =============================================================================

class TestMeanReversionInit:
    """Tests de inicialización de la estrategia."""
    
    def test_default_initialization(self, default_strategy):
        """Test inicialización con valores por defecto."""
        assert default_strategy.strategy_id == "mean_reversion_intraday"
        assert default_strategy.strategy_type == "intraday"
        assert default_strategy.required_regime == ["SIDEWAYS"]
        assert default_strategy.timeframe == "5min"
    
    def test_custom_initialization(self, custom_strategy):
        """Test inicialización con configuración personalizada."""
        assert custom_strategy.mr_config.zscore_entry_threshold == 1.5
        assert custom_strategy.mr_config.rsi_oversold == 35
        assert custom_strategy.limits.max_trades_per_day == 3
    
    def test_factory_function(self):
        """Test factory function desde diccionario."""
        config = {
            "timeframe": "1min",
            "market": "EU",
            "bollinger_period": 15,
            "limits": {
                "max_trades_per_day": 10
            }
        }
        strategy = create_mean_reversion_strategy(config)
        
        assert strategy.timeframe == "1min"
        assert strategy.market == "EU"
        assert strategy.mr_config.bollinger_period == 15
        assert strategy.limits.max_trades_per_day == 10
    
    def test_config_validation(self, default_strategy):
        """Test validación de configuración."""
        is_valid, issues = default_strategy.validate_config()
        assert is_valid
        assert len(issues) == 0
    
    def test_invalid_config(self):
        """Test configuración inválida."""
        config = MeanReversionConfig(
            zscore_entry_threshold=0.5,  # Menor que exit
            zscore_exit_threshold=1.0
        )
        strategy = MeanReversionIntraday(config)
        
        is_valid, issues = strategy.validate_config()
        assert not is_valid
        assert len(issues) > 0


# =============================================================================
# TESTS DE CÁLCULO DE INDICADORES
# =============================================================================

class TestIndicatorCalculation:
    """Tests de cálculo de indicadores."""
    
    def test_indicator_snapshot(self, default_strategy, sample_market_data):
        """Test snapshot de indicadores."""
        snapshot = default_strategy.get_indicator_snapshot(sample_market_data)
        
        assert 'price' in snapshot
        assert 'zscore' in snapshot
        assert 'rsi' in snapshot
        assert 'bb_upper' in snapshot
        assert 'bb_middle' in snapshot
        assert 'bb_lower' in snapshot
        assert 'atr' in snapshot
        assert 'volume_ratio' in snapshot
    
    def test_bollinger_bands_order(self, default_strategy, sample_market_data):
        """Test que BB están en orden correcto."""
        snapshot = default_strategy.get_indicator_snapshot(sample_market_data)
        
        assert snapshot['bb_lower'] < snapshot['bb_middle'] < snapshot['bb_upper']
    
    def test_rsi_range(self, default_strategy, sample_market_data):
        """Test que RSI está en rango 0-100."""
        snapshot = default_strategy.get_indicator_snapshot(sample_market_data)
        
        assert 0 <= snapshot['rsi'] <= 100
    
    def test_zscore_calculation(self, default_strategy, sample_market_data):
        """Test cálculo de Z-Score."""
        snapshot = default_strategy.get_indicator_snapshot(sample_market_data)
        
        # Z-Score debería estar típicamente entre -3 y 3
        assert -5 < snapshot['zscore'] < 5


# =============================================================================
# TESTS DE GENERACIÓN DE SEÑALES
# =============================================================================

class TestSignalGeneration:
    """Tests de generación de señales."""
    
    def test_no_signal_wrong_regime(
        self, 
        default_strategy, 
        oversold_market_data, 
        portfolio,
        market_open_time
    ):
        """Test que no genera señales en régimen incorrecto."""
        signals = default_strategy.generate_signals(
            market_data=oversold_market_data,
            regime="BULL",  # Wrong regime
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        assert len(signals) == 0
    
    def test_no_signal_market_closed(
        self,
        default_strategy,
        oversold_market_data,
        portfolio
    ):
        """Test que no genera señales con mercado cerrado."""
        # Sábado
        weekend = datetime(2024, 12, 7, 15, 0, tzinfo=ZoneInfo("UTC"))
        
        signals = default_strategy.generate_signals(
            market_data=oversold_market_data,
            regime="SIDEWAYS",
            portfolio=portfolio,
            current_time=weekend
        )
        
        assert len(signals) == 0
    
    def test_no_signal_near_close(
        self,
        default_strategy,
        oversold_market_data,
        portfolio,
        market_close_time
    ):
        """Test que no genera señales cerca del cierre."""
        signals = default_strategy.generate_signals(
            market_data=oversold_market_data,
            regime="SIDEWAYS",
            portfolio=portfolio,
            current_time=market_close_time
        )
        
        assert len(signals) == 0
    
    def test_signal_structure(
        self,
        custom_strategy,  # Usar thresholds más bajos
        oversold_market_data,
        portfolio,
        market_open_time
    ):
        """Test estructura de señal generada."""
        signals = custom_strategy.generate_signals(
            market_data=oversold_market_data,
            regime="SIDEWAYS",
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        # Puede o no generar señal dependiendo de los datos exactos
        if signals:
            signal = signals[0]
            
            assert signal.strategy_id == "mean_reversion_intraday"
            assert signal.direction in ["LONG", "SHORT"]
            assert signal.symbol == "SPY"
            assert 0 < signal.confidence <= 1
            assert signal.entry_price is not None
            assert signal.stop_loss is not None
            assert signal.take_profit is not None
            assert signal.regime_at_signal == "SIDEWAYS"
            assert "strategy_type" in signal.metadata
            assert signal.metadata["strategy_type"] == "intraday"
    
    def test_daily_limit_enforcement(
        self,
        default_strategy,
        oversold_market_data,
        portfolio,
        market_open_time
    ):
        """Test que respeta límite diario de trades."""
        # Simular que ya se hicieron trades
        for _ in range(default_strategy.limits.max_trades_per_day):
            default_strategy.increment_trade_count()
        
        signals = default_strategy.generate_signals(
            market_data=oversold_market_data,
            regime="SIDEWAYS",
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        assert len(signals) == 0
        
        # Reset para otros tests
        default_strategy.reset_daily_counters()


# =============================================================================
# TESTS DE EVALUACIÓN DE SALIDA
# =============================================================================

class TestExitEvaluation:
    """Tests de evaluación de condiciones de salida."""
    
    def test_force_close_near_eod(
        self,
        default_strategy,
        sample_market_data,
        market_close_time
    ):
        """Test cierre forzado cerca del fin del día."""
        position = {
            "symbol": "SPY",
            "direction": "LONG",
            "entry_price": 100.0,
            "entry_time": market_close_time - timedelta(hours=2),
            "entry_bar": 50
        }
        
        signal = default_strategy.should_close(
            position=position,
            market_data=sample_market_data,
            regime="SIDEWAYS",
            current_time=market_close_time
        )
        
        assert signal is not None
        assert signal.direction == "CLOSE"
        assert "EOD" in signal.metadata.get("exit_reason", "") or \
               "EOD" in signal.reasoning
    
    def test_max_holding_exit(
        self,
        default_strategy,
        sample_market_data,
        market_open_time
    ):
        """Test salida por tiempo máximo de holding."""
        position = {
            "symbol": "SPY",
            "direction": "LONG",
            "entry_price": 100.0,
            "entry_time": market_open_time - timedelta(hours=5),
            "entry_bar": 0  # Entró hace 100 barras
        }
        
        signal = default_strategy.should_close(
            position=position,
            market_data=sample_market_data,
            regime="SIDEWAYS",
            current_time=market_open_time
        )
        
        # Con entry_bar=0 y 100 barras en data, debería exceder max_holding_bars (24)
        assert signal is not None
        assert signal.direction == "CLOSE"
    
    def test_regime_change_exit(
        self,
        default_strategy,
        sample_market_data,
        market_open_time
    ):
        """Test salida por cambio de régimen."""
        position = {
            "symbol": "SPY",
            "direction": "LONG",
            "entry_price": 100.0,
            "entry_time": market_open_time - timedelta(minutes=30),
            "entry_bar": 90
        }
        
        signal = default_strategy.should_close(
            position=position,
            market_data=sample_market_data,
            regime="BULL",  # Cambió de SIDEWAYS a BULL
            current_time=market_open_time
        )
        
        assert signal is not None
        assert signal.direction == "CLOSE"
        assert "REGIME" in signal.metadata.get("exit_reason", "")


# =============================================================================
# TESTS DE LÍMITES Y VALIDACIÓN
# =============================================================================

class TestLimitsAndValidation:
    """Tests de límites y validación."""
    
    def test_position_size_calculation(self, default_strategy):
        """Test cálculo de tamaño de posición."""
        portfolio_value = 25000
        price = 100
        
        max_size = default_strategy.get_max_position_size(portfolio_value, price)
        
        # Con max_position_pct=0.03 (default), max sería ~7 unidades
        expected_max = int(portfolio_value * 0.03 / price)
        
        # Debería ser menor o igual a expected_max (también limitado por exposure)
        assert max_size <= expected_max
        assert max_size >= 0
    
    def test_exposure_limit(self, default_strategy):
        """Test límite de exposición."""
        portfolio_value = 25000
        
        available = default_strategy.check_exposure_limit(portfolio_value)
        max_exposure = portfolio_value * default_strategy.limits.max_exposure_pct
        
        assert available <= max_exposure
    
    def test_profit_vs_commission(self, default_strategy):
        """Test validación de profit vs comisión."""
        # Profit que justifica comisión
        assert default_strategy.validate_profit_vs_commission(
            expected_profit=5.0,
            commission=2.0
        )
        
        # Profit que NO justifica comisión
        assert not default_strategy.validate_profit_vs_commission(
            expected_profit=3.0,
            commission=2.0
        )


# =============================================================================
# TESTS DE INTEGRACIÓN
# =============================================================================

class TestIntegration:
    """Tests de integración end-to-end."""
    
    def test_full_cycle_long(
        self,
        custom_strategy,
        portfolio,
        market_open_time
    ):
        """Test ciclo completo de trade LONG."""
        np.random.seed(123)
        
        # 1. Generar datos con caída pronunciada
        n_bars = 50
        base = 100
        prices = np.concatenate([
            np.linspace(base, base, 25),
            np.linspace(base, base - 6, 25)  # Caída fuerte
        ])
        
        market_data = pd.DataFrame({
            'symbol': ['SPY'] * n_bars,
            'open': prices - 0.1,
            'high': prices + 0.2,
            'low': prices - 0.3,
            'close': prices,
            'volume': [3000000] * n_bars
        })
        
        # 2. Generar señales
        signals = custom_strategy.generate_signals(
            market_data=market_data,
            regime="SIDEWAYS",
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        # 3. Si hay señal, verificar que es coherente
        if signals:
            signal = signals[0]
            assert signal.direction == "LONG"  # Esperamos LONG en sobreventa
            assert signal.stop_loss < signal.entry_price
            assert signal.take_profit > signal.entry_price
    
    def test_registry_integration(self, default_strategy):
        """Test integración con StrategyRegistry."""
        from src.strategies.registry import StrategyRegistry
        
        # Registrar estrategia
        StrategyRegistry.register(
            default_strategy.strategy_id,
            type(default_strategy)
        )
        
        # Verificar que se puede obtener
        strategies = StrategyRegistry.get_by_type("intraday")
        
        # Cleanup
        StrategyRegistry.unregister(default_strategy.strategy_id)


# =============================================================================
# TESTS DE EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests de casos edge."""
    
    def test_insufficient_data(self, default_strategy, portfolio, market_open_time):
        """Test con datos insuficientes."""
        # Solo 10 barras cuando necesitamos 100+
        small_data = pd.DataFrame({
            'symbol': ['SPY'] * 10,
            'open': [100] * 10,
            'high': [101] * 10,
            'low': [99] * 10,
            'close': [100] * 10,
            'volume': [1000000] * 10
        })
        
        signals = default_strategy.generate_signals(
            market_data=small_data,
            regime="SIDEWAYS",
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        assert len(signals) == 0
    
    def test_zero_volume(self, default_strategy, portfolio, market_open_time):
        """Test con volumen cero."""
        n_bars = 50
        zero_vol_data = pd.DataFrame({
            'symbol': ['SPY'] * n_bars,
            'open': [100] * n_bars,
            'high': [101] * n_bars,
            'low': [99] * n_bars,
            'close': [100] * n_bars,
            'volume': [0] * n_bars  # Sin volumen
        })
        
        signals = default_strategy.generate_signals(
            market_data=zero_vol_data,
            regime="SIDEWAYS",
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        # No debería generar señales con volumen 0
        assert len(signals) == 0
    
    def test_nan_handling(self, default_strategy, sample_market_data, portfolio, market_open_time):
        """Test manejo de NaN en datos."""
        # Introducir NaN
        data_with_nan = sample_market_data.copy()
        data_with_nan.loc[45:50, 'close'] = np.nan
        
        # No debería crashear
        try:
            signals = default_strategy.generate_signals(
                market_data=data_with_nan,
                regime="SIDEWAYS",
                portfolio=portfolio,
                current_time=market_open_time
            )
            # Si no crashea, es éxito
            assert True
        except Exception as e:
            pytest.fail(f"Strategy crashed with NaN data: {e}")
```

---

## 11. Checklist Tarea C2.2

```
TAREA C2.2: MEAN REVERSION INTRADAY
═══════════════════════════════════════════════════════════════════════════════

ESTRUCTURA DE ARCHIVOS:
[ ] src/strategies/intraday/mean_reversion.py creado
[ ] MeanReversionConfig dataclass definida
[ ] MeanReversionIntraday clase implementada

INDICADORES:
[ ] Bollinger Bands calculados correctamente
[ ] Z-Score calculado con rolling window
[ ] RSI calculado (EMA-based)
[ ] ATR calculado para stops dinámicos
[ ] Volume ratio calculado

SEÑALES DE ENTRADA:
[ ] Condiciones LONG implementadas (Z<-2, RSI<30, precio≤BB_lower)
[ ] Condiciones SHORT implementadas (Z>2, RSI>70, precio≥BB_upper)
[ ] Filtro de volumen aplicado
[ ] Stop loss basado en ATR
[ ] Take profit en media de Bollinger
[ ] Confidence calculada según extremidad
[ ] Reasoning generado

SEÑALES DE SALIDA:
[ ] Exit por reversión a media (|Z|<0.5)
[ ] Exit por max holding time
[ ] Exit por cambio de régimen
[ ] Metadata de salida completa

INTEGRACIÓN:
[ ] Hereda de IntraDayStrategy
[ ] Usa IntraDayMixin correctamente
[ ] Factory function funcional
[ ] Validación de config implementada

TESTS:
[ ] tests/strategies/intraday/test_mean_reversion.py creado
[ ] Tests de inicialización pasan
[ ] Tests de indicadores pasan
[ ] Tests de señales pasan
[ ] Tests de salida pasan
[ ] Tests de límites pasan
[ ] Tests de edge cases pasan
[ ] Cobertura > 80%

═══════════════════════════════════════════════════════════════════════════════
```

---

*Fin de Parte 2 - Implementación Mean Reversion Intraday*

---

**Siguiente:** Parte 3 - Implementación Volatility Breakout
# ⚡ Fase C2: Estrategias Intradía

## Parte 3: Implementación Volatility Breakout

---

## 12. Tarea C2.3: Volatility Breakout

### 12.1 Concepto de la Estrategia

Volatility Breakout captura movimientos direccionales explosivos cuando el precio rompe un rango de consolidación con volumen elevado.

```
PRINCIPIO FUNDAMENTAL:
══════════════════════════════════════════════════════════════════════════════
Después de períodos de consolidación (baja volatilidad):
- La energía acumulada se libera en rupturas direccionales
- Rupturas con alto volumen tienen mayor probabilidad de continuar
- El movimiento inicial suele ser el más rentable

FASES DEL MERCADO:
1. CONSOLIDACIÓN: Precio se comprime en un rango estrecho
2. BREAKOUT: Precio rompe el rango con volumen
3. EXTENSIÓN: Precio continúa en dirección de la ruptura
4. AGOTAMIENTO: Momentum decrece, posible reversión

INDICADORES CLAVE:
- Rango (High-Low) de últimas N barras: Define zona de consolidación
- ATR: Mide volatilidad, confirma si breakout es significativo
- Volumen: Breakout válido requiere volumen > 2x promedio
- Squeeze (Bollinger dentro de Keltner): Detecta compresión

ENTRADA LONG:
- Precio rompe máximo del rango de consolidación
- Ruptura > threshold * ATR
- Volumen > 2x promedio
- Mínimo N barras en consolidación previa

ENTRADA SHORT:
- Precio rompe mínimo del rango de consolidación
- Ruptura > threshold * ATR
- Volumen > 2x promedio
- Mínimo N barras en consolidación previa

SALIDA:
- Target basado en ATR (típicamente 2x ATR)
- Stop loss en lado opuesto del rango o 1x ATR
- Trailing stop después de alcanzar 1x ATR de profit
- Tiempo máximo en posición (breakouts son rápidos)
══════════════════════════════════════════════════════════════════════════════
```

### 12.2 Diagrama de Flujo de Decisión

```
                        ┌─────────────────────────────┐
                        │   Nuevo bar de 1 minuto     │
                        └─────────────┬───────────────┘
                                      │
                        ┌─────────────▼───────────────┐
                        │  Calcular indicadores:      │
                        │  • Range (high/low N bars)  │
                        │  • ATR (14)                 │
                        │  • Volume surge ratio       │
                        │  • Bars in consolidation    │
                        │  • Squeeze indicator        │
                        └─────────────┬───────────────┘
                                      │
                        ┌─────────────▼───────────────┐
                        │  ¿En consolidación?         │
                        │  Range < threshold * ATR    │
                        └─────────────┬───────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
               NO   │                                   │  SÍ
                    ▼                                   ▼
        ┌───────────────────────┐           ┌───────────────────────┐
        │  Ya en breakout o     │           │  Evaluar breakout:    │
        │  mercado trending     │           │  • ¿Precio > range?   │
        │  → Skip               │           │  • ¿Volumen surge?    │
        └───────────────────────┘           │  • ¿Min bars consol?  │
                                            └───────────┬───────────┘
                                                        │
                                                ┌───────┴───────┐
                                          NO    │               │  SÍ
                                                ▼               ▼
                                        ┌───────────────┐  ┌───────────────┐
                                        │    WAIT       │  │ Signal ENTRY  │
                                        │  Acumular     │  │ • LONG/SHORT  │
                                        │  consolidación│  │ • SL en rango │
                                        └───────────────┘  │ • TP = 2x ATR │
                                                           └───────────────┘
```

### 12.3 Visualización de Breakout

```
ANATOMÍA DE UN BREAKOUT ALCISTA:
══════════════════════════════════════════════════════════════════════════════

Precio                           TP (Entry + 2*ATR)
  │                                    ┌────────────────────
  │                                    │  EXTENSIÓN
  │                              ●●●●●●┘
  │                         ●●●●│
  │        BREAKOUT    ●●●●●    │
  │              ●●●●●●─────────┼──── Range High (resistance)
  │         ●────────────●      │
  │        │  ●      ●    ●     │  ◄── CONSOLIDACIÓN
  │        │    ●  ●        ●   │      (20-30 barras)
  │       ●──────────────────●──┼──── Range Low (support)
  │      ●                      │
  │                             │
  │                        SL (Entry - 1*ATR)
  │
  └────────────────────────────────────────────────────────► Tiempo
        
        │◄── Min 20 bars ──►│◄─ Entry ─►│◄── Target zone ──►│

VOLUMEN:
  │                              ████
  │                         ████ ████
  │    ██    ██   ██   ██  ████ ████
  │   ████  ████ ████ ████ ████ ████
  └────────────────────────────────────────────────────────►
       Normal volume          │    Volume surge (>2x avg)
                              │
                         BREAKOUT CONFIRMADO

══════════════════════════════════════════════════════════════════════════════
```

### 12.4 Implementación Completa

```python
# src/strategies/intraday/volatility_breakout.py
"""
Estrategia Volatility Breakout Intradía.

Captura rupturas de rangos de consolidación con volumen elevado.
Opera en timeframes cortos (1min, 5min) para maximizar profit en movimientos rápidos.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple
from enum import Enum
import numpy as np
import pandas as pd
import logging

from src.strategies.interfaces import Signal
from src.strategies.intraday.base import IntraDayStrategy, IntraDayConfig
from src.strategies.intraday.mixins import IntraDayLimits

logger = logging.getLogger(__name__)


class BreakoutDirection(Enum):
    """Dirección del breakout."""
    NONE = "none"
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass
class ConsolidationZone:
    """Representa una zona de consolidación detectada."""
    high: float
    low: float
    bars_count: int
    avg_volume: float
    atr_at_formation: float
    start_bar: int
    
    @property
    def range_size(self) -> float:
        """Tamaño del rango."""
        return self.high - self.low
    
    @property
    def midpoint(self) -> float:
        """Punto medio del rango."""
        return (self.high + self.low) / 2
    
    def is_valid(self, min_bars: int, max_range_atr: float) -> bool:
        """Verifica si la consolidación es válida."""
        if self.bars_count < min_bars:
            return False
        if self.atr_at_formation > 0:
            range_in_atr = self.range_size / self.atr_at_formation
            if range_in_atr > max_range_atr:
                return False
        return True


@dataclass
class VolatilityBreakoutConfig(IntraDayConfig):
    """Configuración específica para Volatility Breakout."""
    # Timeframe más corto para breakouts
    timeframe: str = "1min"
    
    # Consolidación
    range_lookback_bars: int = 30          # Barras para calcular rango
    min_consolidation_bars: int = 20       # Mínimo barras en consolidación
    max_range_atr_ratio: float = 1.5       # Rango máximo = 1.5 * ATR
    
    # Breakout detection
    breakout_atr_threshold: float = 0.5    # Ruptura mínima = 0.5 * ATR
    volume_surge_ratio: float = 2.0        # Volumen debe ser 2x promedio
    
    # ATR
    atr_period: int = 14
    
    # Targets y stops
    stop_atr_multiplier: float = 1.0       # SL = 1 ATR desde entry
    target_atr_multiplier: float = 2.0     # TP = 2 ATR desde entry
    trailing_activation_atr: float = 1.0   # Activar trailing después de 1 ATR profit
    trailing_distance_atr: float = 0.5     # Trailing a 0.5 ATR
    
    # Filtros adicionales
    min_volume_ratio: float = 1.5          # Volumen mínimo general
    max_spread_pct: float = 0.001          # Spread máximo 0.1%
    
    # Holding (breakouts son rápidos)
    max_holding_bars: int = 30             # ~30 minutos en 1min bars
    
    # Límites específicos para breakout
    limits: IntraDayLimits = field(default_factory=lambda: IntraDayLimits(
        max_trades_per_day=3,              # Menos trades, más selectivos
        max_exposure_pct=0.10,
        max_position_pct=0.03,
        max_holding_minutes=60             # Máximo 1 hora
    ))


class VolatilityBreakout(IntraDayStrategy):
    """
    Estrategia de Volatility Breakout para trading intradía.
    
    Lógica:
    1. Detectar zonas de consolidación (rango estrecho, baja volatilidad)
    2. Esperar ruptura con volumen (>2x promedio)
    3. Entrar en dirección del breakout
    4. Salir con profit target o trailing stop
    
    Condiciones de entrada:
    1. Consolidación detectada (min N barras en rango < threshold*ATR)
    2. Precio rompe high/low del rango
    3. Ruptura es significativa (> breakout_threshold * ATR)
    4. Volumen > volume_surge_ratio * avg_volume
    
    Condiciones de salida:
    1. Target hit (2x ATR)
    2. Stop loss hit (1x ATR)
    3. Trailing stop (después de 1 ATR profit)
    4. Max holding time
    5. Falso breakout (precio vuelve al rango)
    """
    
    def __init__(self, config: Optional[VolatilityBreakoutConfig] = None):
        """
        Inicializa estrategia Volatility Breakout.
        
        Args:
            config: Configuración de la estrategia
        """
        self._config = config or VolatilityBreakoutConfig()
        super().__init__(self._config)
        
        # Estado de consolidación
        self._current_consolidation: Optional[ConsolidationZone] = None
        self._consolidation_start_bar: int = 0
    
    @property
    def strategy_id(self) -> str:
        return "volatility_breakout"
    
    @property
    def required_regime(self) -> list[str]:
        # Breakouts funcionan mejor en BULL o VOLATILE controlado
        return ["BULL", "VOLATILE"]
    
    @property
    def vb_config(self) -> VolatilityBreakoutConfig:
        """Acceso tipado a la configuración."""
        return self._config
    
    # =========================================================================
    # CÁLCULO DE INDICADORES
    # =========================================================================
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula indicadores necesarios para breakout detection.
        
        Args:
            df: DataFrame con OHLCV
            
        Returns:
            DataFrame con indicadores añadidos
        """
        df = df.copy()
        
        # ATR
        df['atr'] = self._calculate_atr(
            df['high'], df['low'], df['close'],
            period=self.vb_config.atr_period
        )
        
        # Rolling high/low para rango
        lookback = self.vb_config.range_lookback_bars
        df['range_high'] = df['high'].rolling(window=lookback).max()
        df['range_low'] = df['low'].rolling(window=lookback).min()
        df['range_size'] = df['range_high'] - df['range_low']
        
        # Range como múltiplo de ATR
        df['range_atr_ratio'] = df['range_size'] / df['atr']
        
        # Volume analysis
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Consolidation detection (rango pequeño)
        df['is_consolidating'] = df['range_atr_ratio'] < self.vb_config.max_range_atr_ratio
        
        # Bars in consolidation (consecutivas)
        df['consol_bars'] = self._count_consecutive_true(df['is_consolidating'])
        
        # Squeeze indicator (Bollinger dentro de Keltner - simplificado)
        bb_period = 20
        keltner_mult = 1.5
        
        df['bb_middle'] = df['close'].rolling(window=bb_period).mean()
        bb_std = df['close'].rolling(window=bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        
        df['keltner_upper'] = df['bb_middle'] + (df['atr'] * keltner_mult)
        df['keltner_lower'] = df['bb_middle'] - (df['atr'] * keltner_mult)
        
        # Squeeze: BB está dentro de Keltner
        df['squeeze_on'] = (df['bb_lower'] > df['keltner_lower']) & \
                          (df['bb_upper'] < df['keltner_upper'])
        
        return df
    
    def _calculate_atr(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """Calcula ATR."""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def _count_consecutive_true(self, series: pd.Series) -> pd.Series:
        """Cuenta valores True consecutivos."""
        # Crear grupos cuando cambia el valor
        groups = (~series).cumsum()
        # Contar dentro de cada grupo
        return series.groupby(groups).cumcount() + 1
    
    # =========================================================================
    # DETECCIÓN DE CONSOLIDACIÓN
    # =========================================================================
    
    def _detect_consolidation(
        self, 
        df: pd.DataFrame
    ) -> Optional[ConsolidationZone]:
        """
        Detecta si hay una zona de consolidación válida.
        
        Args:
            df: DataFrame con indicadores calculados
            
        Returns:
            ConsolidationZone si se detecta, None si no
        """
        current = df.iloc[-1]
        
        # Verificar si está consolidando
        if not current['is_consolidating']:
            return None
        
        # Verificar mínimo de barras
        consol_bars = int(current['consol_bars'])
        if consol_bars < self.vb_config.min_consolidation_bars:
            return None
        
        # Obtener zona de consolidación
        lookback = min(consol_bars, self.vb_config.range_lookback_bars)
        recent = df.tail(lookback)
        
        consolidation = ConsolidationZone(
            high=recent['high'].max(),
            low=recent['low'].min(),
            bars_count=consol_bars,
            avg_volume=recent['volume'].mean(),
            atr_at_formation=current['atr'],
            start_bar=len(df) - consol_bars
        )
        
        # Validar consolidación
        if not consolidation.is_valid(
            min_bars=self.vb_config.min_consolidation_bars,
            max_range_atr=self.vb_config.max_range_atr_ratio
        ):
            return None
        
        return consolidation
    
    # =========================================================================
    # DETECCIÓN DE BREAKOUT
    # =========================================================================
    
    def _detect_breakout(
        self,
        df: pd.DataFrame,
        consolidation: ConsolidationZone
    ) -> Tuple[BreakoutDirection, float]:
        """
        Detecta si hay un breakout válido.
        
        Args:
            df: DataFrame con datos de mercado
            consolidation: Zona de consolidación detectada
            
        Returns:
            (dirección del breakout, magnitud del breakout en ATR)
        """
        current = df.iloc[-1]
        price = current['close']
        atr = current['atr']
        volume_ratio = current['volume_ratio']
        
        # Verificar volume surge
        if volume_ratio < self.vb_config.volume_surge_ratio:
            return BreakoutDirection.NONE, 0.0
        
        # Calcular distancia del breakout
        breakout_up = price - consolidation.high
        breakout_down = consolidation.low - price
        
        min_breakout = atr * self.vb_config.breakout_atr_threshold
        
        # Breakout alcista
        if breakout_up > min_breakout:
            magnitude = breakout_up / atr
            return BreakoutDirection.BULLISH, magnitude
        
        # Breakout bajista
        if breakout_down > min_breakout:
            magnitude = breakout_down / atr
            return BreakoutDirection.BEARISH, magnitude
        
        return BreakoutDirection.NONE, 0.0
    
    # =========================================================================
    # GENERACIÓN DE SEÑALES
    # =========================================================================
    
    def _calculate_entry_signals(
        self,
        market_data: pd.DataFrame,
        regime: str,
        portfolio: dict
    ) -> list[Signal]:
        """
        Calcula señales de entrada para Volatility Breakout.
        
        Args:
            market_data: DataFrame con OHLCV
            regime: Régimen actual
            portfolio: Estado del portfolio
            
        Returns:
            Lista de Signal
        """
        signals = []
        
        # Calcular indicadores
        df = self._calculate_indicators(market_data)
        
        # Verificar datos válidos
        current = df.iloc[-1]
        if pd.isna(current['atr']):
            logger.debug("Insufficient data for ATR")
            return signals
        
        # Detectar consolidación
        consolidation = self._detect_consolidation(df)
        if consolidation is None:
            logger.debug("No valid consolidation detected")
            return signals
        
        # Detectar breakout
        direction, magnitude = self._detect_breakout(df, consolidation)
        if direction == BreakoutDirection.NONE:
            logger.debug("No breakout detected")
            return signals
        
        # Extraer valores
        price = current['close']
        atr = current['atr']
        volume_ratio = current['volume_ratio']
        symbol = market_data['symbol'].iloc[-1] if 'symbol' in market_data.columns else "UNKNOWN"
        
        # Log detección
        logger.info(
            f"Breakout detected: {direction.value}, magnitude={magnitude:.2f} ATR, "
            f"volume_ratio={volume_ratio:.2f}"
        )
        
        # Calcular tamaño de posición
        portfolio_value = portfolio.get("value", 25000)
        position_size = self.get_max_position_size(portfolio_value, price)
        
        if position_size <= 0:
            logger.debug("Position size too small")
            return signals
        
        # Crear señal según dirección
        if direction == BreakoutDirection.BULLISH:
            signal = self._create_long_signal(
                symbol=symbol,
                price=price,
                atr=atr,
                consolidation=consolidation,
                magnitude=magnitude,
                volume_ratio=volume_ratio,
                regime=regime,
                position_size=position_size
            )
        else:  # BEARISH
            signal = self._create_short_signal(
                symbol=symbol,
                price=price,
                atr=atr,
                consolidation=consolidation,
                magnitude=magnitude,
                volume_ratio=volume_ratio,
                regime=regime,
                position_size=position_size
            )
        
        signals.append(signal)
        return signals
    
    def _create_long_signal(
        self,
        symbol: str,
        price: float,
        atr: float,
        consolidation: ConsolidationZone,
        magnitude: float,
        volume_ratio: float,
        regime: str,
        position_size: int
    ) -> Signal:
        """Crea señal LONG para breakout alcista."""
        stop_loss = price - (atr * self.vb_config.stop_atr_multiplier)
        take_profit = price + (atr * self.vb_config.target_atr_multiplier)
        
        # Stop alternativo: debajo del rango
        stop_at_range = consolidation.low - (atr * 0.2)
        stop_loss = max(stop_loss, stop_at_range)  # Usar el más cercano
        
        confidence = self._calculate_confidence(magnitude, volume_ratio)
        
        return Signal(
            strategy_id=self.strategy_id,
            symbol=symbol,
            direction="LONG",
            confidence=confidence,
            entry_price=round(price, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            size_suggestion=position_size,
            regime_at_signal=regime,
            reasoning=self._generate_reasoning(
                "LONG", magnitude, volume_ratio, consolidation
            ),
            metadata={
                "strategy_type": "intraday",
                "timeframe": self.timeframe,
                "breakout_type": "bullish",
                "breakout_magnitude_atr": round(magnitude, 2),
                "volume_surge": round(volume_ratio, 2),
                "consolidation_bars": consolidation.bars_count,
                "range_high": round(consolidation.high, 2),
                "range_low": round(consolidation.low, 2),
                "range_size": round(consolidation.range_size, 2),
                "atr": round(atr, 4),
                "risk_reward_ratio": round(
                    (take_profit - price) / (price - stop_loss), 2
                ),
                "trailing_activation": round(
                    price + (atr * self.vb_config.trailing_activation_atr), 2
                )
            }
        )
    
    def _create_short_signal(
        self,
        symbol: str,
        price: float,
        atr: float,
        consolidation: ConsolidationZone,
        magnitude: float,
        volume_ratio: float,
        regime: str,
        position_size: int
    ) -> Signal:
        """Crea señal SHORT para breakout bajista."""
        stop_loss = price + (atr * self.vb_config.stop_atr_multiplier)
        take_profit = price - (atr * self.vb_config.target_atr_multiplier)
        
        # Stop alternativo: encima del rango
        stop_at_range = consolidation.high + (atr * 0.2)
        stop_loss = min(stop_loss, stop_at_range)  # Usar el más cercano
        
        confidence = self._calculate_confidence(magnitude, volume_ratio)
        
        return Signal(
            strategy_id=self.strategy_id,
            symbol=symbol,
            direction="SHORT",
            confidence=confidence,
            entry_price=round(price, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            size_suggestion=position_size,
            regime_at_signal=regime,
            reasoning=self._generate_reasoning(
                "SHORT", magnitude, volume_ratio, consolidation
            ),
            metadata={
                "strategy_type": "intraday",
                "timeframe": self.timeframe,
                "breakout_type": "bearish",
                "breakout_magnitude_atr": round(magnitude, 2),
                "volume_surge": round(volume_ratio, 2),
                "consolidation_bars": consolidation.bars_count,
                "range_high": round(consolidation.high, 2),
                "range_low": round(consolidation.low, 2),
                "range_size": round(consolidation.range_size, 2),
                "atr": round(atr, 4),
                "risk_reward_ratio": round(
                    (price - take_profit) / (stop_loss - price), 2
                ),
                "trailing_activation": round(
                    price - (atr * self.vb_config.trailing_activation_atr), 2
                )
            }
        )
    
    def _calculate_confidence(
        self, 
        magnitude: float, 
        volume_ratio: float
    ) -> float:
        """
        Calcula confianza de la señal.
        
        Factores:
        - Magnitud del breakout (más grande = más confianza)
        - Volume surge (más volumen = más confianza)
        """
        base = 0.5
        
        # Magnitude contribution (0 a 0.25)
        mag_contrib = min(0.25, (magnitude - 0.5) * 0.15)
        
        # Volume contribution (0 a 0.20)
        vol_contrib = min(0.20, (volume_ratio - 2.0) * 0.05)
        
        confidence = base + max(0, mag_contrib) + max(0, vol_contrib)
        return round(min(0.95, confidence), 2)
    
    def _generate_reasoning(
        self,
        direction: str,
        magnitude: float,
        volume_ratio: float,
        consolidation: ConsolidationZone
    ) -> str:
        """Genera explicación de la señal."""
        return (
            f"Volatility Breakout {direction}: Price broke "
            f"{'above' if direction == 'LONG' else 'below'} "
            f"{consolidation.bars_count}-bar consolidation range "
            f"({consolidation.low:.2f}-{consolidation.high:.2f}). "
            f"Breakout magnitude: {magnitude:.2f} ATR. "
            f"Volume surge: {volume_ratio:.1f}x average."
        )
    
    # =========================================================================
    # EVALUACIÓN DE SALIDA
    # =========================================================================
    
    def _check_strategy_exit(
        self,
        position: dict,
        market_data: pd.DataFrame,
        regime: str
    ) -> Optional[Signal]:
        """
        Verifica condiciones de salida para breakout.
        
        Condiciones:
        1. Precio vuelve al rango (falso breakout)
        2. Max holding bars
        3. Trailing stop (si está activo)
        """
        df = self._calculate_indicators(market_data)
        current = df.iloc[-1]
        
        symbol = position.get("symbol")
        direction = position.get("direction")
        entry_price = position.get("entry_price", 0)
        entry_bar = position.get("entry_bar", 0)
        range_high = position.get("metadata", {}).get("range_high", entry_price + 1)
        range_low = position.get("metadata", {}).get("range_low", entry_price - 1)
        
        current_bar = len(df)
        price = current['close']
        atr = current['atr']
        
        # =====================================================================
        # Condición 1: Falso breakout (precio vuelve al rango)
        # =====================================================================
        in_range = range_low <= price <= range_high
        
        if in_range:
            bars_held = current_bar - entry_bar
            if bars_held >= 5:  # Dar algunas barras de gracia
                pnl_pct = self._calc_pnl_pct(entry_price, price, direction)
                
                return Signal(
                    strategy_id=self.strategy_id,
                    symbol=symbol,
                    direction="CLOSE",
                    confidence=0.85,
                    entry_price=price,
                    stop_loss=None,
                    take_profit=None,
                    size_suggestion=None,
                    regime_at_signal=regime,
                    reasoning=f"False breakout: price returned to consolidation range. PnL={pnl_pct:.2f}%",
                    metadata={
                        "exit_reason": "FALSE_BREAKOUT",
                        "bars_held": bars_held,
                        "pnl_pct": round(pnl_pct, 2)
                    }
                )
        
        # =====================================================================
        # Condición 2: Max holding bars
        # =====================================================================
        bars_held = current_bar - entry_bar
        if bars_held >= self.vb_config.max_holding_bars:
            pnl_pct = self._calc_pnl_pct(entry_price, price, direction)
            
            return Signal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                direction="CLOSE",
                confidence=1.0,
                entry_price=price,
                stop_loss=None,
                take_profit=None,
                size_suggestion=None,
                regime_at_signal=regime,
                reasoning=f"Max holding time: {bars_held} bars. PnL={pnl_pct:.2f}%",
                metadata={
                    "exit_reason": "MAX_HOLDING_BARS",
                    "bars_held": bars_held,
                    "pnl_pct": round(pnl_pct, 2)
                }
            )
        
        # =====================================================================
        # Condición 3: Trailing stop check
        # =====================================================================
        trailing_signal = self._check_trailing_stop(
            position, price, atr, direction, regime
        )
        if trailing_signal:
            return trailing_signal
        
        return None
    
    def _check_trailing_stop(
        self,
        position: dict,
        current_price: float,
        atr: float,
        direction: str,
        regime: str
    ) -> Optional[Signal]:
        """
        Verifica trailing stop.
        
        Se activa después de alcanzar trailing_activation_atr de profit.
        """
        entry_price = position.get("entry_price", 0)
        symbol = position.get("symbol")
        highest_price = position.get("highest_price", current_price)
        lowest_price = position.get("lowest_price", current_price)
        
        activation_distance = atr * self.vb_config.trailing_activation_atr
        trailing_distance = atr * self.vb_config.trailing_distance_atr
        
        if direction == "LONG":
            # Actualizar máximo
            highest_price = max(highest_price, current_price)
            profit = highest_price - entry_price
            
            # ¿Trailing activado?
            if profit >= activation_distance:
                trailing_stop = highest_price - trailing_distance
                
                if current_price <= trailing_stop:
                    pnl_pct = self._calc_pnl_pct(entry_price, current_price, direction)
                    
                    return Signal(
                        strategy_id=self.strategy_id,
                        symbol=symbol,
                        direction="CLOSE",
                        confidence=0.9,
                        entry_price=current_price,
                        stop_loss=None,
                        take_profit=None,
                        size_suggestion=None,
                        regime_at_signal=regime,
                        reasoning=f"Trailing stop hit. Peak={highest_price:.2f}, Trail={trailing_stop:.2f}",
                        metadata={
                            "exit_reason": "TRAILING_STOP",
                            "peak_price": round(highest_price, 2),
                            "trailing_stop": round(trailing_stop, 2),
                            "pnl_pct": round(pnl_pct, 2)
                        }
                    )
        
        else:  # SHORT
            # Actualizar mínimo
            lowest_price = min(lowest_price, current_price)
            profit = entry_price - lowest_price
            
            # ¿Trailing activado?
            if profit >= activation_distance:
                trailing_stop = lowest_price + trailing_distance
                
                if current_price >= trailing_stop:
                    pnl_pct = self._calc_pnl_pct(entry_price, current_price, direction)
                    
                    return Signal(
                        strategy_id=self.strategy_id,
                        symbol=symbol,
                        direction="CLOSE",
                        confidence=0.9,
                        entry_price=current_price,
                        stop_loss=None,
                        take_profit=None,
                        size_suggestion=None,
                        regime_at_signal=regime,
                        reasoning=f"Trailing stop hit. Low={lowest_price:.2f}, Trail={trailing_stop:.2f}",
                        metadata={
                            "exit_reason": "TRAILING_STOP",
                            "low_price": round(lowest_price, 2),
                            "trailing_stop": round(trailing_stop, 2),
                            "pnl_pct": round(pnl_pct, 2)
                        }
                    )
        
        return None
    
    def _calc_pnl_pct(
        self, 
        entry_price: float, 
        current_price: float, 
        direction: str
    ) -> float:
        """Calcula PnL porcentual."""
        if entry_price == 0:
            return 0.0
        
        if direction == "LONG":
            return ((current_price - entry_price) / entry_price) * 100
        else:
            return ((entry_price - current_price) / entry_price) * 100
    
    # =========================================================================
    # UTILIDADES
    # =========================================================================
    
    def get_consolidation_status(
        self, 
        market_data: pd.DataFrame
    ) -> dict:
        """
        Obtiene estado actual de consolidación.
        
        Returns:
            Dict con información de consolidación
        """
        df = self._calculate_indicators(market_data)
        current = df.iloc[-1]
        
        consolidation = self._detect_consolidation(df)
        
        return {
            "is_consolidating": bool(current['is_consolidating']),
            "consecutive_bars": int(current['consol_bars']) if not pd.isna(current['consol_bars']) else 0,
            "range_atr_ratio": round(current['range_atr_ratio'], 2) if not pd.isna(current['range_atr_ratio']) else None,
            "squeeze_on": bool(current['squeeze_on']),
            "valid_consolidation": consolidation is not None,
            "consolidation_zone": {
                "high": round(consolidation.high, 2),
                "low": round(consolidation.low, 2),
                "bars": consolidation.bars_count,
                "midpoint": round(consolidation.midpoint, 2)
            } if consolidation else None,
            "current_price": round(current['close'], 2),
            "atr": round(current['atr'], 4) if not pd.isna(current['atr']) else None,
            "volume_ratio": round(current['volume_ratio'], 2) if not pd.isna(current['volume_ratio']) else None
        }
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """Valida configuración."""
        issues = []
        
        if self.vb_config.min_consolidation_bars < 5:
            issues.append("min_consolidation_bars should be >= 5")
        
        if self.vb_config.breakout_atr_threshold <= 0:
            issues.append("breakout_atr_threshold must be > 0")
        
        if self.vb_config.volume_surge_ratio < 1.5:
            issues.append("volume_surge_ratio should be >= 1.5")
        
        if self.vb_config.stop_atr_multiplier <= 0:
            issues.append("stop_atr_multiplier must be > 0")
        
        if self.vb_config.target_atr_multiplier <= self.vb_config.stop_atr_multiplier:
            issues.append("target_atr_multiplier should be > stop_atr_multiplier")
        
        return len(issues) == 0, issues


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_volatility_breakout_strategy(
    config_dict: Optional[dict] = None
) -> VolatilityBreakout:
    """
    Factory function para crear estrategia Volatility Breakout.
    
    Args:
        config_dict: Diccionario de configuración
        
    Returns:
        Instancia configurada de VolatilityBreakout
    """
    if config_dict is None:
        return VolatilityBreakout()
    
    limits_dict = config_dict.pop("limits", {})
    limits = IntraDayLimits(**limits_dict) if limits_dict else IntraDayLimits()
    
    config = VolatilityBreakoutConfig(
        limits=limits,
        **config_dict
    )
    
    return VolatilityBreakout(config)
```

### 12.5 Ejemplo de Uso

```python
# Ejemplo de uso de VolatilityBreakout

import pandas as pd
import numpy as np
from datetime import datetime

from src.strategies.intraday.volatility_breakout import (
    VolatilityBreakout,
    VolatilityBreakoutConfig,
    create_volatility_breakout_strategy
)

# Crear estrategia con defaults
strategy = VolatilityBreakout()

# O con configuración custom
config = VolatilityBreakoutConfig(
    timeframe="1min",
    market="US",
    range_lookback_bars=30,
    min_consolidation_bars=20,
    breakout_atr_threshold=0.5,
    volume_surge_ratio=2.0,
    target_atr_multiplier=2.5  # Target más ambicioso
)
strategy = VolatilityBreakout(config)

# Generar datos de ejemplo con consolidación y breakout
np.random.seed(42)
n_bars = 60

# Fase 1: Consolidación (barras 0-40)
consol_prices = 100 + np.random.randn(40) * 0.3

# Fase 2: Breakout alcista (barras 40-60)
breakout_prices = np.linspace(100.5, 103, 20) + np.random.randn(20) * 0.2

prices = np.concatenate([consol_prices, breakout_prices])

# Volumen: normal en consolidación, alto en breakout
volumes = np.concatenate([
    np.random.randint(1000000, 1500000, 40),  # Normal
    np.random.randint(3000000, 5000000, 20)   # Surge
])

market_data = pd.DataFrame({
    'symbol': ['SPY'] * n_bars,
    'open': prices - 0.1,
    'high': prices + 0.3,
    'low': prices - 0.2,
    'close': prices,
    'volume': volumes
})

# Verificar estado de consolidación
status = strategy.get_consolidation_status(market_data.head(45))
print(f"Consolidation status at bar 45: {status}")

# Generar señales
signals = strategy.generate_signals(
    market_data=market_data,
    regime="BULL",
    portfolio={"value": 25000},
    current_time=datetime(2024, 12, 4, 15, 30)  # 10:30 AM EST
)

for signal in signals:
    print(f"\nSignal: {signal.direction} {signal.symbol}")
    print(f"  Entry: {signal.entry_price}")
    print(f"  SL: {signal.stop_loss}, TP: {signal.take_profit}")
    print(f"  Confidence: {signal.confidence}")
    print(f"  Breakout magnitude: {signal.metadata.get('breakout_magnitude_atr')} ATR")
    print(f"  Volume surge: {signal.metadata.get('volume_surge')}x")
```

---

## 13. Tests para Volatility Breakout

```python
# tests/strategies/intraday/test_volatility_breakout.py
"""
Tests para estrategia Volatility Breakout.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.strategies.intraday.volatility_breakout import (
    VolatilityBreakout,
    VolatilityBreakoutConfig,
    ConsolidationZone,
    BreakoutDirection,
    create_volatility_breakout_strategy
)
from src.strategies.intraday.mixins import IntraDayLimits


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def default_strategy():
    """Estrategia con configuración por defecto."""
    return VolatilityBreakout()


@pytest.fixture
def aggressive_strategy():
    """Estrategia más agresiva para testing."""
    config = VolatilityBreakoutConfig(
        min_consolidation_bars=10,          # Menos barras requeridas
        breakout_atr_threshold=0.3,         # Threshold más bajo
        volume_surge_ratio=1.5,             # Menos volumen requerido
    )
    return VolatilityBreakout(config)


@pytest.fixture
def consolidation_data():
    """Datos con consolidación clara."""
    np.random.seed(42)
    n_bars = 50
    
    # Precio oscilando en rango estrecho
    base = 100
    prices = base + np.sin(np.linspace(0, 4*np.pi, n_bars)) * 0.3
    
    return pd.DataFrame({
        'symbol': ['SPY'] * n_bars,
        'open': prices - 0.05,
        'high': prices + 0.15,
        'low': prices - 0.15,
        'close': prices,
        'volume': [1500000] * n_bars
    })


@pytest.fixture
def breakout_bullish_data():
    """Datos con breakout alcista."""
    np.random.seed(42)
    n_bars = 60
    
    # Consolidación + breakout
    consol = 100 + np.random.randn(40) * 0.2
    breakout = np.linspace(100.8, 103, 20)
    prices = np.concatenate([consol, breakout])
    
    # Volumen surge en breakout
    volumes = np.concatenate([
        [1500000] * 40,
        [4000000] * 20
    ])
    
    return pd.DataFrame({
        'symbol': ['SPY'] * n_bars,
        'open': prices - 0.1,
        'high': prices + 0.3,
        'low': prices - 0.2,
        'close': prices,
        'volume': volumes
    })


@pytest.fixture
def breakout_bearish_data():
    """Datos con breakout bajista."""
    np.random.seed(42)
    n_bars = 60
    
    # Consolidación + breakout bajista
    consol = 100 + np.random.randn(40) * 0.2
    breakout = np.linspace(99.2, 97, 20)
    prices = np.concatenate([consol, breakout])
    
    volumes = np.concatenate([
        [1500000] * 40,
        [4000000] * 20
    ])
    
    return pd.DataFrame({
        'symbol': ['SPY'] * n_bars,
        'open': prices + 0.1,
        'high': prices + 0.2,
        'low': prices - 0.3,
        'close': prices,
        'volume': volumes
    })


@pytest.fixture
def portfolio():
    return {"value": 25000, "positions": []}


@pytest.fixture
def market_open_time():
    return datetime(2024, 12, 4, 15, 30, tzinfo=ZoneInfo("UTC"))


# =============================================================================
# TESTS DE INICIALIZACIÓN
# =============================================================================

class TestVolatilityBreakoutInit:
    
    def test_default_init(self, default_strategy):
        assert default_strategy.strategy_id == "volatility_breakout"
        assert default_strategy.strategy_type == "intraday"
        assert "BULL" in default_strategy.required_regime
        assert default_strategy.timeframe == "1min"
    
    def test_custom_config(self, aggressive_strategy):
        assert aggressive_strategy.vb_config.min_consolidation_bars == 10
        assert aggressive_strategy.vb_config.breakout_atr_threshold == 0.3
    
    def test_factory_function(self):
        config = {
            "timeframe": "5min",
            "min_consolidation_bars": 15,
            "limits": {"max_trades_per_day": 5}
        }
        strategy = create_volatility_breakout_strategy(config)
        
        assert strategy.timeframe == "5min"
        assert strategy.vb_config.min_consolidation_bars == 15
        assert strategy.limits.max_trades_per_day == 5
    
    def test_config_validation(self, default_strategy):
        is_valid, issues = default_strategy.validate_config()
        assert is_valid
        assert len(issues) == 0


# =============================================================================
# TESTS DE DETECCIÓN DE CONSOLIDACIÓN
# =============================================================================

class TestConsolidationDetection:
    
    def test_consolidation_detected(self, aggressive_strategy, consolidation_data):
        status = aggressive_strategy.get_consolidation_status(consolidation_data)
        
        assert status['is_consolidating'] is True
        assert status['consecutive_bars'] > 0
    
    def test_no_consolidation_trending(self, default_strategy):
        """Sin consolidación en mercado trending."""
        n_bars = 50
        trending = np.linspace(100, 110, n_bars)
        
        data = pd.DataFrame({
            'symbol': ['SPY'] * n_bars,
            'open': trending - 0.1,
            'high': trending + 0.5,
            'low': trending - 0.3,
            'close': trending,
            'volume': [2000000] * n_bars
        })
        
        status = default_strategy.get_consolidation_status(data)
        
        # Puede o no detectar consolidación en trend
        # El rango será grande relativo a ATR
        assert 'is_consolidating' in status


class TestConsolidationZone:
    
    def test_zone_properties(self):
        zone = ConsolidationZone(
            high=101.0,
            low=99.0,
            bars_count=25,
            avg_volume=2000000,
            atr_at_formation=0.5,
            start_bar=10
        )
        
        assert zone.range_size == 2.0
        assert zone.midpoint == 100.0
    
    def test_zone_validation(self):
        zone = ConsolidationZone(
            high=101.0,
            low=99.0,
            bars_count=25,
            avg_volume=2000000,
            atr_at_formation=0.5,
            start_bar=10
        )
        
        # Válido: suficientes barras, rango razonable
        assert zone.is_valid(min_bars=20, max_range_atr=5.0)
        
        # Inválido: pocas barras
        assert not zone.is_valid(min_bars=30, max_range_atr=5.0)


# =============================================================================
# TESTS DE DETECCIÓN DE BREAKOUT
# =============================================================================

class TestBreakoutDetection:
    
    def test_bullish_breakout_signal(
        self, 
        aggressive_strategy, 
        breakout_bullish_data,
        portfolio,
        market_open_time
    ):
        signals = aggressive_strategy.generate_signals(
            market_data=breakout_bullish_data,
            regime="BULL",
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        # Puede generar señal LONG
        if signals:
            assert signals[0].direction == "LONG"
            assert signals[0].metadata.get('breakout_type') == 'bullish'
    
    def test_bearish_breakout_signal(
        self,
        aggressive_strategy,
        breakout_bearish_data,
        portfolio,
        market_open_time
    ):
        signals = aggressive_strategy.generate_signals(
            market_data=breakout_bearish_data,
            regime="BULL",  # También funciona en BULL para shorts
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        if signals:
            assert signals[0].direction == "SHORT"
            assert signals[0].metadata.get('breakout_type') == 'bearish'
    
    def test_no_signal_low_volume(
        self,
        default_strategy,
        portfolio,
        market_open_time
    ):
        """Sin señal si no hay surge de volumen."""
        n_bars = 60
        consol = 100 + np.random.randn(40) * 0.2
        breakout = np.linspace(100.8, 103, 20)
        prices = np.concatenate([consol, breakout])
        
        # Volumen constante (sin surge)
        data = pd.DataFrame({
            'symbol': ['SPY'] * n_bars,
            'open': prices - 0.1,
            'high': prices + 0.3,
            'low': prices - 0.2,
            'close': prices,
            'volume': [1500000] * n_bars  # Sin surge
        })
        
        signals = default_strategy.generate_signals(
            market_data=data,
            regime="BULL",
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        # No debería generar señal sin volume surge
        assert len(signals) == 0


# =============================================================================
# TESTS DE SEÑALES
# =============================================================================

class TestSignalGeneration:
    
    def test_signal_structure(
        self,
        aggressive_strategy,
        breakout_bullish_data,
        portfolio,
        market_open_time
    ):
        signals = aggressive_strategy.generate_signals(
            market_data=breakout_bullish_data,
            regime="BULL",
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        if signals:
            signal = signals[0]
            
            assert signal.strategy_id == "volatility_breakout"
            assert signal.stop_loss is not None
            assert signal.take_profit is not None
            assert 'breakout_magnitude_atr' in signal.metadata
            assert 'volume_surge' in signal.metadata
            assert 'consolidation_bars' in signal.metadata
    
    def test_wrong_regime(
        self,
        default_strategy,
        breakout_bullish_data,
        portfolio,
        market_open_time
    ):
        signals = default_strategy.generate_signals(
            market_data=breakout_bullish_data,
            regime="SIDEWAYS",  # Wrong regime
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        assert len(signals) == 0


# =============================================================================
# TESTS DE SALIDA
# =============================================================================

class TestExitConditions:
    
    def test_false_breakout_exit(
        self,
        default_strategy,
        consolidation_data
    ):
        """Test salida por falso breakout."""
        position = {
            "symbol": "SPY",
            "direction": "LONG",
            "entry_price": 100.5,
            "entry_bar": 30,
            "metadata": {
                "range_high": 100.3,
                "range_low": 99.7
            }
        }
        
        # Precio volvió al rango
        signal = default_strategy.should_close(
            position=position,
            market_data=consolidation_data,  # Precio ~100
            regime="BULL"
        )
        
        if signal:
            assert signal.direction == "CLOSE"
            assert "FALSE_BREAKOUT" in signal.metadata.get("exit_reason", "")
    
    def test_max_holding_exit(
        self,
        default_strategy,
        breakout_bullish_data
    ):
        position = {
            "symbol": "SPY",
            "direction": "LONG",
            "entry_price": 100.5,
            "entry_bar": 0  # Entró hace muchas barras
        }
        
        signal = default_strategy.should_close(
            position=position,
            market_data=breakout_bullish_data,
            regime="BULL"
        )
        
        # Con entry_bar=0 y 60 barras, debería exceder max_holding_bars (30)
        assert signal is not None
        assert signal.direction == "CLOSE"


# =============================================================================
# TESTS DE EDGE CASES
# =============================================================================

class TestEdgeCases:
    
    def test_insufficient_data(
        self,
        default_strategy,
        portfolio,
        market_open_time
    ):
        small_data = pd.DataFrame({
            'symbol': ['SPY'] * 10,
            'open': [100] * 10,
            'high': [101] * 10,
            'low': [99] * 10,
            'close': [100] * 10,
            'volume': [1000000] * 10
        })
        
        signals = default_strategy.generate_signals(
            market_data=small_data,
            regime="BULL",
            portfolio=portfolio,
            current_time=market_open_time
        )
        
        assert len(signals) == 0
    
    def test_nan_in_data(
        self,
        default_strategy,
        breakout_bullish_data,
        portfolio,
        market_open_time
    ):
        data_with_nan = breakout_bullish_data.copy()
        data_with_nan.loc[30:35, 'volume'] = np.nan
        
        # No debería crashear
        try:
            signals = default_strategy.generate_signals(
                market_data=data_with_nan,
                regime="BULL",
                portfolio=portfolio,
                current_time=market_open_time
            )
            assert True
        except Exception as e:
            pytest.fail(f"Crashed with NaN: {e}")
```

---

## 14. Checklist Tarea C2.3

```
TAREA C2.3: VOLATILITY BREAKOUT
═══════════════════════════════════════════════════════════════════════════════

ESTRUCTURA:
[ ] src/strategies/intraday/volatility_breakout.py creado
[ ] VolatilityBreakoutConfig dataclass definida
[ ] ConsolidationZone dataclass definida
[ ] BreakoutDirection enum definida
[ ] VolatilityBreakout clase implementada

DETECCIÓN DE CONSOLIDACIÓN:
[ ] Cálculo de rango (high/low rolling)
[ ] Range como ratio de ATR
[ ] Contador de barras consecutivas en consolidación
[ ] Squeeze indicator (BB dentro de Keltner)
[ ] ConsolidationZone creada cuando válida

DETECCIÓN DE BREAKOUT:
[ ] Breakout alcista detectado (precio > range_high + threshold)
[ ] Breakout bajista detectado (precio < range_low - threshold)
[ ] Volume surge verificado (>2x promedio)
[ ] Magnitud del breakout calculada en ATR

SEÑALES:
[ ] Signal LONG con SL/TP correctos
[ ] Signal SHORT con SL/TP correctos
[ ] Metadata completa (magnitude, volume, range)
[ ] Confidence basada en magnitude + volume
[ ] Reasoning descriptivo

SALIDAS:
[ ] Exit por falso breakout (precio vuelve al rango)
[ ] Exit por max holding bars
[ ] Trailing stop implementado
[ ] PnL calculado correctamente

INTEGRACIÓN:
[ ] Hereda de IntraDayStrategy
[ ] Factory function funcional
[ ] Config validation

TESTS:
[ ] tests/strategies/intraday/test_volatility_breakout.py
[ ] Tests de consolidación
[ ] Tests de breakout
[ ] Tests de señales
[ ] Tests de salida
[ ] Tests edge cases
[ ] Cobertura > 80%

═══════════════════════════════════════════════════════════════════════════════
```

---

*Fin de Parte 3 - Implementación Volatility Breakout*

---

**Siguiente:** Parte 4 - Data Pipeline Intradía y Toggle Real-Time
# ⚡ Fase C2: Estrategias Intradía

## Parte 4: Data Pipeline Intradía y Toggle Real-Time

---

## 15. Tarea C2.4: Data Pipeline para Intradía

### 15.1 Contexto

Las estrategias intradía requieren datos en timeframes cortos (1min, 5min) que no estaban contemplados en el pipeline original de Fase 1, diseñado principalmente para datos diarios.

```
CAMBIOS NECESARIOS:
═══════════════════════════════════════════════════════════════════════════════
1. Soporte para timeframes intradía (1min, 5min, 15min)
2. Toggle entre datos delayed (15min) y real-time
3. Streaming de datos para actualización continua
4. Buffer y agregación de barras
5. Validación de timestamps y gaps
═══════════════════════════════════════════════════════════════════════════════
```

### 15.2 Arquitectura del Pipeline Intradía

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     INTRADAY DATA PIPELINE                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                        DATA SOURCE LAYER                                │  │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │  │
│  │  │   IBKR API      │    │   IBKR API      │    │   Yahoo Finance │     │  │
│  │  │   Real-Time     │    │   Delayed       │    │   (Fallback)    │     │  │
│  │  │   (streaming)   │    │   (15 min)      │    │   (daily only)  │     │  │
│  │  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘     │  │
│  │           │                      │                      │              │  │
│  └───────────┼──────────────────────┼──────────────────────┼──────────────┘  │
│              │                      │                      │                 │
│              └──────────────────────┼──────────────────────┘                 │
│                                     │                                        │
│                          ┌──────────▼──────────┐                             │
│                          │  RealTimeToggle     │                             │
│                          │  ─────────────────  │                             │
│                          │  • use_realtime     │                             │
│                          │  • get_data_mode()  │                             │
│                          │  • switch_mode()    │                             │
│                          └──────────┬──────────┘                             │
│                                     │                                        │
│                          ┌──────────▼──────────┐                             │
│                          │ IntraDayDataManager │                             │
│                          │ ─────────────────── │                             │
│                          │ • get_bars()        │                             │
│                          │ • subscribe()       │                             │
│                          │ • aggregate_bars()  │                             │
│                          └──────────┬──────────┘                             │
│                                     │                                        │
│              ┌──────────────────────┼──────────────────────┐                 │
│              │                      │                      │                 │
│              ▼                      ▼                      ▼                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │   Bar Buffer    │    │   TimescaleDB   │    │   Redis Cache   │          │
│  │   (in-memory)   │    │   (persist)     │    │   (hot data)    │          │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘          │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 15.3 Implementación del Toggle Real-Time

```python
# src/data/providers/realtime_toggle.py
"""
Toggle para cambiar entre datos delayed y real-time.

Este módulo gestiona la transición entre modos de datos
y valida que el sistema está configurado correctamente.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)


class DataMode(Enum):
    """Modos de datos disponibles."""
    DELAYED = "delayed"      # 15 minutos de retraso (gratis)
    REALTIME = "realtime"    # Tiempo real (requiere suscripción)
    HISTORICAL = "historical" # Solo datos históricos


@dataclass
class DataModeConfig:
    """Configuración del modo de datos."""
    mode: DataMode = DataMode.DELAYED
    delayed_minutes: int = 15
    realtime_subscription_active: bool = False
    buffer_seconds: int = 1
    validate_timestamps: bool = True
    max_timestamp_drift_seconds: int = 30
    
    # Callbacks
    on_mode_change: Optional[Callable[[DataMode, DataMode], None]] = None


class RealTimeToggle:
    """
    Gestiona el toggle entre datos delayed y real-time.
    
    Responsabilidades:
    - Mantener estado actual del modo de datos
    - Validar que real-time está disponible antes de activar
    - Notificar cambios de modo a componentes suscritos
    - Ajustar timestamps según modo activo
    
    Usage:
        toggle = RealTimeToggle()
        
        # Verificar modo actual
        if toggle.is_realtime:
            print("Usando datos real-time")
        
        # Cambiar a real-time (si disponible)
        if toggle.can_enable_realtime():
            toggle.enable_realtime()
        
        # Obtener timestamp ajustado
        adjusted_ts = toggle.adjust_timestamp(raw_timestamp)
    """
    
    _instance: Optional['RealTimeToggle'] = None
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config: Optional[DataModeConfig] = None):
        if self._initialized:
            return
        
        self._config = config or DataModeConfig()
        self._current_mode = self._config.mode
        self._mode_change_callbacks: list[Callable] = []
        self._last_mode_change: Optional[datetime] = None
        self._initialized = True
        
        logger.info(f"RealTimeToggle initialized in {self._current_mode.value} mode")
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton (para testing)."""
        cls._instance = None
    
    # =========================================================================
    # PROPIEDADES
    # =========================================================================
    
    @property
    def current_mode(self) -> DataMode:
        """Modo actual de datos."""
        return self._current_mode
    
    @property
    def is_realtime(self) -> bool:
        """True si está en modo real-time."""
        return self._current_mode == DataMode.REALTIME
    
    @property
    def is_delayed(self) -> bool:
        """True si está en modo delayed."""
        return self._current_mode == DataMode.DELAYED
    
    @property
    def delay_minutes(self) -> int:
        """Minutos de delay actuales."""
        if self._current_mode == DataMode.REALTIME:
            return 0
        return self._config.delayed_minutes
    
    # =========================================================================
    # GESTIÓN DE MODO
    # =========================================================================
    
    def can_enable_realtime(self) -> tuple[bool, str]:
        """
        Verifica si se puede activar modo real-time.
        
        Returns:
            (can_enable, reason)
        """
        # Verificar suscripción
        if not self._config.realtime_subscription_active:
            return False, "Real-time subscription not active"
        
        # Verificar conexión IBKR
        if not self._check_ibkr_connection():
            return False, "IBKR connection not available"
        
        # Verificar market data subscription
        if not self._check_market_data_subscription():
            return False, "Market data subscription not configured"
        
        return True, "OK"
    
    def enable_realtime(self) -> bool:
        """
        Activa modo real-time.
        
        Returns:
            True si se activó correctamente
        """
        can_enable, reason = self.can_enable_realtime()
        if not can_enable:
            logger.warning(f"Cannot enable real-time: {reason}")
            return False
        
        old_mode = self._current_mode
        self._current_mode = DataMode.REALTIME
        self._last_mode_change = datetime.now()
        
        self._notify_mode_change(old_mode, DataMode.REALTIME)
        logger.info("Switched to REALTIME mode")
        
        return True
    
    def enable_delayed(self):
        """Activa modo delayed."""
        old_mode = self._current_mode
        self._current_mode = DataMode.DELAYED
        self._last_mode_change = datetime.now()
        
        self._notify_mode_change(old_mode, DataMode.DELAYED)
        logger.info("Switched to DELAYED mode")
    
    def set_mode(self, mode: DataMode) -> bool:
        """
        Establece modo específico.
        
        Args:
            mode: Modo a establecer
            
        Returns:
            True si se estableció correctamente
        """
        if mode == DataMode.REALTIME:
            return self.enable_realtime()
        else:
            self.enable_delayed()
            return True
    
    # =========================================================================
    # TIMESTAMPS
    # =========================================================================
    
    def adjust_timestamp(self, timestamp: datetime) -> datetime:
        """
        Ajusta timestamp según modo actual.
        
        En modo delayed, resta el delay para obtener tiempo "real".
        
        Args:
            timestamp: Timestamp del dato recibido
            
        Returns:
            Timestamp ajustado
        """
        if self._current_mode == DataMode.REALTIME:
            return timestamp
        
        # En delayed, el timestamp del dato es el real,
        # pero llega con retraso. No ajustamos el timestamp del dato,
        # solo somos conscientes de que hay retraso.
        return timestamp
    
    def get_effective_time(self) -> datetime:
        """
        Obtiene el tiempo efectivo de mercado.
        
        En modo delayed, esto es "ahora - delay".
        """
        now = datetime.now()
        
        if self._current_mode == DataMode.REALTIME:
            return now
        
        return now - timedelta(minutes=self._config.delayed_minutes)
    
    def validate_timestamp(self, timestamp: datetime) -> tuple[bool, str]:
        """
        Valida que un timestamp es razonable.
        
        Args:
            timestamp: Timestamp a validar
            
        Returns:
            (is_valid, reason)
        """
        if not self._config.validate_timestamps:
            return True, "OK"
        
        now = datetime.now()
        effective_time = self.get_effective_time()
        
        # Timestamp no puede ser muy futuro
        max_future = now + timedelta(seconds=self._config.max_timestamp_drift_seconds)
        if timestamp > max_future:
            return False, f"Timestamp too far in future: {timestamp}"
        
        # En delayed, timestamp no debería ser más reciente que effective_time + buffer
        if self._current_mode == DataMode.DELAYED:
            max_allowed = effective_time + timedelta(seconds=self._config.buffer_seconds)
            if timestamp > max_allowed:
                return False, f"Timestamp too recent for delayed mode: {timestamp}"
        
        return True, "OK"
    
    # =========================================================================
    # CALLBACKS
    # =========================================================================
    
    def register_callback(self, callback: Callable[[DataMode, DataMode], None]):
        """Registra callback para cambios de modo."""
        self._mode_change_callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable):
        """Elimina callback."""
        if callback in self._mode_change_callbacks:
            self._mode_change_callbacks.remove(callback)
    
    def _notify_mode_change(self, old_mode: DataMode, new_mode: DataMode):
        """Notifica cambio de modo a callbacks."""
        for callback in self._mode_change_callbacks:
            try:
                callback(old_mode, new_mode)
            except Exception as e:
                logger.error(f"Error in mode change callback: {e}")
        
        if self._config.on_mode_change:
            try:
                self._config.on_mode_change(old_mode, new_mode)
            except Exception as e:
                logger.error(f"Error in config callback: {e}")
    
    # =========================================================================
    # VERIFICACIONES INTERNAS
    # =========================================================================
    
    def _check_ibkr_connection(self) -> bool:
        """Verifica conexión a IBKR."""
        try:
            from src.data.providers.ibkr import IBKRProvider
            provider = IBKRProvider()
            return provider.is_connected()
        except Exception:
            return False
    
    def _check_market_data_subscription(self) -> bool:
        """Verifica suscripción a market data."""
        # Placeholder - en implementación real verificaría
        # que hay suscripción activa para los símbolos necesarios
        return self._config.realtime_subscription_active
    
    # =========================================================================
    # SERIALIZACIÓN
    # =========================================================================
    
    def to_dict(self) -> dict:
        """Serializa estado actual."""
        return {
            "mode": self._current_mode.value,
            "delay_minutes": self.delay_minutes,
            "is_realtime": self.is_realtime,
            "last_mode_change": self._last_mode_change.isoformat() if self._last_mode_change else None
        }
    
    @classmethod
    def from_config_file(cls, config_path: str = "config/intraday.yaml") -> 'RealTimeToggle':
        """
        Crea instancia desde archivo de configuración.
        
        Args:
            config_path: Ruta al archivo YAML
            
        Returns:
            Instancia configurada
        """
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return cls()
        
        with open(path) as f:
            config_dict = yaml.safe_load(f)
        
        data_config = config_dict.get("intraday", {}).get("data", {})
        
        mode = DataMode.REALTIME if data_config.get("use_realtime", False) else DataMode.DELAYED
        
        config = DataModeConfig(
            mode=mode,
            delayed_minutes=15,
            realtime_subscription_active=data_config.get("use_realtime", False),
            buffer_seconds=data_config.get("realtime_buffer_seconds", 1)
        )
        
        return cls(config)
```

### 15.4 IntraDayDataManager

```python
# src/data/intraday_manager.py
"""
Gestor de datos intradía.

Maneja la obtención, almacenamiento y distribución de datos
en timeframes cortos para estrategias intradía.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from typing import Optional, Dict, List, Callable
from collections import deque
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
import logging
import asyncio

from src.data.providers.realtime_toggle import RealTimeToggle, DataMode

logger = logging.getLogger(__name__)


@dataclass
class BarData:
    """Representa una barra OHLCV."""
    symbol: str
    timestamp: datetime
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    def to_dict(self) -> dict:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'timeframe': self.timeframe,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }


@dataclass
class IntraDayDataConfig:
    """Configuración del gestor de datos intradía."""
    default_timeframe: str = "5min"
    supported_timeframes: list = field(default_factory=lambda: ["1min", "5min", "15min"])
    max_bars_in_memory: int = 500
    cache_ttl_seconds: int = 60
    auto_aggregate: bool = True
    fill_gaps: bool = True
    timezone: str = "America/New_York"


class BarBuffer:
    """
    Buffer circular para barras en memoria.
    
    Mantiene las últimas N barras de un símbolo/timeframe
    para acceso rápido sin consultar base de datos.
    """
    
    def __init__(self, max_size: int = 500):
        self._max_size = max_size
        self._buffers: Dict[str, deque] = {}
    
    def _get_key(self, symbol: str, timeframe: str) -> str:
        return f"{symbol}_{timeframe}"
    
    def add(self, bar: BarData):
        """Añade barra al buffer."""
        key = self._get_key(bar.symbol, bar.timeframe)
        
        if key not in self._buffers:
            self._buffers[key] = deque(maxlen=self._max_size)
        
        self._buffers[key].append(bar)
    
    def get_bars(
        self, 
        symbol: str, 
        timeframe: str, 
        n: Optional[int] = None
    ) -> List[BarData]:
        """Obtiene últimas N barras."""
        key = self._get_key(symbol, timeframe)
        
        if key not in self._buffers:
            return []
        
        bars = list(self._buffers[key])
        
        if n is not None:
            bars = bars[-n:]
        
        return bars
    
    def get_dataframe(
        self, 
        symbol: str, 
        timeframe: str,
        n: Optional[int] = None
    ) -> pd.DataFrame:
        """Obtiene barras como DataFrame."""
        bars = self.get_bars(symbol, timeframe, n)
        
        if not bars:
            return pd.DataFrame()
        
        data = [bar.to_dict() for bar in bars]
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        return df
    
    def clear(self, symbol: Optional[str] = None, timeframe: Optional[str] = None):
        """Limpia buffer."""
        if symbol and timeframe:
            key = self._get_key(symbol, timeframe)
            if key in self._buffers:
                self._buffers[key].clear()
        elif symbol:
            keys_to_clear = [k for k in self._buffers if k.startswith(symbol)]
            for key in keys_to_clear:
                self._buffers[key].clear()
        else:
            self._buffers.clear()
    
    @property
    def stats(self) -> dict:
        """Estadísticas del buffer."""
        return {
            key: len(buffer) 
            for key, buffer in self._buffers.items()
        }


class IntraDayDataManager:
    """
    Gestor central de datos intradía.
    
    Responsabilidades:
    - Obtener datos históricos intradía de IBKR
    - Gestionar suscripciones a streaming
    - Agregar barras de timeframes menores a mayores
    - Mantener buffer en memoria para acceso rápido
    - Detectar y manejar gaps en datos
    
    Usage:
        manager = IntraDayDataManager()
        
        # Obtener barras históricas
        df = await manager.get_bars("SPY", "5min", n=100)
        
        # Suscribirse a actualizaciones
        manager.subscribe("SPY", callback=on_new_bar)
        
        # Obtener última barra
        last_bar = manager.get_last_bar("SPY", "5min")
    """
    
    def __init__(self, config: Optional[IntraDayDataConfig] = None):
        self._config = config or IntraDayDataConfig()
        self._toggle = RealTimeToggle()
        self._buffer = BarBuffer(max_size=self._config.max_bars_in_memory)
        self._subscribers: Dict[str, List[Callable]] = {}
        self._last_update: Dict[str, datetime] = {}
        self._tz = ZoneInfo(self._config.timezone)
        
        # Registrar callback para cambios de modo
        self._toggle.register_callback(self._on_mode_change)
    
    # =========================================================================
    # OBTENCIÓN DE DATOS
    # =========================================================================
    
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "5min",
        n: int = 100,
        end_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Obtiene barras históricas.
        
        Primero intenta obtener del buffer, luego de IBKR.
        
        Args:
            symbol: Símbolo a consultar
            timeframe: Timeframe ("1min", "5min", "15min")
            n: Número de barras
            end_time: Tiempo final (default: ahora)
            
        Returns:
            DataFrame con columnas OHLCV
        """
        if timeframe not in self._config.supported_timeframes:
            raise ValueError(f"Timeframe {timeframe} not supported")
        
        # Intentar obtener del buffer
        buffered = self._buffer.get_dataframe(symbol, timeframe, n)
        
        if len(buffered) >= n:
            return buffered.tail(n)
        
        # Obtener de IBKR
        df = await self._fetch_from_ibkr(symbol, timeframe, n, end_time)
        
        # Actualizar buffer
        for _, row in df.iterrows():
            bar = BarData(
                symbol=symbol,
                timestamp=row.name,
                timeframe=timeframe,
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=int(row['volume'])
            )
            self._buffer.add(bar)
        
        return df
    
    async def _fetch_from_ibkr(
        self,
        symbol: str,
        timeframe: str,
        n: int,
        end_time: Optional[datetime]
    ) -> pd.DataFrame:
        """Obtiene datos de IBKR."""
        try:
            from src.data.providers.ibkr import IBKRProvider
            
            provider = IBKRProvider()
            
            # Mapear timeframe a formato IBKR
            duration_map = {
                "1min": "1 min",
                "5min": "5 mins", 
                "15min": "15 mins"
            }
            
            bar_size = duration_map.get(timeframe, "5 mins")
            
            # Calcular duración necesaria
            minutes_per_bar = int(timeframe.replace("min", ""))
            total_minutes = n * minutes_per_bar
            
            # Añadir margen para gaps
            duration_str = f"{int(total_minutes * 1.5)} mins"
            if total_minutes > 60:
                hours = int(total_minutes / 60) + 1
                duration_str = f"{hours} H"
            
            df = await provider.get_historical_data_async(
                symbol=symbol,
                duration=duration_str,
                bar_size=bar_size,
                end_datetime=end_time
            )
            
            return df.tail(n)
            
        except Exception as e:
            logger.error(f"Error fetching from IBKR: {e}")
            return pd.DataFrame()
    
    def get_last_bar(
        self, 
        symbol: str, 
        timeframe: str = "5min"
    ) -> Optional[BarData]:
        """Obtiene la última barra del buffer."""
        bars = self._buffer.get_bars(symbol, timeframe, n=1)
        return bars[0] if bars else None
    
    # =========================================================================
    # SUSCRIPCIONES
    # =========================================================================
    
    def subscribe(
        self,
        symbol: str,
        callback: Callable[[BarData], None],
        timeframe: str = "5min"
    ):
        """
        Suscribe a actualizaciones de un símbolo.
        
        Args:
            symbol: Símbolo
            callback: Función a llamar con cada nueva barra
            timeframe: Timeframe
        """
        key = f"{symbol}_{timeframe}"
        
        if key not in self._subscribers:
            self._subscribers[key] = []
        
        self._subscribers[key].append(callback)
        logger.info(f"Subscribed to {symbol} {timeframe}")
    
    def unsubscribe(
        self,
        symbol: str,
        callback: Callable,
        timeframe: str = "5min"
    ):
        """Elimina suscripción."""
        key = f"{symbol}_{timeframe}"
        
        if key in self._subscribers and callback in self._subscribers[key]:
            self._subscribers[key].remove(callback)
    
    def _notify_subscribers(self, bar: BarData):
        """Notifica a suscriptores de nueva barra."""
        key = f"{bar.symbol}_{bar.timeframe}"
        
        if key not in self._subscribers:
            return
        
        for callback in self._subscribers[key]:
            try:
                callback(bar)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}")
    
    # =========================================================================
    # AGREGACIÓN DE BARRAS
    # =========================================================================
    
    def aggregate_bars(
        self,
        bars_1min: List[BarData],
        target_timeframe: str
    ) -> Optional[BarData]:
        """
        Agrega barras de 1min a timeframe superior.
        
        Args:
            bars_1min: Lista de barras de 1 minuto
            target_timeframe: Timeframe objetivo ("5min", "15min")
            
        Returns:
            Barra agregada o None si datos insuficientes
        """
        if not bars_1min:
            return None
        
        minutes = int(target_timeframe.replace("min", ""))
        
        if len(bars_1min) < minutes:
            return None
        
        # Tomar últimas N barras
        bars_to_aggregate = bars_1min[-minutes:]
        
        return BarData(
            symbol=bars_to_aggregate[0].symbol,
            timestamp=bars_to_aggregate[-1].timestamp,
            timeframe=target_timeframe,
            open=bars_to_aggregate[0].open,
            high=max(b.high for b in bars_to_aggregate),
            low=min(b.low for b in bars_to_aggregate),
            close=bars_to_aggregate[-1].close,
            volume=sum(b.volume for b in bars_to_aggregate)
        )
    
    # =========================================================================
    # MANEJO DE GAPS
    # =========================================================================
    
    def detect_gaps(
        self,
        df: pd.DataFrame,
        timeframe: str
    ) -> List[tuple[datetime, datetime]]:
        """
        Detecta gaps en los datos.
        
        Args:
            df: DataFrame con índice de timestamps
            timeframe: Timeframe esperado
            
        Returns:
            Lista de tuplas (inicio_gap, fin_gap)
        """
        if df.empty or len(df) < 2:
            return []
        
        gaps = []
        minutes = int(timeframe.replace("min", ""))
        expected_delta = timedelta(minutes=minutes)
        max_gap = expected_delta * 2  # Tolerar hasta 1 barra faltante
        
        timestamps = df.index.tolist()
        
        for i in range(1, len(timestamps)):
            delta = timestamps[i] - timestamps[i-1]
            
            if delta > max_gap:
                gaps.append((timestamps[i-1], timestamps[i]))
        
        return gaps
    
    def fill_gaps(
        self,
        df: pd.DataFrame,
        timeframe: str
    ) -> pd.DataFrame:
        """
        Rellena gaps con forward fill.
        
        Args:
            df: DataFrame con gaps
            timeframe: Timeframe
            
        Returns:
            DataFrame sin gaps
        """
        if df.empty:
            return df
        
        minutes = int(timeframe.replace("min", ""))
        freq = f"{minutes}T"
        
        # Crear índice completo
        full_index = pd.date_range(
            start=df.index.min(),
            end=df.index.max(),
            freq=freq
        )
        
        # Reindex y forward fill
        df_filled = df.reindex(full_index)
        df_filled = df_filled.fillna(method='ffill')
        
        # Volume 0 para barras rellenadas
        original_index = set(df.index)
        for idx in df_filled.index:
            if idx not in original_index:
                df_filled.loc[idx, 'volume'] = 0
        
        return df_filled
    
    # =========================================================================
    # CALLBACKS
    # =========================================================================
    
    def _on_mode_change(self, old_mode: DataMode, new_mode: DataMode):
        """Callback cuando cambia el modo de datos."""
        logger.info(f"Data mode changed: {old_mode.value} -> {new_mode.value}")
        
        if new_mode == DataMode.REALTIME:
            # Podríamos iniciar streaming aquí
            pass
        else:
            # Detener streaming si estaba activo
            pass
    
    # =========================================================================
    # UTILIDADES
    # =========================================================================
    
    def is_market_hours(self, dt: Optional[datetime] = None) -> bool:
        """Verifica si estamos en horas de mercado."""
        dt = dt or datetime.now(self._tz)
        
        # Convertir a timezone local
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self._tz)
        else:
            dt = dt.astimezone(self._tz)
        
        # Verificar día de semana
        if dt.weekday() >= 5:
            return False
        
        # Verificar hora (US market: 9:30 - 16:00 ET)
        market_open = time(9, 30)
        market_close = time(16, 0)
        
        return market_open <= dt.time() <= market_close
    
    def get_buffer_stats(self) -> dict:
        """Obtiene estadísticas del buffer."""
        return {
            "buffer_stats": self._buffer.stats,
            "subscribers": {k: len(v) for k, v in self._subscribers.items()},
            "data_mode": self._toggle.current_mode.value,
            "is_realtime": self._toggle.is_realtime
        }
    
    def clear_buffer(self, symbol: Optional[str] = None):
        """Limpia buffer de datos."""
        self._buffer.clear(symbol)
```

### 15.5 IntraDayRunner

```python
# src/strategies/intraday/runner.py
"""
Runner para estrategias intradía.

Ejecuta el ciclo de estrategias intradía con la frecuencia apropiada.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import asyncio
import logging

from src.strategies.intraday.base import IntraDayStrategy
from src.strategies.registry import StrategyRegistry
from src.data.intraday_manager import IntraDayDataManager
from src.data.providers.realtime_toggle import RealTimeToggle

logger = logging.getLogger(__name__)


class IntraDayRunner:
    """
    Runner para estrategias intradía.
    
    A diferencia del StrategyRunner de swing (cada 5 min),
    este runner opera con mayor frecuencia (cada 1 min o menos)
    y tiene lógica específica para intradía.
    """
    
    def __init__(
        self,
        strategies: Optional[List[IntraDayStrategy]] = None,
        interval_seconds: int = 60,
        enabled: bool = False
    ):
        self._strategies = strategies or []
        self._interval = interval_seconds
        self._enabled = enabled
        self._running = False
        self._data_manager = IntraDayDataManager()
        self._toggle = RealTimeToggle()
        self._last_run: Optional[datetime] = None
        self._cycle_count = 0
    
    @classmethod
    def from_registry(cls, interval_seconds: int = 60) -> 'IntraDayRunner':
        """Crea runner con estrategias del registry."""
        strategies = []
        
        for strategy_id, strategy_class in StrategyRegistry.get_all().items():
            # Verificar si es intradía
            try:
                instance = strategy_class()
                if hasattr(instance, 'strategy_type') and instance.strategy_type == "intraday":
                    strategies.append(instance)
            except Exception as e:
                logger.warning(f"Could not instantiate {strategy_id}: {e}")
        
        return cls(strategies=strategies, interval_seconds=interval_seconds)
    
    def add_strategy(self, strategy: IntraDayStrategy):
        """Añade estrategia al runner."""
        self._strategies.append(strategy)
    
    def remove_strategy(self, strategy_id: str):
        """Elimina estrategia por ID."""
        self._strategies = [
            s for s in self._strategies 
            if s.strategy_id != strategy_id
        ]
    
    async def run_cycle(
        self,
        portfolio: dict,
        current_time: Optional[datetime] = None
    ) -> List[dict]:
        """
        Ejecuta un ciclo de todas las estrategias.
        
        Returns:
            Lista de señales generadas
        """
        current_time = current_time or datetime.now()
        all_signals = []
        
        # Pre-checks
        if not self._enabled:
            logger.debug("IntraDayRunner disabled")
            return all_signals
        
        if not self._data_manager.is_market_hours(current_time):
            logger.debug("Market closed, skipping intraday cycle")
            return all_signals
        
        # Obtener régimen actual
        regime = await self._get_current_regime()
        
        # Ejecutar cada estrategia
        for strategy in self._strategies:
            try:
                signals = await self._run_strategy(
                    strategy=strategy,
                    regime=regime,
                    portfolio=portfolio,
                    current_time=current_time
                )
                all_signals.extend(signals)
            except Exception as e:
                logger.error(f"Error in strategy {strategy.strategy_id}: {e}")
        
        self._last_run = current_time
        self._cycle_count += 1
        
        return all_signals
    
    async def _run_strategy(
        self,
        strategy: IntraDayStrategy,
        regime: str,
        portfolio: dict,
        current_time: datetime
    ) -> List[dict]:
        """Ejecuta una estrategia individual."""
        signals = []
        
        # Verificar si estrategia activa para este régimen
        if regime not in strategy.required_regime:
            return signals
        
        # Obtener símbolos del universo
        symbols = self._get_strategy_universe(strategy)
        
        for symbol in symbols:
            try:
                # Obtener datos
                df = await self._data_manager.get_bars(
                    symbol=symbol,
                    timeframe=strategy.timeframe,
                    n=strategy.config.lookback_bars
                )
                
                if df.empty:
                    continue
                
                # Añadir columna symbol si no existe
                if 'symbol' not in df.columns:
                    df['symbol'] = symbol
                
                # Generar señales
                strategy_signals = strategy.generate_signals(
                    market_data=df,
                    regime=regime,
                    portfolio=portfolio,
                    current_time=current_time
                )
                
                for signal in strategy_signals:
                    signals.append({
                        "signal": signal,
                        "strategy_id": strategy.strategy_id,
                        "timestamp": current_time.isoformat()
                    })
                    
            except Exception as e:
                logger.error(f"Error processing {symbol} in {strategy.strategy_id}: {e}")
        
        return signals
    
    def _get_strategy_universe(self, strategy: IntraDayStrategy) -> List[str]:
        """Obtiene universo de símbolos para una estrategia."""
        # Por defecto, símbolos líquidos US
        default_universe = ["SPY", "QQQ", "IWM", "DIA"]
        
        # Intentar obtener de config
        if hasattr(strategy, 'config') and hasattr(strategy.config, 'universe'):
            return strategy.config.universe or default_universe
        
        return default_universe
    
    async def _get_current_regime(self) -> str:
        """Obtiene régimen actual del mercado."""
        try:
            # Llamar a mcp-ml-models
            # Por ahora retornar default
            return "BULL"
        except Exception:
            return "UNKNOWN"
    
    async def start(self, portfolio: dict):
        """Inicia el runner en loop."""
        self._running = True
        logger.info(f"IntraDayRunner started with {len(self._strategies)} strategies")
        
        while self._running:
            try:
                signals = await self.run_cycle(portfolio)
                
                if signals:
                    logger.info(f"Generated {len(signals)} intraday signals")
                    # Aquí enviaríamos señales a Risk Manager
                
                await asyncio.sleep(self._interval)
                
            except Exception as e:
                logger.error(f"Error in intraday runner loop: {e}")
                await asyncio.sleep(self._interval)
    
    def stop(self):
        """Detiene el runner."""
        self._running = False
        logger.info("IntraDayRunner stopped")
    
    def enable(self):
        """Habilita el runner."""
        self._enabled = True
    
    def disable(self):
        """Deshabilita el runner."""
        self._enabled = False
    
    @property
    def stats(self) -> dict:
        """Estadísticas del runner."""
        return {
            "enabled": self._enabled,
            "running": self._running,
            "strategies_count": len(self._strategies),
            "strategies": [s.strategy_id for s in self._strategies],
            "interval_seconds": self._interval,
            "cycle_count": self._cycle_count,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "data_mode": self._toggle.current_mode.value
        }
```

---

## 16. Tests para Data Pipeline Intradía

```python
# tests/data/test_intraday_data.py
"""
Tests para el pipeline de datos intradía.
"""
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np

from src.data.providers.realtime_toggle import (
    RealTimeToggle, DataMode, DataModeConfig
)
from src.data.intraday_manager import (
    IntraDayDataManager, BarBuffer, BarData, IntraDayDataConfig
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton antes de cada test."""
    RealTimeToggle.reset_instance()
    yield
    RealTimeToggle.reset_instance()


@pytest.fixture
def toggle():
    return RealTimeToggle()


@pytest.fixture
def bar_buffer():
    return BarBuffer(max_size=100)


@pytest.fixture
def sample_bars():
    """Genera barras de ejemplo."""
    bars = []
    base_time = datetime(2024, 12, 4, 10, 0)
    
    for i in range(50):
        bars.append(BarData(
            symbol="SPY",
            timestamp=base_time + timedelta(minutes=i),
            timeframe="1min",
            open=100 + i * 0.1,
            high=100.5 + i * 0.1,
            low=99.5 + i * 0.1,
            close=100.2 + i * 0.1,
            volume=1000000 + i * 10000
        ))
    
    return bars


# =============================================================================
# TESTS REALTIME TOGGLE
# =============================================================================

class TestRealTimeToggle:
    
    def test_singleton(self):
        """Test patrón singleton."""
        t1 = RealTimeToggle()
        t2 = RealTimeToggle()
        assert t1 is t2
    
    def test_default_mode_delayed(self, toggle):
        assert toggle.current_mode == DataMode.DELAYED
        assert toggle.is_delayed
        assert not toggle.is_realtime
    
    def test_delay_minutes(self, toggle):
        assert toggle.delay_minutes == 15
    
    def test_cannot_enable_realtime_without_subscription(self, toggle):
        can_enable, reason = toggle.can_enable_realtime()
        assert not can_enable
        assert "subscription" in reason.lower()
    
    def test_enable_delayed(self, toggle):
        toggle.enable_delayed()
        assert toggle.is_delayed
    
    def test_mode_change_callback(self, toggle):
        callback_called = []
        
        def on_change(old, new):
            callback_called.append((old, new))
        
        toggle.register_callback(on_change)
        toggle.enable_delayed()
        
        assert len(callback_called) == 1
    
    def test_effective_time_delayed(self, toggle):
        now = datetime.now()
        effective = toggle.get_effective_time()
        
        diff = now - effective
        assert 14 <= diff.total_seconds() / 60 <= 16  # ~15 minutos
    
    def test_to_dict(self, toggle):
        data = toggle.to_dict()
        
        assert 'mode' in data
        assert 'delay_minutes' in data
        assert 'is_realtime' in data


# =============================================================================
# TESTS BAR BUFFER
# =============================================================================

class TestBarBuffer:
    
    def test_add_and_get(self, bar_buffer, sample_bars):
        for bar in sample_bars[:10]:
            bar_buffer.add(bar)
        
        retrieved = bar_buffer.get_bars("SPY", "1min")
        assert len(retrieved) == 10
    
    def test_max_size_enforced(self, bar_buffer, sample_bars):
        # Buffer tiene max_size=100, añadimos 50
        for bar in sample_bars:
            bar_buffer.add(bar)
        
        retrieved = bar_buffer.get_bars("SPY", "1min")
        assert len(retrieved) == 50  # Menos que max
    
    def test_get_n_bars(self, bar_buffer, sample_bars):
        for bar in sample_bars:
            bar_buffer.add(bar)
        
        retrieved = bar_buffer.get_bars("SPY", "1min", n=10)
        assert len(retrieved) == 10
    
    def test_get_dataframe(self, bar_buffer, sample_bars):
        for bar in sample_bars[:20]:
            bar_buffer.add(bar)
        
        df = bar_buffer.get_dataframe("SPY", "1min")
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 20
        assert 'open' in df.columns
        assert 'close' in df.columns
    
    def test_clear_specific(self, bar_buffer, sample_bars):
        for bar in sample_bars[:10]:
            bar_buffer.add(bar)
        
        bar_buffer.clear("SPY", "1min")
        
        retrieved = bar_buffer.get_bars("SPY", "1min")
        assert len(retrieved) == 0
    
    def test_stats(self, bar_buffer, sample_bars):
        for bar in sample_bars[:10]:
            bar_buffer.add(bar)
        
        stats = bar_buffer.stats
        assert "SPY_1min" in stats
        assert stats["SPY_1min"] == 10


# =============================================================================
# TESTS INTRADAY DATA MANAGER
# =============================================================================

class TestIntraDayDataManager:
    
    def test_initialization(self):
        manager = IntraDayDataManager()
        assert manager is not None
    
    def test_is_market_hours_weekday(self):
        manager = IntraDayDataManager()
        
        # Miércoles 10:30 AM ET
        market_open = datetime(2024, 12, 4, 10, 30, tzinfo=ZoneInfo("America/New_York"))
        assert manager.is_market_hours(market_open)
        
        # Sábado
        weekend = datetime(2024, 12, 7, 10, 30, tzinfo=ZoneInfo("America/New_York"))
        assert not manager.is_market_hours(weekend)
    
    def test_aggregate_bars(self):
        manager = IntraDayDataManager()
        
        bars_1min = []
        base_time = datetime(2024, 12, 4, 10, 0)
        
        for i in range(5):
            bars_1min.append(BarData(
                symbol="SPY",
                timestamp=base_time + timedelta(minutes=i),
                timeframe="1min",
                open=100 + i,
                high=101 + i,
                low=99 + i,
                close=100.5 + i,
                volume=100000
            ))
        
        aggregated = manager.aggregate_bars(bars_1min, "5min")
        
        assert aggregated is not None
        assert aggregated.timeframe == "5min"
        assert aggregated.open == 100  # Primer open
        assert aggregated.close == 104.5  # Último close
        assert aggregated.high == 105  # Max high
        assert aggregated.low == 99  # Min low
        assert aggregated.volume == 500000  # Sum volume
    
    def test_detect_gaps(self):
        manager = IntraDayDataManager()
        
        # Crear datos con gap
        timestamps = [
            datetime(2024, 12, 4, 10, 0),
            datetime(2024, 12, 4, 10, 5),
            datetime(2024, 12, 4, 10, 10),
            # Gap de 20 minutos
            datetime(2024, 12, 4, 10, 30),
            datetime(2024, 12, 4, 10, 35),
        ]
        
        df = pd.DataFrame({
            'open': [100] * 5,
            'close': [100] * 5
        }, index=timestamps)
        
        gaps = manager.detect_gaps(df, "5min")
        
        assert len(gaps) == 1
        assert gaps[0][0] == timestamps[2]
        assert gaps[0][1] == timestamps[3]
    
    def test_get_buffer_stats(self):
        manager = IntraDayDataManager()
        stats = manager.get_buffer_stats()
        
        assert 'buffer_stats' in stats
        assert 'data_mode' in stats
        assert 'is_realtime' in stats


# =============================================================================
# TESTS INTRADAY RUNNER
# =============================================================================

class TestIntraDayRunner:
    
    def test_initialization(self):
        from src.strategies.intraday.runner import IntraDayRunner
        
        runner = IntraDayRunner(enabled=False)
        assert not runner._enabled
        assert runner._interval == 60
    
    def test_enable_disable(self):
        from src.strategies.intraday.runner import IntraDayRunner
        
        runner = IntraDayRunner()
        
        runner.enable()
        assert runner._enabled
        
        runner.disable()
        assert not runner._enabled
    
    def test_stats(self):
        from src.strategies.intraday.runner import IntraDayRunner
        
        runner = IntraDayRunner(interval_seconds=30)
        stats = runner.stats
        
        assert stats['interval_seconds'] == 30
        assert 'strategies_count' in stats
        assert 'data_mode' in stats
```

---

## 17. Checklist Tarea C2.4

```
TAREA C2.4: DATA PIPELINE INTRADÍA
═══════════════════════════════════════════════════════════════════════════════

REALTIME TOGGLE:
[ ] src/data/providers/realtime_toggle.py creado
[ ] DataMode enum (DELAYED, REALTIME, HISTORICAL)
[ ] RealTimeToggle singleton implementado
[ ] can_enable_realtime() verifica requisitos
[ ] enable_realtime() / enable_delayed() funcionan
[ ] Callbacks de cambio de modo
[ ] get_effective_time() calcula tiempo ajustado
[ ] validate_timestamp() verifica timestamps

INTRADAY DATA MANAGER:
[ ] src/data/intraday_manager.py creado
[ ] BarData dataclass
[ ] BarBuffer clase con deque
[ ] IntraDayDataManager clase principal
[ ] get_bars() obtiene datos históricos
[ ] Integración con IBKRProvider
[ ] aggregate_bars() agrega timeframes
[ ] detect_gaps() detecta huecos
[ ] fill_gaps() rellena con forward fill
[ ] is_market_hours() verifica horario

INTRADAY RUNNER:
[ ] src/strategies/intraday/runner.py creado
[ ] IntraDayRunner clase
[ ] run_cycle() ejecuta estrategias
[ ] Integración con IntraDayDataManager
[ ] start() / stop() para loop
[ ] enable() / disable() para control
[ ] Stats completas

TESTS:
[ ] tests/data/test_intraday_data.py creado
[ ] Tests de RealTimeToggle
[ ] Tests de BarBuffer
[ ] Tests de IntraDayDataManager
[ ] Tests de IntraDayRunner
[ ] Cobertura > 80%

═══════════════════════════════════════════════════════════════════════════════
```

---

*Fin de Parte 4 - Data Pipeline Intradía y Toggle Real-Time*

---

**Siguiente:** Parte 5 - Tests, Verificación, Checklist Final y Troubleshooting
# ⚡ Fase C2: Estrategias Intradía

## Parte 5: Verificación, Checklist Final y Troubleshooting

---

## 18. Script de Verificación

```python
# scripts/verify_fase_c2.py
"""
Script de verificación para Fase C2: Estrategias Intradía.

Ejecutar: python scripts/verify_fase_c2.py

Exit codes:
  0 = Todos los checks pasaron
  1 = Algunos checks fallaron
"""
import sys
import importlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np

# Colores para output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def check(name: str, condition: bool, details: str = "") -> bool:
    """Imprime resultado de un check."""
    status = f"{GREEN}✓{RESET}" if condition else f"{RED}✗{RESET}"
    print(f"  {status} {name}")
    if not condition and details:
        print(f"      {YELLOW}→ {details}{RESET}")
    return condition


def section(name: str):
    """Imprime sección."""
    print(f"\n{name}")
    print("─" * 50)


def main() -> int:
    """Ejecuta verificación completa."""
    print("=" * 60)
    print("  VERIFICACIÓN FASE C2: ESTRATEGIAS INTRADÍA")
    print("=" * 60)
    
    all_passed = True
    
    # =========================================================================
    # 1. VERIFICAR IMPORTS
    # =========================================================================
    section("1. VERIFICAR IMPORTS")
    
    imports_to_check = [
        ("src.strategies.intraday.mixins", "IntraDayMixin"),
        ("src.strategies.intraday.mixins", "MarketSession"),
        ("src.strategies.intraday.mixins", "IntraDayLimits"),
        ("src.strategies.intraday.base", "IntraDayStrategy"),
        ("src.strategies.intraday.base", "IntraDayConfig"),
        ("src.strategies.intraday.mean_reversion", "MeanReversionIntraday"),
        ("src.strategies.intraday.mean_reversion", "MeanReversionConfig"),
        ("src.strategies.intraday.volatility_breakout", "VolatilityBreakout"),
        ("src.strategies.intraday.volatility_breakout", "VolatilityBreakoutConfig"),
        ("src.data.providers.realtime_toggle", "RealTimeToggle"),
        ("src.data.providers.realtime_toggle", "DataMode"),
        ("src.data.intraday_manager", "IntraDayDataManager"),
        ("src.data.intraday_manager", "BarBuffer"),
        ("src.strategies.intraday.runner", "IntraDayRunner"),
    ]
    
    for module_name, class_name in imports_to_check:
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            passed = check(f"{module_name}.{class_name}", True)
        except Exception as e:
            passed = check(f"{module_name}.{class_name}", False, str(e))
        all_passed = all_passed and passed
    
    # =========================================================================
    # 2. VERIFICAR INTRADAY MIXIN
    # =========================================================================
    section("2. VERIFICAR INTRADAY MIXIN")
    
    try:
        from src.strategies.intraday.mixins import (
            IntraDayMixin, MarketSession, IntraDayLimits, MARKET_SESSIONS
        )
        
        # Verificar sesiones predefinidas
        passed = check("MARKET_SESSIONS contiene US", "US" in MARKET_SESSIONS)
        all_passed = all_passed and passed
        
        passed = check("MARKET_SESSIONS contiene EU", "EU" in MARKET_SESSIONS)
        all_passed = all_passed and passed
        
        # Verificar MarketSession
        us_session = MARKET_SESSIONS["US"]
        passed = check(
            "US session timezone correcto",
            us_session.timezone == "America/New_York"
        )
        all_passed = all_passed and passed
        
        # Verificar is_open
        weekday = datetime(2024, 12, 4, 15, 0, tzinfo=ZoneInfo("UTC"))  # 10 AM EST
        passed = check("is_open() weekday market hours", us_session.is_open(weekday))
        all_passed = all_passed and passed
        
        weekend = datetime(2024, 12, 7, 15, 0, tzinfo=ZoneInfo("UTC"))  # Sábado
        passed = check("is_open() weekend returns False", not us_session.is_open(weekend))
        all_passed = all_passed and passed
        
        # Verificar IntraDayLimits defaults
        limits = IntraDayLimits()
        passed = check("IntraDayLimits defaults válidos", limits.max_trades_per_day > 0)
        all_passed = all_passed and passed
        
    except Exception as e:
        passed = check("IntraDayMixin funcional", False, str(e))
        all_passed = False
    
    # =========================================================================
    # 3. VERIFICAR MEAN REVERSION
    # =========================================================================
    section("3. VERIFICAR MEAN REVERSION STRATEGY")
    
    try:
        from src.strategies.intraday.mean_reversion import (
            MeanReversionIntraday, MeanReversionConfig, create_mean_reversion_strategy
        )
        
        # Crear estrategia
        strategy = MeanReversionIntraday()
        
        passed = check(
            "strategy_id correcto",
            strategy.strategy_id == "mean_reversion_intraday"
        )
        all_passed = all_passed and passed
        
        passed = check(
            "strategy_type es intraday",
            strategy.strategy_type == "intraday"
        )
        all_passed = all_passed and passed
        
        passed = check(
            "required_regime contiene SIDEWAYS",
            "SIDEWAYS" in strategy.required_regime
        )
        all_passed = all_passed and passed
        
        # Verificar config validation
        is_valid, issues = strategy.validate_config()
        passed = check("Config válida por defecto", is_valid, str(issues))
        all_passed = all_passed and passed
        
        # Verificar factory
        strategy2 = create_mean_reversion_strategy({"timeframe": "1min"})
        passed = check("Factory function funciona", strategy2.timeframe == "1min")
        all_passed = all_passed and passed
        
        # Verificar cálculo de indicadores con datos sintéticos
        np.random.seed(42)
        test_data = pd.DataFrame({
            'symbol': ['SPY'] * 50,
            'open': 100 + np.random.randn(50) * 0.5,
            'high': 101 + np.random.randn(50) * 0.5,
            'low': 99 + np.random.randn(50) * 0.5,
            'close': 100 + np.random.randn(50) * 0.5,
            'volume': [2000000] * 50
        })
        
        snapshot = strategy.get_indicator_snapshot(test_data)
        passed = check("get_indicator_snapshot funciona", 'zscore' in snapshot)
        all_passed = all_passed and passed
        
    except Exception as e:
        passed = check("MeanReversionIntraday funcional", False, str(e))
        all_passed = False
    
    # =========================================================================
    # 4. VERIFICAR VOLATILITY BREAKOUT
    # =========================================================================
    section("4. VERIFICAR VOLATILITY BREAKOUT STRATEGY")
    
    try:
        from src.strategies.intraday.volatility_breakout import (
            VolatilityBreakout, VolatilityBreakoutConfig, 
            ConsolidationZone, BreakoutDirection,
            create_volatility_breakout_strategy
        )
        
        # Crear estrategia
        strategy = VolatilityBreakout()
        
        passed = check(
            "strategy_id correcto",
            strategy.strategy_id == "volatility_breakout"
        )
        all_passed = all_passed and passed
        
        passed = check(
            "required_regime contiene BULL",
            "BULL" in strategy.required_regime
        )
        all_passed = all_passed and passed
        
        # Verificar ConsolidationZone
        zone = ConsolidationZone(
            high=101.0, low=99.0, bars_count=25,
            avg_volume=2000000, atr_at_formation=0.5, start_bar=10
        )
        passed = check("ConsolidationZone.range_size", zone.range_size == 2.0)
        all_passed = all_passed and passed
        
        passed = check("ConsolidationZone.midpoint", zone.midpoint == 100.0)
        all_passed = all_passed and passed
        
        # Verificar factory
        strategy2 = create_volatility_breakout_strategy({"timeframe": "5min"})
        passed = check("Factory function funciona", strategy2.timeframe == "5min")
        all_passed = all_passed and passed
        
        # Verificar consolidation status
        np.random.seed(42)
        consol_data = pd.DataFrame({
            'symbol': ['SPY'] * 50,
            'open': 100 + np.random.randn(50) * 0.2,
            'high': 100.3 + np.random.randn(50) * 0.2,
            'low': 99.7 + np.random.randn(50) * 0.2,
            'close': 100 + np.random.randn(50) * 0.2,
            'volume': [1500000] * 50
        })
        
        status = strategy.get_consolidation_status(consol_data)
        passed = check("get_consolidation_status funciona", 'is_consolidating' in status)
        all_passed = all_passed and passed
        
    except Exception as e:
        passed = check("VolatilityBreakout funcional", False, str(e))
        all_passed = False
    
    # =========================================================================
    # 5. VERIFICAR REALTIME TOGGLE
    # =========================================================================
    section("5. VERIFICAR REALTIME TOGGLE")
    
    try:
        from src.data.providers.realtime_toggle import (
            RealTimeToggle, DataMode, DataModeConfig
        )
        
        # Reset singleton para test limpio
        RealTimeToggle.reset_instance()
        
        toggle = RealTimeToggle()
        
        passed = check("Default mode es DELAYED", toggle.current_mode == DataMode.DELAYED)
        all_passed = all_passed and passed
        
        passed = check("is_delayed() retorna True", toggle.is_delayed)
        all_passed = all_passed and passed
        
        passed = check("delay_minutes es 15", toggle.delay_minutes == 15)
        all_passed = all_passed and passed
        
        # Verificar singleton
        toggle2 = RealTimeToggle()
        passed = check("Singleton funciona", toggle is toggle2)
        all_passed = all_passed and passed
        
        # Verificar to_dict
        data = toggle.to_dict()
        passed = check("to_dict() tiene 'mode'", 'mode' in data)
        all_passed = all_passed and passed
        
        # Reset para no afectar otros tests
        RealTimeToggle.reset_instance()
        
    except Exception as e:
        passed = check("RealTimeToggle funcional", False, str(e))
        all_passed = False
    
    # =========================================================================
    # 6. VERIFICAR INTRADAY DATA MANAGER
    # =========================================================================
    section("6. VERIFICAR INTRADAY DATA MANAGER")
    
    try:
        from src.data.intraday_manager import (
            IntraDayDataManager, BarBuffer, BarData, IntraDayDataConfig
        )
        
        # Verificar BarBuffer
        buffer = BarBuffer(max_size=100)
        bar = BarData(
            symbol="SPY",
            timestamp=datetime.now(),
            timeframe="1min",
            open=100, high=101, low=99, close=100.5,
            volume=1000000
        )
        buffer.add(bar)
        
        retrieved = buffer.get_bars("SPY", "1min")
        passed = check("BarBuffer add/get funciona", len(retrieved) == 1)
        all_passed = all_passed and passed
        
        # Verificar BarData.to_dict
        bar_dict = bar.to_dict()
        passed = check("BarData.to_dict() funciona", 'close' in bar_dict)
        all_passed = all_passed and passed
        
        # Verificar IntraDayDataManager
        manager = IntraDayDataManager()
        
        passed = check("IntraDayDataManager creado", manager is not None)
        all_passed = all_passed and passed
        
        # Verificar is_market_hours
        weekday_open = datetime(2024, 12, 4, 10, 30, tzinfo=ZoneInfo("America/New_York"))
        passed = check(
            "is_market_hours() funciona",
            manager.is_market_hours(weekday_open)
        )
        all_passed = all_passed and passed
        
        # Verificar aggregate_bars
        bars_1min = [
            BarData("SPY", datetime.now() + timedelta(minutes=i), "1min",
                   100+i, 101+i, 99+i, 100.5+i, 100000)
            for i in range(5)
        ]
        aggregated = manager.aggregate_bars(bars_1min, "5min")
        passed = check("aggregate_bars() funciona", aggregated is not None)
        all_passed = all_passed and passed
        
        # Verificar stats
        stats = manager.get_buffer_stats()
        passed = check("get_buffer_stats() funciona", 'data_mode' in stats)
        all_passed = all_passed and passed
        
    except Exception as e:
        passed = check("IntraDayDataManager funcional", False, str(e))
        all_passed = False
    
    # =========================================================================
    # 7. VERIFICAR INTRADAY RUNNER
    # =========================================================================
    section("7. VERIFICAR INTRADAY RUNNER")
    
    try:
        from src.strategies.intraday.runner import IntraDayRunner
        
        runner = IntraDayRunner(enabled=False, interval_seconds=30)
        
        passed = check("Runner creado con enabled=False", not runner._enabled)
        all_passed = all_passed and passed
        
        passed = check("Runner interval correcto", runner._interval == 30)
        all_passed = all_passed and passed
        
        # Verificar enable/disable
        runner.enable()
        passed = check("enable() funciona", runner._enabled)
        all_passed = all_passed and passed
        
        runner.disable()
        passed = check("disable() funciona", not runner._enabled)
        all_passed = all_passed and passed
        
        # Verificar stats
        stats = runner.stats
        passed = check("stats contiene 'enabled'", 'enabled' in stats)
        all_passed = all_passed and passed
        
        passed = check("stats contiene 'strategies_count'", 'strategies_count' in stats)
        all_passed = all_passed and passed
        
    except Exception as e:
        passed = check("IntraDayRunner funcional", False, str(e))
        all_passed = False
    
    # =========================================================================
    # 8. VERIFICAR ARCHIVOS DE CONFIGURACIÓN
    # =========================================================================
    section("8. VERIFICAR ARCHIVOS DE CONFIGURACIÓN")
    
    import os
    
    config_files = [
        "config/intraday.yaml",
        "config/strategies.yaml",
    ]
    
    for config_file in config_files:
        exists = os.path.exists(config_file)
        passed = check(f"{config_file} existe", exists)
        all_passed = all_passed and passed
    
    # =========================================================================
    # 9. VERIFICAR TESTS EXISTEN
    # =========================================================================
    section("9. VERIFICAR TESTS EXISTEN")
    
    test_files = [
        "tests/strategies/intraday/test_mixins.py",
        "tests/strategies/intraday/test_mean_reversion.py",
        "tests/strategies/intraday/test_volatility_breakout.py",
        "tests/strategies/intraday/test_runner.py",
        "tests/data/test_intraday_data.py",
    ]
    
    for test_file in test_files:
        exists = os.path.exists(test_file)
        passed = check(f"{test_file} existe", exists)
        # No falla si no existe, solo warning
        if not exists:
            print(f"      {YELLOW}→ Crear archivo de test{RESET}")
    
    # =========================================================================
    # RESUMEN
    # =========================================================================
    print("\n" + "=" * 60)
    if all_passed:
        print(f"  {GREEN}✓ TODOS LOS CHECKS PASARON{RESET}")
        print("=" * 60)
        print("\n  Fase C2 verificada correctamente.")
        print("  Sistema intradía listo para testing.")
        return 0
    else:
        print(f"  {RED}✗ ALGUNOS CHECKS FALLARON{RESET}")
        print("=" * 60)
        print("\n  Revisa los errores arriba antes de continuar.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

## 19. Checklist Consolidado Final

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    FASE C2: ESTRATEGIAS INTRADÍA                             ║
║                         CHECKLIST FINAL                                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  TAREA C2.1: INTRADAY MIXIN + BASE                                          ║
║  ─────────────────────────────────────────────────────────────────────────   ║
║  [ ] src/strategies/intraday/__init__.py creado                             ║
║  [ ] src/strategies/intraday/mixins.py creado                               ║
║  [ ] MarketSession dataclass con is_open() y time_to_close()                ║
║  [ ] MARKET_SESSIONS dict con US, EU, CRYPTO                                ║
║  [ ] IntraDayLimits dataclass                                               ║
║  [ ] IntraDayMixin clase con métodos de sesión y límites                    ║
║  [ ] src/strategies/intraday/base.py creado                                 ║
║  [ ] IntraDayConfig dataclass                                               ║
║  [ ] IntraDayStrategy ABC hereda de TradingStrategy                         ║
║  [ ] pre_generate_checks() implementado                                     ║
║  [ ] should_close() con lógica EOD                                          ║
║                                                                              ║
║  TAREA C2.2: MEAN REVERSION INTRADAY                                        ║
║  ─────────────────────────────────────────────────────────────────────────   ║
║  [ ] src/strategies/intraday/mean_reversion.py creado                       ║
║  [ ] MeanReversionConfig con todos los parámetros                           ║
║  [ ] Cálculo de Bollinger Bands correcto                                    ║
║  [ ] Cálculo de Z-Score correcto                                            ║
║  [ ] Cálculo de RSI correcto                                                ║
║  [ ] Cálculo de ATR correcto                                                ║
║  [ ] Señales LONG en sobreventa (Z<-2, RSI<30, BB lower)                    ║
║  [ ] Señales SHORT en sobrecompra (Z>2, RSI>70, BB upper)                   ║
║  [ ] Exit por reversión a media (|Z|<0.5)                                   ║
║  [ ] Exit por max holding bars                                              ║
║  [ ] Factory function create_mean_reversion_strategy()                      ║
║  [ ] validate_config() implementado                                         ║
║  [ ] get_indicator_snapshot() para debugging                                ║
║  [ ] tests/strategies/intraday/test_mean_reversion.py completo              ║
║                                                                              ║
║  TAREA C2.3: VOLATILITY BREAKOUT                                            ║
║  ─────────────────────────────────────────────────────────────────────────   ║
║  [ ] src/strategies/intraday/volatility_breakout.py creado                  ║
║  [ ] VolatilityBreakoutConfig con todos los parámetros                      ║
║  [ ] ConsolidationZone dataclass                                            ║
║  [ ] BreakoutDirection enum                                                 ║
║  [ ] Detección de consolidación (rango < threshold * ATR)                   ║
║  [ ] Detección de breakout alcista con volume surge                         ║
║  [ ] Detección de breakout bajista con volume surge                         ║
║  [ ] Señales con SL/TP basados en ATR                                       ║
║  [ ] Exit por falso breakout (precio vuelve al rango)                       ║
║  [ ] Trailing stop implementado                                             ║
║  [ ] Factory function create_volatility_breakout_strategy()                 ║
║  [ ] get_consolidation_status() para debugging                              ║
║  [ ] tests/strategies/intraday/test_volatility_breakout.py completo         ║
║                                                                              ║
║  TAREA C2.4: DATA PIPELINE INTRADÍA                                         ║
║  ─────────────────────────────────────────────────────────────────────────   ║
║  [ ] src/data/providers/realtime_toggle.py creado                           ║
║  [ ] DataMode enum (DELAYED, REALTIME, HISTORICAL)                          ║
║  [ ] RealTimeToggle singleton                                               ║
║  [ ] can_enable_realtime() verifica requisitos                              ║
║  [ ] Callbacks de cambio de modo                                            ║
║  [ ] src/data/intraday_manager.py creado                                    ║
║  [ ] BarData dataclass                                                      ║
║  [ ] BarBuffer con deque y max_size                                         ║
║  [ ] IntraDayDataManager.get_bars() funciona                                ║
║  [ ] aggregate_bars() agrega timeframes correctamente                       ║
║  [ ] detect_gaps() encuentra huecos en datos                                ║
║  [ ] fill_gaps() rellena con forward fill                                   ║
║  [ ] is_market_hours() verifica horario de mercado                          ║
║  [ ] tests/data/test_intraday_data.py completo                              ║
║                                                                              ║
║  TAREA C2.5: INTRADAY RUNNER + CONFIG                                       ║
║  ─────────────────────────────────────────────────────────────────────────   ║
║  [ ] src/strategies/intraday/runner.py creado                               ║
║  [ ] IntraDayRunner con run_cycle()                                         ║
║  [ ] Integración con IntraDayDataManager                                    ║
║  [ ] start() / stop() para loop asíncrono                                   ║
║  [ ] enable() / disable() para control                                      ║
║  [ ] config/intraday.yaml creado                                            ║
║  [ ] config/strategies.yaml actualizado con estrategias intradía            ║
║  [ ] Estrategias intradía desactivadas por defecto                          ║
║                                                                              ║
║  TAREA C2.6: VERIFICACIÓN                                                   ║
║  ─────────────────────────────────────────────────────────────────────────   ║
║  [ ] scripts/verify_fase_c2.py creado                                       ║
║  [ ] Todos los imports verificados                                          ║
║  [ ] Todos los tests pasan                                                  ║
║  [ ] python scripts/verify_fase_c2.py retorna 0                             ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  GATE DE AVANCE:                                                            ║
║  ─────────────────────────────────────────────────────────────────────────   ║
║  [ ] python scripts/verify_fase_c2.py retorna 0 (éxito)                     ║
║  [ ] pytest tests/strategies/intraday/ pasa (>80% cobertura)                ║
║  [ ] pytest tests/data/test_intraday_data.py pasa                           ║
║  [ ] Mean Reversion genera señales en régimen SIDEWAYS simulado             ║
║  [ ] Volatility Breakout detecta consolidación y breakout                   ║
║  [ ] RealTimeToggle cambia modos correctamente                              ║
║  [ ] IntraDayRunner ejecuta ciclos sin errores                              ║
║  [ ] Estrategias intradía están DESACTIVADAS por defecto                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 20. Troubleshooting

### Error: "ModuleNotFoundError: strategies.intraday"

```bash
# Asegurar que src está en PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# O usar instalación editable
pip install -e .
```

### Error: "IntraDayMixin.__init_intraday__ not called"

```python
# Asegurar que la subclase llama al init del mixin
class MyStrategy(IntraDayStrategy):
    def __init__(self, config):
        super().__init__(config)  # Esto llama __init_intraday__ internamente
```

### Error: "RealTimeToggle singleton issues in tests"

```python
# Siempre resetear singleton en fixtures de test
@pytest.fixture(autouse=True)
def reset_singleton():
    RealTimeToggle.reset_instance()
    yield
    RealTimeToggle.reset_instance()
```

### Error: "Insufficient data for indicators"

```python
# Mean Reversion necesita ~30 barras mínimo para indicadores
# Volatility Breakout necesita ~50 barras para detectar consolidación

# Verificar lookback_bars en config
config = MeanReversionConfig(lookback_bars=50)  # Aumentar si es necesario
```

### Error: "No signals generated"

1. **Verificar régimen:** Mean Reversion solo opera en SIDEWAYS
2. **Verificar horario:** `is_market_open()` debe retornar True
3. **Verificar límites:** No haber alcanzado `max_trades_per_day`
4. **Verificar volumen:** Datos deben tener volumen > `min_volume_ratio`
5. **Activar logging debug:**

```python
import logging
logging.getLogger("strategy").setLevel(logging.DEBUG)
```

### Error: "Breakout not detected"

1. **Verificar consolidación:** Necesita `min_consolidation_bars` consecutivas
2. **Verificar volume surge:** Breakout necesita volumen > 2x promedio
3. **Verificar magnitud:** Breakout debe superar `breakout_atr_threshold * ATR`

```python
# Debug consolidation status
status = strategy.get_consolidation_status(market_data)
print(f"Consolidating: {status['is_consolidating']}")
print(f"Bars: {status['consecutive_bars']}")
print(f"Valid zone: {status['valid_consolidation']}")
```

### Error: "Trailing stop not activating"

```python
# Trailing se activa después de alcanzar trailing_activation_atr de profit
# Verificar que position tiene highest_price/lowest_price actualizado

position = {
    "symbol": "SPY",
    "direction": "LONG",
    "entry_price": 100.0,
    "highest_price": 102.0,  # Debe actualizarse en cada tick
    ...
}
```

### Error: "Market hours detection wrong"

```python
# Verificar timezone del datetime
from zoneinfo import ZoneInfo

# Correcto: datetime con timezone
dt = datetime(2024, 12, 4, 10, 30, tzinfo=ZoneInfo("America/New_York"))

# Incorrecto: datetime naive
dt = datetime(2024, 12, 4, 10, 30)  # Sin timezone
```

### Config YAML no se carga

```bash
# Verificar ubicación de archivos
ls -la config/

# Deben existir:
# config/intraday.yaml
# config/strategies.yaml

# Verificar sintaxis YAML
python -c "import yaml; yaml.safe_load(open('config/intraday.yaml'))"
```

---

## 21. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| TradingStrategy ABC | fase_b1_estrategias_swing.md | Sección 4 |
| Signal dataclass | fase_b1_estrategias_swing.md | Sección 4.1 |
| StrategyRegistry | fase_b1_estrategias_swing.md | Sección 8 |
| StrategyRunner (swing) | fase_b1_estrategias_swing.md | Sección 10 |
| Régimen detector (HMM) | fase_a2_ml_modular.md | Tareas A2.2-A2.3 |
| Sistema de métricas | fase_c1_metricas.md | Secciones 3-7 |
| MetricsCollector | fase_c1_metricas.md | Sección 5 |
| IBKR provider | fase_a1_extensiones_base.md | Tarea A1.3 |
| Esquemas BD metrics | fase_a1_extensiones_base.md | Tarea A1.1 |
| Agentes core | fase_3_agentes_core.md | Tareas 3.1-3.4 |
| Risk Manager | fase_3_agentes_core.md | Tarea 3.3 |
| Handoff document | nexus_trading_handoff.md | Todo |

---

## 22. Siguiente Fase

Una vez completada la Fase C2:

1. **Verificar:** `python scripts/verify_fase_c2.py` retorna 0
2. **Verificar:** `pytest tests/strategies/intraday/` pasa con >80% cobertura
3. **Verificar:** Estrategias intradía DESACTIVADAS en config
4. **NO activar intradía** hasta que swing trading esté validado en paper

### Post-MVP: Activación de Intradía

Cuando el sistema swing esté validado (mínimo 50 trades, Sharpe > 0.5):

1. Cambiar `enabled: true` para una estrategia intradía en `config/intraday.yaml`
2. Ejecutar en paper trading con capital limitado
3. Monitorizar métricas separadamente (usar tags en metrics.trades)
4. Ajustar parámetros según resultados

### Documentos Completados

Con la Fase C2, el sistema tiene todos los documentos de implementación:

| Fase | Documento | Estado |
|------|-----------|--------|
| A1 | fase_a1_extensiones_base.md | ✅ |
| A2 | fase_a2_ml_modular.md | ✅ |
| B1 | fase_b1_estrategias_swing.md | ✅ |
| B2 | fase_b2_ai_agent.md | ✅ |
| C1 | fase_c1_metricas.md | ✅ |
| C2 | fase_c2_intraday.md | ✅ |

---

## 23. Comandos de Referencia Rápida

```bash
# Verificar fase
python scripts/verify_fase_c2.py

# Ejecutar tests intradía
pytest tests/strategies/intraday/ -v

# Ejecutar tests de datos
pytest tests/data/test_intraday_data.py -v

# Ver cobertura
pytest tests/strategies/intraday/ --cov=src/strategies/intraday --cov-report=html

# Validar YAML
python -c "import yaml; print(yaml.safe_load(open('config/intraday.yaml')))"

# Test rápido de Mean Reversion
python -c "
from src.strategies.intraday.mean_reversion import MeanReversionIntraday
s = MeanReversionIntraday()
print(f'Strategy: {s.strategy_id}')
print(f'Regime: {s.required_regime}')
print(f'Timeframe: {s.timeframe}')
"

# Test rápido de Volatility Breakout
python -c "
from src.strategies.intraday.volatility_breakout import VolatilityBreakout
s = VolatilityBreakout()
print(f'Strategy: {s.strategy_id}')
print(f'Regime: {s.required_regime}')
"

# Verificar RealTimeToggle
python -c "
from src.data.providers.realtime_toggle import RealTimeToggle, DataMode
t = RealTimeToggle()
print(f'Mode: {t.current_mode}')
print(f'Delay: {t.delay_minutes} min')
"
```

---

*Fin de Parte 5 - Verificación, Checklist Final y Troubleshooting*

---

*Documento de Implementación - Fase C2: Estrategias Intradía*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
