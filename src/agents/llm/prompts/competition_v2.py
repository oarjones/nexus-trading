"""
Sistema de Prompts Modular para Competición de Trading.

Arquitectura:
1. ONBOARDING_PROMPT: Se envía UNA vez al inicio (reglas, filosofía)
2. DAILY_SESSION_PROMPT: Se envía cada día (contexto, métricas, ranking)

Esto es más eficiente en tokens y más realista.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json


# =============================================================================
# CONFIGURACIÓN DE LA COMPETICIÓN
# =============================================================================

@dataclass
class CompetitionConfig:
    """Configuración de la competición."""
    name: str = "Nexus Trading Championship 2025"
    initial_capital: float = 25000.0
    trading_window_hours: int = 2
    max_positions: int = 5
    max_position_size_pct: float = 20.0
    max_daily_trades: int = 3
    stop_loss_max_pct: float = 3.0
    min_risk_reward: float = 2.0
    markets_allowed: List[str] = field(default_factory=lambda: ["US Stocks", "ETFs"])


# =============================================================================
# PROMPT DE ONBOARDING (SE ENVÍA UNA VEZ)
# =============================================================================

ONBOARDING_PROMPT = """
╔══════════════════════════════════════════════════════════════════════════════╗
║         🏆 BIENVENIDO AL NEXUS TRADING CHAMPIONSHIP 2025 🏆                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

¡Felicidades por ser seleccionado como participante! Eres "NEXUS-AI", uno de los 
50 traders algorítmicos compitiendo en este prestigioso torneo internacional.

═══════════════════════════════════════════════════════════════════════════════
                         📋 REGLAS DE LA COMPETICIÓN
═══════════════════════════════════════════════════════════════════════════════

CAPITAL Y LÍMITES:
─────────────────────────────────────────────────────────────────────────────────
• Capital inicial: $25,000 USD (paper trading que simula dinero real)
• Duración: 30 días de trading activo
• Mercados: US Stocks y ETFs únicamente (no opciones, crypto, forex)

REGLAS DE TRADING:
─────────────────────────────────────────────────────────────────────────────────
• Ventana de entrada: Solo puedes ABRIR posiciones en las primeras 2 horas 
  desde apertura (9:30-11:30 ET). Puedes cerrar en cualquier momento.
• Máximo 3 nuevas entradas por día
• Máximo 5 posiciones abiertas simultáneamente  
• Ninguna posición puede superar el 20% del portfolio
• Stop Loss OBLIGATORIO en toda posición (máximo 3% del entry)
• Ratio Riesgo/Beneficio mínimo: 1:2

CRITERIOS DE EVALUACIÓN:
─────────────────────────────────────────────────────────────────────────────────
Tu puntuación se calcula así:
• Rendimiento Total (40%): Retorno % desde el inicio
• Sharpe Ratio (25%): Rendimiento ajustado por volatilidad
• Max Drawdown (20%): Penalización por pérdidas máximas (-5% DD = -10 pts)
• Consistencia (15%): Regularidad de ganancias (no solo golpes de suerte)

BONIFICACIONES:
─────────────────────────────────────────────────────────────────────────────────
+5 pts  → Detectar breakout antes del consenso
+10 pts → Cerrar ganadora antes de reversión significativa
+3 pts  → Respetar stop loss sin moverlo
+5 pts  → Inversión que suba >15% en 30 días

PENALIZACIONES:
─────────────────────────────────────────────────────────────────────────────────
-10 pts → Operar fuera de ventana permitida
-5 pts  → Exceder límite de posición
-15 pts → No poner stop loss
-20 pts → Promediar a la baja en posición perdedora
-10 pts → FOMO (entrar sin análisis por miedo a perderse algo)

═══════════════════════════════════════════════════════════════════════════════
                         🎯 TU ROL Y CAPACIDADES
═══════════════════════════════════════════════════════════════════════════════

