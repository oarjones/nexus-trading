"""
Tests de integración: UniverseManager + StrategyRunner

Verifica que el flujo completo funciona:
1. UniverseManager filtra símbolos
2. StrategyRunner inyecta símbolos a estrategias
3. Estrategias usan símbolos dinámicos
"""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.universe import UniverseManager, AISuggestion, SuggestionType
from src.strategies.runner import StrategyRunner
from src.strategies.swing.etf_momentum import ETFMomentumStrategy
from src.strategies.interfaces import MarketRegime, MarketContext


class TestUniverseStrategyIntegration:
    """Tests de integración Universe + Strategy."""
    
    @pytest.fixture
    def mock_symbol_registry(self):
        """Mock del SymbolRegistry con símbolos de prueba."""
        registry = MagicMock()
        
        mock_symbols = [
            MagicMock(ticker="SPY", asset_type="etf", sector="broad_market", 
                     liquidity_tier=1, defensive=False),
            MagicMock(ticker="QQQ", asset_type="etf", sector="technology", 
                     liquidity_tier=1, defensive=False),
            MagicMock(ticker="AAPL", asset_type="stock", sector="technology", 
                     liquidity_tier=1, defensive=False),
            MagicMock(ticker="NVDA", asset_type="stock", sector="semiconductors", 
                     liquidity_tier=1, defensive=False),
            MagicMock(ticker="TLT", asset_type="etf", sector="bonds", 
                     liquidity_tier=1, defensive=True),
        ]
        
        registry.get_all.return_value = mock_symbols
        registry.count.return_value = len(mock_symbols)
        registry.get_by_ticker.side_effect = lambda t: next(
            (s for s in mock_symbols if s.ticker == t), None
        )
        
        return registry
    
    @pytest.fixture
    def mock_data_provider(self):
        """Mock del DataProvider."""
        provider = AsyncMock()
        
        quotes = {
            "SPY": {"price": 450.0, "avg_volume_20d": 50_000_000},
            "QQQ": {"price": 380.0, "avg_volume_20d": 30_000_000},
            "AAPL": {"price": 175.0, "avg_volume_20d": 60_000_000},
            "NVDA": {"price": 500.0, "avg_volume_20d": 40_000_000},
            "TLT": {"price": 95.0, "avg_volume_20d": 15_000_000},
        }
        
        indicators = {
            "SPY": {"price": 450.0, "sma_200": 420.0, "atr_14": 8.0},
            "QQQ": {"price": 380.0, "sma_200": 350.0, "atr_14": 10.0},
            "AAPL": {"price": 175.0, "sma_200": 160.0, "atr_14": 4.0},
            "NVDA": {"price": 500.0, "sma_200": 450.0, "atr_14": 15.0},
            "TLT": {"price": 95.0, "sma_200": 100.0, "atr_14": 2.0},
        }
        
        provider.get_quote.side_effect = lambda s: quotes.get(s, {})
        provider.get_indicators.side_effect = lambda s, _: indicators.get(s, {})
        
        return provider
    
    @pytest.fixture
    def universe_manager(self, mock_symbol_registry, mock_data_provider):
        """UniverseManager configurado."""
        return UniverseManager(
            symbol_registry=mock_symbol_registry,
            data_provider=mock_data_provider,
            db_pool=None,
        )
    
    def test_strategy_uses_hardcoded_without_universe(self):
        """Sin UniverseManager, estrategia usa símbolos hardcodeados."""
        strategy = ETFMomentumStrategy()
        
        # Sin set_universe, debe usar los hardcodeados
        assert strategy._dynamic_symbols is None
        assert len(strategy.active_symbols) == 12  # 6 EU + 6 US hardcoded
        assert "SPY" in strategy.active_symbols
    
    def test_strategy_uses_dynamic_with_set_universe(self):
        """Con set_universe, estrategia usa símbolos dinámicos."""
        strategy = ETFMomentumStrategy()
        
        # Inyectar universo dinámico
        dynamic_symbols = ["SPY", "QQQ", "NVDA"]
        strategy.set_universe(dynamic_symbols)
        
        # Ahora debe usar los dinámicos
        assert strategy._dynamic_symbols is not None
        assert strategy.active_symbols == dynamic_symbols
        assert len(strategy.active_symbols) == 3
    
    def test_strategy_clears_universe(self):
        """clear_universe vuelve a usar hardcodeados."""
        strategy = ETFMomentumStrategy()
        
        # Inyectar y luego limpiar
        strategy.set_universe(["SPY", "QQQ"])
        assert len(strategy.active_symbols) == 2
        
        strategy.clear_universe()
        assert strategy._dynamic_symbols is None
        assert len(strategy.active_symbols) == 12  # Vuelve a hardcoded
    
    @pytest.mark.asyncio
    async def test_universe_manager_filters_correctly(self, universe_manager):
        """UniverseManager filtra símbolos según régimen."""
        # En BULL, TLT debería ser excluido (precio < SMA200)
        universe = await universe_manager.run_daily_screening(MarketRegime.BULL)
        
        assert "SPY" in universe.active_symbols
        assert "QQQ" in universe.active_symbols
        assert "NVDA" in universe.active_symbols
        assert "TLT" not in universe.active_symbols  # Filtrado en BULL
    
    @pytest.mark.asyncio
    async def test_ai_suggestion_adds_symbol(self, universe_manager):
        """AI Agent puede sugerir añadir símbolos."""
        # Primera ejecución
        await universe_manager.run_daily_screening(MarketRegime.BULL, force=True)
        initial_count = len(universe_manager.active_symbols)
        
        # AI sugiere añadir
        suggestion = AISuggestion(
            symbol="AAPL",
            suggestion_type=SuggestionType.ADD,
            reason="Strong momentum breakout",
            confidence=0.85,
        )
        universe_manager.add_suggestion(suggestion)
        
        # Re-ejecutar screening
        universe = await universe_manager.run_daily_screening(
            MarketRegime.BULL, force=True
        )
        
        # AAPL ya estaba, así que el count no debería cambiar mucho
        # pero la sugerencia debería estar procesada
        assert "AAPL" in universe.active_symbols
        assert len(universe.ai_suggestions) == 1
    
    @pytest.mark.asyncio
    async def test_ai_suggestion_removes_symbol(self, universe_manager):
        """AI Agent puede sugerir quitar símbolos."""
        # Primera ejecución
        await universe_manager.run_daily_screening(MarketRegime.BULL, force=True)
        assert "SPY" in universe_manager.active_symbols
        
        # AI sugiere quitar SPY
        suggestion = AISuggestion(
            symbol="SPY",
            suggestion_type=SuggestionType.REMOVE,
            reason="Overextended, expecting pullback",
            confidence=0.80,
        )
        universe_manager.add_suggestion(suggestion)
        
        # Re-ejecutar screening
        universe = await universe_manager.run_daily_screening(
            MarketRegime.BULL, force=True
        )
        
        # SPY debería haber sido removido
        assert "SPY" not in universe.active_symbols
        assert "SPY" in universe.ai_removals
    
    @pytest.mark.asyncio
    async def test_full_integration_flow(
        self, 
        universe_manager, 
        mock_symbol_registry
    ):
        """Test del flujo completo: Universe -> Runner -> Strategy."""
        # 1. Crear estrategia
        strategy = ETFMomentumStrategy()
        assert len(strategy.active_symbols) == 12  # Hardcoded inicialmente
        
        # 2. Ejecutar screening
        await universe_manager.run_daily_screening(MarketRegime.BULL)
        active_symbols = universe_manager.active_symbols
        
        # 3. Simular lo que hace StrategyRunner._inject_universe_to_strategies
        strategy.set_universe(active_symbols)
        
        # 4. Verificar que la estrategia ahora usa símbolos dinámicos
        assert strategy._dynamic_symbols is not None
        assert strategy.active_symbols == active_symbols
        assert len(strategy.active_symbols) < 12  # Menos que hardcoded
        
        # 5. Verificar métricas
        metrics = strategy.get_metrics()
        assert metrics["using_dynamic_universe"] is True
    
    @pytest.mark.asyncio
    async def test_runner_with_universe_manager(self, universe_manager):
        """StrategyRunner integra UniverseManager correctamente."""
        # Mock del MCP client
        mock_mcp = AsyncMock()
        mock_mcp.call.return_value = {
            "regime": "BULL",
            "confidence": 0.75,
            "probabilities": {"BULL": 0.75, "BEAR": 0.10, "SIDEWAYS": 0.10, "VOLATILE": 0.05}
        }
        
        # Crear runner con UniverseManager
        runner = StrategyRunner(
            mcp_client=mock_mcp,
            universe_manager=universe_manager
        )
        
        # Verificar que tiene referencia al UniverseManager
        assert runner.universe_manager is not None
        
        # Verificar métricas incluyen info del universe
        metrics = runner.get_metrics()
        assert "universe" in metrics
        assert metrics["universe"]["enabled"] is True


