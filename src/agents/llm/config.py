"""
Configuración del LLM Agent.

Carga configuración desde YAML y proporciona defaults seguros.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
import os

import yaml


@dataclass
class LLMAgentConfig:
    """Configuración global de agentes."""
    active_provider: str = "claude"
    autonomy_level: str = "moderate"
    providers: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    def get_provider_config(self, provider: str) -> dict[str, Any]:
        """Obtiene configuración específica de un provider."""
        return self.providers.get(provider, {})


def load_agent_config(config_path: Optional[str] = None) -> LLMAgentConfig:
    """
    Carga configuración desde archivo YAML.
    
    Args:
        config_path: Ruta al archivo (default: config/agents.yaml)
    
    Returns:
        Objeto LLMAgentConfig
    """
    if config_path is None:
        # Buscar en rutas estándar
        paths = [
            "config/agents.yaml",
            "../config/agents.yaml",
            "../../config/agents.yaml"
        ]
        for p in paths:
            if os.path.exists(p):
                config_path = p
                break
    
    if config_path and os.path.exists(config_path):
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            return LLMAgentConfig(
                active_provider=data.get("active_provider", "claude"),
                autonomy_level=data.get("autonomy_level", "moderate"),
                providers=data.get("providers", {})
            )
    
    # Default config si no existe archivo
    return LLMAgentConfig(
        active_provider="claude",
        autonomy_level="moderate",
        providers={
            "claude": {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "temperature": 0.3
            }
        }
    )
