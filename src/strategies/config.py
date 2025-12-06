"""
Carga y gestión de configuración de estrategias.
"""

from pathlib import Path
from typing import Optional
import yaml
import logging

from .registry import StrategyRegistry


logger = logging.getLogger("strategy.config")


class StrategyConfig:
    """
    Gestión de configuración de estrategias.
    
    Carga configuración desde YAML y la proporciona al Registry.
    """
    
    DEFAULT_CONFIG_PATH = "config/strategies.yaml"
    
    def __init__(self, config_path: str = None):
        """
        Inicializar gestor de configuración.
        
        Args:
            config_path: Ruta al archivo YAML (opcional)
        """
        self.config_path = Path(config_path or self.DEFAULT_CONFIG_PATH)
        self._config: dict = {}
        self._loaded = False
    
    def load(self) -> dict:
        """
        Cargar configuración desde archivo YAML.
        
        Returns:
            Diccionario de configuración
            
        Raises:
            FileNotFoundError: Si el archivo no existe
            yaml.YAMLError: Si el YAML es inválido
        """
        if not self.config_path.exists():
            logger.warning(f"Config no encontrada: {self.config_path}")
            self._config = self._default_config()
            return self._config
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        self._loaded = True
        logger.info(f"Configuración cargada desde {self.config_path}")
        
        # Actualizar Registry
        StrategyRegistry.set_config(self._config)
        
        return self._config
    
    def reload(self) -> dict:
        """Recargar configuración (hot reload)."""
        return self.load()
    
    def get(self, key: str, default=None):
        """Obtener valor de configuración."""
        keys = key.split(".")
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        
        return value if value is not None else default
    
    def get_strategy_config(self, strategy_id: str) -> dict:
        """
        Obtener configuración específica de una estrategia.
        
        Args:
            strategy_id: ID de la estrategia
            
        Returns:
            Configuración de la estrategia o dict vacío
        """
        return self._config.get("strategies", {}).get(strategy_id, {})
    
    def is_strategy_enabled(self, strategy_id: str) -> bool:
        """Verificar si una estrategia está habilitada."""
        return self.get_strategy_config(strategy_id).get("enabled", False)
    
    def get_enabled_strategies(self) -> list[str]:
        """Obtener lista de estrategias habilitadas."""
        strategies = self._config.get("strategies", {})
        return [
            sid for sid, conf in strategies.items()
            if conf.get("enabled", False)
        ]
    
    @property
    def config(self) -> dict:
        """Configuración completa."""
        return self._config
    
    def _default_config(self) -> dict:
        """Configuración por defecto si no hay archivo."""
        return {
            "global": {
                "default_timeframe": "1d",
                "signal_ttl_hours": 24,
            },
            "strategies": {
                "etf_momentum": {
                    "enabled": True,
                    "markets": ["EU", "US"],
                }
            }
        }


# Instancia global
_config_instance: Optional[StrategyConfig] = None


def get_strategy_config(config_path: str = None) -> StrategyConfig:
    """
    Obtener instancia de configuración (singleton).
    
    Args:
        config_path: Ruta al config (solo para primera llamada)
        
    Returns:
        Instancia de StrategyConfig
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = StrategyConfig(config_path)
        _config_instance.load()
    
    return _config_instance


def reload_config() -> dict:
    """Recargar configuración."""
    global _config_instance
    
    if _config_instance:
        return _config_instance.reload()
    
    return get_strategy_config().config
