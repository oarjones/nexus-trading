# DOC-05: Guía de Configuración

> **Propósito**: Documentar todas las configuraciones necesarias para ejecutar Nexus Trading  
> **Audiencia**: Desarrollador que implementa o despliega el sistema

## 1. Resumen de Archivos de Configuración

```
nexus-trading/
├── .env                        # Variables de entorno (SECRETOS)
├── .env.example                # Plantilla de .env (sin secretos)
├── config/
│   ├── strategies.yaml         # Configuración de estrategias
│   ├── symbols.yaml            # Universo maestro de símbolos
│   ├── paper_trading.yaml      # Config de paper trading
│   ├── ml_models.yaml          # Config de modelos ML
│   ├── mcp-servers.yaml        # URLs de servidores MCP
│   ├── scheduler.yaml          # Programación de tareas
│   └── agents.yaml             # Config de agentes LLM
```

---

## 2. Variables de Entorno (.env)

### 2.1. Archivo .env.example (Plantilla)

Crear/actualizar `.env.example` con todas las variables necesarias:

```bash
# ==============================================================================
# NEXUS TRADING - ENVIRONMENT CONFIGURATION
# ==============================================================================
# Copiar este archivo a .env y completar los valores
# NUNCA commitear .env al repositorio
# ==============================================================================

# ------------------------------------------------------------------------------
# API KEYS - REQUERIDAS
# ------------------------------------------------------------------------------

# Anthropic Claude API
# Obtener en: https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Brave Search API (para web search del AI Agent)
# Obtener en: https://brave.com/search/api/
# Plan gratuito: 2,000 búsquedas/mes
BRAVE_SEARCH_API_KEY=BSAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ------------------------------------------------------------------------------
# BROKER - INTERACTIVE BROKERS
# ------------------------------------------------------------------------------

# TWS/Gateway connection
IBKR_HOST=127.0.0.1
IBKR_PORT=7497                    # 7497=TWS Paper, 7496=TWS Live, 4002=Gateway Paper
IBKR_CLIENT_ID=1
IBKR_ACCOUNT=DU1234567            # Tu cuenta de paper trading

# API mode (paper/live)
IBKR_TRADING_MODE=paper           # paper | live (NUNCA cambiar a live sin verificar)

# ------------------------------------------------------------------------------
# MCP SERVERS - URLs de los microservicios
# ------------------------------------------------------------------------------

# Servidores MCP (ajustar puertos si es necesario)
MCP_MARKET_DATA_URL=http://localhost:8001
MCP_TECHNICAL_URL=http://localhost:8002
MCP_ML_MODELS_URL=http://localhost:8003
MCP_RISK_URL=http://localhost:8004
MCP_IBKR_URL=http://localhost:8005

# ------------------------------------------------------------------------------
# BASE DE DATOS (opcional para MVP)
# ------------------------------------------------------------------------------

# PostgreSQL (para persistencia avanzada)
# DATABASE_URL=postgresql://user:password@localhost:5432/nexus_trading
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# POSTGRES_USER=nexus
# POSTGRES_PASSWORD=your_secure_password
# POSTGRES_DB=nexus_trading

# Redis (para caché y pub/sub)
# REDIS_URL=redis://localhost:6379/0

# ------------------------------------------------------------------------------
# LOGGING & MONITORING
# ------------------------------------------------------------------------------

# Nivel de log (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Archivo de log
LOG_FILE=strategy_lab.log

# Telegram notifications (opcional)
# TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
# TELEGRAM_CHAT_ID=123456789

# ------------------------------------------------------------------------------
# PAPER TRADING SETTINGS
# ------------------------------------------------------------------------------

# Capital inicial por estrategia (EUR)
PAPER_TRADING_INITIAL_CAPITAL=25000

# Archivo de persistencia del portfolio
PAPER_PORTFOLIO_FILE=data/paper_portfolios.json

# ------------------------------------------------------------------------------
# AI AGENT SETTINGS
# ------------------------------------------------------------------------------

# Modelo de Claude a usar
CLAUDE_MODEL=claude-3-5-sonnet-20241022

# Límites de tokens
CLAUDE_MAX_TOKENS=4096

# Habilitar web search (true/false)
AI_AGENT_WEB_SEARCH_ENABLED=true

# Máximo de búsquedas por decisión
AI_AGENT_MAX_SEARCHES=3

# ------------------------------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------------------------------

# Puerto del dashboard web
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=8050

# ------------------------------------------------------------------------------
# DESARROLLO
# ------------------------------------------------------------------------------

# Modo debug (más logs, auto-reload)
DEBUG=false

# Entorno
ENVIRONMENT=development           # development | staging | production
```

