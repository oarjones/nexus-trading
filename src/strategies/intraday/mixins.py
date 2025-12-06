"""
Mixin para funcionalidad común de estrategias intradía.
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional, Dict
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
        try:
            tz = ZoneInfo(self.timezone)
            local_dt = dt.astimezone(tz)
            current_time = local_dt.time()
            
            # Verificar día de semana (0=lunes, 6=domingo)
            if local_dt.weekday() >= 5:  # Sábado o domingo
                return False
            
            return self.open_time <= current_time <= self.close_time
        except Exception as e:
            logger.error(f"Error checking market session: {e}")
            return False
    
    def time_to_close(self, dt: datetime) -> timedelta:
        """Retorna tiempo restante hasta el cierre."""
        try:
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
        except Exception as e:
            logger.error(f"Error calculating time to close: {e}")
            return timedelta(0)


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
