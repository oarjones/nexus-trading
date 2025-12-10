"""
Universe Manager - Gestión Dinámica del Universo de Símbolos

Este módulo gestiona qué símbolos están disponibles para operar cada día.
El proceso es:

1. Universo Maestro (config/symbols.yaml): ~80-100 símbolos curados
2. Screening Diario: filtros de liquidez, tendencia, régimen
3. AI Suggestions: el agente puede sugerir añadir/quitar símbolos
4. Universo Activo: símbolos operables para el día

El screening se ejecuta diariamente antes de apertura de mercados.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from typing import Optional, Protocol
from enum import Enum
import logging
import json

from ..data.symbols import SymbolRegistry, Symbol
from ..strategies.interfaces import MarketRegime

logger = logging.getLogger(__name__)


class SuggestionType(Enum):
    """Tipo de sugerencia del AI Agent."""
    ADD = "add"          # Añadir símbolo al universo activo
    REMOVE = "remove"    # Quitar símbolo del universo activo
    WATCH = "watch"      # Añadir a watchlist para siguiente día


class SuggestionStatus(Enum):
    """Estado de una sugerencia."""
    PENDING = "pending"      # Pendiente de validación
    APPROVED = "approved"    # Aprobada y aplicada
    REJECTED = "rejected"    # Rechazada (no pasó filtros)
    EXPIRED = "expired"      # Expirada (no procesada a tiempo)


@dataclass
class AISuggestion:
    """
    Sugerencia del AI Agent para modificar el universo.
    
    El AI puede sugerir añadir o quitar símbolos con una razón.
    Las sugerencias pasan validación automática antes de aplicarse.
    """
    symbol: str
    suggestion_type: SuggestionType
    reason: str
    confidence: float  # 0.0 - 1.0
    suggested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: SuggestionStatus = SuggestionStatus.PENDING
    validation_notes: str = ""
    
    def to_dict(self) -> dict:
        """Serializar para persistencia."""
        return {
            "symbol": self.symbol,
            "type": self.suggestion_type.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "suggested_at": self.suggested_at.isoformat(),
            "status": self.status.value,
            "validation_notes": self.validation_notes,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AISuggestion":
        """Deserializar desde persistencia."""
        return cls(
            symbol=data["symbol"],
            suggestion_type=SuggestionType(data["type"]),
            reason=data["reason"],
            confidence=data["confidence"],
            suggested_at=datetime.fromisoformat(data["suggested_at"]),
            status=SuggestionStatus(data["status"]),
            validation_notes=data.get("validation_notes", ""),
        )


@dataclass
class DailyUniverse:
    """
    Universo activo para un día específico.
    
    Contiene los símbolos operables y el historial de cómo se llegó
    a esa selección (para análisis posterior).
    """
    date: date
    active_symbols: list[str]
    regime_at_screening: MarketRegime
    
    # Metadata de screening
    master_universe_size: int = 0
    passed_liquidity: int = 0
    passed_trend: int = 0
    
    # Sugerencias del AI
    ai_suggestions: list[AISuggestion] = field(default_factory=list)
    ai_additions: list[str] = field(default_factory=list)
    ai_removals: list[str] = field(default_factory=list)
    
    # Timestamps
    screened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        """Serializar para persistencia en BD."""
        return {
            "date": self.date.isoformat(),
            "active_symbols": self.active_symbols,
            "regime": self.regime_at_screening.value,
            "master_universe_size": self.master_universe_size,
            "passed_liquidity": self.passed_liquidity,
            "passed_trend": self.passed_trend,
            "ai_suggestions": [s.to_dict() for s in self.ai_suggestions],
            "ai_additions": self.ai_additions,
            "ai_removals": self.ai_removals,
            "screened_at": self.screened_at.isoformat(),
        }


class DataProvider(Protocol):
    """
    Protocolo para proveedores de datos de mercado.
    
    El UniverseManager necesita datos para aplicar filtros.
    Puede ser el MCP Market Data server o Yahoo Finance directo.
    """
    
    async def get_quote(self, symbol: str) -> dict:
        """Obtener cotización actual con volumen."""
        ...
    
    async def get_indicators(self, symbol: str, indicators: list[str]) -> dict:
        """Obtener indicadores técnicos."""
        ...
    
    async def get_historical(self, symbol: str, days: int) -> list[dict]:
        """Obtener datos históricos OHLCV."""
        ...


class UniverseManager:
    """
    Gestor del universo de símbolos operables.
    
    Responsabilidades:
    - Cargar universo maestro desde configuración
    - Aplicar filtros de screening diario
    - Procesar sugerencias del AI Agent
    - Persistir universo activo en BD
    - Proveer universo activo a las estrategias
    
    Uso típico:
        manager = UniverseManager(registry, data_provider, db)
        
        # Screening diario (ejecutar antes de apertura)
        await manager.run_daily_screening(current_regime)
        
        # Las estrategias obtienen símbolos activos
        symbols = manager.get_active_symbols()
        
        # AI Agent puede sugerir cambios
        manager.add_suggestion(AISuggestion(...))
    """
    
    # Configuración de filtros
    DEFAULT_CONFIG = {
        # Liquidez
        "min_avg_volume_usd": 500_000,   # Volumen promedio mínimo en USD
        "min_avg_volume_shares": 100_000, # Volumen promedio mínimo en acciones
        "max_spread_pct": 0.5,            # Spread máximo permitido
        
        # Tendencia
        "trend_sma_period": 200,          # SMA para filtro de tendencia
        "min_price": 5.0,                 # Precio mínimo (evitar penny stocks)
        "max_price": 10_000,              # Precio máximo
        
        # Volatilidad
        "min_atr_pct": 0.5,               # ATR mínimo (evitar "muertos")
        "max_atr_pct": 10.0,              # ATR máximo (evitar locos)
        
        # AI Suggestions
        "max_ai_suggestions_per_day": 10,  # Límite de sugerencias diarias
        "min_suggestion_confidence": 0.6,  # Confianza mínima para aprobar
        
        # Universo
        "max_active_symbols": 50,          # Máximo símbolos activos
        "min_active_symbols": 10,          # Mínimo símbolos activos
    }
    
    def __init__(
        self,
        symbol_registry: SymbolRegistry,
        data_provider: DataProvider,
        db_pool = None,  # asyncpg pool
        config: dict = None,
    ):
        """
        Inicializar Universe Manager.
        
        Args:
            symbol_registry: Registro con universo maestro
            data_provider: Proveedor de datos de mercado
            db_pool: Pool de conexiones PostgreSQL (opcional)
            config: Configuración personalizada de filtros
        """
        self.registry = symbol_registry
        self.data_provider = data_provider
        self.db_pool = db_pool
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        
        # Estado actual
        self._current_universe: Optional[DailyUniverse] = None
        self._pending_suggestions: list[AISuggestion] = []
        
        logger.info(
            f"UniverseManager initialized with {self.registry.count()} "
            f"symbols in master universe"
        )
    
    @property
    def active_symbols(self) -> list[str]:
        """Obtener lista de símbolos activos para hoy."""
        if self._current_universe is None:
            logger.warning("No active universe set, returning empty list")
            return []
        return self._current_universe.active_symbols.copy()
    
    @property
    def current_universe(self) -> Optional[DailyUniverse]:
        """Obtener universo completo del día."""
        return self._current_universe
    
    def get_symbol_metadata(self, ticker: str) -> Optional[Symbol]:
        """Obtener metadata de un símbolo del registro maestro."""
        return self.registry.get_by_ticker(ticker)
    
    async def run_daily_screening(
        self,
        regime: MarketRegime,
        force: bool = False,
    ) -> DailyUniverse:
        """
        Ejecutar screening diario del universo.
        
        Este método debería ejecutarse una vez al día, típicamente
        antes de apertura de mercados (06:00 UTC para EU).
        
        Args:
            regime: Régimen de mercado actual
            force: Forzar re-screening aunque ya exista para hoy
            
        Returns:
            DailyUniverse con símbolos activos
        """
        today = date.today()
        
        # Verificar si ya existe screening para hoy
        if not force and self._current_universe:
            if self._current_universe.date == today:
                logger.info(f"Using existing universe for {today}")
                return self._current_universe
        
        logger.info(f"Starting daily screening for {today}, regime={regime.value}")
        
        # 1. Obtener universo maestro
        master_symbols = self.registry.get_all()
        master_tickers = [s.ticker for s in master_symbols]
        
        # 2. Aplicar filtros
        passed_liquidity = await self._filter_by_liquidity(master_tickers)
        logger.info(f"Liquidity filter: {len(master_tickers)} -> {len(passed_liquidity)}")
        
        passed_trend = await self._filter_by_trend(passed_liquidity, regime)
        logger.info(f"Trend filter: {len(passed_liquidity)} -> {len(passed_trend)}")
        
        passed_volatility = await self._filter_by_volatility(passed_trend)
        logger.info(f"Volatility filter: {len(passed_trend)} -> {len(passed_volatility)}")
        
        # 3. Procesar sugerencias pendientes del AI
        ai_additions, ai_removals = await self._process_ai_suggestions(
            passed_volatility, regime
        )
        
        # 4. Aplicar modificaciones del AI
        final_symbols = set(passed_volatility)
        for symbol in ai_additions:
            final_symbols.add(symbol)
        for symbol in ai_removals:
            final_symbols.discard(symbol)
        
        # 5. Aplicar límites
        final_list = list(final_symbols)
        if len(final_list) > self.config["max_active_symbols"]:
            # Priorizar por algún criterio (ej: liquidez)
            final_list = final_list[:self.config["max_active_symbols"]]
            logger.warning(f"Capped active universe to {len(final_list)} symbols")
        
        # 6. Crear universo del día
        universe = DailyUniverse(
            date=today,
            active_symbols=sorted(final_list),
            regime_at_screening=regime,
            master_universe_size=len(master_tickers),
            passed_liquidity=len(passed_liquidity),
            passed_trend=len(passed_trend),
            ai_suggestions=self._pending_suggestions.copy(),
            ai_additions=ai_additions,
            ai_removals=ai_removals,
        )
        
        # 7. Persistir
        if self.db_pool:
            await self._persist_universe(universe)
        
        # 8. Limpiar sugerencias procesadas
        self._pending_suggestions.clear()
        
        # 9. Actualizar estado
        self._current_universe = universe
        
        logger.info(
            f"Daily screening complete: {len(final_list)} active symbols "
            f"(+{len(ai_additions)} AI additions, -{len(ai_removals)} AI removals)"
        )
        
        return universe
    
    async def _filter_by_liquidity(self, symbols: list[str]) -> list[str]:
        """
        Filtrar por liquidez (volumen y spread).
        
        Elimina símbolos que no tienen suficiente volumen diario
        o tienen spreads muy amplios.
        """
        passed = []
        min_volume = self.config["min_avg_volume_shares"]
        max_spread = self.config["max_spread_pct"]
        
        for symbol in symbols:
            try:
                quote = await self.data_provider.get_quote(symbol)
                
                # Verificar volumen
                avg_volume = quote.get("avg_volume_20d", 0)
                if avg_volume < min_volume:
                    logger.debug(f"{symbol}: Low volume ({avg_volume:,.0f} < {min_volume:,.0f})")
                    continue
                
                # Verificar spread (si disponible)
                bid = quote.get("bid", 0)
                ask = quote.get("ask", 0)
                if bid and ask and bid > 0:
                    spread_pct = ((ask - bid) / bid) * 100
                    if spread_pct > max_spread:
                        logger.debug(f"{symbol}: Wide spread ({spread_pct:.2f}% > {max_spread}%)")
                        continue
                
                passed.append(symbol)
                
            except Exception as e:
                logger.warning(f"Error checking liquidity for {symbol}: {e}")
                # Si no podemos verificar, lo excluimos por seguridad
                continue
        
        return passed
    
    async def _filter_by_trend(
        self, 
        symbols: list[str], 
        regime: MarketRegime
    ) -> list[str]:
        """
        Filtrar por tendencia según el régimen actual.
        
        - BULL: precio > SMA200 (solo alcistas)
        - BEAR: precio < SMA200 (solo bajistas) o defensivos
        - SIDEWAYS/VOLATILE: sin filtro de tendencia
        """
        if regime in [MarketRegime.SIDEWAYS, MarketRegime.VOLATILE]:
            # No aplicar filtro de tendencia en estos regímenes
            return symbols
        
        passed = []
        sma_period = self.config["trend_sma_period"]
        
        for symbol in symbols:
            try:
                data = await self.data_provider.get_indicators(
                    symbol, [f"sma_{sma_period}"]
                )
                
                price = data.get("price", 0)
                sma = data.get(f"sma_{sma_period}", 0)
                
                if not price or not sma:
                    # Sin datos, excluir
                    continue
                
                if regime == MarketRegime.BULL:
                    # Solo símbolos en tendencia alcista
                    if price > sma:
                        passed.append(symbol)
                    else:
                        logger.debug(f"{symbol}: Below SMA{sma_period} in BULL regime")
                
                elif regime == MarketRegime.BEAR:
                    # Solo símbolos en tendencia bajista o defensivos
                    symbol_meta = self.registry.get_by_ticker(symbol)
                    is_defensive = symbol_meta and symbol_meta.asset_type == "etf"
                    
                    if price < sma or is_defensive:
                        passed.append(symbol)
                        
            except Exception as e:
                logger.warning(f"Error checking trend for {symbol}: {e}")
                continue
        
        return passed
    
    async def _filter_by_volatility(self, symbols: list[str]) -> list[str]:
        """
        Filtrar por volatilidad (ATR como % del precio).
        
        Elimina símbolos "muertos" (muy baja volatilidad, no hay oportunidad)
        y símbolos "locos" (muy alta volatilidad, demasiado riesgo).
        """
        passed = []
        min_atr = self.config["min_atr_pct"]
        max_atr = self.config["max_atr_pct"]
        min_price = self.config["min_price"]
        max_price = self.config["max_price"]
        
        for symbol in symbols:
            try:
                data = await self.data_provider.get_indicators(
                    symbol, ["atr_14"]
                )
                
                price = data.get("price", 0)
                atr = data.get("atr_14", 0)
                
                if not price or price < min_price or price > max_price:
                    logger.debug(f"{symbol}: Price out of range ({price})")
                    continue
                
                if atr:
                    atr_pct = (atr / price) * 100
                    if atr_pct < min_atr:
                        logger.debug(f"{symbol}: Too low volatility ({atr_pct:.2f}%)")
                        continue
                    if atr_pct > max_atr:
                        logger.debug(f"{symbol}: Too high volatility ({atr_pct:.2f}%)")
                        continue
                
                passed.append(symbol)
                
            except Exception as e:
                logger.warning(f"Error checking volatility for {symbol}: {e}")
                continue
        
        return passed
    
    # =========================================================================
    # AI Suggestions
    # =========================================================================
    
    def add_suggestion(self, suggestion: AISuggestion) -> bool:
        """
        Añadir sugerencia del AI Agent.
        
        Las sugerencias se acumulan y se procesan en el siguiente
        screening diario.
        
        Args:
            suggestion: Sugerencia a añadir
            
        Returns:
            True si se añadió, False si se rechazó (límite alcanzado)
        """
        # Verificar límite diario
        today_suggestions = [
            s for s in self._pending_suggestions
            if s.suggested_at.date() == date.today()
        ]
        
        if len(today_suggestions) >= self.config["max_ai_suggestions_per_day"]:
            logger.warning(
                f"AI suggestion limit reached ({self.config['max_ai_suggestions_per_day']}/day)"
            )
            return False
        
        # Verificar confianza mínima
        if suggestion.confidence < self.config["min_suggestion_confidence"]:
            logger.info(
                f"AI suggestion for {suggestion.symbol} rejected: "
                f"low confidence ({suggestion.confidence:.2f})"
            )
            suggestion.status = SuggestionStatus.REJECTED
            suggestion.validation_notes = "Confidence below threshold"
            self._pending_suggestions.append(suggestion)
            return False
        
        self._pending_suggestions.append(suggestion)
        logger.info(
            f"AI suggestion added: {suggestion.suggestion_type.value} "
            f"{suggestion.symbol} (confidence={suggestion.confidence:.2f})"
        )
        return True
    
    def add_suggestion_from_dict(self, data: dict) -> bool:
        """
        Añadir sugerencia desde diccionario (para uso desde MCP).
        
        Args:
            data: {
                "symbol": "AAPL",
                "type": "add" | "remove" | "watch",
                "reason": "Strong momentum...",
                "confidence": 0.85
            }
        """
        try:
            suggestion = AISuggestion(
                symbol=data["symbol"],
                suggestion_type=SuggestionType(data["type"]),
                reason=data["reason"],
                confidence=data.get("confidence", 0.7),
            )
            return self.add_suggestion(suggestion)
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid suggestion data: {e}")
            return False
    
    async def _process_ai_suggestions(
        self,
        current_symbols: list[str],
        regime: MarketRegime,
    ) -> tuple[list[str], list[str]]:
        """
        Procesar sugerencias pendientes del AI.
        
        Valida cada sugerencia contra los filtros básicos y decide
        si aprobarla o rechazarla.
        
        Returns:
            Tuple de (símbolos a añadir, símbolos a quitar)
        """
        additions = []
        removals = []
        
        for suggestion in self._pending_suggestions:
            if suggestion.status != SuggestionStatus.PENDING:
                continue
            
            symbol = suggestion.symbol
            
            if suggestion.suggestion_type == SuggestionType.ADD:
                # Validar que el símbolo existe y pasa filtros básicos
                if await self._validate_ai_addition(symbol):
                    suggestion.status = SuggestionStatus.APPROVED
                    additions.append(symbol)
                    logger.info(f"AI ADD approved: {symbol} - {suggestion.reason}")
                else:
                    suggestion.status = SuggestionStatus.REJECTED
                    suggestion.validation_notes = "Failed validation filters"
                    
            elif suggestion.suggestion_type == SuggestionType.REMOVE:
                # Para remover, solo verificamos que está en el universo
                if symbol in current_symbols:
                    suggestion.status = SuggestionStatus.APPROVED
                    removals.append(symbol)
                    logger.info(f"AI REMOVE approved: {symbol} - {suggestion.reason}")
                else:
                    suggestion.status = SuggestionStatus.REJECTED
                    suggestion.validation_notes = "Symbol not in current universe"
                    
            elif suggestion.suggestion_type == SuggestionType.WATCH:
                # Watch no modifica el universo, solo se registra
                suggestion.status = SuggestionStatus.APPROVED
                logger.info(f"AI WATCH noted: {symbol} - {suggestion.reason}")
        
        return additions, removals
    
    async def _validate_ai_addition(self, symbol: str) -> bool:
        """
        Validar que un símbolo sugerido por AI puede añadirse.
        
        Debe pasar filtros básicos de liquidez y precio.
        """
        try:
            # 1. Verificar que existe en el universo maestro o es válido
            meta = self.registry.get_by_ticker(symbol)
            if not meta:
                logger.debug(f"AI addition {symbol}: Not in master universe")
                # Podríamos permitirlo si pasa otros filtros, pero por ahora no
                return False
            
            # 2. Verificar liquidez básica
            quote = await self.data_provider.get_quote(symbol)
            avg_volume = quote.get("avg_volume_20d", 0)
            if avg_volume < self.config["min_avg_volume_shares"] * 0.5:  # 50% del mínimo
                logger.debug(f"AI addition {symbol}: Insufficient liquidity")
                return False
            
            # 3. Verificar precio razonable
            price = quote.get("price", 0)
            if price < self.config["min_price"] or price > self.config["max_price"]:
                logger.debug(f"AI addition {symbol}: Price out of range")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error validating AI addition {symbol}: {e}")
            return False
    
    # =========================================================================
    # Persistencia
    # =========================================================================
    
    async def _persist_universe(self, universe: DailyUniverse):
        """Guardar universo del día en PostgreSQL."""
        if not self.db_pool:
            return
        
        query = """
            INSERT INTO universe.daily_universe (
                screening_date,
                active_symbols,
                regime,
                master_universe_size,
                passed_liquidity,
                passed_trend,
                ai_suggestions,
                ai_additions,
                ai_removals,
                screened_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (screening_date) DO UPDATE SET
                active_symbols = EXCLUDED.active_symbols,
                regime = EXCLUDED.regime,
                ai_suggestions = EXCLUDED.ai_suggestions,
                ai_additions = EXCLUDED.ai_additions,
                ai_removals = EXCLUDED.ai_removals,
                screened_at = EXCLUDED.screened_at
        """
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    query,
                    universe.date,
                    universe.active_symbols,
                    universe.regime_at_screening.value,
                    universe.master_universe_size,
                    universe.passed_liquidity,
                    universe.passed_trend,
                    json.dumps([s.to_dict() for s in universe.ai_suggestions]),
                    universe.ai_additions,
                    universe.ai_removals,
                    universe.screened_at,
                )
            logger.info(f"Persisted universe for {universe.date}")
        except Exception as e:
            logger.error(f"Error persisting universe: {e}")
    
    async def load_universe_for_date(self, target_date: date) -> Optional[DailyUniverse]:
        """Cargar universo de una fecha específica desde BD."""
        if not self.db_pool:
            return None
        
        query = """
            SELECT * FROM universe.daily_universe
            WHERE screening_date = $1
        """
        
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(query, target_date)
                
            if not row:
                return None
            
            return DailyUniverse(
                date=row["screening_date"],
                active_symbols=row["active_symbols"],
                regime_at_screening=MarketRegime(row["regime"]),
                master_universe_size=row["master_universe_size"],
                passed_liquidity=row["passed_liquidity"],
                passed_trend=row["passed_trend"],
                ai_suggestions=[
                    AISuggestion.from_dict(s) 
                    for s in json.loads(row["ai_suggestions"])
                ],
                ai_additions=row["ai_additions"],
                ai_removals=row["ai_removals"],
                screened_at=row["screened_at"],
            )
        except Exception as e:
            logger.error(f"Error loading universe for {target_date}: {e}")
            return None
    
    # =========================================================================
    # Utilidades
    # =========================================================================
    
    def get_symbols_by_asset_type(self, asset_type: str) -> list[str]:
        """
        Obtener símbolos activos filtrados por tipo de activo.
        
        Args:
            asset_type: 'stock', 'etf', 'forex', 'crypto'
        """
        active = set(self.active_symbols)
        return [
            s.ticker for s in self.registry.get_by_asset_type(asset_type)
            if s.ticker in active
        ]
    
    def get_symbols_by_market(self, market: str) -> list[str]:
        """
        Obtener símbolos activos filtrados por mercado.
        
        Args:
            market: 'EU', 'US', 'FOREX', 'CRYPTO'
        """
        active = set(self.active_symbols)
        return [
            s.ticker for s in self.registry.get_by_market(market)
            if s.ticker in active
        ]
    
    def is_symbol_active(self, symbol: str) -> bool:
        """Verificar si un símbolo está en el universo activo."""
        return symbol in self.active_symbols
    
    def get_screening_summary(self) -> dict:
        """Obtener resumen del último screening."""
        if not self._current_universe:
            return {"status": "no_screening"}
        
        u = self._current_universe
        return {
            "date": u.date.isoformat(),
            "regime": u.regime_at_screening.value,
            "active_count": len(u.active_symbols),
            "master_size": u.master_universe_size,
            "filter_funnel": {
                "master": u.master_universe_size,
                "after_liquidity": u.passed_liquidity,
                "after_trend": u.passed_trend,
                "final": len(u.active_symbols),
            },
            "ai_impact": {
                "suggestions": len(u.ai_suggestions),
                "additions": len(u.ai_additions),
                "removals": len(u.ai_removals),
            },
            "screened_at": u.screened_at.isoformat(),
        }
