"""
Configuration management for agents.

Provides utilities for loading and validating agent configuration from
YAML files with environment variable overrides.
"""

import yaml
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Supports environment variable overrides using ${VAR_NAME} syntax in YAML.
    
    Args:
        config_path: Path to YAML configuration file
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
        
    Example:
        >>> config = load_config("config/agents.yaml")
        >>> technical_config = config.get("technical_analyst", {})
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    logger.info(f"Loading configuration from: {config_path}")
    
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        if config is None:
            config = {}
        
        # Process environment variable substitutions
        config = _substitute_env_vars(config)
        
        logger.info(f"Configuration loaded successfully: {len(config)} sections")
        return config
    
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML config: {e}")
        raise


def _substitute_env_vars(config: Any) -> Any:
    """
    Recursively substitute ${VAR_NAME} with environment variables.
    
    Args:
        config: Configuration value (dict, list, or scalar)
        
    Returns:
        Configuration with environment variables substituted
    """
    if isinstance(config, dict):
        return {k: _substitute_env_vars(v) for k, v in config.items()}
    
    elif isinstance(config, list):
        return [_substitute_env_vars(item) for item in config]
    
    elif isinstance(config, str):
        # Check for ${VAR_NAME} pattern
        if config.startswith('${') and config.endswith('}'):
            var_name = config[2:-1]
            value = os.getenv(var_name)
            
            if value is None:
                logger.warning(
                    f"Environment variable '{var_name}' not set, "
                    f"using literal value '{config}'"
                )
                return config
            
            return value
        
        return config
    
    else:
        return config


def get_agent_config(
    config: Dict[str, Any],
    agent_name: str,
    defaults: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get configuration for a specific agent with defaults.
    
    Args:
        config: Full configuration dictionary
        agent_name: Name of agent to get config for
        defaults: Default values to use if not in config
        
    Returns:
        Agent-specific configuration
        
    Example:
        >>> config = load_config("config/agents.yaml")
        >>> ta_config = get_agent_config(
        ...     config,
        ...     "technical_analyst",
        ...     defaults={"interval_seconds": 300}
        ... )
    """
    agent_config = config.get(agent_name, {})
    
    if defaults:
        # Merge with defaults (config overrides defaults)
        merged = defaults.copy()
        merged.update(agent_config)
        return merged
    
    return agent_config


def validate_required_keys(config: Dict[str, Any], required_keys: list[str]):
    """
    Validate that required configuration keys are present.
    
    Args:
        config: Configuration dictionary
        required_keys: List of required key names
        
    Raises:
        ValueError: If any required keys are missing
        
    Example:
        >>> validate_required_keys(
        ...     config,
        ...     ["symbols", "interval_seconds"]
        ... )
    """
    missing = [key for key in required_keys if key not in config]
    
    if missing:
        raise ValueError(f"Missing required configuration keys: {missing}")