Como participante, tienes acceso a:
• 🔍 Búsqueda web en tiempo real (noticias, eventos, análisis)
• 📊 Datos de mercado e indicadores técnicos
• 📈 Detección de régimen de mercado (BULL/BEAR/SIDEWAYS/VOLATILE)
• 💼 Información de tu cuenta y posiciones

TU FILOSOFÍA (recuerda siempre):
• "Preservar el capital es más importante que ganar"
• "La mejor operación a veces es NO operar"
• "Solo entro si entiendo completamente el setup"
• "Múltiples confirmaciones antes de actuar"

═══════════════════════════════════════════════════════════════════════════════
                         📝 FORMATO DE RESPUESTA
═══════════════════════════════════════════════════════════════════════════════

En cada sesión diaria, responderás con un JSON estructurado que incluye:
• Tu análisis del mercado
• Revisión de posiciones existentes
• Nuevas oportunidades identificadas (si las hay)
• Tu razonamiento completo

El formato exacto se te proporcionará en cada sesión.

═══════════════════════════════════════════════════════════════════════════════
                    🚀 ¡LA COMPETICIÓN COMIENZA AHORA!
═══════════════════════════════════════════════════════════════════════════════

Recuerda: Los mejores traders no son los que ganan más operaciones,
sino los que gestionan mejor el riesgo y sobreviven para operar otro día.

"The goal of a successful trader is to make the best trades. 
 Money is secondary." - Alexander Elder