### 2.2. Variables Críticas por Componente

| Variable | Componente | Requerida | Descripción |
|----------|------------|-----------|-------------|
| `ANTHROPIC_API_KEY` | AI Agent | ✅ Sí | Clave API de Claude |
| `BRAVE_SEARCH_API_KEY` | Web Search | ⚠️ Recomendada | Sin ella, el agente no puede buscar |
| `IBKR_HOST` | Data/Execution | ✅ Sí | Host de TWS/Gateway |
| `IBKR_PORT` | Data/Execution | ✅ Sí | Puerto de conexión |
| `IBKR_TRADING_MODE` | Execution | ✅ Sí | Siempre "paper" para MVP |
| `MCP_*_URL` | MCP Servers | ✅ Sí | URLs de microservicios |
| `LOG_LEVEL` | Logging | No | Default: INFO |
| `PAPER_TRADING_INITIAL_CAPITAL` | Paper Trading | No | Default: 25000 |

---

## 3. Configuración de Estrategias (strategies.yaml)

### 3.1. Cambios Necesarios

Actualizar `config/strategies.yaml` para reflejar las nuevas capacidades:

```yaml
# config/strategies.yaml
# Configuración de estrategias de trading

# ==============================================================================
# CONFIGURACIÓN GLOBAL
# ==============================================================================
global:
  default_timeframe: "1d"
  signal_ttl_hours: 24
  max_signals_per_run: 10
  
  # Capital por estrategia (override en .env)
  paper_trading_capital: 25000
  
  # Universo: ahora gestionado por UniverseManager
  universe:
    use_dynamic: true              # Usar UniverseManager
    fallback_symbols:              # Solo si UniverseManager falla
      - SPY
      - QQQ
      - IWM

# ==============================================================================
# ESTRATEGIAS
# ==============================================================================
strategies:
  
  # --------------------------------------------------------------------------
  # HMM RULES STRATEGY (Sistemática)
  # --------------------------------------------------------------------------
  hmm_rules:
    enabled: true
    description: "Estrategia sistemática basada en régimen HMM"
    
    # Scheduling: Una vez al día a las 10:00 UTC
    schedule:
      type: "cron"
      days: "mon-fri"
      time: "10:00"
      timezone: "UTC"
    
    # Mercados objetivo
    markets:
      - US
    
    # Regímenes en los que puede operar
    required_regime:
      - BULL
      - SIDEWAYS
    
    # Reglas por régimen
    rules:
      bull:
        strategy: "buy_the_dip"
        rsi_entry_threshold: 40       # RSI < 40 = dip
        rsi_exit_threshold: 70        # RSI > 70 = take profit
        position_size_pct: 0.05       # 5% del capital por posición
        stop_loss_pct: 0.03           # Stop loss 3%
        take_profit_pct: 0.06         # Take profit 6%
      
      sideways:
        strategy: "mean_reversion"
        rsi_buy_threshold: 30         # Comprar en sobreventa
        rsi_sell_threshold: 70        # Vender en sobrecompra
        position_size_pct: 0.03       # Posiciones más pequeñas
        stop_loss_pct: 0.02
        take_profit_pct: 0.04
    
    # Gestión de riesgo
    risk:
      max_positions: 5
      max_portfolio_exposure_pct: 25
      min_risk_reward: 1.5

  # --------------------------------------------------------------------------
  # AI AGENT SWING (Inteligente)
  # --------------------------------------------------------------------------
  ai_agent_swing:
    enabled: true
    description: "Agente IA para swing trading con web search"
    
    # Scheduling: Cada 4 horas durante mercado
    schedule:
      type: "interval"
      hours: 4
    
    # Nivel de autonomía
    autonomy_level: conservative      # conservative | moderate | aggressive
    
    # Configuración del agente LLM
    agent_config:
      provider: "claude"
      model: "claude-3-5-sonnet-20241022"  # Override desde .env
      max_tokens: 4096
      temperature: 0.0                     # Determinístico
      
      # Web Search (NUEVO)
      web_search:
        enabled: true                      # Habilitar búsquedas
        max_searches_per_decision: 3       # Límite por decisión
        search_provider: "brave"           # brave | tavily | serp
        freshness: "pw"                    # Past week
    
    # Símbolos (ahora dinámicos via UniverseManager)
    # Estos son fallback si UniverseManager no está disponible
    symbols:
      - SPY
      - QQQ
      - IWM
      - GLD
      - TLT
    
    # Regímenes permitidos
    required_regime:
      - BULL
      - SIDEWAYS
    
    # Gestión de riesgo (el agente puede ser más conservador)
    risk:
      max_positions: 5
      max_position_pct: 5.0
      max_daily_trades: 3
      max_daily_loss_pct: 2.0

# ==============================================================================
# MAPEO DE RÉGIMEN
# ==============================================================================
regime_mapping:
  BULL:
    description: "Mercado alcista - Momentum largo"
    active_strategies:
      - hmm_rules
      - ai_agent_swing
    risk_modifier: 1.0              # Riesgo normal
    
  BEAR:
    description: "Mercado bajista - Solo cierres"
    active_strategies: []           # Ninguna estrategia de entrada
    risk_modifier: 0.5              # Reducir exposición
    actions:
      - close_losing_positions
      - tighten_stops
    
  SIDEWAYS:
    description: "Mercado lateral - Mean reversion"
    active_strategies:
      - hmm_rules
      - ai_agent_swing
    risk_modifier: 0.8
    
  VOLATILE:
    description: "Alta volatilidad - Pausar operaciones"
    active_strategies: []
    risk_modifier: 0.3
    actions:
      - reduce_position_sizes
      - widen_stops
```

