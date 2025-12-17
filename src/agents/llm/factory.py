"""
LLM Agent Factory - Crea agentes según configuración.

Permite cambiar entre Claude, GPT-4, Gemini con solo cambiar config.
"""

from __future__ import annotations

import os
from typing import Optional, Type
import logging

from .interfaces import LLMAgent, AutonomyLevel
from .config import LLMAgentConfig, load_agent_config
from .agents.claude_agent import ClaudeAgent
from .agents.claude_cli_agent import ClaudeCliAgent
from .agents.competition_agent import CompetitionClaudeAgent


logger = logging.getLogger(__name__)


# Registry de implementaciones disponibles
_AGENT_REGISTRY: dict[str, Type[LLMAgent]] = {
    "claude": ClaudeAgent,
    "claude_cli": CompetitionClaudeAgent,  # Usar el nuevo agente de competición
    "competition": CompetitionClaudeAgent,  # Alias
    # Futuras implementaciones:
    # "openai": OpenAIAgent,
    # "gemini": GeminiAgent,
}


class LLMAgentFactory:
    """
    Factory para crear instancias de LLM Agents.
    
    Uso:
        # Desde configuración YAML
        agent = LLMAgentFactory.create_from_config()
        
        # Especificando parámetros
        agent = LLMAgentFactory.create(
            provider="claude",
            model="claude-sonnet-4-20250514",
            autonomy=AutonomyLevel.MODERATE
        )
    """
    
    @classmethod
    def create_from_config(
        cls,
        config_path: Optional[str] = None
    ) -> LLMAgent:
        """
        Crea un agente desde archivo de configuración.
        
        Args:
            config_path: Ruta al archivo YAML (default: config/agents.yaml)
        
        Returns:
            Instancia de LLMAgent configurada
        """
        config = load_agent_config(config_path)
        return cls.create_from_config_object(config)
    
    @classmethod
    def create_from_config_object(cls, config: LLMAgentConfig) -> LLMAgent:
        """
        Crea un agente desde objeto de configuración.
        
        Args:
            config: Objeto LLMAgentConfig
        
        Returns:
            Instancia de LLMAgent
        """
        provider = config.active_provider
        
        if provider not in _AGENT_REGISTRY:
            available = list(_AGENT_REGISTRY.keys())
            raise ValueError(f"Unknown provider '{provider}'. Available: {available}")
        
        provider_config = config.get_provider_config(provider)
        
        # Obtener API key desde env o config
        api_key = cls._get_api_key(provider, provider_config)
        
        logger.info(f"Creating {provider} agent with model={provider_config.get('model')}")
        
        if provider == "claude":
            return ClaudeAgent(
                api_key=api_key,
                model=provider_config.get("model", "claude-sonnet-4-20250514"),
                max_tokens=provider_config.get("max_tokens", 2000),
                temperature=provider_config.get("temperature", 0.3),
                default_autonomy=AutonomyLevel(config.autonomy_level),
                timeout_seconds=provider_config.get("timeout", 60.0),
            )
            
        if provider == "claude_cli":
            # return ClaudeCliAgent(
            #     model=provider_config.get("model", "claude-sonnet-4-5"),
            #     timeout_seconds=provider_config.get("timeout", 120.0),
            # )
            # USE COMPETITION AGENT AS REQUESTED
            return CompetitionClaudeAgent(
                model=provider_config.get("model", "claude-sonnet-4-5"),
                timeout_seconds=provider_config.get("timeout", 120.0),
            )
        
        # Placeholder para otros providers
        raise NotImplementedError(f"Provider {provider} not yet implemented")
    
    @classmethod
    def create(
        cls,
        provider: str = "claude",
        model: Optional[str] = None,
        autonomy: AutonomyLevel = AutonomyLevel.MODERATE,
        api_key: Optional[str] = None,
        **kwargs
    ) -> LLMAgent:
        """
        Crea un agente con parámetros explícitos.
        
        Args:
            provider: Nombre del provider (claude, openai, gemini)
            model: Modelo específico (usa default del provider si no se especifica)
            autonomy: Nivel de autonomía
            api_key: API key (usa env var si no se especifica)
            **kwargs: Parámetros adicionales para el agente
        
        Returns:
            Instancia de LLMAgent
        """
        if provider not in _AGENT_REGISTRY:
            raise ValueError(f"Unknown provider: {provider}")
        
        # Defaults por provider
        defaults = {
            "claude": {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "temperature": 0.3,
            },
            "openai": {
                "model": "gpt-4-turbo",
                "max_tokens": 2000,
                "temperature": 0.3,
            },
        }
        
        provider_defaults = defaults.get(provider, {})
        final_model = model or provider_defaults.get("model")
        final_api_key = api_key or cls._get_api_key(provider, {})
        
        if provider == "claude":
            return ClaudeAgent(
                api_key=final_api_key,
                model=final_model,
                temperature=kwargs.get("temperature", provider_defaults.get("temperature", 0.3)),
                default_autonomy=autonomy,
                timeout_seconds=kwargs.get("timeout", 60.0),
            )
            
        if provider == "claude_cli":
            return CompetitionClaudeAgent(
                model=kwargs.get("model", "claude-sonnet-4-5"),
                timeout_seconds=kwargs.get("timeout", 120.0),
                cwd=kwargs.get("cwd")
            )
        
        raise NotImplementedError(f"Provider {provider} not yet implemented")
    
    @classmethod
    def _get_api_key(cls, provider: str, config: dict) -> str:
        """Obtiene API key desde config o environment."""
        # Primero intentar desde config
        if "api_key" in config and config["api_key"]:
            return config["api_key"]
        
        # Luego desde environment
        env_vars = {
            "claude": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "claude_cli": None, # No API key needed
        }
        
        env_var = env_vars.get(provider)
        
        # Provider explicitamente sin key requerida
        if provider in env_vars and env_var is None:
            return ""

        if env_var:
            api_key = os.environ.get(env_var)
            if api_key:
                return api_key
        
        raise ValueError(
            f"No API key found for {provider}. "
            f"Set {env_var} environment variable or provide in config."
        )
    
    @classmethod
    def list_available_providers(cls) -> list[str]:
        """Lista providers disponibles."""
        return list(_AGENT_REGISTRY.keys())
    
    @classmethod
    def register_provider(cls, name: str, agent_class: Type[LLMAgent]):
        """
        Registra un nuevo provider.
        
        Args:
            name: Nombre del provider
            agent_class: Clase que implementa LLMAgent
        """
        if not issubclass(agent_class, LLMAgent):
            raise TypeError(f"{agent_class} must be a subclass of LLMAgent")
        _AGENT_REGISTRY[name] = agent_class
        logger.info(f"Registered LLM provider: {name}")
