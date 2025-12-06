"""
Módulo de Prompts para AI Agent.
"""

from .base import SYSTEM_PROMPT_BASE, JSON_OUTPUT_INSTRUCTIONS
from .conservative import CONSERVATIVE_PROMPT
from .moderate import MODERATE_PROMPT

__all__ = [
    "SYSTEM_PROMPT_BASE",
    "JSON_OUTPUT_INSTRUCTIONS",
    "CONSERVATIVE_PROMPT",
    "MODERATE_PROMPT",
]