class TestUniverseManagerScreeningSummary:
    """Tests del resumen de screening."""
    
    @pytest.fixture
    def universe_manager(self):
        """UniverseManager con mocks básicos."""
        registry = MagicMock()
        registry.get_all.return_value = [
            MagicMock(ticker="SPY", liquidity_tier=1, defensive=False),
            MagicMock(ticker="QQQ", liquidity_tier=1, defensive=False),
        ]
        registry.count.return_value = 2
        registry.get_by_ticker.return_value = MagicMock()
        
        provider = AsyncMock()
        provider.get_quote.return_value = {"price": 100, "avg_volume_20d": 1_000_000}
        provider.get_indicators.return_value = {"price": 100, "sma_200": 95, "atr_14": 2}
        
        return UniverseManager(registry, provider)
    
    def test_no_screening_summary(self, universe_manager):
        """Sin screening, summary indica no_screening."""
        summary = universe_manager.get_screening_summary()
        assert summary["status"] == "no_screening"
    
    @pytest.mark.asyncio
    async def test_screening_summary_has_funnel(self, universe_manager):
        """Con screening, summary incluye funnel de filtros."""
        await universe_manager.run_daily_screening(MarketRegime.BULL)
        
        summary = universe_manager.get_screening_summary()
        
        assert "date" in summary
        assert "regime" in summary
        assert "filter_funnel" in summary
        assert "ai_impact" in summary
        assert summary["filter_funnel"]["master"] == 2
