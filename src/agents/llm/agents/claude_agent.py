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
        
        # 2. Preparar mensaje de usuario con el contexto
        user_message = context.to_prompt_text()
        
        try:
            # 3. Llamada a la API
            logger.info(f"Calling Claude ({self._model}) with context_id={context.context_id}")
            
            response = await self.client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ],
                timeout=self._timeout
            )
            
            # 4. Parsear respuesta
            content_text = response.content[0].text
            parsed_json = self._extract_json(content_text)
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # 5. Convertir a AgentDecision
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
