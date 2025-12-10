"""
Tests for Universe Manager

Verifica la funcionalidad del gestor de universo de símbolos.
"""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.universe import (
    UniverseManager,
    DailyUniverse,
    AISuggestion,
    SuggestionType,
    SuggestionStatus,
)
from src.strategies.interfaces import MarketRegime


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_symbol_registry():
    """Mock del SymbolRegistry con símbolos de prueba."""
    registry = MagicMock()
    
    # Crear símbolos mock
    mock_symbols = [
        MagicMock(
            ticker="SPY",
            name="SPDR S&P 500",
            market="US",
            asset_type="etf",
            sector="broad_market",
            liquidity_tier=1,
            defensive=False,
        ),
        MagicMock(
            ticker="QQQ",
            name="Invesco QQQ",
            market="US",
            asset_type="etf",
            sector="technology",
            liquidity_tier=1,
            defensive=False,
        ),
        MagicMock(
            ticker="AAPL",
            name="Apple Inc.",
            market="US",
            asset_type="stock",
            sector="technology",
            liquidity_tier=1,
            defensive=False,
        ),
        MagicMock(
            ticker="TLT",
            name="iShares 20+ Year Treasury",
            market="US",
            asset_type="etf",
            sector="bonds",
            liquidity_tier=1,
            defensive=True,
        ),
        MagicMock(
            ticker="GLD",
            name="SPDR Gold Shares",
            market="US",
            asset_type="etf",
            sector="gold",
            liquidity_tier=1,
            defensive=True,
        ),
    ]
    
    registry.get_all.return_value = mock_symbols
    registry.count.return_value = len(mock_symbols)
    
    def get_by_ticker(ticker):
        for s in mock_symbols:
            if s.ticker == ticker:
                return s
        return None
    
    registry.get_by_ticker.side_effect = get_by_ticker
    registry.get_by_asset_type.side_effect = lambda t: [s for s in mock_symbols if s.asset_type == t]
    
    return registry


@pytest.fixture
def mock_data_provider():
    """Mock del DataProvider para datos de mercado."""
    provider = AsyncMock()
    
    # Datos de quote por símbolo
    quotes = {
        "SPY": {"price": 450.0, "avg_volume_20d": 50_000_000, "bid": 449.98, "ask": 450.02},
        "QQQ": {"price": 380.0, "avg_volume_20d": 30_000_000, "bid": 379.95, "ask": 380.05},
        "AAPL": {"price": 175.0, "avg_volume_20d": 60_000_000, "bid": 174.98, "ask": 175.02},
        "TLT": {"price": 95.0, "avg_volume_20d": 15_000_000, "bid": 94.98, "ask": 95.02},
        "GLD": {"price": 185.0, "avg_volume_20d": 10_000_000, "bid": 184.95, "ask": 185.05},
    }
    
    # Indicadores por símbolo
    indicators = {
        "SPY": {"price": 450.0, "sma_200": 420.0, "atr_14": 8.0},
        "QQQ": {"price": 380.0, "sma_200": 350.0, "atr_14": 10.0},
        "AAPL": {"price": 175.0, "sma_200": 160.0, "atr_14": 4.0},
        "TLT": {"price": 95.0, "sma_200": 100.0, "atr_14": 2.0},
        "GLD": {"price": 185.0, "sma_200": 175.0, "atr_14": 3.0},
    }
    
    provider.get_quote.side_effect = lambda s: quotes.get(s, {})
    provider.get_indicators.side_effect = lambda s, _: indicators.get(s, {})
    
    return provider


@pytest.fixture
def universe_manager(mock_symbol_registry, mock_data_provider):
    """UniverseManager con mocks inyectados."""
    return UniverseManager(
        symbol_registry=mock_symbol_registry,
        data_provider=mock_data_provider,
        db_pool=None,  # Sin BD para tests
    )


# =============================================================================
# Tests: Inicialización
# =============================================================================

class TestUniverseManagerInit:
    """Tests de inicialización del UniverseManager."""
    
    def test_init_with_registry(self, universe_manager):
        """Debe inicializarse correctamente con el registry."""
        assert universe_manager.registry is not None
        assert universe_manager.data_provider is not None
        assert universe_manager._current_universe is None
        assert universe_manager._pending_suggestions == []
    
    def test_default_config(self, universe_manager):
        """Debe tener configuración por defecto."""
        assert "min_avg_volume_shares" in universe_manager.config
        assert "max_spread_pct" in universe_manager.config
        assert "max_ai_suggestions_per_day" in universe_manager.config
    
    def test_active_symbols_empty_initially(self, universe_manager):
        """Debe retornar lista vacía si no hay screening."""
        assert universe_manager.active_symbols == []


