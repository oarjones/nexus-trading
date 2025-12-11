# DOC-02: Web Search para AI Agent + Tracking de Costes

> **Prioridad**: 🔴 ALTA  
> **Esfuerzo estimado**: 6-8 horas  
> **Dependencias**: DOC-01 (UniverseManager) recomendado pero no bloqueante

## 1. Contexto y Objetivo

### Problema Actual
El AI Agent opera "a ciegas" sin acceso a información actual del mercado:
- Solo recibe indicadores técnicos calculados
- No puede consultar noticias, earnings, eventos macro
- El prompt menciona "noticias" pero no se envían
- Estamos infrautilizando las capacidades del LLM

### Objetivo
1. Habilitar **web search** en Claude para que el agente pueda buscar información relevante
2. Modificar **prompts** para guiar el uso efectivo de búsquedas
3. Implementar **tracking de costes** por consulta (tokens input/output, búsquedas)
4. **Persistir métricas** para análisis de rentabilidad

### Estimación de Costes
| Concepto | Tokens | Coste unitario | Coste |
|----------|--------|----------------|-------|
| Contexto (portfolio, régimen, indicadores) | ~1,500 input | $0.003/1K | $0.0045 |
| Web search results (3-5 búsquedas) | ~2,000 input | $0.003/1K | $0.006 |
| Prompt + instrucciones | ~500 input | $0.003/1K | $0.0015 |
| Respuesta del agente | ~800 output | $0.015/1K | $0.012 |
| **Total por decisión** | ~4,800 | - | **~$0.024** |

**Proyección mensual**: 6 ejecuciones/día × 30 días = **~$4.30/mes**

---

## 2. Arquitectura de la Solución

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUJO DEL AI AGENT CON WEB SEARCH            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. ContextBuilder.build()                                     │
│     │                                                           │
│     ├─► Régimen + Portfolio + Indicadores técnicos             │
│     │                                                           │
│     └─► NO incluir noticias (el agente las buscará)            │
│                                                                 │
│  2. ClaudeAgent.decide(context)                                │
│     │                                                           │
│     ├─► Construir mensajes con tool definitions                │
│     │   • web_search tool habilitado                           │
│     │                                                           │
│     ├─► Primera llamada a Claude API                           │
│     │   Claude analiza contexto y decide si buscar             │
│     │                                                           │
│     ├─► [Si tool_use] Ejecutar búsquedas                       │
│     │   • Brave Search API / Tavily / SerpAPI                  │
│     │   • Procesar resultados                                  │
│     │                                                           │
│     ├─► Segunda llamada con resultados                         │
│     │   Claude genera decisión final                           │
│     │                                                           │
│     └─► CostTracker.record(usage)                              │
│                                                                 │
│  3. Persistencia                                               │
│     │                                                           │
│     └─► data/costs/YYYY-MM-DD.json                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Implementación

### 3.1. Sistema de Tracking de Costes

**Archivo**: `src/agents/llm/cost_tracker.py` (NUEVO)

