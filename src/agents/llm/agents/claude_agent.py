"""
Implementación del agente usando Claude (Anthropic).
"""

import os
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Any

try:
    import anthropic
except ImportError:
    anthropic = None

from src.agents.llm.interfaces import (
    LLMAgent,
    AgentContext,
    AgentDecision,
    AutonomyLevel,
    MarketView,
)
from src.strategies.interfaces import Signal, SignalDirection, MarketRegime
from src.agents.llm.prompts import CONSERVATIVE_PROMPT, MODERATE_PROMPT
from src.agents.llm.web_search import WebSearchClient
from src.agents.llm.cost_tracker import get_cost_tracker

logger = logging.getLogger(__name__)


class ClaudeAgent(LLMAgent):
    """
    Agente que usa modelos Claude de Anthropic.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20240620",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        default_autonomy: AutonomyLevel = AutonomyLevel.CONSERVATIVE,
        timeout_seconds: float = 60.0,
    ):
        """
        Inicializar ClaudeAgent.
        
        Args:
            api_key: API Key de Anthropic (opcional si está en env)
            model: ID del modelo a usar
            max_tokens: Límite de tokens de salida
            temperature: Creatividad (0.0 para trading)
            default_autonomy: Nivel de autonomía por defecto
            timeout_seconds: Timeout para llamadas a API
        """
        if not anthropic:
            raise ImportError("anthropic package not installed. Run 'pip install anthropic'")
            
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")
            
        self.client = anthropic.AsyncAnthropic(api_key=self._api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._default_autonomy = default_autonomy
        self._timeout = timeout_seconds
        
        # Tools initialization
        self.search_client = WebSearchClient()
        self.cost_tracker = get_cost_tracker()
        
        # Tool definition
        self.WEB_SEARCH_TOOL = {
            "name": "web_search",
            "description": "Search the web for current financial news, market sentiment, and analyst ratings. Use this when you need real-time data not present in your context.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific search query (e.g., 'AAPL earnings report Q3 2024 analysis')"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why you need this information"
                    }
                },
                "required": ["query"]
            }
        }
        
    @property
    def agent_id(self) -> str:
        return f"claude_agent_{self._model}"
    
    @property
    def provider(self) -> str:
        return "claude"
        
    async def decide(self, context: AgentContext) -> AgentDecision:
        """
        Toma una decisión usando Claude.
        """
        start_time = time.time()
        
        # 0. Chequeo de seguridad: No operar en régimen VOLATILE a menos que EXPERIMENTAL
        if context.regime.regime == "VOLATILE" and context.autonomy_level != AutonomyLevel.EXPERIMENTAL:
            logger.info("Skipping Claude call due to VOLATILE regime")
            return AgentDecision(
                decision_id=f"dec_skip_{int(time.time())}",
                timestamp=datetime.now(timezone.utc),
                market_view=MarketView.UNCERTAIN,
                confidence=0.0,
                reasoning="Market regime is VOLATILE. Trading skipped for safety.",
                signals=[],
                model_used=self._model,
                tokens_used=0,
                execution_time_ms=0
            )
        
        # 1. Seleccionar Prompt según autonomía
        system_prompt = self._get_system_prompt(context.autonomy_level)
        
        # 2. Preparar historial de mensajes
        messages = [
            {"role": "user", "content": context.to_prompt_text()}
        ]
        
        search_count = 0
        MAX_SEARCHES = 3  # DOC-07 limit
        
        try:
            while True:
                # 3. Llamada a la API
                logger.info(f"Calling Claude ({self._model}) [Loop {search_count}]")
                logger.debug(f"FULL PROMPT:\n{json.dumps(messages, indent=2, default=str)}")
                
                # Check if we should disable tools (reached limit)
                tools = [self.WEB_SEARCH_TOOL] if search_count < MAX_SEARCHES else []
                
                response = await self.client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                    timeout=self._timeout
                )
                
                # Track Cost
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                self.cost_tracker.track_llm_call(
                    self.agent_id, self._model, input_tokens, output_tokens, 
                    context=f"Loop {search_count}"
                )
                
                # Process response
                stop_reason = response.stop_reason
                content_blocks = response.content
                logger.debug(f"CLAUDE RESPONSE:\n{content_blocks}")
                
                # Add assistant response to history
                # Convert blocks to simple list of dicts for message history
                # We reuse the raw 'content' list from the response object which is compatible
                messages.append({"role": "assistant", "content": content_blocks})
                
                # Check for Tool Use
                tool_uses = [b for b in content_blocks if b.type == "tool_use"]
                
                if tool_uses:
                    if search_count >= MAX_SEARCHES:
                         # Should ideally not happen if we passed empty tools, but safety check
                        logger.warning("Max searches reached, forcing stop.")
                        break
                        
                    # Execute tools
                    tool_results = []
                    for tool_use in tool_uses:
                        if tool_use.name == "web_search":
                            query = tool_use.input.get("query")
                            logger.info(f"Executing Web Search: {query}")
                            
                            # Track search cost
                            self.cost_tracker.track_search(self.agent_id, 1, context=query)
                            
                            # Execute search
                            results = await self.search_client.search(query)
                            
                            # Format result
                            result_text = "No results found."
                            if results:
                                result_text = "\n".join([r.to_string() for r in results])
                                
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": result_text
                            })
                            search_count += 1
                            
                    # Add tool results to history
                    if tool_results:
                        messages.append({"role": "user", "content": tool_results})
                        # Continue loop to let Claude process results
                        continue
                
                # If no tool use or done tools, we expect the JSON decision
                # Look for text content
                text_content = next((b.text for b in content_blocks if b.type == "text"), "")
                
                if not text_content and not tool_uses:
                    # Should not happen
                    raise ValueError("Empty response from Claude")
                
                # Try to parse JSON from the final text response
                if text_content:
                    try:
                        parsed_json = self._extract_json(text_content)
                        if parsed_json:
                            execution_time = int((time.time() - start_time) * 1000)
                            # We estimate total tokens loosely as sum of last call (accurate enough for now)
                            total_tokens = response.usage.input_tokens + response.usage.output_tokens
                            
                            return self._create_decision(
                                parsed_json, 
                                context, 
                                execution_time,
                                total_tokens
                            )
                    except ValueError:
                         # If we can't parse JSON but stopped, maybe it just chatted?
                         pass
                
                # If we are here, we might need to prompt it to finalize?
                # Or maybe it outputted text without JSON.
                if stop_reason == "end_turn" and not tool_uses:
                     # Force JSON extraction from what we have
                     parsed_json = self._extract_json(text_content)
                     execution_time = int((time.time() - start_time) * 1000)
                     return self._create_decision(
                        parsed_json, 
                        context, 
                        execution_time,
                        response.usage.output_tokens + response.usage.input_tokens
                    )
            
        except Exception as e:
            logger.error(f"Error in ClaudeAgent.decide: {e}")
            # Retornar decisión vacía/error
            return AgentDecision(
                decision_id=f"error_{int(time.time())}",
                timestamp=datetime.now(timezone.utc),
                market_view=MarketView.UNCERTAIN,
                confidence=0.0,
                reasoning=f"ERROR: {str(e)}",
                signals=[],
                model_used=self._model,
                tokens_used=0,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
    
    def _get_system_prompt(self, autonomy: AutonomyLevel) -> str:
        """Selecciona el prompt adecuado."""
        if autonomy == AutonomyLevel.CONSERVATIVE:
            return CONSERVATIVE_PROMPT
        elif autonomy == AutonomyLevel.MODERATE:
            return MODERATE_PROMPT
        # Fallback to moderate for experimental for now
        return MODERATE_PROMPT
    
    def _extract_json(self, text: str) -> dict:
        """Extrae y parsea JSON de la respuesta."""
        text = text.strip()
        
        def try_parse(s):
            try:
                return json.loads(s, strict=False)
            except json.JSONDecodeError:
                return None

        # 1. Intentar parseo directo
        res = try_parse(text)
        if res: return res

        # 2. Buscar bloque json ```json ... ```
        import re
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            res = try_parse(match.group(1))
            if res: return res

        # 3. Buscar primer { y último }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            res = try_parse(text[start:end+1])
            if res: return res
            
        raise ValueError(f"No valid JSON found in response. Content start: {text[:50]}...")
            
    def _create_decision(
        self, 
        data: dict, 
        context: AgentContext,
        exec_time: int,
        tokens: int
    ) -> AgentDecision:
        """Crea objeto AgentDecision desde dict."""
        
        signals = []
        for sig_data in data.get("signals", []):
            try:
                # Mapear a objeto Signal
                signal = Signal(
                    strategy_id=self.agent_id,
                    symbol=sig_data.get("symbol"),
                    direction=SignalDirection(sig_data.get("direction")),
                    confidence=sig_data.get("confidence", 0.0),
                    entry_price=sig_data.get("entry_price"),
                    stop_loss=sig_data.get("stop_loss"),
                    take_profit=sig_data.get("take_profit"),
                    size_suggestion=sig_data.get("size_suggestion"),
                    regime_at_signal=MarketRegime(context.regime.regime),
                    regime_confidence=context.regime.confidence,
                    reasoning=sig_data.get("reasoning", ""),
                    metadata={"autonomy": context.autonomy_level.value}
                )
                signals.append(signal)
            except Exception as e:
                logger.warning(f"Skipping invalid signal data: {sig_data} - {e}")
        
        return AgentDecision(
            decision_id=f"dec_{int(time.time())}",
            timestamp=datetime.now(timezone.utc),
            market_view=MarketView(data.get("market_view", "uncertain")),
            confidence=data.get("confidence", 0.0),
            reasoning=data.get("reasoning", ""),
            signals=signals,
            model_used=self._model,
            tokens_used=tokens,
            execution_time_ms=exec_time
        )
