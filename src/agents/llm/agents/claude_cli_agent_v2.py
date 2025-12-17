"""
Implementación mejorada del agente usando Claude Code CLI.

Mejoras respecto a la versión anterior:
1. Usa el prompt de competición de trading
2. Implementa timeout correctamente
3. Mejor manejo de errores y limpieza de procesos
4. Soporte para modo de revisión de portfolio
"""

import asyncio
import json
import logging
import os
import re
import time
import platform
from datetime import datetime, timezone
from typing import Optional, Any, List

from src.agents.llm.interfaces import (
    LLMAgent,
    AgentContext,
    AgentDecision,
    AutonomyLevel,
    MarketView,
)
from src.strategies.interfaces import Signal, SignalDirection, MarketRegime
from src.agents.llm.prompts.competition import (
    build_competition_prompt,
    build_review_prompt,
    COMPETITION_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class ClaudeCliAgent(LLMAgent):
    """
    Agente que usa la herramienta CLI 'claude' (Claude Code) localmente.
    
    Permite acceso a herramientas nativas:
    - Web search para noticias y datos en tiempo real
    - File interaction para análisis
    - Razonamiento extendido
    
    Usa el marco de "Competición de Trading" para mejorar las respuestas.
    """
    
    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        timeout_seconds: float = 180.0,  # Aumentado para permitir búsquedas web
        cwd: str = None,
        use_competition_prompt: bool = True,
    ):
        """
        Inicializa el agente CLI.
        
        Args:
            model: Modelo a usar (CLI generalmente autoselecciona)
            timeout_seconds: Timeout máximo para cada decisión
            cwd: Directorio de trabajo para el proceso
            use_competition_prompt: Si usar el prompt de competición (recomendado)
        """
        self._model = model
        self._timeout = timeout_seconds
        self._cwd = cwd or os.getcwd()
        self._use_competition_prompt = use_competition_prompt
        self._proc = None
        self._running = False
        
    @property
    def agent_id(self) -> str:
        return "nexus_ai_competitor"  # Nombre de la competición
    
    @property
    def provider(self) -> str:
        return "claude_cli"

    async def decide(self, context: AgentContext) -> AgentDecision:
        """
        Toma una decisión lanzando una sesión de Claude CLI.
        
        El proceso es efímero (se crea y destruye por cada decisión)
        para evitar contaminación de contexto entre sesiones.
        """
        start_time = time.time()
        response_text = ""
        tokens_est = 0
        
        try:
            # 1. Construir prompt
            if self._use_competition_prompt:
                full_message = build_competition_prompt(
                    context_data=context.to_prompt_text(),
                    current_datetime=context.timestamp,
                    additional_instructions=context.notes
                )
            else:
                # Fallback al prompt básico
                full_message = self._build_basic_prompt(context)
            
            tokens_est = len(full_message) // 4
            logger.info(f"Prompt size: ~{tokens_est} tokens")
            
            # 2. Iniciar proceso
            await self._start_process()
            
            # 3. Enviar mensaje con timeout
            try:
                response_text = await asyncio.wait_for(
                    self._send_and_wait(full_message),
                    timeout=self._timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout after {self._timeout}s waiting for Claude CLI response")
                raise TimeoutError(f"Claude CLI did not respond within {self._timeout} seconds")
            
            # 4. Limpiar proceso
            await self._stop_process()
            
            # 5. Parsear respuesta
            logger.debug(f"Raw response length: {len(response_text)} chars")
            parsed_json = self._extract_json(response_text)
            
            if parsed_json:
                execution_time = int((time.time() - start_time) * 1000)
                return self._create_decision(
                    parsed_json, context, execution_time, tokens_est
                )
            
            # Si no hay JSON válido, intentar crear decisión desde texto
            logger.warning("No valid JSON found, attempting text parsing")
            return self._create_fallback_decision(
                response_text, context, int((time.time() - start_time) * 1000)
            )

        except Exception as e:
            logger.error(f"Error in ClaudeCliAgent.decide: {e}", exc_info=True)
            await self._stop_process()
            
            return AgentDecision(
                decision_id=f"err_{int(time.time())}",
                timestamp=datetime.now(timezone.utc),
                market_view=MarketView.UNCERTAIN,
                confidence=0.0,
                reasoning=f"Error executing Claude CLI: {str(e)}\n\nPartial response: {response_text[:500] if response_text else 'None'}",
                signals=[],
                model_used=self._model,
                tokens_used=tokens_est,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

    async def _start_process(self):
        """Inicia el proceso claude CLI."""
        if self._proc and self._running:
            logger.warning("Process already running, stopping first")
            await self._stop_process()
        
        cmd = [
            "claude",
            "--print",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--permission-mode", "bypassPermissions",
            "--verbose"
        ]
        
        if platform.system() == "Windows":
            cmd[0] = "claude.cmd"
        
        env = os.environ.copy()
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "100000"
        
        logger.info(f"Starting Claude CLI process...")
        logger.debug(f"Command: {' '.join(cmd)}")
        
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._cwd,
            env=env
        )
        self._running = True
        logger.info(f"Claude CLI process started (PID: {self._proc.pid})")

    async def _stop_process(self):
        """Detiene el proceso de forma segura."""
        if not self._proc:
            return
            
        try:
            # Cerrar stdin para señalar EOF
            if self._proc.stdin and not self._proc.stdin.is_closing():
                self._proc.stdin.close()
                await self._proc.stdin.wait_closed()
            
            # Esperar terminación con timeout
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Process did not terminate gracefully, killing...")
                self._proc.kill()
                await self._proc.wait()
            
            # Leer stderr si hay errores
            if self._proc.stderr:
                try:
                    stderr_output = await asyncio.wait_for(
                        self._proc.stderr.read(),
                        timeout=1.0
                    )
                    if stderr_output:
                        stderr_str = stderr_output.decode(errors='replace')
                        if 'error' in stderr_str.lower():
                            logger.error(f"CLI STDERR: {stderr_str[:1000]}")
                        else:
                            logger.debug(f"CLI STDERR: {stderr_str[:500]}")
                except asyncio.TimeoutError:
                    pass
                    
        except Exception as e:
            logger.error(f"Error stopping process: {e}")
        finally:
            self._proc = None
            self._running = False

    async def _send_and_wait(self, text: str) -> str:
        """
        Envía mensaje y espera respuesta completa.
        
        Returns:
            Texto acumulado de la respuesta
        """
        if not self._proc or not self._proc.stdin:
            raise RuntimeError("Process not running")
        
        # Formato stream-json input
        msg_json = {
            "type": "user",
            "message": {
                "role": "user",
                "content": text
            }
        }
        
        line_to_send = json.dumps(msg_json) + "\n"
        self._proc.stdin.write(line_to_send.encode('utf-8'))
        await self._proc.stdin.drain()
        logger.debug("Message sent to Claude CLI")
        
        # Leer respuesta
        accumulated_text = ""
        tool_uses = []
        
        while True:
            try:
                line = await asyncio.wait_for(
                    self._proc.stdout.readline(),
                    timeout=30.0  # Timeout por línea
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout reading line, continuing...")
                continue
                
            if not line:
                logger.debug("EOF reached")
                break
            
            line_str = line.decode().strip()
            if not line_str:
                continue
            
            # Log truncado para debug
            if len(line_str) > 200:
                logger.debug(f"CLI OUT: {line_str[:100]}...{line_str[-50:]}")
            else:
                logger.debug(f"CLI OUT: {line_str}")
            
            try:
                data = json.loads(line_str)
                event_type = data.get("type")
                
                if event_type == "content_block_delta":
                    delta = data.get("delta", {}).get("text", "")
                    accumulated_text += delta
                    
                elif event_type == "assistant":
                    # Mensaje completo
                    content = data.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if block.get("type") == "text":
                                # Puede ser el mensaje final
                                if block.get("text"):
                                    accumulated_text = block.get("text")
                            elif block.get("type") == "tool_use":
                                tool_uses.append(block)
                    elif isinstance(content, str):
                        accumulated_text = content
                        
                elif event_type == "message_stop":
                    logger.debug("Message stop received")
                    break
                    
                elif event_type == "result":
                    subtype = data.get("subtype", "")
                    if subtype == "success":
                        logger.debug("CLI interaction completed successfully")
                        break
                    elif subtype == "error":
                        logger.error(f"CLI error: {data.get('error', 'Unknown')}")
                        break
                        
            except json.JSONDecodeError:
                # Líneas que no son JSON (posible output de herramientas)
                logger.debug(f"Non-JSON line: {line_str[:100]}")
        
        if tool_uses:
            logger.info(f"Tools used: {[t.get('name') for t in tool_uses]}")
        
        return accumulated_text

    def _extract_json(self, text: str) -> Optional[dict]:
        """
        Extrae el objeto JSON de la respuesta.
        
        Intenta múltiples estrategias de parsing.
        """
        if not text:
            return None
            
        text = text.strip()
        
        # Estrategia 1: Parse directo
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Estrategia 2: Buscar bloque ```json
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Estrategia 3: Buscar primer { hasta último }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                # Intentar limpiar caracteres problemáticos
                candidate = text[start:end+1]
                candidate = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', candidate)
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
        
        # Estrategia 4: Buscar objeto JSON más grande
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        for candidate in sorted(matches, key=len, reverse=True):
            try:
                result = json.loads(candidate)
                if isinstance(result, dict) and 'market_view' in result:
                    return result
            except json.JSONDecodeError:
                continue
        
        return None

    def _build_basic_prompt(self, context: AgentContext) -> str:
        """Construye prompt básico si no se usa competición."""
        from src.agents.llm.prompts import CONSERVATIVE_PROMPT, MODERATE_PROMPT
        
        if context.autonomy_level == AutonomyLevel.CONSERVATIVE:
            system = CONSERVATIVE_PROMPT
        else:
            system = MODERATE_PROMPT
            
        return f"{system}\n\nCONTEXTO ACTUAL:\n{context.to_prompt_text()}"

    def _create_decision(
        self, 
        data: dict, 
        context: AgentContext, 
        exec_time: int, 
        tokens: int
    ) -> AgentDecision:
        """Crea AgentDecision desde JSON parseado."""
        signals = []
        
        # Soportar tanto "signals" como "actions" (del prompt experimental)
        signal_list = data.get("signals", data.get("actions", []))
        
        for sig_data in signal_list:
            try:
                signal = Signal(
                    strategy_id=self.agent_id,
                    symbol=sig_data.get("symbol"),
                    direction=SignalDirection(sig_data.get("direction", "").upper()),
                    confidence=sig_data.get("confidence", 0.0),
                    entry_price=sig_data.get("entry_price"),
                    stop_loss=sig_data.get("stop_loss"),
                    take_profit=sig_data.get("take_profit"),
                    size_suggestion=sig_data.get("size_suggestion"),
                    regime_at_signal=MarketRegime(context.regime.regime) if context.regime else None,
                    regime_confidence=context.regime.confidence if context.regime else 0.0,
                    reasoning=sig_data.get("reasoning", ""),
                    metadata={
                        "autonomy": context.autonomy_level.value,
                        "provider": "claude_cli",
                        "risk_reward": sig_data.get("risk_reward_ratio"),
                        "confluent_indicators": sig_data.get("confluent_indicators", []),
                        "risks": sig_data.get("risks", []),
                    }
                )
                signals.append(signal)
            except Exception as e:
                logger.warning(f"Skipping invalid signal: {sig_data} - {e}")
        
        # Extraer market_view
        mv_str = data.get("market_view", "uncertain").lower()
        try:
            market_view = MarketView(mv_str)
        except ValueError:
            market_view = MarketView.UNCERTAIN
        
        # Construir reasoning completo
        reasoning_parts = []
        if data.get("session_analysis"):
            sa = data["session_analysis"]
            reasoning_parts.append(f"Market Regime: {sa.get('market_regime', 'N/A')}")
            reasoning_parts.append(f"VIX: {sa.get('vix_level', 'N/A')}")
            if sa.get("web_research_summary"):
                reasoning_parts.append(f"Research: {sa['web_research_summary']}")
        
        if data.get("reasoning"):
            reasoning_parts.append(data["reasoning"])
            
        if data.get("warnings"):
            reasoning_parts.append(f"Warnings: {', '.join(data['warnings'])}")
        
        return AgentDecision(
            decision_id=f"nexus_{int(time.time())}",
            timestamp=datetime.now(timezone.utc),
            market_view=market_view,
            confidence=data.get("confidence", 0.0),
            reasoning="\n\n".join(reasoning_parts) if reasoning_parts else "No reasoning provided",
            signals=signals,
            model_used=self._model,
            tokens_used=tokens,
            execution_time_ms=exec_time
        )

    def _create_fallback_decision(
        self,
        response_text: str,
        context: AgentContext,
        exec_time: int
    ) -> AgentDecision:
        """
        Crea una decisión de fallback cuando no hay JSON válido.
        
        Intenta extraer información del texto plano.
        """
        # Intentar detectar sentiment del texto
        text_lower = response_text.lower()
        
        if any(word in text_lower for word in ['bullish', 'buy', 'long', 'positive']):
            market_view = MarketView.BULLISH
        elif any(word in text_lower for word in ['bearish', 'sell', 'short', 'negative']):
            market_view = MarketView.BEARISH
        elif any(word in text_lower for word in ['neutral', 'sideways', 'hold']):
            market_view = MarketView.NEUTRAL
        else:
            market_view = MarketView.UNCERTAIN
        
        return AgentDecision(
            decision_id=f"fallback_{int(time.time())}",
            timestamp=datetime.now(timezone.utc),
            market_view=market_view,
            confidence=0.3,  # Baja confianza porque es fallback
            reasoning=f"[FALLBACK - No valid JSON found]\n\nRaw response:\n{response_text[:2000]}",
            signals=[],  # Sin señales por seguridad
            model_used=self._model,
            tokens_used=len(response_text) // 4,
            execution_time_ms=exec_time
        )