```python
"""
Cost Tracker para AI Agent.

Registra y persiste el consumo de tokens y costes de cada consulta al LLM.
Permite análisis posterior de rentabilidad del sistema.
"""

import json
import logging
from datetime import datetime, timezone, date
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class CostModel(Enum):
    """Modelos y sus costes por 1K tokens (USD)."""
    # Claude 3.5 Sonnet
    CLAUDE_35_SONNET_INPUT = 0.003
    CLAUDE_35_SONNET_OUTPUT = 0.015
    
    # Claude 3.5 Haiku (más barato, para tareas simples)
    CLAUDE_35_HAIKU_INPUT = 0.0008
    CLAUDE_35_HAIKU_OUTPUT = 0.004
    
    # Claude 3 Opus (más caro, máxima calidad)
    CLAUDE_3_OPUS_INPUT = 0.015
    CLAUDE_3_OPUS_OUTPUT = 0.075


@dataclass
class TokenUsage:
    """Uso de tokens en una llamada."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0  # Tokens leídos de caché (descuento)
    cache_creation_tokens: int = 0  # Tokens escritos a caché
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class SearchUsage:
    """Uso de búsquedas web."""
    searches_performed: int = 0
    queries: List[str] = field(default_factory=list)
    results_tokens: int = 0  # Tokens de resultados inyectados


@dataclass
class AgentCostRecord:
    """
    Registro completo de costes de una ejecución del agente.
    """
    # Identificación
    record_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy_id: str = ""
    
    # Modelo usado
    model: str = "claude-3-5-sonnet-20241022"
    
    # Uso de tokens
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    
    # Uso de búsquedas
    search_usage: SearchUsage = field(default_factory=SearchUsage)
    
    # Número de llamadas API (puede ser >1 si hay tool_use)
    api_calls: int = 1
    
    # Costes calculados (USD)
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    
    # Resultado
    signals_generated: int = 0
    decision_confidence: float = 0.0
    
    # Metadata
    context_symbols_count: int = 0
    regime: str = ""
    
    def calculate_costs(self):
        """Calcular costes basados en el modelo y uso."""
        # Determinar modelo de costes
        if "sonnet" in self.model.lower():
            input_rate = CostModel.CLAUDE_35_SONNET_INPUT.value
            output_rate = CostModel.CLAUDE_35_SONNET_OUTPUT.value
        elif "haiku" in self.model.lower():
            input_rate = CostModel.CLAUDE_35_HAIKU_INPUT.value
            output_rate = CostModel.CLAUDE_35_HAIKU_OUTPUT.value
        elif "opus" in self.model.lower():
            input_rate = CostModel.CLAUDE_3_OPUS_INPUT.value
            output_rate = CostModel.CLAUDE_3_OPUS_OUTPUT.value
        else:
            # Default a Sonnet
            input_rate = CostModel.CLAUDE_35_SONNET_INPUT.value
            output_rate = CostModel.CLAUDE_35_SONNET_OUTPUT.value
        
        # Calcular (tokens / 1000) * rate
        # Cache reads tienen 90% descuento
        effective_input = (
            self.token_usage.input_tokens + 
            self.token_usage.cache_creation_tokens +
            (self.token_usage.cache_read_tokens * 0.1)  # 90% descuento
        )
        
        self.input_cost = (effective_input / 1000) * input_rate
        self.output_cost = (self.token_usage.output_tokens / 1000) * output_rate
        self.total_cost = self.input_cost + self.output_cost
        
        return self.total_cost
    
    def to_dict(self) -> dict:
        """Serializar para JSON."""
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "strategy_id": self.strategy_id,
            "model": self.model,
            "token_usage": {
                "input_tokens": self.token_usage.input_tokens,
                "output_tokens": self.token_usage.output_tokens,
                "cache_read_tokens": self.token_usage.cache_read_tokens,
                "cache_creation_tokens": self.token_usage.cache_creation_tokens,
                "total_tokens": self.token_usage.total_tokens,
            },
            "search_usage": {
                "searches_performed": self.search_usage.searches_performed,
                "queries": self.search_usage.queries,
                "results_tokens": self.search_usage.results_tokens,
            },
            "api_calls": self.api_calls,
            "costs_usd": {
                "input": round(self.input_cost, 6),
                "output": round(self.output_cost, 6),
                "total": round(self.total_cost, 6),
            },
            "result": {
                "signals_generated": self.signals_generated,
                "decision_confidence": self.decision_confidence,
            },
            "context": {
                "symbols_count": self.context_symbols_count,
                "regime": self.regime,
            }
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AgentCostRecord":
        """Deserializar desde JSON."""
        record = cls(
            record_id=data["record_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            strategy_id=data["strategy_id"],
            model=data["model"],
            api_calls=data.get("api_calls", 1),
            signals_generated=data.get("result", {}).get("signals_generated", 0),
            decision_confidence=data.get("result", {}).get("decision_confidence", 0),
            context_symbols_count=data.get("context", {}).get("symbols_count", 0),
            regime=data.get("context", {}).get("regime", ""),
        )
        
        # Token usage
        tu = data.get("token_usage", {})
        record.token_usage = TokenUsage(
            input_tokens=tu.get("input_tokens", 0),
            output_tokens=tu.get("output_tokens", 0),
            cache_read_tokens=tu.get("cache_read_tokens", 0),
            cache_creation_tokens=tu.get("cache_creation_tokens", 0),
        )
        
        # Search usage
        su = data.get("search_usage", {})
        record.search_usage = SearchUsage(
            searches_performed=su.get("searches_performed", 0),
            queries=su.get("queries", []),
            results_tokens=su.get("results_tokens", 0),
        )
        
        # Costs
        costs = data.get("costs_usd", {})
        record.input_cost = costs.get("input", 0)
        record.output_cost = costs.get("output", 0)
        record.total_cost = costs.get("total", 0)
        
        return record


class CostTracker:
    """
    Gestor de tracking de costes del AI Agent.
    
    Persiste registros diarios en JSON y proporciona métricas agregadas.
    
    Uso:
        tracker = CostTracker()
        
        # Después de cada llamada al agente
        record = tracker.create_record(strategy_id="ai_agent_swing", model="claude-3-5-sonnet")
        record.token_usage = TokenUsage(input_tokens=1500, output_tokens=800)
        record.calculate_costs()
        tracker.save_record(record)
        
        # Consultar métricas
        daily = tracker.get_daily_summary()
        monthly = tracker.get_monthly_summary()
    """
    
    def __init__(self, data_dir: str = "data/costs"):
        """
        Args:
            data_dir: Directorio para persistir archivos JSON
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache de registros del día actual
        self._today_records: List[AgentCostRecord] = []
        self._today_date: date = None
        
    def _get_daily_file(self, target_date: date = None) -> Path:
        """Obtener path del archivo JSON para una fecha."""
        if target_date is None:
            target_date = date.today()
        return self.data_dir / f"{target_date.isoformat()}.json"
    
    def create_record(
        self,
        strategy_id: str,
        model: str = "claude-3-5-sonnet-20241022"
    ) -> AgentCostRecord:
        """
        Crear un nuevo registro de costes.
        
        Args:
            strategy_id: ID de la estrategia que hace la consulta
            model: Modelo de Claude usado
            
        Returns:
            AgentCostRecord listo para poblar
        """
        import uuid
        
        return AgentCostRecord(
            record_id=str(uuid.uuid4())[:8],
            strategy_id=strategy_id,
            model=model,
        )
    
    def save_record(self, record: AgentCostRecord):
        """
        Guardar registro de costes.
        
        Añade al archivo JSON del día.
        """
        # Asegurar que costes están calculados
        if record.total_cost == 0:
            record.calculate_costs()
        
        # Cargar registros existentes del día
        today = date.today()
        file_path = self._get_daily_file(today)
        
        if file_path.exists():
            with open(file_path, 'r') as f:
                data = json.load(f)
                records = data.get("records", [])
        else:
            records = []
        
        # Añadir nuevo registro
        records.append(record.to_dict())
        
        # Calcular totales del día
        total_cost = sum(r.get("costs_usd", {}).get("total", 0) for r in records)
        total_tokens = sum(
            r.get("token_usage", {}).get("total_tokens", 0) for r in records
        )
        total_searches = sum(
            r.get("search_usage", {}).get("searches_performed", 0) for r in records
        )
        
        # Guardar
        output = {
            "date": today.isoformat(),
            "summary": {
                "total_records": len(records),
                "total_cost_usd": round(total_cost, 6),
                "total_tokens": total_tokens,
                "total_searches": total_searches,
            },
            "records": records,
        }
        
        with open(file_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(
            f"Cost recorded: ${record.total_cost:.4f} | "
            f"Tokens: {record.token_usage.total_tokens} | "
            f"Searches: {record.search_usage.searches_performed}"
        )
    
    def get_daily_summary(self, target_date: date = None) -> dict:
        """
        Obtener resumen de costes de un día.
        
        Returns:
            {
                "date": "2024-01-15",
                "total_cost_usd": 0.15,
                "total_tokens": 25000,
                "total_searches": 12,
                "total_records": 6,
                "avg_cost_per_decision": 0.025,
                "by_strategy": {
                    "ai_agent_swing": {"cost": 0.15, "calls": 6}
                }
            }
        """
        if target_date is None:
            target_date = date.today()
            
        file_path = self._get_daily_file(target_date)
        
        if not file_path.exists():
            return {
                "date": target_date.isoformat(),
                "total_cost_usd": 0,
                "total_tokens": 0,
                "total_searches": 0,
                "total_records": 0,
            }
        
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        records = data.get("records", [])
        summary = data.get("summary", {})
        
        # Agregar por estrategia
        by_strategy = {}
        for r in records:
            sid = r.get("strategy_id", "unknown")
            if sid not in by_strategy:
                by_strategy[sid] = {"cost": 0, "calls": 0, "tokens": 0}
            by_strategy[sid]["cost"] += r.get("costs_usd", {}).get("total", 0)
            by_strategy[sid]["calls"] += 1
            by_strategy[sid]["tokens"] += r.get("token_usage", {}).get("total_tokens", 0)
        
        return {
            "date": target_date.isoformat(),
            "total_cost_usd": summary.get("total_cost_usd", 0),
            "total_tokens": summary.get("total_tokens", 0),
            "total_searches": summary.get("total_searches", 0),
            "total_records": summary.get("total_records", 0),
            "avg_cost_per_decision": (
                summary.get("total_cost_usd", 0) / max(len(records), 1)
            ),
            "by_strategy": by_strategy,
        }
    
    def get_monthly_summary(self, year: int = None, month: int = None) -> dict:
        """
        Obtener resumen de costes de un mes.
        
        Returns:
            {
                "month": "2024-01",
                "total_cost_usd": 4.50,
                "total_tokens": 750000,
                "total_decisions": 180,
                "avg_daily_cost": 0.15,
                "daily_breakdown": [...]
            }
        """
        if year is None:
            year = date.today().year
        if month is None:
            month = date.today().month
        
        # Buscar todos los archivos del mes
        pattern = f"{year}-{month:02d}-*.json"
        monthly_files = sorted(self.data_dir.glob(pattern))
        
        total_cost = 0
        total_tokens = 0
        total_searches = 0
        total_records = 0
        daily_breakdown = []
        
        for file_path in monthly_files:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            summary = data.get("summary", {})
            day_cost = summary.get("total_cost_usd", 0)
            day_tokens = summary.get("total_tokens", 0)
            day_searches = summary.get("total_searches", 0)
            day_records = summary.get("total_records", 0)
            
            total_cost += day_cost
            total_tokens += day_tokens
            total_searches += day_searches
            total_records += day_records
            
            daily_breakdown.append({
                "date": data.get("date"),
                "cost": day_cost,
                "tokens": day_tokens,
                "decisions": day_records,
            })
        
        days_with_data = len(daily_breakdown)
        
        return {
            "month": f"{year}-{month:02d}",
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "total_searches": total_searches,
            "total_decisions": total_records,
            "days_with_data": days_with_data,
            "avg_daily_cost": round(total_cost / max(days_with_data, 1), 4),
            "avg_cost_per_decision": round(total_cost / max(total_records, 1), 4),
            "daily_breakdown": daily_breakdown,
        }


# Singleton global para fácil acceso
_cost_tracker: Optional[CostTracker] = None

def get_cost_tracker() -> CostTracker:
    """Obtener instancia global del CostTracker."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker
```

