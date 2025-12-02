# Nexus Trading

Sistema autónomo de trading algorítmico basado en arquitectura multi-agente con MCP (Model Context Protocol).

## 🎯 Visión General

Nexus Trading es un sistema de trading automatizado que utiliza múltiples agentes especializados coordinados mediante MCP para análisis de mercados, gestión de riesgo y ejecución de operaciones.

### Características Principales

- **Arquitectura Multi-Agente**: Agentes especializados en análisis técnico, fundamental, sentimiento y ejecución
- **MCP Integration**: Comunicación estandarizada entre agentes mediante Model Context Protocol
- **Multi-Broker**: Soporte para Interactive Brokers (acciones, ETFs, opciones) y Kraken (crypto)
- **Risk Management**: Sistema de gestión de riesgo multinivel con límites dinámicos
- **ML Pipeline**: Modelos de predicción con feature store centralizado

## 📁 Estructura del Proyecto

```
nexus-trading/
├── src/
│   ├── agents/              # Agentes MCP
│   │   ├── coordinator/     # Agente orquestador principal
│   │   ├── technical/       # Análisis técnico
│   │   ├── fundamental/     # Análisis fundamental
│   │   ├── sentiment/       # Análisis de sentimiento
│   │   ├── risk/            # Gestión de riesgo
│   │   └── execution/       # Ejecución de órdenes
│   ├── mcp_servers/         # Servidores MCP
│   │   ├── market_data/     # Datos de mercado
│   │   ├── broker_ibkr/     # Interactive Brokers
│   │   ├── broker_kraken/   # Kraken Exchange
│   │   ├── database/        # Acceso a datos
│   │   └── ml_models/       # Modelos ML
│   ├── core/                # Lógica central
│   │   ├── trading_engine/  # Motor de trading
│   │   ├── risk_manager/    # Gestión de riesgo
│   │   └── portfolio/       # Gestión de portfolio
│   ├── data/                # Pipeline de datos
│   │   ├── collectors/      # Recolectores
│   │   ├── processors/      # Procesadores
│   │   └── feature_store/   # Feature engineering
│   ├── ml/                  # Machine Learning
│   │   ├── models/          # Definición de modelos
│   │   ├── training/        # Entrenamiento
│   │   └── inference/       # Inferencia
│   └── utils/               # Utilidades
├── config/                  # Configuraciones
├── tests/                   # Tests
├── docs/                    # Documentación
├── scripts/                 # Scripts de utilidad
├── docker/                  # Docker configs
└── notebooks/               # Jupyter notebooks
```

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|------|------------|
| **Lenguaje Principal** | Python 3.11+ |
| **MCP Servers** | TypeScript / Node.js |
| **Base de Datos Principal** | PostgreSQL + TimescaleDB |
| **Cache/Real-time** | Redis |
| **Métricas** | InfluxDB + Grafana |
| **ML Framework** | PyTorch |
| **Broker APIs** | IBKR TWS API, Kraken REST/WS |
| **Contenedores** | Docker + Docker Compose |

## 🚀 Quick Start

### Prerrequisitos

- Python 3.11+
- Node.js 18+
- Docker y Docker Compose
- Cuenta en Interactive Brokers y/o Kraken

### Instalación

```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/nexus-trading.git
cd nexus-trading

# Configurar entorno
cp .env.example .env
# Editar .env con tus credenciales

# Levantar infraestructura
docker-compose up -d

# Instalar dependencias Python
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Instalar dependencias MCP servers
cd src/mcp_servers
npm install
```

### Configuración

1. Configurar credenciales en `.env`
2. Ajustar parámetros de riesgo en `config/risk.yaml`
3. Configurar estrategias en `config/strategies.yaml`

## 📊 Documentación

- [Arquitectura General](docs/01_arquitectura_vision_general.md)
- [Arquitectura de Datos](docs/02_arquitectura_datos.md)
- [Sistema de Agentes MCP](docs/03_sistema_agentes_mcp.md)
- [Motor de Trading](docs/04_motor_trading.md)
- [Pipeline ML](docs/05_machine_learning.md)
- [Gestión de Riesgo](docs/06_gestion_riesgo.md)
- [Operaciones](docs/07_operaciones.md)

## ⚠️ Disclaimer

Este software es para uso educativo y de investigación. El trading algorítmico conlleva riesgos significativos. No se garantizan beneficios. Úsalo bajo tu propia responsabilidad.

## 📄 Licencia

MIT License - ver [LICENSE](LICENSE) para más detalles.
