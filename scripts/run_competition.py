#!/usr/bin/env python3
"""
Script Principal de Ejecución del Sistema de Competición.

Este script:
1. Carga la configuración
2. Inicializa el orquestador
3. Ejecuta la sesión diaria
4. Mantiene el monitor de posiciones activo
5. Procesa el fin del día

Uso:
    # Ejecutar sesión diaria
    python scripts/run_competition.py
    
    # Ejecutar con configuración custom
    python scripts/run_competition.py --config path/to/config.yaml
    
    # Solo mostrar estado
    python scripts/run_competition.py --status
    
    # Reiniciar competición
    python scripts/run_competition.py --reset
"""

import asyncio
import argparse
import logging
import signal
import sys
from pathlib import Path
from datetime import datetime, timezone
import yaml

# Setup path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.trading.orchestrator import CompetitionOrchestrator, TradingSessionConfig
from src.agents.llm.interfaces import (
    AgentContext, RegimeInfo, MarketContext,
    PortfolioSummary, PortfolioPosition, RiskLimits,
    AutonomyLevel
)


# =============================================================================
# CONFIGURACIÓN DE LOGGING
# =============================================================================

def setup_logging(config: dict):
    """Configura el sistema de logging."""
    log_config = config.get('logging', {})
    
    level = getattr(logging, log_config.get('level', 'INFO'))
    format_str = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    handlers = [logging.StreamHandler()]
    
    if log_config.get('file_enabled', False):
        log_path = Path(log_config.get('file_path', './logs/competition.log'))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))
    
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=handlers
    )


# =============================================================================
# CARGA DE CONFIGURACIÓN
# =============================================================================

def load_config(config_path: str = None) -> dict:
    """Carga la configuración desde YAML."""
    if config_path is None:
        config_path = project_root / 'config' / 'competition.yaml'
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def config_to_session_config(config: dict) -> TradingSessionConfig:
    """Convierte config YAML a TradingSessionConfig."""
    from datetime import time as dt_time
    
    schedule = config.get('schedule', {})
    monitoring = config.get('monitoring', {})
    orders = config.get('orders', {})
    risk = config.get('risk', {})
    storage = config.get('storage', {})
    
    def parse_time(time_str: str) -> dt_time:
        parts = time_str.split(':')
        return dt_time(int(parts[0]), int(parts[1]))
    
    return TradingSessionConfig(
        session_start_time=parse_time(schedule.get('session_start', '10:00')),
        trading_window_end=parse_time(schedule.get('trading_window_end', '11:30')),
        market_close_time=parse_time(schedule.get('market_close', '16:00')),
        monitor_interval_minutes=monitoring.get('interval_minutes', 5),
        entry_tolerance_pct=orders.get('entry_tolerance_pct', 1.0),
        order_expiry_hours=orders.get('limit_order_expiry_hours', 2),
        default_order_type=orders.get('default_type', 'LIMIT'),
        max_position_pct=risk.get('max_position_pct', 20.0),
        max_positions=risk.get('max_positions', 5),
        max_daily_trades=risk.get('max_daily_trades', 3),
        max_stop_loss_pct=risk.get('max_stop_loss_pct', 3.0),
        state_dir=storage.get('base_dir', './data/competition')
    )


# =============================================================================
# CONSTRUCCIÓN DE CONTEXTO
# =============================================================================

async def build_context(config: dict, orchestrator: CompetitionOrchestrator) -> AgentContext:
    """
    Construye el contexto para la sesión.
    
    En una implementación real, esto obtendría datos de:
    - MCP Market Data (precios, volumen)
    - MCP ML Models (régimen)
    - Portfolio Manager (posiciones, cash)
    
    Por ahora usa datos de ejemplo/mock.
    """
    logger = logging.getLogger(__name__)
    
    # TODO: Integrar con MCP servers reales
    # Por ahora, datos de ejemplo
    
    logger.info("Building context for session...")
    
    # Obtener posiciones del monitor
    monitored_positions = orchestrator.monitor.get_positions() if orchestrator.monitor else []
    
    # Convertir a PortfolioPosition
    positions = tuple(
        PortfolioPosition(
            symbol=p.symbol,
            quantity=p.quantity,
            avg_entry_price=p.entry_price,
            current_price=p.current_price,
            unrealized_pnl=(p.current_price - p.entry_price) * p.quantity,
            unrealized_pnl_pct=p.unrealized_pnl_pct,
            holding_days=0  # TODO: Calcular días
        )
        for p in monitored_positions
    )
    
    # Calcular valores del portfolio
    initial_capital = config.get('competition', {}).get('initial_capital', 25000.0)
    invested_value = sum(p.current_price * p.quantity for p in positions)
    # TODO: Obtener cash real del PortfolioManager
    cash_available = initial_capital - invested_value
    total_value = cash_available + invested_value
    
    context = AgentContext(
        context_id=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        timestamp=datetime.now(timezone.utc),
        regime=RegimeInfo(
            regime="BULL",  # TODO: Obtener de MCP ML Models
            confidence=0.72,
            probabilities={"BULL": 0.72, "BEAR": 0.08, "SIDEWAYS": 0.15, "VOLATILE": 0.05},
            model_id="hmm_v1",
            days_in_regime=5
        ),
        market=MarketContext(
            spy_change_pct=0.0,  # TODO: Obtener de MCP Market Data
            qqq_change_pct=0.0,
            vix_level=15.0,
            vix_change_pct=0.0,
            market_breadth=0.5,
            sector_rotation={}
        ),
        portfolio=PortfolioSummary(
            total_value=total_value,
            cash_available=cash_available,
            invested_value=invested_value,
            positions=positions,
            daily_pnl=0.0,
            daily_pnl_pct=0.0,
            total_pnl=total_value - initial_capital,
            total_pnl_pct=((total_value - initial_capital) / initial_capital) * 100
        ),
        watchlist=(),  # El agente usará web search
        risk_limits=RiskLimits(
            max_position_pct=config.get('risk', {}).get('max_position_pct', 20.0),
            max_portfolio_risk_pct=2.0,
            max_daily_trades=config.get('risk', {}).get('max_daily_trades', 3),
            max_daily_loss_pct=config.get('risk', {}).get('max_daily_loss_pct', 5.0),
            current_daily_trades=orchestrator._today_trades,
            current_daily_pnl_pct=0.0
        ),
        autonomy_level=AutonomyLevel.MODERATE,
        notes=""
    )
    
    return context


# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================

async def run_session(config: dict, orchestrator: CompetitionOrchestrator):
    """Ejecuta una sesión de trading."""
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("🏆 NEXUS TRADING COMPETITION - DAILY SESSION")
    logger.info("=" * 60)
    
    # 1. Construir contexto
    context = await build_context(config, orchestrator)
    
    # 2. Ejecutar sesión
    result = await orchestrator.run_daily_session(context)
    
    # 3. Mostrar resultado
    logger.info("\n" + "=" * 60)
    logger.info("📊 SESSION RESULTS")
    logger.info("=" * 60)
    logger.info(f"Competition Day: {result.competition_day}")
    logger.info(f"Signals Generated: {result.signals_generated}")
    logger.info(f"Orders Placed: {result.orders_placed}")
    logger.info(f"Positions Closed: {result.positions_closed}")
    
    if result.decision:
        logger.info(f"Market View: {result.decision.market_view.value}")
        logger.info(f"Confidence: {result.decision.confidence:.0%}")
    
    if result.errors:
        logger.warning(f"Errors: {result.errors}")
    
    return result


async def show_status(orchestrator: CompetitionOrchestrator):
    """Muestra el estado actual del sistema."""
    status = orchestrator.get_status()
    
    print("\n" + "=" * 60)
    print("📊 COMPETITION STATUS")
    print("=" * 60)
    print(f"Initialized: {status['initialized']}")
    print(f"Competition Day: {status['competition_day']}")
    print(f"Today's Trades: {status['today_trades']}/{status['max_daily_trades']}")
    print(f"Positions Monitored: {status['positions_monitored']}")
    print(f"Pending Orders: {status['pending_orders']}")
    
    if status['competition_status']:
        cs = status['competition_status']
        print(f"\n📈 METRICS:")
        print(f"   Total Return: {cs['metrics']['total_return']:.2f}%")
        print(f"   Sharpe Ratio: {cs['metrics']['sharpe']:.2f}")
        print(f"   Max Drawdown: {cs['metrics']['max_drawdown']:.2f}%")
        print(f"   Win Rate: {cs['metrics']['win_rate']:.1f}%")
        print(f"   Total Trades: {cs['metrics']['total_trades']}")
        print(f"   Score: {cs['score']:.1f}")
    
    if status['monitor_stats']:
        ms = status['monitor_stats']
        print(f"\n📡 MONITOR STATS:")
        print(f"   SL Triggered: {ms['stop_losses_triggered']}")
        print(f"   TP Triggered: {ms['take_profits_triggered']}")
        print(f"   Orders Filled: {ms['orders_filled']}")
        print(f"   Orders Expired: {ms['orders_expired']}")


async def run_monitor_only(orchestrator: CompetitionOrchestrator):
    """Ejecuta solo el monitor de posiciones (sin sesión)."""
    logger = logging.getLogger(__name__)
    
    logger.info("Running position monitor only...")
    logger.info("Press Ctrl+C to stop")
    
    # Mantener el monitor corriendo
    try:
        while True:
            await asyncio.sleep(60)
            stats = orchestrator.monitor.get_stats()
            logger.debug(f"Monitor stats: {stats}")
    except asyncio.CancelledError:
        pass


async def main():
    """Función principal."""
    parser = argparse.ArgumentParser(description='Nexus Trading Competition System')
    parser.add_argument('--config', type=str, help='Path to config file')
    parser.add_argument('--status', action='store_true', help='Show current status')
    parser.add_argument('--reset', action='store_true', help='Reset competition')
    parser.add_argument('--monitor-only', action='store_true', help='Run monitor only')
    parser.add_argument('--end-of-day', action='store_true', help='Process end of day')
    
    args = parser.parse_args()
    
    # Cargar configuración
    config = load_config(args.config)
    setup_logging(config)
    
    logger = logging.getLogger(__name__)
    
    # Crear orquestador
    session_config = config_to_session_config(config)
    orchestrator = CompetitionOrchestrator(config=session_config)
    
    # Manejar señales de terminación
    def handle_shutdown(sig, frame):
        logger.info("Shutdown signal received...")
        asyncio.create_task(orchestrator.shutdown())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        # Inicializar
        await orchestrator.initialize()
        
        if args.reset:
            logger.info("Resetting competition...")
            orchestrator.agent.reset_competition()
            logger.info("Competition reset complete")
            return
        
        if args.status:
            await show_status(orchestrator)
            return
        
        if args.end_of_day:
            await orchestrator.end_of_day()
            return
        
        if args.monitor_only:
            await run_monitor_only(orchestrator)
            return
        
        # Ejecutar sesión normal
        await run_session(config, orchestrator)
        
        # Mantener monitor activo hasta que el usuario detenga
        logger.info("\n📡 Monitor running in background. Press Ctrl+C to stop.")
        
        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise
    finally:
        await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