---

### 3.2. Cliente de Web Search

**Archivo**: `src/agents/llm/web_search.py` (NUEVO)

```python
"""
Web Search Client para AI Agent.

Proporciona capacidad de búsqueda web usando Brave Search API.
Alternativas: Tavily, SerpAPI, Google Custom Search.
"""

import os
import logging
import aiohttp
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Resultado de una búsqueda."""
    title: str
    url: str
    snippet: str
    source: str = ""
    published_date: str = ""
    
    def to_context_string(self) -> str:
        """Formatear para incluir en contexto del LLM."""
        date_str = f" ({self.published_date})" if self.published_date else ""
        return f"**{self.title}**{date_str}\n{self.snippet}\nSource: {self.url}"


class WebSearchClient:
    """
    Cliente de búsqueda web usando Brave Search API.
    
    Configuración:
        Requiere BRAVE_SEARCH_API_KEY en variables de entorno.
        Obtener en: https://brave.com/search/api/
        
    Uso:
        client = WebSearchClient()
        results = await client.search("NVDA earnings Q4 2024")
    """
    
    BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
    
    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: Brave Search API key (o desde env BRAVE_SEARCH_API_KEY)
        """
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY")
        
        if not self.api_key:
            logger.warning(
                "BRAVE_SEARCH_API_KEY not set. Web search will be disabled. "
                "Get a free key at https://brave.com/search/api/"
            )
    
    @property
    def is_available(self) -> bool:
        """Verificar si el servicio está disponible."""
        return bool(self.api_key)
    
    async def search(
        self,
        query: str,
        count: int = 5,
        freshness: str = "pw",  # Past week
        search_lang: str = "en",
    ) -> List[SearchResult]:
        """
        Ejecutar búsqueda web.
        
        Args:
            query: Consulta de búsqueda
            count: Número de resultados (1-20)
            freshness: Filtro temporal
                - "pd": Past day
                - "pw": Past week  
                - "pm": Past month
                - "py": Past year
                - None: Sin filtro
            search_lang: Idioma de búsqueda
            
        Returns:
            Lista de SearchResult
        """
        if not self.is_available:
            logger.warning("Web search not available (no API key)")
            return []
        
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }
        
        params = {
            "q": query,
            "count": min(count, 20),
            "search_lang": search_lang,
            "text_decorations": False,
        }
        
        if freshness:
            params["freshness"] = freshness
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.BRAVE_API_URL,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        logger.error(f"Brave Search error: {response.status}")
                        return []
                    
                    data = await response.json()
                    
            # Parsear resultados
            results = []
            web_results = data.get("web", {}).get("results", [])
            
            for item in web_results[:count]:
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    source=item.get("profile", {}).get("name", ""),
                    published_date=item.get("age", ""),  # e.g., "2 days ago"
                ))
            
            logger.info(f"Web search '{query}': {len(results)} results")
            return results
            
        except aiohttp.ClientError as e:
            logger.error(f"Web search network error: {e}")
            return []
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return []
    
    async def search_financial_news(
        self,
        symbol: str,
        topics: List[str] = None
    ) -> List[SearchResult]:
        """
        Búsqueda especializada para noticias financieras.
        
        Args:
            symbol: Ticker del activo (e.g., "AAPL")
            topics: Temas adicionales ["earnings", "SEC filing", etc.]
            
        Returns:
            Lista de SearchResult relevantes
        """
        # Construir query optimizada para finanzas
        base_query = f"{symbol} stock"
        
        if topics:
            base_query += " " + " OR ".join(topics)
        else:
            base_query += " news earnings analysis"
        
        return await self.search(
            query=base_query,
            count=5,
            freshness="pw",  # Última semana
        )
    
    async def search_market_context(self) -> List[SearchResult]:
        """
        Búsqueda de contexto general del mercado.
        
        Útil para entender el sentiment general antes de operar.
        """
        queries = [
            "stock market today analysis",
            "Fed interest rates news",
            "S&P 500 outlook",
        ]
        
        all_results = []
        for query in queries:
            results = await self.search(query, count=3, freshness="pd")
            all_results.extend(results)
        
        return all_results[:10]  # Limitar total


def format_search_results_for_context(results: List[SearchResult]) -> str:
    """
    Formatear resultados de búsqueda para incluir en el contexto del LLM.
    
    Args:
        results: Lista de SearchResult
        
    Returns:
        String formateado para el prompt
    """
    if not results:
        return "No recent news found."
    
    formatted = []
    for i, r in enumerate(results, 1):
        formatted.append(f"{i}. {r.to_context_string()}")
    
    return "\n\n".join(formatted)
```

