"""
Configuration loader for MCP servers.

Loads and validates server configuration from YAML files.
Supports environment variable substitution.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict
from .exceptions import ConfigError


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Supports environment variable substitution using ${VAR_NAME} syntax.
    
    Args:
        config_path: Path to YAML configuration file
        
    Returns:
        Configuration dictionary
        
    Raises:
        ConfigError: If file not found or invalid YAML
        
    Example:
        >>> config = load_config('config/mcp-servers.yaml')
        >>> db_url = config['database']['url']
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_file, 'r') as f:
            config_text = f.read()
        
        # Substitute environment variables
        config_text = _substitute_env_vars(config_text)
        
        # Parse YAML
        config = yaml.safe_load(config_text)
        
        if not isinstance(config, dict):
            raise ConfigError("Configuration must be a dictionary")
        
        return config
        
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {config_path}: {e}")
    except Exception as e:
        raise ConfigError(f"Error loading config: {e}")


def _substitute_env_vars(text: str) -> str:
    """
    Substitute ${VAR_NAME} with environment variable values.
    
    Args:
        text: Text with ${VAR_NAME} placeholders
        
    Returns:
        Text with substituted values
    """
    import re
    
    def replace_var(match):
        full_match = match.group(1)
        
        # Handle default value syntax: ${VAR:-default}
        if ":-" in full_match:
            var_name, default_value = full_match.split(":-", 1)
            return os.getenv(var_name, default_value)
        
        # Handle standard syntax: ${VAR}
        value = os.getenv(full_match)
        if value is None:
            raise ConfigError(f"Environment variable not found: {full_match}")
        
        return value
    
    return re.sub(r'\$\{([^}]+)\}', replace_var, text)
