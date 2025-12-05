"""
Data Source Configuration - Phase A1.2
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List
import yaml
from pydantic import BaseModel, Field


class SourceCapabilities(BaseModel):
    """Capabilities of a data source."""
    supports_realtime: bool = False
    supports_historical: bool = True
    supports_intraday: bool = False
    supports_options: bool = False
    supports_forex: bool = False


class IBKRConfig(BaseModel):
    """IBKR specific configuration."""
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1
    timeout_seconds: int = 30
    delayed_data_ok: bool = True


class YahooConfig(BaseModel):
    """Yahoo Finance specific configuration."""
    rate_limit_seconds: float = 0.5
    max_retries: int = 3
    retry_delay_seconds: int = 5


class GlobalConfig(BaseModel):
    """Global data system configuration."""
    retry_count: int = 3
    retry_delay_seconds: int = 2
    request_timeout_seconds: int = 30
    unhealthy_threshold: int = 5
    recovery_check_interval: int = 300


@dataclass
class DataSourceInfo:
    """Complete information about a data source."""
    name: str
    enabled: bool
    priority: int
    capabilities: SourceCapabilities
    config: dict
    is_healthy: bool = True
    consecutive_failures: int = 0


class DataSourceConfig:
    """
    Data source configuration manager.
    
    Loads configuration from YAML and allows DB override.
    
    Usage:
        config = DataSourceConfig('config/data_sources.yaml')
        primary = config.get_primary_source()
        fallback = config.get_fallback_source()
    """
    
    def __init__(self, config_path: str = "config/data_sources.yaml"):
        self.config_path = Path(config_path)
        self._raw_config: dict = {}
        self._sources: dict[str, DataSourceInfo] = {}
        self._global: GlobalConfig = GlobalConfig()
        self._symbol_mapping: dict[str, dict[str, str]] = {}
        
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML."""
        if not self.config_path.exists():
            # Try finding it relative to project root if not found
            project_root = Path(__file__).parent.parent.parent
            alt_path = project_root / self.config_path
            if alt_path.exists():
                self.config_path = alt_path
            else:
                raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._raw_config = yaml.safe_load(f)
        
        # Load global config
        if 'global' in self._raw_config:
            self._global = GlobalConfig(**self._raw_config['global'])
        
        # Load sources
        sources_config = self._raw_config.get('sources', {})
        for name, source_data in sources_config.items():
            capabilities = SourceCapabilities(**source_data.get('capabilities', {}))
            
            self._sources[name] = DataSourceInfo(
                name=name,
                enabled=source_data.get('enabled', True),
                priority=source_data.get('priority', 100),
                capabilities=capabilities,
                config=source_data
            )
        
        # Load symbol mapping
        self._symbol_mapping = self._raw_config.get('symbol_mapping', {})
    
    def get_primary_source(self) -> Optional[DataSourceInfo]:
        """Get the configured primary source."""
        primary_name = self._raw_config.get('primary')
        if primary_name and primary_name in self._sources:
            source = self._sources[primary_name]
            if source.enabled and source.is_healthy:
                return source
        
        # Fallback: find by priority
        return self._get_best_available_source()
    
    def get_fallback_source(self) -> Optional[DataSourceInfo]:
        """Get the configured fallback source."""
        fallback_name = self._raw_config.get('fallback')
        if fallback_name and fallback_name in self._sources:
            source = self._sources[fallback_name]
            if source.enabled:
                return source
        return None
    
    def _get_best_available_source(self) -> Optional[DataSourceInfo]:
        """Get the best available source by priority."""
        available = [
            s for s in self._sources.values()
            if s.enabled and s.is_healthy
        ]
        if not available:
            return None
        
        return min(available, key=lambda s: s.priority)
    
    def get_source(self, name: str) -> Optional[DataSourceInfo]:
        """Get a specific source by name."""
        return self._sources.get(name)
    
    def get_all_sources(self) -> List[DataSourceInfo]:
        """Get all configured sources."""
        return list(self._sources.values())
    
    def get_enabled_sources(self) -> List[DataSourceInfo]:
        """Get enabled sources sorted by priority."""
        enabled = [s for s in self._sources.values() if s.enabled]
        return sorted(enabled, key=lambda s: s.priority)
    
    def get_symbol_for_source(self, internal_symbol: str, source_name: str) -> str:
        """
        Get the specific symbol for a source.
        
        Args:
            internal_symbol: Internal symbol (e.g., "EURUSD")
            source_name: Source name (e.g., "ibkr", "yahoo")
        
        Returns:
            Specific symbol for the source, or internal if no mapping
        """
        if internal_symbol in self._symbol_mapping:
            mapping = self._symbol_mapping[internal_symbol]
            if source_name in mapping and mapping[source_name]:
                return mapping[source_name]
        
        return internal_symbol
    
    def mark_source_failure(self, source_name: str) -> None:
        """Mark a failure for a source."""
        if source_name in self._sources:
            source = self._sources[source_name]
            source.consecutive_failures += 1
            
            if source.consecutive_failures >= self._global.unhealthy_threshold:
                source.is_healthy = False
    
    def mark_source_success(self, source_name: str) -> None:
        """Mark a success for a source (resets failure count)."""
        if source_name in self._sources:
            source = self._sources[source_name]
            source.consecutive_failures = 0
            source.is_healthy = True
    
    @property
    def global_config(self) -> GlobalConfig:
        """Get global configuration."""
        return self._global
    
    def get_ibkr_config(self) -> IBKRConfig:
        """Get IBKR specific configuration."""
        ibkr_source = self._sources.get('ibkr')
        if not ibkr_source:
            return IBKRConfig()
        
        conn_config = ibkr_source.config.get('connection', {})
        return IBKRConfig(**conn_config)
    
    def get_yahoo_config(self) -> YahooConfig:
        """Get Yahoo specific configuration."""
        yahoo_source = self._sources.get('yahoo')
        if not yahoo_source:
            return YahooConfig()
        
        conn_config = yahoo_source.config.get('connection', {})
        return YahooConfig(**conn_config)