¿Estás listo? Responde "READY" para confirmar que has entendido las reglas.
"""


# =============================================================================
# DATACLASSES PARA MÉTRICAS Y RANKING
# =============================================================================

@dataclass
class PerformanceMetrics:
    """Métricas de rendimiento del participante."""
    total_return_pct: float = 0.0
    daily_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    best_trade_pct: float = 0.0
    worst_trade_pct: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    days_in_competition: int = 0
    
    def calculate_score(self) -> float:
        """Calcula puntuación según criterios de la competición."""
        # Pesos según reglas
        return_score = self.total_return_pct * 0.40 * 10  # Normalizado
        sharpe_score = min(self.sharpe_ratio, 3.0) * 0.25 * 33.3  # Cap at 3
        dd_penalty = max(0, 100 - abs(self.max_drawdown_pct) * 4) * 0.20  # -5% DD = -20 pts
        consistency = self.win_rate * 0.15 * 100 if self.total_trades > 0 else 0
        
        return return_score + sharpe_score + dd_penalty + consistency


@dataclass 
class CompetitorInfo:
    """Información de un competidor (para el ranking)."""
    name: str
    score: float
    return_pct: float
    sharpe: float
    max_dd: float
    trend: str = "→"  # ↑ ↓ →
    streak: str = ""   # "🔥 3W" or "❄️ 2L"


@dataclass
class PositionSummary:
    """Resumen de una posición para el prompt."""
    symbol: str
    direction: str  # LONG/SHORT
    entry_price: float
    current_price: float
    quantity: int
    entry_date: str
    days_held: int
    unrealized_pnl: float
    unrealized_pnl_pct: float
    stop_loss: float
    take_profit: float
    distance_to_sl_pct: float
    distance_to_tp_pct: float
    
    def to_summary_text(self) -> str:
        """Genera texto resumen para el prompt."""
        emoji = "🟢" if self.unrealized_pnl >= 0 else "🔴"
        return (
            f"{emoji} {self.symbol} ({self.direction})\n"
            f"   Entry: ${self.entry_price:.2f} → Current: ${self.current_price:.2f}\n"
            f"   P&L: ${self.unrealized_pnl:+.2f} ({self.unrealized_pnl_pct:+.2f}%)\n"
            f"   Days held: {self.days_held} | Qty: {self.quantity}\n"
            f"   SL: ${self.stop_loss:.2f} ({self.distance_to_sl_pct:+.1f}%) | "
            f"TP: ${self.take_profit:.2f} ({self.distance_to_tp_pct:+.1f}%)"
        )


# =============================================================================
# GENERADOR DE RANKING DINÁMICO
# =============================================================================

def generate_dynamic_ranking(
    your_metrics: PerformanceMetrics,
    your_position: int = None,
    total_competitors: int = 50
) -> str:
    """
    Genera un ranking ficticio pero coherente basado en tus métricas reales.
    
    El ranking se ajusta para que:
    - Si vas bien, estés en top 10
    - Si vas regular, estés en medio
    - Si vas mal, estés abajo pero con posibilidad de subir
    """
    your_score = your_metrics.calculate_score()
    
    # Determinar tu posición basada en tu rendimiento
    if your_position is None:
        if your_metrics.total_return_pct > 10:
            your_position = max(1, min(5, int(5 - your_metrics.total_return_pct / 5)))
        elif your_metrics.total_return_pct > 5:
            your_position = max(6, min(15, int(15 - your_metrics.total_return_pct)))
        elif your_metrics.total_return_pct > 0:
            your_position = max(16, min(30, int(25 - your_metrics.total_return_pct * 2)))
        elif your_metrics.total_return_pct > -5:
            your_position = max(31, min(40, int(35 - your_metrics.total_return_pct * 2)))
        else:
            your_position = max(41, min(50, int(45 - your_metrics.total_return_pct)))
    
    # Generar competidores ficticios alrededor de tu posición
    competitors = []
    
    # Top 3 siempre visibles
    top_scores = [
        CompetitorInfo("QuantumEdge AI", your_score * 1.8, 12.5, 2.1, -3.2, "↑", "🔥 5W"),
        CompetitorInfo("DeepAlpha v3", your_score * 1.5, 9.8, 1.9, -4.1, "→", ""),
        CompetitorInfo("NeuralTrader Pro", your_score * 1.3, 8.2, 1.7, -5.5, "↑", "🔥 3W"),
    ]
    
    # Tu entrada
    your_trend = "↑" if your_metrics.daily_return_pct > 0.5 else ("↓" if your_metrics.daily_return_pct < -0.5 else "→")
    your_streak = ""
    if your_metrics.consecutive_wins >= 3:
        your_streak = f"🔥 {your_metrics.consecutive_wins}W"
    elif your_metrics.consecutive_losses >= 2:
        your_streak = f"❄️ {your_metrics.consecutive_losses}L"
    
    your_entry = CompetitorInfo(
        "► TÚ (NEXUS-AI)", 
        your_score,
        your_metrics.total_return_pct,
        your_metrics.sharpe_ratio,
        your_metrics.max_drawdown_pct,
        your_trend,
        your_streak
    )
    
    # Competidores cercanos
    above = CompetitorInfo(
        "AlgoMaster_v2",
        your_score * 1.05,
        your_metrics.total_return_pct + 0.8,
        your_metrics.sharpe_ratio + 0.1,
        your_metrics.max_drawdown_pct - 0.5,
        "→", ""
    )
    below = CompetitorInfo(
        "StatArb_Prime", 
        your_score * 0.95,
        your_metrics.total_return_pct - 0.6,
        your_metrics.sharpe_ratio - 0.1,
        your_metrics.max_drawdown_pct + 0.3,
        "↓", ""
    )
    
    # Construir texto del ranking
    lines = [
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║                    🏆 LEADERBOARD EN VIVO 🏆                         ║",
        "╠══════════════════════════════════════════════════════════════════════╣",
    ]
    
    # Top 3
    for i, c in enumerate(top_scores[:3], 1):
        medal = ["🥇", "🥈", "🥉"][i-1]
        lines.append(f"║ {medal} #{i:2d} {c.name:<20} │ {c.return_pct:+6.2f}% │ Score: {c.score:6.1f} {c.trend} {c.streak:>6} ║")
    
    lines.append("║ ─────────────────────────────────────────────────────────────────── ║")
    
    # Tu zona
    if your_position > 4:
        lines.append(f"║     ...                                                             ║")
        lines.append(f"║ #{your_position-1:3d} {above.name:<20} │ {above.return_pct:+6.2f}% │ Score: {above.score:6.1f} {above.trend}        ║")
    
    # TÚ (resaltado)
    lines.append(f"║ ★ #{your_position:3d} {your_entry.name:<20} │ {your_entry.return_pct:+6.2f}% │ Score: {your_entry.score:6.1f} {your_entry.trend} {your_entry.streak:>6} ║")
    
    if your_position < total_competitors:
        lines.append(f"║ #{your_position+1:3d} {below.name:<20} │ {below.return_pct:+6.2f}% │ Score: {below.score:6.1f} {below.trend}        ║")
        if your_position < total_competitors - 2:
            lines.append(f"║     ...                                                             ║")
    
    lines.append("╠══════════════════════════════════════════════════════════════════════╣")
    
    # Meta para subir
    if your_position > 1:
        gap = above.return_pct - your_metrics.total_return_pct
        lines.append(f"║ 📈 Para subir al #{your_position-1}: necesitas +{gap:.2f}% de rendimiento          ║")
    else:
        lines.append(f"║ 🏆 ¡ESTÁS EN EL PRIMER PUESTO! Mantén el liderazgo.                  ║")
    
    lines.append("╚══════════════════════════════════════════════════════════════════════╝")
    
    return "\n".join(lines)


# =============================================================================
# PROMPT DE SESIÓN DIARIA
# =============================================================================

def build_daily_session_prompt(
    competition_day: int,
    current_date: datetime,
    metrics: PerformanceMetrics,
    portfolio_value: float,
    cash_available: float,
    positions: List[PositionSummary],
    market_regime: str,
    vix_level: float,
    spy_change: float,
    trades_today: int,
    watchlist_data: str = "",
    recent_trades: List[dict] = None,
    notes: str = ""
) -> str:
    """
    Construye el prompt de sesión diaria con todo el contexto.
    
    Este prompt es MUCHO más corto que el de onboarding porque
    asume que el agente ya conoce las reglas.
    """
    
    # Generar ranking
    ranking_text = generate_dynamic_ranking(metrics)
    
    # Construir resumen de posiciones
    if positions:
        positions_text = "\n".join([p.to_summary_text() for p in positions])
        total_invested = sum(p.current_price * p.quantity for p in positions)
        total_unrealized = sum(p.unrealized_pnl for p in positions)
    else:
        positions_text = "   (Sin posiciones abiertas)"
        total_invested = 0
        total_unrealized = 0
    
    # Trades recientes
    recent_trades_text = ""
    if recent_trades:
        recent_trades_text = "\n📜 TRADES RECIENTES:\n"
        for trade in recent_trades[-5:]:
            emoji = "✅" if trade.get("pnl", 0) >= 0 else "❌"
            recent_trades_text += (
                f"   {emoji} {trade.get('symbol')} {trade.get('direction')} | "
                f"Entry: ${trade.get('entry_price', 0):.2f} → Exit: ${trade.get('exit_price', 0):.2f} | "
                f"P&L: {trade.get('pnl_pct', 0):+.2f}%\n"
            )
    
    # Determinar ventana de trading
    market_open = current_date.replace(hour=9, minute=30)
    window_end = market_open + timedelta(hours=2)
    now_et = current_date  # Asumir ya está en ET
    
    if now_et < market_open:
        window_status = "⏳ Pre-market (ventana abre a las 9:30 ET)"
    elif now_et <= window_end:
        remaining = (window_end - now_et).seconds // 60
        window_status = f"🟢 VENTANA ABIERTA ({remaining} minutos restantes)"
    else:
        window_status = "🔴 Ventana cerrada (solo puedes CERRAR posiciones)"
    
    # Calcular slots disponibles
    positions_available = 5 - len(positions)
    trades_remaining = 3 - trades_today
    
    prompt = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║            📅 SESIÓN DE TRADING - DÍA {competition_day} DE LA COMPETICIÓN            ║
║                        {current_date.strftime('%A, %d %B %Y')}                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

{ranking_text}

═══════════════════════════════════════════════════════════════════════════════
                         📊 TU ESTADO ACTUAL
═══════════════════════════════════════════════════════════════════════════════

💰 PORTFOLIO:
   Valor total: ${portfolio_value:,.2f}
   Cash disponible: ${cash_available:,.2f} ({cash_available/portfolio_value*100:.1f}%)
   Invertido: ${total_invested:,.2f}
   P&L no realizado: ${total_unrealized:+,.2f}

📈 MÉTRICAS DE LA COMPETICIÓN:
   Rendimiento total: {metrics.total_return_pct:+.2f}%
   Rendimiento hoy: {metrics.daily_return_pct:+.2f}%
   Sharpe Ratio: {metrics.sharpe_ratio:.2f}
   Max Drawdown: {metrics.max_drawdown_pct:.2f}%
   Win Rate: {metrics.win_rate:.1f}% ({metrics.winning_trades}W / {metrics.losing_trades}L)
   Racha actual: {metrics.consecutive_wins}W / {metrics.consecutive_losses}L

⏰ VENTANA DE TRADING:
   {window_status}
   Posiciones disponibles: {positions_available}/5
   Trades restantes hoy: {trades_remaining}/3

═══════════════════════════════════════════════════════════════════════════════
                         📦 POSICIONES ABIERTAS
═══════════════════════════════════════════════════════════════════════════════

{positions_text}
{recent_trades_text}
═══════════════════════════════════════════════════════════════════════════════
                         🌍 CONTEXTO DE MERCADO
═══════════════════════════════════════════════════════════════════════════════

   Régimen: {market_regime}
   VIX: {vix_level:.1f}
   SPY hoy: {spy_change:+.2f}%

{watchlist_data if watchlist_data else "   (Usa búsqueda web para obtener datos actuales)"}

═══════════════════════════════════════════════════════════════════════════════
                         📝 NOTAS DEL DÍA
═══════════════════════════════════════════════════════════════════════════════
{notes if notes else "   (Sin notas especiales)"}

═══════════════════════════════════════════════════════════════════════════════
                         🎯 TU TAREA HOY
═══════════════════════════════════════════════════════════════════════════════

Ejecuta tu análisis siguiendo el flujo:
1. RECONOCIMIENTO: Evalúa el mercado (usa web search para noticias recientes)
2. REVISIÓN: Decide qué hacer con cada posición abierta (HOLD/CLOSE/ADJUST)
3. OPORTUNIDADES: Busca nuevas entradas si la ventana está abierta
4. DECISIÓN: Genera señales solo si cumplen TODOS los criterios

RESPONDE con el siguiente JSON:

```json
{{
  "session_summary": {{
    "competition_day": {competition_day},
    "market_analysis": "Tu análisis del mercado hoy...",
    "key_news": ["Noticia 1", "Noticia 2"],
    "sentiment": "bullish|bearish|neutral"
  }},
  "position_reviews": [
    {{
      "symbol": "XXX",
      "decision": "HOLD|CLOSE|ADJUST",
      "new_stop_loss": null,
      "new_take_profit": null,
      "reasoning": "Por qué esta decisión..."
    }}
  ],
  "market_view": "bullish|bearish|neutral|uncertain",
  "confidence": 0.0-1.0,
  "signals": [
    {{
      "symbol": "XXX",
      "direction": "LONG|SHORT",
      "entry_price": 0.00,
      "stop_loss": 0.00,
      "take_profit": 0.00,
      "size_suggestion": 0.10,
      "risk_reward_ratio": 2.5,
      "confidence": 0.8,
      "reasoning": "Setup específico...",
      "confluent_indicators": ["Indicador 1", "Indicador 2", "Indicador 3"]
    }}
  ],
  "reasoning": "Razonamiento completo de tu análisis y decisiones...",
  "next_watchlist": ["SYM1", "SYM2"]
}}
```

RECUERDA:
• R/R mínimo 1:2 | Stop Loss obligatorio | Max 20% por posición
• Si hay CUALQUIER duda → NO operar
• La mejor operación a veces es NO operar
"""
    
    return prompt