# =============================================================================
# Tests: Screening Diario
# =============================================================================

class TestDailyScreening:
    """Tests del proceso de screening diario."""
    
    @pytest.mark.asyncio
    async def test_run_daily_screening_bull(self, universe_manager):
        """Debe filtrar símbolos correctamente en régimen BULL."""
        universe = await universe_manager.run_daily_screening(MarketRegime.BULL)
        
        assert universe is not None
        assert universe.date == date.today()
        assert universe.regime_at_screening == MarketRegime.BULL
        assert len(universe.active_symbols) > 0
        
        # En BULL, TLT debería ser excluido (precio < SMA200)
        # porque TLT.price=95 < TLT.sma_200=100
        assert "TLT" not in universe.active_symbols
        
        # SPY, QQQ, AAPL, GLD deberían estar (precio > SMA200)
        assert "SPY" in universe.active_symbols
        assert "QQQ" in universe.active_symbols
    
    @pytest.mark.asyncio
    async def test_run_daily_screening_sideways(self, universe_manager):
        """En SIDEWAYS no se aplica filtro de tendencia."""
        universe = await universe_manager.run_daily_screening(MarketRegime.SIDEWAYS)
        
        # En SIDEWAYS, TLT debería estar (sin filtro de tendencia)
        assert "TLT" in universe.active_symbols
    
    @pytest.mark.asyncio
    async def test_screening_updates_current_universe(self, universe_manager):
        """El screening debe actualizar el universo actual."""
        assert universe_manager._current_universe is None
        
        await universe_manager.run_daily_screening(MarketRegime.BULL)
        
        assert universe_manager._current_universe is not None
        assert len(universe_manager.active_symbols) > 0
    
    @pytest.mark.asyncio
    async def test_screening_records_filter_funnel(self, universe_manager):
        """El screening debe registrar el funnel de filtros."""
        universe = await universe_manager.run_daily_screening(MarketRegime.BULL)
        
        assert universe.master_universe_size == 5
        assert universe.passed_liquidity > 0
        assert universe.passed_trend > 0


# =============================================================================
# Tests: AI Suggestions
# =============================================================================

class TestAISuggestions:
    """Tests del sistema de sugerencias del AI."""
    
    def test_add_suggestion(self, universe_manager):
        """Debe poder añadir sugerencias válidas."""
        suggestion = AISuggestion(
            symbol="NVDA",
            suggestion_type=SuggestionType.ADD,
            reason="Strong momentum in AI sector",
            confidence=0.85,
        )
        
        result = universe_manager.add_suggestion(suggestion)
        
        assert result is True
        assert len(universe_manager._pending_suggestions) == 1
    
    def test_add_suggestion_from_dict(self, universe_manager):
        """Debe poder añadir sugerencias desde diccionario."""
        data = {
            "symbol": "MSFT",
            "type": "add",
            "reason": "Cloud growth momentum",
            "confidence": 0.80,
        }
        
        result = universe_manager.add_suggestion_from_dict(data)
        
        assert result is True
        assert universe_manager._pending_suggestions[0].symbol == "MSFT"
    
    def test_reject_low_confidence(self, universe_manager):
        """Debe rechazar sugerencias con confianza baja."""
        suggestion = AISuggestion(
            symbol="PENNY",
            suggestion_type=SuggestionType.ADD,
            reason="Random pick",
            confidence=0.3,  # Por debajo del umbral 0.6
        )
        
        result = universe_manager.add_suggestion(suggestion)
        
        assert result is False
        # La sugerencia se guarda pero con estado REJECTED
        assert universe_manager._pending_suggestions[0].status == SuggestionStatus.REJECTED
    
    def test_suggestion_limit_per_day(self, universe_manager):
        """Debe respetar el límite diario de sugerencias."""
        # Cambiar límite a 2 para test
        universe_manager.config["max_ai_suggestions_per_day"] = 2
        
        # Primera y segunda: OK
        universe_manager.add_suggestion(AISuggestion(
            symbol="A", suggestion_type=SuggestionType.ADD,
            reason="Test 1", confidence=0.7
        ))
        universe_manager.add_suggestion(AISuggestion(
            symbol="B", suggestion_type=SuggestionType.ADD,
            reason="Test 2", confidence=0.7
        ))
        
        # Tercera: debería fallar
        result = universe_manager.add_suggestion(AISuggestion(
            symbol="C", suggestion_type=SuggestionType.ADD,
            reason="Test 3", confidence=0.7
        ))
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_process_add_suggestion(self, universe_manager):
        """Las sugerencias ADD deben procesarse en el screening."""
        # Añadir sugerencia
        universe_manager.add_suggestion(AISuggestion(
            symbol="AAPL",  # Símbolo que existe en el registry mock
            suggestion_type=SuggestionType.ADD,
            reason="Strong momentum",
            confidence=0.85,
        ))
        
        # Ejecutar screening
        universe = await universe_manager.run_daily_screening(MarketRegime.BULL)
        
        # Verificar que se procesó
        assert len(universe.ai_suggestions) == 1
        # Si AAPL ya pasaba los filtros, debería seguir ahí
        assert "AAPL" in universe.active_symbols
    
    @pytest.mark.asyncio
    async def test_process_remove_suggestion(self, universe_manager):
        """Las sugerencias REMOVE deben procesarse en el screening."""
        # Primero hacer un screening para tener universo
        await universe_manager.run_daily_screening(MarketRegime.BULL, force=True)
        
        # Añadir sugerencia de REMOVE
        universe_manager.add_suggestion(AISuggestion(
            symbol="SPY",
            suggestion_type=SuggestionType.REMOVE,
            reason="Overextended, expecting pullback",
            confidence=0.75,
        ))
        
        # Re-ejecutar screening
        universe = await universe_manager.run_daily_screening(MarketRegime.BULL, force=True)
        
        # SPY debería haber sido removido
        assert "SPY" not in universe.active_symbols
        assert "SPY" in universe.ai_removals


