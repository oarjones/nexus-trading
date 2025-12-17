"""
Módulo de Prompts para AI Agent.

Incluye:
- Prompts básicos (conservative, moderate)
- Prompt de competición para Claude Code CLI
"""

from .base import SYSTEM_PROMPT_BASE, JSON_OUTPUT_INSTRUCTIONS
from .conservative import CONSERVATIVE_PROMPT
from .moderate import MODERATE_PROMPT
from .competition import (
    COMPETITION_SYSTEM_PROMPT,
    PORTFOLIO_REVIEW_PROMPT,
    build_competition_prompt,
    build_review_prompt,
    COMPETITION_NAME,
    INITIAL_CAPITAL,
)
from .competition_v2 import (
    CompetitionManager,
    CompetitionConfig,
    PerformanceMetrics,
    PositionSummary,
    ONBOARDING_PROMPT,
    build_daily_session_prompt,
    generate_dynamic_ranking,
)

__all__ = [
    # Base
    "SYSTEM_PROMPT_BASE",
    "JSON_OUTPUT_INSTRUCTIONS",
    # Levels
    "CONSERVATIVE_PROMPT",
    "MODERATE_PROMPT",
    # Competition v1
    "COMPETITION_SYSTEM_PROMPT",
    "PORTFOLIO_REVIEW_PROMPT",
    "build_competition_prompt",
    "build_review_prompt",
    "COMPETITION_NAME",
    "INITIAL_CAPITAL",
    # Competition v2
    "CompetitionManager",
    "CompetitionConfig", 
    "PerformanceMetrics",
    "PositionSummary",
    "ONBOARDING_PROMPT",
    "build_daily_session_prompt",
    "generate_dynamic_ranking",
]