---

## 4. Configuración de Paper Trading (paper_trading.yaml)

```yaml
# config/paper_trading.yaml
# Configuración del motor de simulación

paper_trading:
  enabled: true
  
  # Persistencia
  persistence:
    file: "data/paper_portfolios.json"
    auto_save: true
    save_interval_seconds: 60
  
  # Cuentas (una por estrategia)
  accounts:
    hmm_rules:
      initial_capital: 25000
      currency: EUR
      
    ai_agent_swing:
      initial_capital: 25000
      currency: EUR
  
  # Simulación de ejecución
  execution:
    # Slippage simulado
    slippage:
      enabled: true
      model: "percentage"           # percentage | fixed | volatility_based
      base_pct: 0.05               # 0.05% de slippage base
      
    # Comisiones simuladas (IBKR tiered)
    commissions:
      enabled: true
      model: "ibkr_tiered"
      min_per_order: 1.00          # Mínimo $1 por orden
      per_share: 0.005             # $0.005 por acción
      max_pct: 0.5                 # Máximo 0.5% del valor
    
    # Retrasos simulados
    latency:
      enabled: false               # Deshabilitado para MVP
      mean_ms: 50
      std_ms: 20
  
  # Límites de seguridad
  limits:
    max_order_value: 10000         # Máximo $10K por orden
    max_daily_orders: 20           # Máximo 20 órdenes/día
    max_position_pct: 20           # Máximo 20% en una posición

# Reportes
reporting:
  daily_reports:
    enabled: true
    output_dir: "reports"
    format: "csv"
    
  metrics:
    track_pnl: true
    track_trades: true
    track_signals: true
```

---

## 5. Configuración de Agentes (agents.yaml)

```yaml
# config/agents.yaml
# Configuración de agentes LLM

# Configuración por defecto
defaults:
  provider: claude
  model: claude-3-5-sonnet-20241022
  max_tokens: 4096
  temperature: 0.0
  timeout_seconds: 60

# Proveedores disponibles
providers:
  claude:
    api_base: "https://api.anthropic.com"
    api_version: "2024-01-01"
    # API key desde .env: ANTHROPIC_API_KEY
    
    models:
      - claude-3-5-sonnet-20241022    # Recomendado: balance costo/calidad
      - claude-3-5-haiku-20241022     # Más barato, menos capaz
      - claude-3-opus-20240229        # Más caro, máxima calidad

# Configuración de Web Search
web_search:
  provider: brave
  # API key desde .env: BRAVE_SEARCH_API_KEY
  
  settings:
    default_count: 5               # Resultados por búsqueda
    default_freshness: "pw"        # Past week
    timeout_seconds: 10
    
  # Proveedores alternativos (para futuro)
  alternatives:
    - tavily     # TAVILY_API_KEY
    - serp       # SERP_API_KEY

# Rate limiting
rate_limits:
  claude:
    requests_per_minute: 50
    tokens_per_minute: 100000
    
  brave_search:
    requests_per_minute: 15        # Plan gratuito
    requests_per_month: 2000

# Cost tracking
cost_tracking:
  enabled: true
  output_dir: "data/costs"
  
  # Alertas de coste
  alerts:
    daily_threshold_usd: 1.00      # Alertar si > $1/día
    monthly_threshold_usd: 10.00   # Alertar si > $10/mes
```

