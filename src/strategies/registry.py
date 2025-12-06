"""
Registry de estrategias de trading.

Permite registrar, descubrir y obtener estrategias de forma dinámica.
La activación/desactivación se controla via YAML.
"""

from typing import Type, Optional
import logging

from .interfaces import TradingStrategy, MarketRegime


class StrategyRegistry:
    """
    Registro centralizado de estrategias de trading.
    
    Patrón Singleton para asegurar un único registro global.
    
    Uso:
        # Registrar estrategia
        StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)
        
        # Obtener estrategia
        strategy = StrategyRegistry.get("etf_momentum", config)
        
        # Obtener activas para régimen
        activas = StrategyRegistry.get_active_for_regime(MarketRegime.BULL)
    """
    
    _instance: Optional["StrategyRegistry"] = None
    _registry: dict[str, Type[TradingStrategy]] = {}
    _instances: dict[str, TradingStrategy] = {}
    _config: dict = {}
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logger = logging.getLogger("strategy.registry")
        return cls._instance
    
    @classmethod
    def register(
        cls, 
        strategy_id: str, 
        strategy_class: Type[TradingStrategy]
    ) -> None:
        """
        Registrar una clase de estrategia.
        
        Args:
            strategy_id: Identificador único
            strategy_class: Clase que hereda de TradingStrategy
        """
        if not issubclass(strategy_class, TradingStrategy):
            raise TypeError(
                f"{strategy_class} debe heredar de TradingStrategy"
            )
        
        cls._registry[strategy_id] = strategy_class
        logging.getLogger("strategy.registry").info(
            f"Estrategia registrada: {strategy_id}"
        )
    
    @classmethod
    def unregister(cls, strategy_id: str) -> None:
        """Eliminar estrategia del registro."""
        cls._registry.pop(strategy_id, None)
        cls._instances.pop(strategy_id, None)
    
    @classmethod
    def get(
        cls, 
        strategy_id: str, 
        config: dict = None
    ) -> Optional[TradingStrategy]:
        """
        Obtener instancia de estrategia.
        
        Usa caché de instancias para reutilizar objetos.
        
        Args:
            strategy_id: ID de la estrategia
            config: Configuración específica
            
        Returns:
            Instancia de TradingStrategy o None si no existe
        """
        if strategy_id not in cls._registry:
            logging.getLogger("strategy.registry").warning(
                f"Estrategia no registrada: {strategy_id}"
            )
            return None
        
        # Verificar si ya existe instancia
        # Usamos str(config) como parte de la key, aunque es una aproximación
        # idealmente usaríamos un hash más robusto o solo strategy_id si config no cambia
        cache_key = f"{strategy_id}_{hash(str(config))}"
        if cache_key not in cls._instances:
            strategy_class = cls._registry[strategy_id]
            cls._instances[cache_key] = strategy_class(config)
        
        return cls._instances[cache_key]
    
    @classmethod
    def get_all_registered(cls) -> list[str]:
        """Obtener lista de IDs de estrategias registradas."""
        return list(cls._registry.keys())
    
    @classmethod
    def get_active_for_regime(
        cls, 
        regime: MarketRegime,
        strategies_config: dict = None
    ) -> list[TradingStrategy]:
        """
        Obtener estrategias activas para un régimen específico.
        
        Una estrategia está activa si:
        1. Está habilitada en configuración (enabled: true)
        2. Su required_regime incluye el régimen actual
        
        Args:
            regime: Régimen de mercado actual
            strategies_config: Configuración de estrategias (del YAML)
            
        Returns:
            Lista de estrategias activas para este régimen
        """
        active = []
        config = strategies_config or cls._config
        
        for strategy_id in cls._registry.keys():
            # Verificar si está habilitada en config
            strategy_conf = config.get("strategies", {}).get(strategy_id, {})
            if not strategy_conf.get("enabled", False):
                continue
            
            # Obtener instancia
            strategy = cls.get(strategy_id, strategy_conf)
            if strategy is None:
                continue
            
            # Verificar si puede operar en este régimen
            if strategy.can_operate_in_regime(regime):
                active.append(strategy)
        
        return active
    
    @classmethod
    def get_by_type(
        cls, 
        strategy_type: str,
        strategies_config: dict = None
    ) -> list[TradingStrategy]:
        """
        Obtener estrategias por tipo (swing, intraday).
        """
        filtered = []
        config = strategies_config or cls._config
        
        for strategy_id in cls._registry.keys():
            strategy_conf = config.get("strategies", {}).get(strategy_id, {})
            
            # Instanciar
            strategy = cls.get(strategy_id, strategy_conf)
            if strategy is None:
                continue
                
            # Verificar tipo (asumiendo que la estrategia tiene propiedad strategy_type)
            if hasattr(strategy, "strategy_type") and strategy.strategy_type == strategy_type:
                filtered.append(strategy)
                
        return filtered
    
    @classmethod
    def set_config(cls, config: dict) -> None:
        """
        Establecer configuración global de estrategias.
        
        Args:
            config: Configuración cargada del YAML
        """
        cls._config = config
        
        # Actualizar estado enabled de instancias existentes
        for strategy_id, strategy_conf in config.get("strategies", {}).items():
            cache_keys = [k for k in cls._instances.keys() if k.startswith(strategy_id)]
            for cache_key in cache_keys:
                cls._instances[cache_key].enabled = strategy_conf.get("enabled", False)
    
    @classmethod
    def reset(cls) -> None:
        """Limpiar registro (útil para tests)."""
        cls._registry.clear()
        cls._instances.clear()
        cls._config.clear()
    
    @classmethod
    def get_info(cls) -> dict:
        """Obtener información del registry."""
        return {
            "registered_count": len(cls._registry),
            "registered_strategies": list(cls._registry.keys()),
            "cached_instances": len(cls._instances),
            "config_loaded": bool(cls._config),
        }


# Decorador para auto-registro
def register_strategy(strategy_id: str):
    """
    Decorador para registrar automáticamente estrategias.
    
    Uso:
        @register_strategy("etf_momentum")
        class ETFMomentumStrategy(TradingStrategy):
            ...
    """
    def decorator(cls: Type[TradingStrategy]) -> Type[TradingStrategy]:
        StrategyRegistry.register(strategy_id, cls)
        return cls
    return decorator