---

### 3.3. Modificar Claude Agent para Tool Use

**Archivo**: `src/agents/llm/agents/claude_agent.py`

Este archivo necesita modificaciones significativas para soportar tool_use. Aquí está la versión actualizada:

```python
"""
Claude Agent con soporte para Web Search via Tool Use.

Este agente puede buscar información actualizada del mercado
antes de tomar decisiones de trading.
"""

import json
import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

import anthropic

from src.agents.llm.interfaces import (
    LLMAgent,
    AgentContext,
    AgentDecision,
    AutonomyLevel,
)
from src.agents.llm.prompts import get_prompt_for_autonomy
from src.agents.llm.web_search import WebSearchClient, format_search_results_for_context
from src.agents.llm.cost_tracker import (
    get_cost_tracker,
    AgentCostRecord,
    TokenUsage,
    SearchUsage,
)
from src.strategies.interfaces import Signal, SignalDirection

logger = logging.getLogger(__name__)


# Definición del tool de web search para Claude
WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the web for current financial news, market analysis, "
        "earnings reports, and other relevant information. Use this to get "
        "up-to-date information before making trading decisions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The search query. Be specific and include the stock symbol "
                    "if searching for company-specific news. "
                    "Examples: 'AAPL earnings Q4 2024', 'Fed interest rate decision', "
                    "'SPY technical analysis today'"
                )
            },
            "search_type": {
                "type": "string",
                "enum": ["news", "analysis", "earnings", "general"],
                "description": "Type of information to search for"
            }
        },
        "required": ["query"]
    }
}


class ClaudeAgent(LLMAgent):
    """
    Agente de trading basado en Claude con capacidad de web search.
    
    Características:
    - Análisis de contexto técnico y fundamental
    - Búsqueda web para información actualizada
    - Tracking de costes por consulta
    - Respuestas estructuradas en JSON
    """
    
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    MAX_SEARCH_CALLS = 3  # Límite de búsquedas por decisión
    
    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        enable_web_search: bool = True,
    ):
        """
        Args:
            api_key: Anthropic API key (o desde env ANTHROPIC_API_KEY)
            model: Modelo a usar
            max_tokens: Máximo tokens de respuesta
            temperature: Temperatura (0.0 = determinístico)
            enable_web_search: Habilitar búsqueda web
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.enable_web_search = enable_web_search
        
        # Clientes auxiliares
        self.web_search = WebSearchClient() if enable_web_search else None
        self.cost_tracker = get_cost_tracker()
        
        # Estado de la sesión actual
        self._current_record: Optional[AgentCostRecord] = None
        
    @property
    def provider(self) -> str:
        return "claude"
    
    async def decide(self, context: AgentContext) -> AgentDecision:
        """
        Tomar decisión de trading basada en el contexto.
        
        Flujo:
        1. Construir prompt con contexto
        2. Llamar a Claude (puede solicitar web search)
        3. Si hay tool_use, ejecutar búsquedas
        4. Obtener decisión final
        5. Registrar costes
        """
        # Iniciar tracking
        self._current_record = self.cost_tracker.create_record(
            strategy_id="ai_agent_swing",
            model=self.model,
        )
        self._current_record.context_symbols_count = len(context.watchlist)
        self._current_record.regime = context.regime.regime
        
        try:
            # 1. Construir mensajes
            system_prompt = get_prompt_for_autonomy(context.autonomy_level)
            user_message = self._build_user_message(context)
            
            messages = [{"role": "user", "content": user_message}]
            
            # 2. Preparar tools si web search está habilitado
            tools = [WEB_SEARCH_TOOL] if self.enable_web_search and self.web_search.is_available else None
            
            # 3. Primera llamada a Claude
            response = await self._call_claude(
                system=system_prompt,
                messages=messages,
                tools=tools,
            )
            
            # 4. Procesar respuesta (puede haber tool_use)
            final_response = await self._process_response(
                response=response,
                system=system_prompt,
                messages=messages,
                tools=tools,
            )
            
            # 5. Parsear decisión
            decision = self._parse_decision(final_response, context)
            
            # 6. Completar y guardar registro de costes
            self._current_record.signals_generated = len(decision.signals)
            self._current_record.decision_confidence = decision.confidence
            self._current_record.calculate_costs()
            self.cost_tracker.save_record(self._current_record)
            
            return decision
            
        except Exception as e:
            logger.error(f"Error in Claude Agent decide: {e}", exc_info=True)
            # Guardar registro aunque haya error
            if self._current_record:
                self._current_record.calculate_costs()
                self.cost_tracker.save_record(self._current_record)
            raise
    
    def _build_user_message(self, context: AgentContext) -> str:
        """Construir mensaje de usuario con todo el contexto."""
        
        # Formatear watchlist
        watchlist_str = ""
        for symbol_data in context.watchlist:
            watchlist_str += f"""
### {symbol_data.symbol} - {symbol_data.name}
- Price: ${symbol_data.current_price:.2f} ({symbol_data.change_pct:+.2f}%)
- Volume: {symbol_data.volume:,.0f} (avg: {symbol_data.avg_volume_20d:,.0f})
- RSI(14): {symbol_data.rsi_14:.1f}
- MACD: {symbol_data.macd:.3f} (signal: {symbol_data.macd_signal:.3f})
- SMAs: 20={symbol_data.sma_20:.2f}, 50={symbol_data.sma_50:.2f}, 200={symbol_data.sma_200:.2f}
- Bollinger: {symbol_data.bb_lower:.2f} / {symbol_data.bb_middle:.2f} / {symbol_data.bb_upper:.2f}
- ATR(14): {symbol_data.atr_14:.2f}
- ADX(14): {symbol_data.adx_14:.1f}
"""
        
        # Formatear posiciones actuales
        positions_str = ""
        if context.portfolio.positions:
            for pos in context.portfolio.positions:
                positions_str += f"""
- {pos.symbol}: {pos.quantity} shares @ ${pos.avg_price:.2f}
  Current: ${pos.current_price:.2f} | PnL: ${pos.unrealized_pnl:.2f} ({pos.unrealized_pnl_pct:+.2f}%)
  Entry: {pos.entry_date} | Days held: {pos.days_held}
"""
        else:
            positions_str = "No open positions."
        
        # Construir mensaje completo
        message = f"""
# TRADING ANALYSIS REQUEST

## Current Date & Time
{context.timestamp.strftime("%Y-%m-%d %H:%M UTC")}

## Market Regime
- **Regime**: {context.regime.regime}
- **Confidence**: {context.regime.confidence:.2f}
- **Days in regime**: {context.regime.days_in_regime}
- Probabilities: {json.dumps(context.regime.probabilities)}

## Market Context
- SPY: {context.market.spy_change_pct:+.2f}%
- QQQ: {context.market.qqq_change_pct:+.2f}%
- VIX: {context.market.vix_level:.1f} ({context.market.vix_change_pct:+.2f}%)

## Portfolio Status
- **Total Value**: ${context.portfolio.total_value:,.2f}
- **Cash Available**: ${context.portfolio.cash_available:,.2f}
- **Invested**: ${context.portfolio.invested_value:,.2f}
- **Daily P&L**: ${context.portfolio.daily_pnl:,.2f} ({context.portfolio.daily_pnl_pct:+.2f}%)
- **Total P&L**: ${context.portfolio.total_pnl:,.2f} ({context.portfolio.total_pnl_pct:+.2f}%)

### Current Positions
{positions_str}

## Risk Limits
- Max position size: {context.risk_limits.max_position_pct}% of portfolio
- Max portfolio risk: {context.risk_limits.max_portfolio_risk_pct}%
- Max daily trades: {context.risk_limits.max_daily_trades}
- Max daily loss: {context.risk_limits.max_daily_loss_pct}%
- Today's trades: {context.risk_limits.current_daily_trades}
- Today's P&L: {context.risk_limits.current_daily_pnl_pct:+.2f}%

## Watchlist Analysis
{watchlist_str}

## Instructions
1. First, use web_search to find relevant current news about the market or specific symbols if needed.
2. Analyze the technical setup and fundamental context.
3. Provide your trading decision in the required JSON format.

**Important**: Only suggest trades with high conviction (confidence > 0.8). When in doubt, recommend HOLD.
"""
        return message
    
    async def _call_claude(
        self,
        system: str,
        messages: List[Dict],
        tools: List[Dict] = None,
    ) -> anthropic.types.Message:
        """Llamada a la API de Claude."""
        
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system,
            "messages": messages,
        }
        
        if tools:
            kwargs["tools"] = tools
        
        response = self.client.messages.create(**kwargs)
        
        # Actualizar tracking de tokens
        self._current_record.token_usage.input_tokens += response.usage.input_tokens
        self._current_record.token_usage.output_tokens += response.usage.output_tokens
        self._current_record.api_calls += 1
        
        # Cache tokens si están disponibles
        if hasattr(response.usage, 'cache_read_input_tokens'):
            self._current_record.token_usage.cache_read_tokens += response.usage.cache_read_input_tokens
        if hasattr(response.usage, 'cache_creation_input_tokens'):
            self._current_record.token_usage.cache_creation_tokens += response.usage.cache_creation_input_tokens
        
        return response
    
    async def _process_response(
        self,
        response: anthropic.types.Message,
        system: str,
        messages: List[Dict],
        tools: List[Dict],
    ) -> str:
        """
        Procesar respuesta de Claude, manejando tool_use si es necesario.
        
        Returns:
            Texto final de la respuesta (JSON de decisión)
        """
        search_count = 0
        
        while response.stop_reason == "tool_use" and search_count < self.MAX_SEARCH_CALLS:
            # Encontrar tool_use blocks
            tool_uses = [
                block for block in response.content
                if block.type == "tool_use"
            ]
            
            if not tool_uses:
                break
            
            # Procesar cada tool_use
            tool_results = []
            for tool_use in tool_uses:
                if tool_use.name == "web_search":
                    search_count += 1
                    
                    query = tool_use.input.get("query", "")
                    search_type = tool_use.input.get("search_type", "general")
                    
                    logger.info(f"Web search requested: '{query}' (type: {search_type})")
                    
                    # Ejecutar búsqueda
                    results = await self.web_search.search(
                        query=query,
                        count=5,
                        freshness="pw" if search_type == "news" else "pm",
                    )
                    
                    # Formatear resultados
                    results_text = format_search_results_for_context(results)
                    
                    # Actualizar tracking
                    self._current_record.search_usage.searches_performed += 1
                    self._current_record.search_usage.queries.append(query)
                    self._current_record.search_usage.results_tokens += len(results_text.split()) * 1.3  # Estimado
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": results_text,
                    })
            
            # Construir mensajes con resultados
            # Añadir la respuesta del asistente que pidió los tools
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
            
            messages = messages + [
                {"role": "assistant", "content": assistant_content},
                {"role": "user", "content": tool_results},
            ]
            
            # Nueva llamada con resultados
            response = await self._call_claude(
                system=system,
                messages=messages,
                tools=tools,
            )
        
        # Extraer texto final
        for block in response.content:
            if block.type == "text":
                return block.text
        
        return ""
    
    def _parse_decision(self, response_text: str, context: AgentContext) -> AgentDecision:
        """Parsear respuesta JSON a AgentDecision."""
        try:
            # Limpiar respuesta (puede tener markdown)
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            data = json.loads(text.strip())
            
            # Parsear señales
            signals = []
            for sig_data in data.get("signals", []):
                direction = SignalDirection(sig_data["direction"].upper())
                
                signal = Signal(
                    strategy_id="ai_agent_swing",
                    symbol=sig_data["symbol"],
                    direction=direction,
                    confidence=sig_data.get("confidence", 0.5),
                    entry_price=sig_data.get("entry_price"),
                    stop_loss=sig_data.get("stop_loss"),
                    take_profit=sig_data.get("take_profit"),
                    reasoning=sig_data.get("reasoning", ""),
                    metadata={
                        "size_suggestion": sig_data.get("size_suggestion"),
                        "agent": "claude",
                        "model": self.model,
                    }
                )
                signals.append(signal)
            
            return AgentDecision(
                decision_id=str(uuid.uuid4())[:8],
                timestamp=datetime.now(timezone.utc),
                market_view=data.get("market_view", "neutral"),
                confidence=data.get("confidence", 0.5),
                reasoning=data.get("reasoning", ""),
                signals=signals,
                context_id=context.context_id,
                autonomy_level=context.autonomy_level,
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.debug(f"Response was: {response_text[:500]}")
            
            # Retornar decisión vacía
            return AgentDecision(
                decision_id=str(uuid.uuid4())[:8],
                timestamp=datetime.now(timezone.utc),
                market_view="uncertain",
                confidence=0.0,
                reasoning=f"Failed to parse response: {str(e)}",
                signals=[],
                context_id=context.context_id,
                autonomy_level=context.autonomy_level,
            )
```

