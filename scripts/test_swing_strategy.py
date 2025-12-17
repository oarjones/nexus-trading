"""
Script de prueba 'Realista' para la Estrategia Swing con Agente IA.

Este script simula la ejecución de la estrategia `AIAgentStrategy` en un entorno 
controlado pero lo más cercano posible a la realidad:
1. Carga la configuración real desde strategies.yaml.
2. Inicializa el Agente con el modelo LLM especificado (Claude Sonnet 4.5).
3. Usa un proveedor de portfolio 'Paper' para no arriesgar capital real.
4. Intenta conectar con servidores MCP para datos de mercado (con fallback a datos simulados si fallan).
5. Ejecuta el ciclo completo de `generate_signals` e imprime el razonamiento del LLM.

Uso:
    python scripts/test_swing_strategy.py
"""

import asyncio
import logging
import os
import sys
import yaml
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Añadir directorio raíz al path para imports
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Cargar variables de entorno (.env)
load_dotenv(project_root / ".env")

# Configurar Logging para ver detalles
log_filename = "test_strategy_execution.log"
file_handler = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Root logger config
logging.basicConfig(
    level=logging.INFO, # Default level
    handlers=[file_handler, console_handler]
)

# Set specific loggers to DEBUG
logging.getLogger("src.agents.llm.agents.claude_agent").setLevel(logging.DEBUG)
logging.getLogger("src.agents.llm.web_search").setLevel(logging.DEBUG)

logger = logging.getLogger("TestSwingStrategy")

# Imports del sistema
from src.strategies.swing.ai_agent_strategy import AIAgentStrategy
from src.strategies.interfaces import MarketContext, MarketRegime
from src.trading.paper.provider import PaperPortfolioProvider, PaperPortfolioManager

async def run_test():
    print("="*80)
    print(" INICIANDO PRUEBA REALISTA DE AI AGENT STRATEGY")
    print("="*80)

    # 1. Cargar Configuración Real
    config_path = project_root / "config" / "strategies.yaml"
    print(f"\n[1] Cargando configuración desde: {config_path}")
    
    if not config_path.exists():
        print(f"❌ Error: No se encuentra {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        full_config = yaml.safe_load(f)
    
    # Extraer config específica de la estrategia
    strategy_config = full_config.get("strategies", {}).get("ai_agent_swing", {})
    if not strategy_config:
        print("❌ Error: No se encontró configuración para 'ai_agent_swing'")
        return

    print(f"✅ Configuración cargada. Modelo LLM: {strategy_config.get('agent_config', {}).get('model')}")

    # 2. Inicializar Estrategia
    print("\n[2] Inicializando Estrategia...")
    try:
        strategy = AIAgentStrategy(config=strategy_config)
        print("✅ Estrategia inicializada correctamente.")
    except Exception as e:
        print(f"❌ Error al inicializar estrategia: {e}")
        return

    # 3. Configurar Portfolio Provider (Paper Trading)
    # Esto simula una cuenta sin dinero real, pero con estructura válida.
    print("\n[3] Configurando Paper Portfolio...")
    # PaperPortfolioManager no acepta initial_capital en init, carga de config o DB
    portfolio_manager = PaperPortfolioManager(config_path="config/paper_trading.yaml") 
    
    # Asegurar que existe el portfolio para nuestra estrategia con capital de prueba
    if "ai_agent_swing" not in portfolio_manager.portfolios:
        portfolio_manager.portfolios["ai_agent_swing"] = PaperPortfolioManager.PaperPortfolio(
            strategy_id="ai_agent_swing", 
            initial_capital=100000.0
        )
    # Nota: PaperPortfolioManager.PaperPortfolio no es accesible así si no importamos la clase interna o usamos el modulo
    # Vamos a usar la importación directa de PaperPortfolio que ya tenemos disponible implicitamente o añadirla
    from src.trading.paper.portfolio import PaperPortfolio
    if "ai_agent_swing" not in portfolio_manager.portfolios:
        portfolio_manager.portfolios["ai_agent_swing"] = PaperPortfolio(
            strategy_id="ai_agent_swing", 
            initial_capital=100000.0
        )
    else:
        # Resetear para prueba
        portfolio_manager.portfolios["ai_agent_swing"].cash = 100000.0
        portfolio_manager.portfolios["ai_agent_swing"].positions = {}

    portfolio_provider = PaperPortfolioProvider(portfolio_manager, strategy_id="ai_agent_swing")
    
    # Inyectar dependencia
    strategy.set_portfolio_provider(portfolio_provider)
    print("✅ Portfolio Provider inyectado. Capital inicial: $100,000")

    # 4. Crear Contexto de Mercado Simulado (Trigger)
    # Aunque la estrategia busca sus propios datos via ContextBuilder -> MCP,
    # necesita un MarketContext inicial como disparador en `generate_signals`.
    print("\n[4] Preparando contexto de disparo...")
    trigger_context = MarketContext(
        regime=MarketRegime.BULL, 
        regime_confidence=0.8,
        regime_probabilities={"BULL": 0.8, "SIDEWAYS": 0.2},
        market_data={}, 
        capital_available=100000.0,
        positions=[],
        timestamp=datetime.now(timezone.utc),
        # Instrucción explícita para forzar el uso de herramientas de búsqueda
        metadata={"notes": "URGENT: Please verify the latest market sentiment and news for SPY using your web_search tool before making any decision. The market might be closed, so check for news from yesterday."}
    )

    # 5. Ejecutar Generación de Señales
    print("\n[5] 🚀 EJECUTANDO ANÁLISIS DEL AGENTE (Esto llama al LLM real)...")
    print("    Por favor espere, puede tardar unos segundos...")
    
    try:
        signals = await strategy.generate_signals(trigger_context)
        
        print("\n" + "="*80)
        print(" RESULTADOS DEL ANÁLISIS")
        print("="*80)
        
        if not signals:
            print("ℹ️ El agente no generó señales de entrada en esta ejecución.")
            print("   (Esto es normal si el mercado no cumple sus criterios o decide esperar)")
        else:
            print(f"✅ Se generaron {len(signals)} señales:")
            for i, sig in enumerate(signals, 1):
                print(f"\n   --- Señal #{i} ---")
                print(f"   Símbolo: {sig.symbol}")
                print(f"   Dirección: {sig.direction}")
                print(f"   Confianza: {sig.confidence}")
                print(f"   Razonamiento: {sig.reasoning}")
                print(f"   Precio Entrada: {sig.entry_price}")
                print(f"   Stop Loss: {sig.stop_loss}")
                print(f"   Take Profit: {sig.take_profit}")
        
    except Exception as e:
        print(f"\n❌ ERROR DURANTE LA EJECUCIÓN: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print(" FIN DE LA PRUEBA")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_test())
