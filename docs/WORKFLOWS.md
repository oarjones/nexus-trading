# Nexus Trading - Workflows
> **Secuencias de Ejecución del Strategy Lab**

## 1. Ciclo de Ejecución de Estrategia

Flujo estándar disparado por el Scheduler.

```mermaid
sequenceDiagram
    participant S as Scheduler
    participant R as StrategyRunner
    participant MCP as MCP Servers
    participant ST as Strategy (HMM/AI)
    participant OS as OrderSimulator
    participant DB as JSON Persistence

    S->>R: run_single_strategy(id)
    activate R
    
    R->>MCP: get_regime()
    MCP-->>R: Regime (e.g. BULL)
    
    R->>MCP: get_market_data(symbols)
    MCP-->>R: Prices & Indicators

    R->>R: Build MarketContext
    
    R->>ST: generate_signals(context)
    activate ST
    ST-->>R: List[Signal]
    deactivate ST
    
    loop For each Signal
        R->>OS: process_signal(Signal)
        activate OS
        OS->>OS: Calculate Slippage/Comm
        OS->>DB: Update Portfolio State
        OS-->>R: Trade Result
        deactivate OS
    end
    
    R->>R: Publish Signals (Event Bus)
    deactivate R
```

## 2. Flujo de Revisión de Portfolio (AI Agent)

Proceso específico donde el Agente audita posiciones existentes.

```mermaid
sequenceDiagram
    participant R as Runner
    participant PR as AI PortfolioReviewer
    participant LLM as Claude Model
    participant PP as PaperPortfolio

    R->>PR: review_portfolio(context)
    activate PR
    
    PR->>PP: Get Open Positions
    PP-->>PR: Positions List
    
    PR->>PR: Build "Review Prompt" (Focus: HOLD/CLOSE)
    
    PR->>LLM: decide(prompt)
    LLM-->>PR: Validated Decision (JSON)
    
    loop For each CLOSE decision
        PR->>R: Signal(CLOSE)
    end
    
    deactivate PR
```

## 3. Generación de Reportes Diarios

Se ejecuta al detener el servicio o al cambio de día.

```mermaid
sequenceDiagram
    participant Main as run_strategy_lab.py
    participant Rep as CSVReporter
    participant PM as PortfolioManager
    participant FS as File System

    Main->>Main: Stop Signal Received
    Main->>PM: save_state()
    PM->>FS: Write paper_portfolios.json
    
    Main->>Rep: generate_daily_report(portfolios)
    activate Rep
    
    Rep->>FS: Create reports/YYYY-MM-DD/
    
    Rep->>Rep: Calculate Metrics (NAV, Cash, Alloc)
    Rep->>FS: Write portfolio_summary.csv
    
    Rep->>Rep: Extract Open Positions
    Rep->>FS: Write positions.csv
    
    deactivate Rep
    Main->>Main: Exit
```