---

### 3.4. Actualizar Prompts para Web Search

**Archivo**: `src/agents/llm/prompts/base.py`

```python
"""
Prompts base y compartidos para el AI Agent.
Actualizados para incluir instrucciones de web search.
"""

SYSTEM_PROMPT_BASE = """
Eres un AI Trading Agent experto operando en el sistema Nexus Trading.
Tu objetivo es analizar el mercado y tomar decisiones de trading racionales,
basadas en datos y gestionando estrictamente el riesgo.

## Tus Capacidades

1. **Análisis Técnico**: Recibes indicadores calculados (RSI, MACD, SMAs, Bollinger, ATR, ADX).
2. **Contexto de Mercado**: Conoces el régimen actual (BULL/BEAR/SIDEWAYS/VOLATILE) y estado del portfolio.
3. **Web Search**: Puedes buscar noticias y análisis actualizados usando la herramienta web_search.

## Tus Principios Fundamentales

1. **PRESERVACIÓN DE CAPITAL**: La gestión de riesgo es más importante que las ganancias.
2. **ANÁLISIS BASADO EN DATOS**: No adivines. Usa los indicadores, el contexto y la información actual.
3. **DISCIPLINA**: Sigue tu nivel de autonomía asignado. No alucines datos.
4. **TRANSPARENCIA**: Explica siempre tu razonamiento paso a paso.

## Uso de Web Search

DEBES usar web_search cuando:
- Vas a tomar una decisión de entrada (BUY/LONG)
- Hay earnings próximos de un símbolo en tu watchlist
- El mercado muestra movimientos inusuales (VIX alto, gaps grandes)
- Necesitas contexto sobre eventos macro (Fed, datos económicos)

NO uses web_search para:
- Decidir HOLD en posiciones existentes sin cambios significativos
- Preguntas sobre indicadores técnicos (ya los tienes)
- Información histórica (usa los datos proporcionados)

Limita tus búsquedas a 2-3 por decisión para mantener costes controlados.

## Formato de Respuesta

SIEMPRE responde con un JSON válido con esta estructura:

{
  "market_view": "bullish" | "bearish" | "neutral" | "uncertain",
  "confidence": 0.0 a 1.0,
  "reasoning": "Explicación detallada incluyendo qué información de web search usaste...",
  "signals": [
    {
      "symbol": "TICKER",
      "direction": "LONG" | "SHORT" | "CLOSE",
      "entry_price": float,
      "stop_loss": float,
      "take_profit": float,
      "size_suggestion": float (0.0 a 1.0, % del capital),
      "reasoning": "Por qué este trade específico, qué noticias/datos lo soportan",
      "confidence": 0.0 a 1.0
    }
  ]
}

Si no recomiendas ninguna acción, la lista "signals" debe estar vacía [].
"""

JSON_OUTPUT_INSTRUCTIONS = """
## Recordatorio de Formato

Tu respuesta DEBE ser un único objeto JSON válido.
No incluyas texto antes o después del JSON.
No uses markdown code blocks.
"""
```