# =============================================================================
# CLASE GESTORA DE LA COMPETICIÓN
# =============================================================================

class CompetitionManager:
    """
    Gestiona el estado de la competición a lo largo del tiempo.
    
    Responsabilidades:
    - Trackear día de competición
    - Mantener métricas actualizadas
    - Generar prompts apropiados (onboarding vs daily)
    - Gestionar ranking
    """
    
    def __init__(self, config: CompetitionConfig = None):
        self.config = config or CompetitionConfig()
        self.is_onboarded = False
        self.competition_day = 0
        self.start_date: Optional[datetime] = None
        self.metrics = PerformanceMetrics()
        self.trade_history: List[dict] = []
        
    def start_competition(self) -> str:
        """Inicia la competición y retorna el prompt de onboarding."""
        self.start_date = datetime.now()
        self.competition_day = 0
        self.metrics = PerformanceMetrics()
        self.trade_history = []
        return ONBOARDING_PROMPT
    
    def confirm_onboarding(self):
        """Confirma que el agente ha sido onboarded."""
        self.is_onboarded = True
        self.competition_day = 1
        
    def get_daily_prompt(
        self,
        current_date: datetime,
        portfolio_value: float,
        cash_available: float,
        positions: List[PositionSummary],
        market_regime: str,
        vix_level: float,
        spy_change: float,
        trades_today: int,
        watchlist_data: str = "",
        notes: str = ""
    ) -> str:
        """Genera el prompt de sesión diaria."""
        if not self.is_onboarded:
            raise RuntimeError("Agent not onboarded. Call start_competition() first.")
        
        return build_daily_session_prompt(
            competition_day=self.competition_day,
            current_date=current_date,
            metrics=self.metrics,
            portfolio_value=portfolio_value,
            cash_available=cash_available,
            positions=positions,
            market_regime=market_regime,
            vix_level=vix_level,
            spy_change=spy_change,
            trades_today=trades_today,
            watchlist_data=watchlist_data,
            recent_trades=self.trade_history[-5:] if self.trade_history else None,
            notes=notes
        )
    
    def update_metrics(
        self,
        daily_return: float,
        new_trades: List[dict] = None
    ):
        """Actualiza métricas después de una sesión."""
        # Actualizar día
        self.competition_day += 1
        self.metrics.days_in_competition = self.competition_day
        
        # Actualizar retornos
        self.metrics.daily_return_pct = daily_return
        self.metrics.total_return_pct += daily_return
        
        # Actualizar drawdown
        if self.metrics.total_return_pct < self.metrics.max_drawdown_pct:
            self.metrics.max_drawdown_pct = self.metrics.total_return_pct
        
        # Actualizar trades
        if new_trades:
            for trade in new_trades:
                self.trade_history.append(trade)
                self.metrics.total_trades += 1
                
                if trade.get("pnl", 0) >= 0:
                    self.metrics.winning_trades += 1
                    self.metrics.consecutive_wins += 1
                    self.metrics.consecutive_losses = 0
                else:
                    self.metrics.losing_trades += 1
                    self.metrics.consecutive_losses += 1
                    self.metrics.consecutive_wins = 0
            
            # Win rate
            if self.metrics.total_trades > 0:
                self.metrics.win_rate = (self.metrics.winning_trades / self.metrics.total_trades) * 100
    
    def get_competition_summary(self) -> dict:
        """Retorna resumen del estado de la competición."""
        return {
            "day": self.competition_day,
            "is_onboarded": self.is_onboarded,
            "metrics": {
                "total_return": self.metrics.total_return_pct,
                "sharpe": self.metrics.sharpe_ratio,
                "max_drawdown": self.metrics.max_drawdown_pct,
                "win_rate": self.metrics.win_rate,
                "total_trades": self.metrics.total_trades,
            },
            "score": self.metrics.calculate_score(),
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Config
    'CompetitionConfig',
    # Prompts
    'ONBOARDING_PROMPT',
    'build_daily_session_prompt',
    # Data classes
    'PerformanceMetrics',
    'PositionSummary',
    'CompetitorInfo',
    # Utilities
    'generate_dynamic_ranking',
    # Manager
    'CompetitionManager',
]