# =============================================================================
# Tests: Utilidades
# =============================================================================

class TestUtilities:
    """Tests de métodos de utilidad."""
    
    @pytest.mark.asyncio
    async def test_get_screening_summary(self, universe_manager):
        """Debe generar resumen del screening."""
        # Sin screening
        summary = universe_manager.get_screening_summary()
        assert summary["status"] == "no_screening"
        
        # Con screening
        await universe_manager.run_daily_screening(MarketRegime.BULL)
        summary = universe_manager.get_screening_summary()
        
        assert "date" in summary
        assert "regime" in summary
        assert "active_count" in summary
        assert "filter_funnel" in summary
        assert "ai_impact" in summary
    
    @pytest.mark.asyncio
    async def test_is_symbol_active(self, universe_manager):
        """Debe verificar si un símbolo está activo."""
        assert universe_manager.is_symbol_active("SPY") is False
        
        await universe_manager.run_daily_screening(MarketRegime.BULL)
        
        assert universe_manager.is_symbol_active("SPY") is True
        assert universe_manager.is_symbol_active("UNKNOWN") is False


# =============================================================================
# Tests: DailyUniverse
# =============================================================================

class TestDailyUniverse:
    """Tests del dataclass DailyUniverse."""
    
    def test_to_dict_serialization(self):
        """Debe serializar correctamente a diccionario."""
        universe = DailyUniverse(
            date=date(2025, 1, 15),
            active_symbols=["SPY", "QQQ", "AAPL"],
            regime_at_screening=MarketRegime.BULL,
            master_universe_size=100,
            passed_liquidity=80,
            passed_trend=50,
        )
        
        data = universe.to_dict()
        
        assert data["date"] == "2025-01-15"
        assert data["active_symbols"] == ["SPY", "QQQ", "AAPL"]
        assert data["regime"] == "BULL"


# =============================================================================
# Tests: AISuggestion
# =============================================================================

class TestAISuggestion:
    """Tests del dataclass AISuggestion."""
    
    def test_to_dict_serialization(self):
        """Debe serializar correctamente a diccionario."""
        suggestion = AISuggestion(
            symbol="NVDA",
            suggestion_type=SuggestionType.ADD,
            reason="Strong AI momentum",
            confidence=0.85,
        )
        
        data = suggestion.to_dict()
        
        assert data["symbol"] == "NVDA"
        assert data["type"] == "add"
        assert data["confidence"] == 0.85
    
    def test_from_dict_deserialization(self):
        """Debe deserializar correctamente desde diccionario."""
        data = {
            "symbol": "MSFT",
            "type": "remove",
            "reason": "Losing momentum",
            "confidence": 0.7,
            "suggested_at": "2025-01-15T10:30:00+00:00",
            "status": "pending",
        }
        
        suggestion = AISuggestion.from_dict(data)
        
        assert suggestion.symbol == "MSFT"
        assert suggestion.suggestion_type == SuggestionType.REMOVE
        assert suggestion.status == SuggestionStatus.PENDING