**Archivo**: `src/agents/llm/prompts/conservative.py`

```python
"""
Prompt para nivel de autonomía CONSERVATIVE con web search.
"""

from .base import SYSTEM_PROMPT_BASE, JSON_OUTPUT_INSTRUCTIONS

CONSERVATIVE_PROMPT = f"""{SYSTEM_PROMPT_BASE}

## NIVEL DE AUTONOMÍA: CONSERVATIVE

En este modo, tu función principal es ANALISTA DE RIESGOS CAUTELOSO.

### Reglas Estrictas

1. **NO sugieras trades agresivos** - Solo setups excepcionales (A+)
2. **SIEMPRE busca confirmación** - Usa web_search para verificar que no hay eventos adversos próximos
3. **Prioriza protección** - Ante la duda, recomienda NO OPERAR
4. **Ratio mínimo 1:3** - Risk/Reward debe ser al menos 1:3

### Proceso de Decisión

1. **Analiza el Régimen**: Si es VOLATILE o BEAR, rechaza nuevas entradas largas.
2. **Verifica Tendencia**: Precio debe estar alineado con SMA50/200.
3. **Busca Noticias**: Usa web_search para verificar:
   - No hay earnings en los próximos 3 días
   - No hay eventos macro importantes hoy/mañana
   - El sector del activo no está bajo presión
4. **Confirma Indicadores**: RSI no sobrecomprado, MACD sin divergencias.
5. **Evalúa Riesgo**: Solo si TODO está alineado, emite señal con confianza > 0.8.

### Ejemplos de Búsquedas Útiles

- "AAPL earnings date 2024" - Verificar calendario de earnings
- "Fed meeting this week" - Eventos macro
- "Technology sector news today" - Contexto sectorial
- "SPY unusual options activity" - Detectar movimientos institucionales

{JSON_OUTPUT_INSTRUCTIONS}
"""
```

