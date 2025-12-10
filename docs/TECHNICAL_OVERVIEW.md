# Nexus Trading - Strategy Lab MVP
> **Technical Overview**

## 🎯 Objetivo
El **Strategy Lab** es un entorno de ejecución iso-morfico (Live/Paper) diseñado para el desarrollo, validación y ejecución de estrategias de trading algorítmico y agentes basados en LLMs. Su arquitectura permite operar múltiples estrategias en paralelo, gestionar estados de portfolio persistentes y cambiar transparentemente entre simulación y operativa real.

## 🚀 Capabilities Principales

### 1. Market Regime Awareness
El sistema adapta su comportamiento según el régimen de mercado detectado mediante Machine Learning:
*   **Modelo**: Gaussian HMM (Hidden Markov Model) con 4 estados.
*   **Estados**: BULL (Alcista), BEAR (Bajista), SIDEWAYS (Lateral), VOLATILE (Volátil).
*   **Inferencia**: Provista por `mcp-ml-models` server.

### 2. Paper Trading de Alta Fidelidad
Motor de simulación que replica la gestión de cartera real:
*   **Persistencia**: Estado del portfolio guardado en disco (`data/paper_portfolios.json`), sobreviviendo reinicios.
*   **Pricing**: Simulación de órdenes con precios de mercado real (via `mcp-market-data`).
*   **Contabilidad**: Tracking preciso de Cash, Posiciones y PnL no realizado.

### 3. Agentes Híbridos (Systematic + AI)
Soporte para dos tipos de lógica de trading:
*   **Sistemática (`HMMRulesStrategy`)**: Reglas deterministas condicionadas por el régimen HMM (ej. Buy the Dip en Bull, Mean Reversion en Sideways).
*   **Agente IA (`AIAgentStrategy`)**: LLM (Claude) con contexto enriquecido que toma decisiones discrecionales y revisa el portfolio.

### 4. Scheduler & Reporting
*   **Automated Scheduling**: Ejecución desatendida via `APScheduler` (Cron/Interval).
*   **Daily Reports**: Generación automática de reportes CSV (NAV, Posiciones, Trades) al cierre.

## 🛠️ Tech Stack Core

| Componente | Tecnología | Rol |
|------------|------------|-----|
| **Core Logic** | Python 3.10+ | Lógica de negocio y orquestación |
| **Arquitectura** | MCP (Microservice Comm Protocol) | Comunicación estandarizada con Data/ML/Broker |
| **Scheduling** | APScheduler (AsyncIO) | Programación de tareas asíncronas |
| **Persistencia** | JSON / Pandas | Almacenamiento ligero de estado y reportes |
| **AI/ML** | `hmmlearn`, `anthropic` | Detección de régimen y razonamiento de agente |

## 📦 Estructura del Proyecto (MVP)

```text
nexus-trading/
├── config/                 # Configuración (strategies.yaml, paper_trading.yaml)
├── data/                   # Persistencia (portfolios, databases)
├── docs/                   # Documentación técnica
├── reports/                # Reportes generados (CSV)
├── scripts/                # Entry points (run_strategy_lab.py, train_hmm.py)
└── src/
    ├── agents/             # Lógica de Agentes (Context, Reviewer)
    ├── metrics/            # Exportadores y Métricas
    ├── ml/                 # Modelos ML (HMM)
    ├── scheduling/         # Scheduler System
    ├── strategies/         # Implementación de estrategias
    └── trading/            # Motor de Paper Trading
```
