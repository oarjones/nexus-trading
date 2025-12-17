"""
Implementación del agente usando Claude Code CLI (local).
Wrapper para 'claude' CLI command.
"""

import asyncio
import json
import logging
import os
import shutil
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
from src.agents.llm.prompts import CONSERVATIVE_PROMPT, MODERATE_PROMPT

logger = logging.getLogger(__name__)

class ClaudeCliAgent(LLMAgent):
    """
    Agente que usa la herramienta CLI 'claude' (Claude Code) localmente.
    Permite acceso a herramientas nativas (web search, file interaction) via shell.
    """
    
    def __init__(
        self,
        model: str = "claude-sonnet-4-5", # CLI usually defaults to best, but we can pass it if supported
        timeout_seconds: float = 120.0,
        cwd: str = None
    ):
        self._model = model
        self._timeout = timeout_seconds
        self._cwd = cwd or os.getcwd()
        self._proc = None
        self._running = False
        
    @property
    def agent_id(self) -> str:
        return "claude_cli_agent"
    
    @property
    def provider(self) -> str:
        return "claude_cli"

    async def decide(self, context: AgentContext) -> AgentDecision:
        """
        Toma una decisión lanzando una sesión de Claude CLI.
        
        Nota: Para evitar contaminación de contexto entre decisiones,
        lanzamos un proceso efímero o gestionamos la sesión cuidadosamente.
        Por simplicidad incial: Lanzamos proceso fresh por cada decisión.
        """
        start_time = time.time()
        
        # 1. Preparar Prompt
        system_prompt = self._get_system_prompt(context.autonomy_level)
        user_prompt = context.to_prompt_text()
        
        # Combinamos para el CLI
        full_message = f"{system_prompt}\n\nCONTEXTO ACTUAL:\n{user_prompt}\n\nINSTRUCCIONES: Tienes acceso a herramientas (como búsqueda web). ÚSALAS si necesitas información actualizada (ej: precios, noticias). NO inventes datos. Una vez tengas la información, Responde SOLAMENTE con el objeto JSON de decisión final."

        response_text = ""
        tokens_est = len(full_message) // 4
        
        try:
            # 2. Iniciar Proceso (si no existe o si queremos uno nuevo)
            # Para 'decide' atómico, es mejor fresh process para asegurar limpieza del context window
            # Aunque Claude Code inicia rápido, el overhead puede ser notable.
            # TODO: Evaluar modo persistente real si la latencia es alta.
            await self._start_process()
            
            # 3. Enviar mensaje
            response_text = await self._send_and_wait(full_message)
            
            # 4. Parsear respuesta
            parsed_json = self._extract_json(response_text)
            
            # 5. Parar proceso (clean up)
            await self._stop_process()
            
            logger.debug(f"FULL RAW RESPONSE:\n{response_text}")
            
            if parsed_json:
                execution_time = int((time.time() - start_time) * 1000)
                return self._create_decision(
                    parsed_json, context, execution_time, tokens_est
                )
            
            raise ValueError("No valid JSON in response")

        except Exception as e:
            logger.error(f"Error in ClaudeCliAgent.decide: {e}")
            await self._stop_process()
            
            return AgentDecision(
                decision_id=f"err_{int(time.time())}",
                timestamp=datetime.now(timezone.utc),
                market_view=MarketView.UNCERTAIN,
                confidence=0.0,
                reasoning=f"Error executing Claude CLI: {str(e)}",
                signals=[],
                model_used=self._model,
                tokens_used=0,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

    async def _start_process(self):
        """Inicia el proceso claude CLI."""
        cmd = [
            "claude", 
            "--print", 
            "--input-format", "stream-json", 
            "--output-format", "stream-json",
            "--permission-mode", "bypassPermissions", # Importante para no bloquear
            "--verbose" # Required for stream-json
        ]
        
        if platform.system() == "Windows":
             cmd[0] = "claude.cmd"
            
        env = os.environ.copy()
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "100000"
        
        logger.info(f"Starting process: {' '.join(cmd)}")
        
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._cwd,
            env=env
        )
        self._running = True

    async def _stop_process(self):
        """Detiene el proceso y loguea stderr final de forma segura."""
        if self._proc:
            try:
                # Close stdin to signal EOF
                if self._proc.stdin:
                    self._proc.stdin.close()
                
                # Wait for termination with timeout
                try:
                    # Give it a moment to flush stderr/stdout
                    await asyncio.wait_for(self._proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self._proc.terminate()
                    await self._proc.wait()
                
                # Try to read stderr if available (now that process is done)
                # But don't block forever
                if self._proc.stderr:
                   # Since process is done, read() should return immediately
                   stderr_output = await self._proc.stderr.read()
                   if stderr_output:
                       logger.error(f"CLI STDERR: {stderr_output.decode(errors='replace')}")

            except Exception as e:
                logger.error(f"Error stopping process: {e}")
                
        self._proc = None
        self._running = False

    async def _send_and_wait(self, text: str) -> str:
        """Envía mensaje y espera respuesta completa."""
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
        
        # Leer respuesta hasta que termine
        accumulated_text = ""
        
        while True:
            line = await self._proc.stdout.readline()
            if not line:
                break
                
            line_str = line.decode().strip()
            if not line_str: continue
            
            logger.debug(f"CLI OUTPUT: {line_str[:500]}")
            
            try:
                data = json.loads(line_str)
                event_type = data.get("type")
                
                if event_type == "content_block_delta":
                    delta = data.get("delta", {}).get("text", "")
                    accumulated_text += delta
                    # print(delta, end="", flush=True) # DEBUG UI
                    
                elif event_type == "assistant":
                    # Mensaje completo a veces viene aquí
                    content = data.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if block.get("type") == "text":
                                accumulated_text = block.get("text", "") # Reemplaza o append? Normalmente Assistant trae todo
                    elif isinstance(content, str):
                        accumulated_text = content
                        
                elif event_type == "message_stop":
                    # Fin del turno
                    break
                    
                elif event_type == "result" and data.get("subtype") == "success":
                     # CLI interaction finished
                     break

                    
                # Ignoramos message_start, ping, etc
                
            except json.JSONDecodeError:
                pass
                
        return accumulated_text

    def _extract_json(self, text: str) -> dict:
        """Reutiliza lógica de extracción JSON."""
        # Simple extraction similar to ClaudeAgent
        text = text.strip()
        try:
            return json.loads(text, strict=False)
        except:
             # Try regex
            import re
            match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1), strict=False)
                except: pass
            
            # Brackets
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end+1], strict=False)
                except: pass
                
        return None

    def _get_system_prompt(self, autonomy: AutonomyLevel) -> str:
        if autonomy == AutonomyLevel.CONSERVATIVE:
            return CONSERVATIVE_PROMPT
        return MODERATE_PROMPT

    def _create_decision(self, data: dict, context: AgentContext, exec_time: int, tokens: int) -> AgentDecision:
        # Reutilizar lógica de mapeo (duplicada de ClaudeAgent por ahora, ideal refactor a Base)
        signals = []
        for sig_data in data.get("signals", []):
            try:
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
                    metadata={"autonomy": context.autonomy_level.value, "provider": "claude_cli"}
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