---

### 3.5. Variables de Entorno Necesarias

Añadir a `.env`:

```bash
# .env

# Claude API (ya debería existir)
ANTHROPIC_API_KEY=sk-ant-...

# Brave Search API (NUEVO)
# Obtener en: https://brave.com/search/api/
# Plan gratuito: 2,000 búsquedas/mes
BRAVE_SEARCH_API_KEY=BSA...

# Opcional: Alternativos
# TAVILY_API_KEY=tvly-...
# SERP_API_KEY=...
```

---

## 4. Testing

### 4.1. Test del CostTracker

```python
# tests/agents/llm/test_cost_tracker.py

import pytest
from datetime import date
from pathlib import Path
import tempfile
import shutil

from src.agents.llm.cost_tracker import (
    CostTracker,
    AgentCostRecord,
    TokenUsage,
    SearchUsage,
)


@pytest.fixture
def temp_cost_dir():
    """Crear directorio temporal para tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_cost_calculation_sonnet():
    """Test cálculo de costes para Claude Sonnet."""
    record = AgentCostRecord(
        model="claude-3-5-sonnet-20241022",
        token_usage=TokenUsage(input_tokens=1500, output_tokens=800),
    )
    
    cost = record.calculate_costs()
    
    # Input: 1500/1000 * 0.003 = 0.0045
    # Output: 800/1000 * 0.015 = 0.012
    # Total: 0.0165
    assert abs(record.input_cost - 0.0045) < 0.0001
    assert abs(record.output_cost - 0.012) < 0.0001
    assert abs(cost - 0.0165) < 0.0001


def test_cost_tracker_save_and_retrieve(temp_cost_dir):
    """Test guardar y recuperar registros."""
    tracker = CostTracker(data_dir=temp_cost_dir)
    
    # Crear y guardar registro
    record = tracker.create_record(strategy_id="test_strategy")
    record.token_usage = TokenUsage(input_tokens=1000, output_tokens=500)
    record.search_usage = SearchUsage(searches_performed=2, queries=["test1", "test2"])
    tracker.save_record(record)
    
    # Recuperar resumen
    summary = tracker.get_daily_summary()
    
    assert summary["total_records"] == 1
    assert summary["total_searches"] == 2
    assert summary["total_cost_usd"] > 0


def test_monthly_summary(temp_cost_dir):
    """Test resumen mensual."""
    tracker = CostTracker(data_dir=temp_cost_dir)
    
    # Guardar varios registros
    for i in range(3):
        record = tracker.create_record(strategy_id="test")
        record.token_usage = TokenUsage(input_tokens=1000, output_tokens=500)
        tracker.save_record(record)
    
    summary = tracker.get_monthly_summary()
    
    assert summary["total_decisions"] == 3
    assert summary["days_with_data"] == 1
```