---

## 6. Configuración de MCP Servers (mcp-servers.yaml)

```yaml
# config/mcp-servers.yaml
# URLs y configuración de servidores MCP

servers:
  market_data:
    url: "${MCP_MARKET_DATA_URL:-http://localhost:8001}"
    timeout: 30
    retries: 3
    
  technical:
    url: "${MCP_TECHNICAL_URL:-http://localhost:8002}"
    timeout: 30
    retries: 3
    
  ml_models:
    url: "${MCP_ML_MODELS_URL:-http://localhost:8003}"
    timeout: 60                    # Más tiempo para inferencia
    retries: 2
    
  risk:
    url: "${MCP_RISK_URL:-http://localhost:8004}"
    timeout: 30
    retries: 3
    
  ibkr:
    url: "${MCP_IBKR_URL:-http://localhost:8005}"
    timeout: 45
    retries: 2

# Health checks
health_check:
  enabled: true
  interval_seconds: 60
  timeout_seconds: 5
```

---

## 7. Configuración del Universe Manager

Añadir a `config/universe.yaml` (NUEVO):

```yaml
# config/universe.yaml
# Configuración del UniverseManager

universe:
  # Archivo maestro de símbolos
  master_file: "config/symbols.yaml"
  
  # Filtros de screening diario
  screening:
    # Liquidez
    min_avg_volume_shares: 100000
    min_avg_volume_usd: 500000
    max_spread_pct: 0.5
    
    # Precio
    min_price: 5.0
    max_price: 10000
    
    # Volatilidad
    min_atr_pct: 0.5
    max_atr_pct: 10.0
    
    # Tendencia
    trend_sma_period: 200
  
  # Límites del universo activo
  limits:
    max_active_symbols: 50
    min_active_symbols: 10
  
  # Sugerencias del AI Agent
  ai_suggestions:
    enabled: true
    max_per_day: 10
    min_confidence: 0.6
    require_validation: true       # Validar antes de añadir
  
  # Scheduling del screening
  screening_schedule:
    time: "06:00"                  # 06:00 UTC (antes de mercado EU)
    timezone: "UTC"
    days: "mon-fri"
```

---

## 8. Configuración del Dashboard

Añadir a `config/dashboard.yaml` (NUEVO):

```yaml
# config/dashboard.yaml
# Configuración del dashboard de supervisión

dashboard:
  # Servidor
  host: "${DASHBOARD_HOST:-127.0.0.1}"
  port: "${DASHBOARD_PORT:-8050}"
  
  # Actualizaciones
  refresh_intervals:
    status: 10                     # Segundos
    accounts: 15
    signals: 10
    errors: 15
    costs: 30
  
  # SSE (Server-Sent Events)
  sse:
    enabled: true
    heartbeat_seconds: 30
  
  # Límites de visualización
  display:
    max_signals: 50
    max_errors: 20
    max_logs: 100
  
  # Notificaciones del navegador
  notifications:
    enabled: true
    on_new_signal: true
    on_error: true
    on_trade_executed: true
```

---

## 9. Verificación de Configuración

### 9.1. Script de Verificación

Crear `scripts/verify_config.py`:

```python
#!/usr/bin/env python
"""
Verificar que toda la configuración necesaria está presente y es válida.

Uso:
    python scripts/verify_config.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env
load_dotenv()

# Colores para output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check(condition, name, critical=True):
    """Verificar una condición."""
    if condition:
        print(f"  {GREEN}✓{RESET} {name}")
        return True
    else:
        marker = f"{RED}✗{RESET}" if critical else f"{YELLOW}⚠{RESET}"
        print(f"  {marker} {name}")
        return False

def main():
    print("\n" + "=" * 60)
    print("NEXUS TRADING - CONFIGURATION CHECK")
    print("=" * 60)
    
    all_ok = True
    
    # 1. Variables de entorno críticas
    print("\n[1] Environment Variables (Critical)")
    all_ok &= check(
        os.getenv("ANTHROPIC_API_KEY"),
        "ANTHROPIC_API_KEY is set"
    )
    all_ok &= check(
        os.getenv("IBKR_HOST"),
        "IBKR_HOST is set"
    )
    all_ok &= check(
        os.getenv("IBKR_PORT"),
        "IBKR_PORT is set"
    )
    
    # 2. Variables recomendadas
    print("\n[2] Environment Variables (Recommended)")
    check(
        os.getenv("BRAVE_SEARCH_API_KEY"),
        "BRAVE_SEARCH_API_KEY is set (web search)",
        critical=False
    )
    check(
        os.getenv("IBKR_TRADING_MODE") == "paper",
        "IBKR_TRADING_MODE is 'paper'",
        critical=False
    )
    
    # 3. Archivos de configuración
    print("\n[3] Configuration Files")
    config_dir = Path("config")
    
    required_files = [
        "strategies.yaml",
        "symbols.yaml",
        "paper_trading.yaml",
        "mcp-servers.yaml",
    ]
    
    for f in required_files:
        all_ok &= check(
            (config_dir / f).exists(),
            f"config/{f} exists"
        )
    
    # 4. Directorios necesarios
    print("\n[4] Required Directories")
    required_dirs = [
        "data",
        "data/costs",
        "reports",
        "logs",
    ]
    
    for d in required_dirs:
        path = Path(d)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"  {YELLOW}+{RESET} Created {d}/")
        else:
            print(f"  {GREEN}✓{RESET} {d}/ exists")
    
    # 5. Modelo HMM
    print("\n[5] ML Models")
    hmm_path = Path("models/hmm_regime/latest/model.pkl")
    all_ok &= check(
        hmm_path.exists(),
        "HMM model exists (models/hmm_regime/latest/model.pkl)"
    )
    
    # 6. Verificar conexión MCP (opcional)
    print("\n[6] MCP Servers (connectivity check skipped)")
    print("  ℹ Run servers and use health endpoints to verify")
    
    # Resultado
    print("\n" + "=" * 60)
    if all_ok:
        print(f"{GREEN}✓ All critical checks passed{RESET}")
        print("  Ready to run: python scripts/run_strategy_lab.py")
    else:
        print(f"{RED}✗ Some checks failed{RESET}")
        print("  Please fix the issues above before running")
    print("=" * 60 + "\n")
    
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
```

### 9.2. Checklist Pre-Ejecución

Antes de ejecutar el sistema, verificar:

```bash
# 1. Copiar y configurar .env
cp .env.example .env
# Editar .env con tus claves

# 2. Verificar configuración
python scripts/verify_config.py

# 3. Verificar universo de símbolos
python scripts/validate_universe.py

# 4. Iniciar servidores MCP (en terminales separadas)
# Terminal 1: python -m mcp_servers.market_data.server
# Terminal 2: python -m mcp_servers.technical.server
# Terminal 3: python -m mcp_servers.ml_models.server

# 5. Iniciar Strategy Lab
python scripts/run_strategy_lab.py

# 6. (Opcional) Iniciar Dashboard
python scripts/run_dashboard.py
```

---

## 10. Resumen de Cambios de Configuración

| Archivo | Cambio | Razón |
|---------|--------|-------|
| `.env` | Añadir `BRAVE_SEARCH_API_KEY` | Web search para AI Agent |
| `.env` | Añadir `AI_AGENT_*` | Configuración del agente |
| `.env` | Añadir `DASHBOARD_*` | Puerto del dashboard |
| `strategies.yaml` | Sección `web_search` en `ai_agent_swing` | Habilitar búsquedas |
| `strategies.yaml` | Sección `universe.use_dynamic` | Usar UniverseManager |
| `agents.yaml` | NUEVO archivo | Configuración centralizada de LLM |
| `universe.yaml` | NUEVO archivo | Configuración del UniverseManager |
| `dashboard.yaml` | NUEVO archivo | Configuración del dashboard |

---

## 11. Troubleshooting

### Problemas Comunes

| Problema | Causa | Solución |
|----------|-------|----------|
| "ANTHROPIC_API_KEY not set" | .env no cargado | Verificar que .env existe y tiene la clave |
| "Connection refused" en MCP | Servidores no iniciados | Iniciar servidores MCP primero |
| "Web search not available" | BRAVE_SEARCH_API_KEY no configurada | Añadir clave o deshabilitar web_search |
| "HMM model not found" | Modelo no entrenado | Ejecutar `python scripts/train_hmm.py` |
| Dashboard no accesible | Puerto ocupado | Cambiar DASHBOARD_PORT en .env |
