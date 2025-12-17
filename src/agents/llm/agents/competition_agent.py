"""
Agente Claude CLI con Sistema de Competición de Trading.

Este agente implementa:
1. Onboarding inicial (reglas de la competición)
2. Sesiones diarias (contexto, métricas, ranking)
3. Tracking de métricas y rendimiento
"""

import asyncio
import json
import logging
import os
import re
import time
import platform
from datetime import datetime, timezone
from typing import Optional, List
from pathlib import Path

from src.agents.llm.interfaces import (
    LLMAgent,
    AgentContext,
    AgentDecision,
    AutonomyLevel,
    MarketView,
)
from src.strategies.interfaces import Signal, SignalDirection, MarketRegime
from src.agents.llm.prompts.competition_v2 import (
    CompetitionManager,
    CompetitionConfig,
    PerformanceMetrics,
    PositionSummary,
    ONBOARDING_PROMPT,
)
from src.data.competition_repository import CompetitionRepository

logger = logging.getLogger(__name__)


class CompetitionClaudeAgent(LLMAgent):
    """
    Agente Claude CLI optimizado para la competición de trading.
    
    Características:
    - Onboarding inicial con reglas (una sola vez)
    - Sesiones diarias con contexto optimizado
    - Tracking de métricas y ranking dinámico
    - Persistencia del estado entre sesiones
    """
    
    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        timeout_seconds: float = 180.0,
        cwd: str = None,
        state_file: str = None,
        config: CompetitionConfig = None,
    ):
        """
        Inicializa el agente de competición.
        
        Args:
            model: Modelo de Claude a usar
            timeout_seconds: Timeout para cada llamada
            cwd: Directorio de trabajo
            state_file: Archivo para persistir estado entre sesiones
            config: Configuración de la competición
        """
        self._model = model
        self._timeout = timeout_seconds
        self._cwd = cwd or os.getcwd()
        self._state_file = state_file or os.path.join(self._cwd, "data", "competition_state.json")
        
        # Repository (lazy init)
        self._repo = CompetitionRepository()
        
        # Manager de competición
        self._competition = CompetitionManager(config)
        
        # Estado del proceso
        self._proc = None
        self._running = False
        
        # Init state flag
        self._initialized_state = False
    
    @property
    def agent_id(self) -> str:
        return "nexus_ai_competitor"
    
    @property
    def provider(self) -> str:
        return "claude_cli_competition"
    
    @property
    def competition_day(self) -> int:
        return self._competition.competition_day
    
    @property
    def metrics(self) -> PerformanceMetrics:
        return self._competition.metrics
    
    # =========================================================================
    # MÉTODOS PRINCIPALES
    # =========================================================================
    
    async def ensure_onboarded(self) -> bool:
        """
        Asegura que el agente ha sido onboarded.
        
        Si no lo está, envía el prompt de onboarding y espera confirmación.
        
        Returns:
            True si está onboarded (ya estaba o se completó ahora)
        """
        if not self._initialized_state:
            await self._load_state()
            self._initialized_state = True

        if self._competition.is_onboarded:
            logger.info(f"Agent already onboarded (Day {self.competition_day})")
            return True
        
        logger.info("Starting onboarding process...")
        
        try:
            await self._start_process()
            
            # Enviar prompt de onboarding
            response = await asyncio.wait_for(
                self._send_and_wait(ONBOARDING_PROMPT),
                timeout=60.0
            )
            
            await self._stop_process()
            
            # Verificar que entendió (buscar "READY" o similar)
            response_lower = response.lower()
            if "ready" in response_lower or "entendido" in response_lower or "listo" in response_lower:
                self._competition.confirm_onboarding()
                await self._save_state()
                logger.info("Onboarding completed successfully!")
                return True
            else:
                logger.warning(f"Onboarding response unclear: {response[:200]}")
                # Asumir que está OK si respondió algo coherente
                self._competition.confirm_onboarding()
                await self._save_state()
                return True
                
        except Exception as e:
            logger.error(f"Onboarding failed: {e}")
            await self._stop_process()
            return False
    
    async def decide(self, context: AgentContext) -> AgentDecision:
        """
        Toma una decisión de trading para la sesión actual.
        
        Si no está onboarded, primero hace el onboarding.
        """
        start_time = time.time()
        response_text = ""
        tokens_est = 0
        
        try:
            # Asegurar onboarding
            if not await self.ensure_onboarded():
                raise RuntimeError("Failed to complete onboarding")
            
            # Construir prompt de sesión diaria
            daily_prompt = self._build_daily_prompt(context)
            tokens_est = len(daily_prompt) // 4
            logger.info(f"Daily prompt size: ~{tokens_est} tokens (Day {self.competition_day})")
            
            # Iniciar proceso
            await self._start_process()
            
            # Enviar y esperar respuesta
            try:
                response_text = await asyncio.wait_for(
                    self._send_and_wait(daily_prompt),
                    timeout=self._timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout after {self._timeout}s")
                raise TimeoutError(f"No response within {self._timeout}s")
            
            await self._stop_process()
            
            # Parsear respuesta
            parsed_json = self._extract_json(response_text)
            
            if parsed_json:
                execution_time = int((time.time() - start_time) * 1000)
                decision = self._create_decision(parsed_json, context, execution_time, tokens_est)
                
                # Actualizar métricas con los resultados
                self._update_metrics_from_decision(decision)
                await self._save_state()
                
                return decision
            
            # Fallback si no hay JSON
            return self._create_fallback_decision(response_text, context, int((time.time() - start_time) * 1000))
            
        except Exception as e:
            logger.error(f"Error in decide: {e}", exc_info=True)
            await self._stop_process()
            
            return AgentDecision(
                decision_id=f"err_{int(time.time())}",
                timestamp=datetime.now(timezone.utc),
                market_view=MarketView.UNCERTAIN,
                confidence=0.0,
                reasoning=f"Error: {str(e)}\n\nPartial response: {response_text[:500] if response_text else 'None'}",
                signals=[],
                model_used=self._model,
                tokens_used=tokens_est,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
    
    def update_trade_results(self, trades: List[dict]):
        """
        Actualiza las métricas con los resultados de trades cerrados.
        
        Llamar después de ejecutar trades para mantener métricas precisas.
        
        Args:
            trades: Lista de trades con formato:
                {"symbol": "XXX", "direction": "LONG", "entry_price": 100,
                 "exit_price": 105, "pnl": 50, "pnl_pct": 5.0}
        """
        if trades:
            self._competition.update_metrics(
                daily_return=sum(t.get("pnl_pct", 0) for t in trades) / len(trades),
                new_trades=trades
            )
            # self.update_trade_results is rarely called directly, usually part of flow
            # We can't await easily here if called from sync context, but usually it's async flow
            # For now, let's assume it's called from async context or we create task
            asyncio.create_task(self._save_state())
    
    async def advance_day(self, daily_return: float = 0.0):
        """
        Avanza al siguiente día de competición.
        
        Llamar al final de cada sesión de trading.
        
        Args:
            daily_return: Retorno del día (%)
        """
        self._competition.update_metrics(daily_return=daily_return)
        await self._save_state()
        logger.info(f"Advanced to Day {self.competition_day}")
    
    def get_competition_status(self) -> dict:
        """Obtiene el estado actual de la competición."""
        return self._competition.get_competition_summary()
    
    async def reset_competition(self):
        """Reinicia la competición desde cero."""
        self._competition = CompetitionManager()
        await self._save_state()
        logger.info("Competition reset")
    
    # =========================================================================
    # MÉTODOS PRIVADOS - GESTIÓN DE PROMPTS
    # =========================================================================
    
    def _build_daily_prompt(self, context: AgentContext) -> str:
        """Construye el prompt de sesión diaria desde el contexto."""
        
        # Convertir posiciones del portfolio a PositionSummary
        positions = []
        if context.portfolio and context.portfolio.positions:
            for pos in context.portfolio.positions:
                # Calcular distancias a SL/TP (estimadas si no están disponibles)
                entry = pos.avg_entry_price
                current = pos.current_price
                
                # Usar valores por defecto si no hay SL/TP
                sl = entry * 0.97  # -3% por defecto
                tp = entry * 1.06  # +6% por defecto
                
                positions.append(PositionSummary(
                    symbol=pos.symbol,
                    direction="LONG",  # TODO: detectar SHORT
                    entry_price=entry,
                    current_price=current,
                    quantity=pos.quantity,
                    entry_date="N/A",
                    days_held=pos.holding_days,
                    unrealized_pnl=pos.unrealized_pnl,
                    unrealized_pnl_pct=pos.unrealized_pnl_pct,
                    stop_loss=sl,
                    take_profit=tp,
                    distance_to_sl_pct=((current - sl) / current) * 100,
                    distance_to_tp_pct=((tp - current) / current) * 100,
                ))
        
        # Generar prompt
        return self._competition.get_daily_prompt(
            current_date=context.timestamp,
            portfolio_value=context.portfolio.total_value if context.portfolio else 25000,
            cash_available=context.portfolio.cash_available if context.portfolio else 25000,
            positions=positions,
            market_regime=context.regime.regime if context.regime else "UNKNOWN",
            vix_level=context.market.vix_level if context.market else 15.0,
            spy_change=context.market.spy_change_pct if context.market else 0.0,
            trades_today=context.risk_limits.current_daily_trades if context.risk_limits else 0,
            watchlist_data=self._format_watchlist(context.watchlist) if context.watchlist else "",
            notes=context.notes or ""
        )
    
    def _format_watchlist(self, watchlist) -> str:
        """Formatea la watchlist para el prompt."""
        if not watchlist:
            return ""
        
        lines = ["📋 WATCHLIST:"]
        for item in watchlist[:10]:  # Limitar a 10
            lines.append(f"   {item.symbol}: ${item.current_price:.2f} ({item.change_pct:+.2f}%) | RSI: {item.rsi_14:.0f}")
        return "\n".join(lines)
    
    def _update_metrics_from_decision(self, decision: AgentDecision):
        """Actualiza métricas basándose en la decisión tomada."""
        # Por ahora solo trackear que hubo actividad
        # Las métricas reales se actualizan cuando se cierran trades
        pass
    
    # =========================================================================
    # MÉTODOS PRIVADOS - GESTIÓN DE PROCESO
    # =========================================================================
    
    async def _start_process(self):
        """Inicia el proceso Claude CLI."""
        if self._proc and self._running:
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
        
        logger.debug(f"Starting process: {' '.join(cmd)}")
        
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._cwd,
            env=env
        )
        self._running = True
        logger.debug(f"Process started (PID: {self._proc.pid})")
    
    async def _stop_process(self):
        """Detiene el proceso de forma segura."""
        if not self._proc:
            return
        
        try:
            if self._proc.stdin and not self._proc.stdin.is_closing():
                self._proc.stdin.close()
                await self._proc.stdin.wait_closed()
            
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()
            
            if self._proc.stderr:
                try:
                    stderr = await asyncio.wait_for(self._proc.stderr.read(), timeout=1.0)
                    if stderr and b'error' in stderr.lower():
                        logger.error(f"CLI stderr: {stderr.decode(errors='replace')[:500]}")
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error stopping process: {e}")
        finally:
            self._proc = None
            self._running = False
    
    async def _send_and_wait(self, text: str) -> str:
        """Envía mensaje y espera respuesta."""
        if not self._proc or not self._proc.stdin:
            raise RuntimeError("Process not running")
        
        msg_json = {
            "type": "user",
            "message": {"role": "user", "content": text}
        }
        
        self._proc.stdin.write((json.dumps(msg_json) + "\n").encode('utf-8'))
        await self._proc.stdin.drain()
        
        accumulated = ""
        
        while True:
            try:
                line = await asyncio.wait_for(self._proc.stdout.readline(), timeout=30.0)
            except asyncio.TimeoutError:
                continue
            
            if not line:
                break
            
            line_str = line.decode().strip()
            if not line_str:
                continue
            
            try:
                data = json.loads(line_str)
                event_type = data.get("type")
                
                if event_type == "content_block_delta":
                    accumulated += data.get("delta", {}).get("text", "")
                elif event_type == "assistant":
                    content = data.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if block.get("type") == "text" and block.get("text"):
                                accumulated = block["text"]
                    elif isinstance(content, str):
                        accumulated = content
                elif event_type in ("message_stop", "result"):
                    break
                    
            except json.JSONDecodeError:
                pass
        
        return accumulated
    
    # =========================================================================
    # MÉTODOS PRIVADOS - PARSING
    # =========================================================================
    
    def _extract_json(self, text: str) -> Optional[dict]:
        """Extrae JSON de la respuesta."""
        if not text:
            return None
        
        text = text.strip()
        
        # Intentar parse directo
        try:
            return json.loads(text)
        except:
            pass
        
        # Buscar bloque ```json
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        # Buscar { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except:
                pass
        
        return None
    
    def _create_decision(self, data: dict, context: AgentContext, exec_time: int, tokens: int) -> AgentDecision:
        """Crea AgentDecision desde JSON."""
        signals = []
        
        for sig_data in data.get("signals", []):
            try:
                signals.append(Signal(
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
                        "provider": "claude_cli_competition",
                        "competition_day": self.competition_day,
                        "risk_reward": sig_data.get("risk_reward_ratio"),
                        "confluent_indicators": sig_data.get("confluent_indicators", []),
                    }
                ))
            except Exception as e:
                logger.warning(f"Skipping invalid signal: {e}")
        
        # Market view
        mv_str = data.get("market_view", "uncertain").lower()
        try:
            market_view = MarketView(mv_str)
        except:
            market_view = MarketView.UNCERTAIN
        
        # Reasoning
        reasoning_parts = []
        if data.get("session_summary"):
            ss = data["session_summary"]
            reasoning_parts.append(f"Market Analysis: {ss.get('market_analysis', 'N/A')}")
            if ss.get("key_news"):
                reasoning_parts.append(f"Key News: {', '.join(ss['key_news'])}")
        if data.get("reasoning"):
            reasoning_parts.append(data["reasoning"])
        
        return AgentDecision(
            decision_id=f"comp_d{self.competition_day}_{int(time.time())}",
            timestamp=datetime.now(timezone.utc),
            market_view=market_view,
            confidence=data.get("confidence", 0.0),
            reasoning="\n\n".join(reasoning_parts) or "No reasoning provided",
            signals=signals,
            model_used=self._model,
            tokens_used=tokens,
            execution_time_ms=exec_time
        )
    
    def _create_fallback_decision(self, text: str, context: AgentContext, exec_time: int) -> AgentDecision:
        """Crea decisión de fallback."""
        text_lower = text.lower()
        
        if any(w in text_lower for w in ['bullish', 'buy', 'long']):
            mv = MarketView.BULLISH
        elif any(w in text_lower for w in ['bearish', 'sell', 'short']):
            mv = MarketView.BEARISH
        elif any(w in text_lower for w in ['neutral', 'hold']):
            mv = MarketView.NEUTRAL
        else:
            mv = MarketView.UNCERTAIN
        
        return AgentDecision(
            decision_id=f"fallback_{int(time.time())}",
            timestamp=datetime.now(timezone.utc),
            market_view=mv,
            confidence=0.3,
            reasoning=f"[FALLBACK]\n\n{text[:1500]}",
            signals=[],
            model_used=self._model,
            tokens_used=len(text) // 4,
            execution_time_ms=exec_time
        )
    
    # =========================================================================
    # MÉTODOS PRIVADOS - PERSISTENCIA DB
    # =========================================================================
    
    async def _save_state(self):
        """Guarda el estado de la competición en DB."""
        try:
            # Serializar métricas
            m = self._competition.metrics
            metrics_dict = {
                "total_return_pct": m.total_return_pct,
                "daily_return_pct": m.daily_return_pct,
                "sharpe_ratio": m.sharpe_ratio,
                "max_drawdown_pct": m.max_drawdown_pct,
                "win_rate": m.win_rate,
                "total_trades": m.total_trades,
                "winning_trades": m.winning_trades,
                "losing_trades": m.losing_trades,
                "consecutive_wins": m.consecutive_wins,
                "consecutive_losses": m.consecutive_losses,
            }

            state = {
                "is_onboarded": self._competition.is_onboarded,
                "competition_day": self._competition.competition_day,
                "start_date": self._competition.start_date.isoformat() if self._competition.start_date else None,
                "metrics": metrics_dict,
                "trade_history": [t if isinstance(t, dict) else t.to_dict() for t in self._competition.trade_history[-50:]], 
            }
            
            await self._repo.save_state(self.agent_id, state)
            logger.debug(f"State saved to DB for {self.agent_id}")
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    async def _load_state(self):
        """Carga el estado de la competición desde DB."""
        try:
            state = await self._repo.load_state(self.agent_id)
            
            if not state:
                logger.info("No previous state found in DB, starting fresh")
                return
            
            self._competition.is_onboarded = state.get("is_onboarded", False)
            self._competition.competition_day = state.get("competition_day", 0)
            
            if state.get("start_date"):
                self._competition.start_date = datetime.fromisoformat(state["start_date"])
            
            if state.get("metrics"):
                m = state["metrics"]
                self._competition.metrics = PerformanceMetrics(
                    total_return_pct=m.get("total_return_pct", 0.0),
                    daily_return_pct=m.get("daily_return_pct", 0.0),
                    sharpe_ratio=m.get("sharpe_ratio", 0.0),
                    max_drawdown_pct=m.get("max_drawdown_pct", 0.0),
                    win_rate=m.get("win_rate", 0.0),
                    total_trades=m.get("total_trades", 0),
                    winning_trades=m.get("winning_trades", 0),
                    losing_trades=m.get("losing_trades", 0),
                    consecutive_wins=m.get("consecutive_wins", 0),
                    consecutive_losses=m.get("consecutive_losses", 0),
                    days_in_competition=state.get("competition_day", 0),
                )
            
            self._competition.trade_history = state.get("trade_history", [])
            
            logger.info(f"Loaded state: Day {self._competition.competition_day}, "
                       f"Return: {self._competition.metrics.total_return_pct:.2f}%")
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