### 4.2. Test de Web Search

```python
# tests/agents/llm/test_web_search.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.llm.web_search import (
    WebSearchClient,
    SearchResult,
    format_search_results_for_context,
)


def test_search_result_formatting():
    """Test formateo de resultados para contexto."""
    results = [
        SearchResult(
            title="AAPL Beats Earnings",
            url="https://example.com/news",
            snippet="Apple reported strong Q4...",
            published_date="2 hours ago",
        )
    ]
    
    formatted = format_search_results_for_context(results)
    
    assert "AAPL Beats Earnings" in formatted
    assert "2 hours ago" in formatted
    assert "Apple reported strong" in formatted


@pytest.mark.asyncio
async def test_search_without_api_key():
    """Test que búsqueda sin API key retorna vacío."""
    client = WebSearchClient(api_key=None)
    
    results = await client.search("test query")
    
    assert results == []
    assert not client.is_available


@pytest.mark.asyncio
async def test_search_with_mock_api():
    """Test búsqueda con API mockeada."""
    with patch('aiohttp.ClientSession') as mock_session:
        # Configurar mock
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "web": {
                "results": [
                    {
                        "title": "Test Result",
                        "url": "https://test.com",
                        "description": "Test description",
                        "age": "1 day ago",
                    }
                ]
            }
        })
        
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        
        client = WebSearchClient(api_key="test_key")
        results = await client.search("test")
        
        assert len(results) == 1
        assert results[0].title == "Test Result"
```

---

## 5. Checklist de Implementación

- [ ] Crear `src/agents/llm/cost_tracker.py`
- [ ] Crear `src/agents/llm/web_search.py`
- [ ] Modificar `src/agents/llm/agents/claude_agent.py` para tool_use
- [ ] Actualizar `src/agents/llm/prompts/base.py`
- [ ] Actualizar `src/agents/llm/prompts/conservative.py`
- [ ] Actualizar `src/agents/llm/prompts/moderate.py` (si existe)
- [ ] Añadir `BRAVE_SEARCH_API_KEY` a `.env.example`
- [ ] Crear directorio `data/costs/` con `.gitkeep`
- [ ] Crear tests para CostTracker
- [ ] Crear tests para WebSearchClient
- [ ] Test de integración completo del agente
- [ ] Verificar que costes se persisten correctamente

---

## 6. Notas Importantes

### Fallback sin Web Search
Si `BRAVE_SEARCH_API_KEY` no está configurado, el agente funcionará normalmente pero sin capacidad de búsqueda. Los prompts detectarán esto y no solicitarán búsquedas.

### Límites de API
- **Brave Search Free**: 2,000 búsquedas/mes
- **Brave Search Basic** ($5/mes): 10,000 búsquedas/mes
- Con 3 búsquedas/decisión × 6 decisiones/día = 18 búsquedas/día = ~540/mes
- El plan gratuito debería ser suficiente para el MVP

### Costes Proyectados (Escenario Realista)

| Concepto | Cantidad | Coste Unitario | Total Mensual |
|----------|----------|----------------|---------------|
| Claude API | 180 llamadas | $0.024 | $4.32 |
| Brave Search | 540 búsquedas | $0 (free tier) | $0 |
| **TOTAL** | - | - | **~$4.50/mes** |

### Monitorización
El dashboard (DOC-03) mostrará métricas de costes en tiempo real, permitiendo detectar anomalías (ej: agente haciendo demasiadas búsquedas).
