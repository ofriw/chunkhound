"""Configuration management for ChunkHound embedding servers.

This module provides:
- Server registry for managing multiple embedding servers
- YAML configuration file support
- Health checking and monitoring
- Provider configuration validation
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import yaml
import aiohttp
from urllib.parse import urljoin

from .embeddings import (
    EmbeddingProvider, 
    OpenAIEmbeddingProvider,
    OpenAICompatibleProvider, 
    TEIProvider,
    create_openai_provider,
    create_openai_compatible_provider,
    create_tei_provider,
    create_bge_in_icl_provider
)

logger = logging.getLogger(__name__)


@dataclass
class ServerHealth:
    """Health status of an embedding server."""
    is_healthy: bool
    response_time_ms: float
    last_check: float
    error_message: Optional[str] = None
    model_info: Optional[Dict[str, Any]] = None


@dataclass 
class ServerConfig:
    """Configuration for an embedding server."""
    name: str
    type: str  # 'openai', 'openai-compatible', 'tei'
    base_url: str
    model: str
    api_key: Optional[str] = None
    enabled: bool = True
    health_check_interval: int = 300  # seconds
    timeout: int = 30  # seconds
    batch_size: Optional[int] = None
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate server configuration."""
        if self.type not in ['openai', 'openai-compatible', 'tei', 'bge-in-icl']:
            raise ValueError(f"Invalid server type: {self.type}")
        
        if not self.base_url:
            raise ValueError("base_url is required")
        
        if not self.model and self.type not in ['tei', 'bge-in-icl']:
            raise ValueError("model is required for non-TEI and non-BGE-IN-ICL servers")


class ServerRegistry:
    """Registry for managing embedding servers."""
    
    def __init__(self):
        self._servers: Dict[str, ServerConfig] = {}
        self._providers: Dict[str, EmbeddingProvider] = {}
        self._health_status: Dict[str, ServerHealth] = {}
        self._health_check_tasks: Dict[str, asyncio.Task] = {}
        self._default_server: Optional[str] = None
        
    def register_server(self, config: ServerConfig, set_default: bool = False) -> None:
        """Register a new embedding server.
        
        Args:
            config: Server configuration
            set_default: Whether to set as default server
        """
        if config.name in self._servers:
            logger.warning(f"Overwriting existing server config: {config.name}")
        
        self._servers[config.name] = config
        logger.info(f"Registered server: {config.name} ({config.type}) at {config.base_url}")
        
        if set_default or self._default_server is None:
            self._default_server = config.name
            logger.info(f"Set default server: {config.name}")
        
        # Initialize health status
        self._health_status[config.name] = ServerHealth(
            is_healthy=False,
            response_time_ms=0.0,
            last_check=0.0
        )
    
    def unregister_server(self, name: str) -> None:
        """Remove a server from the registry.
        
        Args:
            name: Server name to remove
        """
        if name not in self._servers:
            raise ValueError(f"Server not found: {name}")
        
        # Stop health checking
        if name in self._health_check_tasks:
            self._health_check_tasks[name].cancel()
            del self._health_check_tasks[name]
        
        # Clean up
        del self._servers[name]
        self._providers.pop(name, None)
        self._health_status.pop(name, None)
        
        # Update default if needed
        if self._default_server == name:
            remaining = list(self._servers.keys())
            self._default_server = remaining[0] if remaining else None
        
        logger.info(f"Unregistered server: {name}")
    
    def get_server(self, name: Optional[str] = None) -> ServerConfig:
        """Get server configuration by name.
        
        Args:
            name: Server name (uses default if None)
            
        Returns:
            Server configuration
        """
        if name is None:
            if self._default_server is None:
                raise ValueError("No default server set")
            name = self._default_server
        
        if name not in self._servers:
            raise ValueError(f"Server not found: {name}")
        
        return self._servers[name]
    
    def list_servers(self) -> List[str]:
        """List all registered server names."""
        return list(self._servers.keys())
    
    def get_healthy_servers(self) -> List[str]:
        """Get list of healthy server names."""
        return [
            name for name, health in self._health_status.items()
            if health.is_healthy and self._servers[name].enabled
        ]
    
    async def get_provider(self, name: Optional[str] = None) -> EmbeddingProvider:
        """Get embedding provider for a server.
        
        Args:
            name: Server name (uses default if None)
            
        Returns:
            Embedding provider instance
        """
        server = self.get_server(name)
        
        # Return cached provider if available
        if server.name in self._providers:
            return self._providers[server.name]
        
        # Create new provider
        provider = await self._create_provider(server)
        self._providers[server.name] = provider
        
        return provider
    
    async def _create_provider(self, config: ServerConfig) -> EmbeddingProvider:
        """Create embedding provider from server config."""
        if config.type == 'openai':
            return create_openai_provider(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.model
            )
        elif config.type == 'openai-compatible':
            return create_openai_compatible_provider(
                base_url=config.base_url,
                model=config.model,
                api_key=config.api_key,
                provider_name=config.name
            )
        elif config.type == 'tei':
            return create_tei_provider(
                base_url=config.base_url,
                model=config.model
            )
        elif config.type == 'bge-in-icl':
            return create_bge_in_icl_provider(
                base_url=config.base_url,
                model=config.model or "bge-in-icl",
                api_key=config.api_key,
                language=config.metadata.get('language', 'auto'),
                enable_icl=config.metadata.get('enable_icl', True),
                batch_size=config.batch_size,
                timeout=config.timeout
            )
        else:
            raise ValueError(f"Unknown server type: {config.type}")
    
    async def check_server_health(self, name: str) -> ServerHealth:
        """Check health of a specific server.
        
        Args:
            name: Server name to check
            
        Returns:
            Server health status
        """
        if name not in self._servers:
            raise ValueError(f"Server not found: {name}")
        
        config = self._servers[name]
        start_time = time.time()
        
        try:
            # Test connection with a simple health check
            timeout = aiohttp.ClientTimeout(total=config.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Try different health check endpoints
                health_urls = [
                    urljoin(config.base_url, '/health'),
                    urljoin(config.base_url, '/v1/models'),
                    config.base_url  # fallback to base URL
                ]
                
                last_error = None
                for url in health_urls:
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                response_time = (time.time() - start_time) * 1000
                                
                                # Try to get model info
                                model_info = None
                                try:
                                    if url.endswith('/v1/models'):
                                        model_info = await response.json()
                                except:
                                    pass
                                
                                health = ServerHealth(
                                    is_healthy=True,
                                    response_time_ms=response_time,
                                    last_check=time.time(),
                                    model_info=model_info
                                )
                                self._health_status[name] = health
                                logger.debug(f"Server {name} is healthy ({response_time:.1f}ms)")
                                return health
                    except Exception as e:
                        last_error = e
                        continue
                
                # All URLs failed
                raise last_error or Exception("All health check URLs failed")
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            health = ServerHealth(
                is_healthy=False,
                response_time_ms=response_time,
                last_check=time.time(),
                error_message=str(e)
            )
            self._health_status[name] = health
            logger.warning(f"Server {name} health check failed: {e}")
            return health
    
    async def start_health_monitoring(self, name: Optional[str] = None) -> None:
        """Start health monitoring for servers.
        
        Args:
            name: Specific server name (all servers if None)
        """
        servers_to_monitor = [name] if name else list(self._servers.keys())
        
        for server_name in servers_to_monitor:
            if server_name in self._health_check_tasks:
                # Already monitoring
                continue
            
            config = self._servers[server_name]
            if not config.enabled:
                continue
            
            task = asyncio.create_task(self._health_monitor_loop(server_name))
            self._health_check_tasks[server_name] = task
            logger.info(f"Started health monitoring for server: {server_name}")
    
    async def stop_health_monitoring(self, name: Optional[str] = None) -> None:
        """Stop health monitoring for servers.
        
        Args:
            name: Specific server name (all servers if None)
        """
        servers_to_stop = [name] if name else list(self._health_check_tasks.keys())
        
        for server_name in servers_to_stop:
            if server_name in self._health_check_tasks:
                self._health_check_tasks[server_name].cancel()
                del self._health_check_tasks[server_name]
                logger.info(f"Stopped health monitoring for server: {server_name}")
    
    async def _health_monitor_loop(self, name: str) -> None:
        """Continuous health monitoring loop for a server."""
        config = self._servers[name]
        
        while True:
            try:
                await self.check_server_health(name)
                await asyncio.sleep(config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error for {name}: {e}")
                await asyncio.sleep(min(config.health_check_interval, 60))
    
    def get_health_status(self, name: Optional[str] = None) -> Union[ServerHealth, Dict[str, ServerHealth]]:
        """Get health status for servers.
        
        Args:
            name: Specific server name (all servers if None)
            
        Returns:
            Health status for one or all servers
        """
        if name:
            if name not in self._health_status:
                raise ValueError(f"No health status for server: {name}")
            return self._health_status[name]
        
        return self._health_status.copy()


class ConfigManager:
    """Manages ChunkHound configuration from YAML files."""
    
    DEFAULT_CONFIG_PATHS = [
        ".chunkhound/config.yaml",
        ".chunkhound/config.yml", 
        "~/.chunkhound/config.yaml",
        "~/.chunkhound/config.yml",
        "/etc/chunkhound/config.yaml",
        "/etc/chunkhound/config.yml"
    ]
    
    @classmethod
    def discover_config_files(cls, start_path: Optional[Path] = None, include_invalid: bool = False) -> List[Dict[str, Any]]:
        """Discover all configuration files from a starting path.
        
        Args:
            start_path: Directory to start discovery from (default: current dir)
            include_invalid: Include invalid config files in results
            
        Returns:
            List of dictionaries with config file information
        """
        start_path = start_path or Path.cwd()
        discovered = []
        
        # Define search patterns
        search_patterns = [
            # Project-specific configs
            start_path / ".chunkhound",
            start_path / "chunkhound",
            start_path / ".config/chunkhound",
            # Parent directory searches
            start_path.parent / ".chunkhound",
            # User-specific configs
            Path.home() / ".chunkhound",
            Path.home() / ".config/chunkhound", 
            # System-wide configs
            Path("/etc/chunkhound"),
            Path("/usr/local/etc/chunkhound")
        ]
        
        config_filenames = ["config.yaml", "config.yml", "chunkhound.yaml", "chunkhound.yml"]
        
        for search_dir in search_patterns:
            if not search_dir.exists():
                continue
                
            for filename in config_filenames:
                config_file = search_dir / filename
                if not config_file.exists():
                    continue
                
                config_info = {
                    'path': config_file,
                    'directory': search_dir,
                    'filename': filename,
                    'valid': False,
                    'server_count': 0,
                    'servers': [],
                    'default_server': None,
                    'error': None,
                    'priority': cls._get_config_priority(config_file, start_path)
                }
                
                # Try to validate the config
                try:
                    temp_manager = ConfigManager(str(config_file))
                    temp_manager.load_config()
                    
                    servers = temp_manager.registry.list_servers()
                    config_info.update({
                        'valid': True,
                        'server_count': len(servers),
                        'servers': servers,
                        'default_server': temp_manager.registry._default_server
                    })
                except Exception as e:
                    config_info['error'] = str(e)
                    if not include_invalid:
                        continue
                
                discovered.append(config_info)
        
        # Sort by priority (lower number = higher priority)
        discovered.sort(key=lambda x: x['priority'])
        return discovered
    
    @classmethod
    def _get_config_priority(cls, config_path: Path, start_path: Path) -> int:
        """Determine priority of a config file (lower = higher priority)."""
        try:
            # Project-specific configs have highest priority
            if config_path.is_relative_to(start_path):
                if config_path.parent.name == ".chunkhound":
                    return 1  # .chunkhound/config.yaml in project
                elif config_path.parent.name == "chunkhound":
                    return 2  # chunkhound/config.yaml in project
                else:
                    return 3  # other project configs
            
            # User configs
            if config_path.is_relative_to(Path.home()):
                return 4  # ~/.chunkhound/config.yaml
            
            # System configs
            return 5  # /etc/chunkhound/config.yaml
            
        except (ValueError, OSError):
            return 6  # fallback for any issues
    
    @classmethod
    def get_recommended_config_path(cls, start_path: Optional[Path] = None) -> Path:
        """Get the recommended config path for new configurations."""
        start_path = start_path or Path.cwd()
        
        # Check if we're in a project directory (has .git, pyproject.toml, etc.)
        project_indicators = [".git", "pyproject.toml", "package.json", "Cargo.toml", "go.mod"]
        is_project = any((start_path / indicator).exists() for indicator in project_indicators)
        
        if is_project:
            # Use project-specific config
            config_dir = start_path / ".chunkhound"
            config_dir.mkdir(exist_ok=True)
            return config_dir / "config.yaml"
        else:
            # Use user-specific config
            config_dir = Path.home() / ".chunkhound"
            config_dir.mkdir(exist_ok=True)
            return config_dir / "config.yaml"
    
    def validate_config_file(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Validate a configuration file and return detailed results.
        
        Args:
            config_path: Path to config file (uses current if None)
            
        Returns:
            Dictionary with validation results
        """
        config_file = Path(config_path) if config_path else self.find_config_file()
        if not config_file:
            return {
                'valid': False,
                'error': 'No configuration file found',
                'issues': ['No configuration file exists'],
                'recommendations': ['Create a config file with: chunkhound config template']
            }
        
        validation_result = {
            'valid': True,
            'config_path': str(config_file),
            'issues': [],
            'warnings': [],
            'recommendations': [],
            'server_count': 0,
            'healthy_servers': 0
        }
        
        try:
            # Load and parse config
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f) or {}
            
            # Check basic structure
            if 'servers' not in config_data:
                validation_result['issues'].append('Missing "servers" section')
                validation_result['valid'] = False
            
            servers = config_data.get('servers', {})
            validation_result['server_count'] = len(servers)
            
            if not servers:
                validation_result['warnings'].append('No servers configured')
                validation_result['recommendations'].append('Add servers with: chunkhound config add')
            
            # Validate each server
            for name, server_data in servers.items():
                required_fields = ['type', 'base_url']
                missing_fields = [field for field in required_fields if not server_data.get(field)]
                
                if missing_fields:
                    validation_result['issues'].append(f'Server "{name}" missing required fields: {missing_fields}')
                    validation_result['valid'] = False
                
                # Check server type
                valid_types = ['openai', 'openai-compatible', 'tei']
                if server_data.get('type') not in valid_types:
                    validation_result['issues'].append(f'Server "{name}" has invalid type: {server_data.get("type")}')
                    validation_result['valid'] = False
                
                # Check URL format
                base_url = server_data.get('base_url', '')
                if base_url and not base_url.startswith(('http://', 'https://')):
                    validation_result['issues'].append(f'Server "{name}" has invalid URL format: {base_url}')
                    validation_result['valid'] = False
            
            # Check default server
            default_server = config_data.get('default_server')
            if default_server and default_server not in servers:
                validation_result['issues'].append(f'Default server "{default_server}" not found in servers')
                validation_result['valid'] = False
            elif not default_server and servers:
                validation_result['warnings'].append('No default server specified')
                validation_result['recommendations'].append('Set default server with: chunkhound config set-default <name>')
        
        except yaml.YAMLError as e:
            validation_result['valid'] = False
            validation_result['issues'].append(f'YAML parsing error: {e}')
        except Exception as e:
            validation_result['valid'] = False
            validation_result['issues'].append(f'Config validation error: {e}')
        
        return validation_result
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.registry = ServerRegistry()
        self._config_data: Dict[str, Any] = {}
        self._config_file: Optional[str] = None
    
    def find_config_file(self) -> Optional[Path]:
        """Find the configuration file to use."""
        if self.config_path:
            path = Path(self.config_path).expanduser()
            if path.exists():
                return path
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        # Search default locations
        for config_path in self.DEFAULT_CONFIG_PATHS:
            path = Path(config_path).expanduser()
            if path.exists():
                return path
        
        return None
    
    def load_config(self, config_path: Optional[str] = None) -> None:
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to config file (uses default search if None)
        """
        if config_path:
            self.config_path = config_path
        
        config_file = self.find_config_file()
        if not config_file:
            logger.info("No configuration file found, using defaults")
            return
        
        self._config_file = str(config_file)
        
        try:
            with open(config_file, 'r') as f:
                self._config_data = yaml.safe_load(f) or {}
            
            logger.info(f"Loaded configuration from: {config_file}")
            self._parse_config()
            
        except Exception as e:
            logger.error(f"Failed to load config from {config_file}: {e}")
            raise
    
    def _parse_config(self) -> None:
        """Parse configuration data and register servers."""
        # Clear existing servers
        for name in list(self.registry.list_servers()):
            self.registry.unregister_server(name)
        
        # Parse servers section
        servers = self._config_data.get('servers', {})
        default_server = self._config_data.get('default_server')
        
        for name, server_data in servers.items():
            try:
                config = ServerConfig(
                    name=name,
                    type=server_data['type'],
                    base_url=server_data['base_url'],
                    model=server_data.get('model', ''),
                    api_key=server_data.get('api_key'),
                    enabled=server_data.get('enabled', True),
                    health_check_interval=server_data.get('health_check_interval', 300),
                    timeout=server_data.get('timeout', 30),
                    batch_size=server_data.get('batch_size'),
                    max_retries=server_data.get('max_retries', 3),
                    metadata=server_data.get('metadata', {})
                )
                
                is_default = (name == default_server) or (default_server is None)
                self.registry.register_server(config, set_default=is_default)
                
            except Exception as e:
                logger.error(f"Failed to register server {name}: {e}")
    
    def save_config(self, config_path: Optional[str] = None) -> None:
        """Save current configuration to YAML file.
        
        Args:
            config_path: Path to save config (uses current path if None)
        """
        if config_path:
            self.config_path = config_path
        
        if not self.config_path:
            # Use the loaded config file path, or create default
            if self._config_file:
                self.config_path = self._config_file
            else:
                # Create default config directory
                config_dir = Path.home() / '.chunkhound'
                config_dir.mkdir(exist_ok=True)
                self.config_path = str(config_dir / 'config.yaml')
        
        # Build config data
        config_data = {
            'default_server': self.registry._default_server,
            'servers': {}
        }
        
        for name in self.registry.list_servers():
            server = self.registry.get_server(name)
            config_data['servers'][name] = {
                'type': server.type,
                'base_url': server.base_url,
                'model': server.model,
                'enabled': server.enabled,
                'health_check_interval': server.health_check_interval,
                'timeout': server.timeout,
                'max_retries': server.max_retries
            }
            
            if server.api_key:
                config_data['servers'][name]['api_key'] = server.api_key
            if server.batch_size:
                config_data['servers'][name]['batch_size'] = server.batch_size
            if server.metadata:
                config_data['servers'][name]['metadata'] = server.metadata
        
        # Save to file
        config_path = Path(self.config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
        
        logger.info(f"Saved configuration to: {config_path}")
    
    def add_server(
        self,
        name: str,
        server_type: str,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
        set_default: bool = False,
        **kwargs
    ) -> None:
        """Add a new server to the configuration.
        
        Args:
            name: Server name
            server_type: Server type ('openai', 'openai-compatible', 'tei')
            base_url: Server base URL
            model: Model name
            api_key: Optional API key
            set_default: Whether to set as default
            **kwargs: Additional server configuration
        """
        config = ServerConfig(
            name=name,
            type=server_type,
            base_url=base_url,
            model=model,
            api_key=api_key,
            **kwargs
        )
        
        self.registry.register_server(config, set_default=set_default)
    
    def remove_server(self, name: str) -> None:
        """Remove a server from the configuration.
        
        Args:
            name: Server name to remove
        """
        self.registry.unregister_server(name)
    
    async def start_monitoring(self) -> None:
        """Start health monitoring for all enabled servers."""
        await self.registry.start_health_monitoring()
    
    async def stop_monitoring(self) -> None:
        """Stop health monitoring for all servers."""
        await self.registry.stop_health_monitoring()


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """Get or create the global configuration manager.
    
    Args:
        config_path: Path to config file (for initialization only)
        
    Returns:
        Global ConfigManager instance
    """
    global _config_manager
    
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
        try:
            _config_manager.load_config()
        except Exception as e:
            logger.warning(f"Failed to load configuration: {e}")
    
    return _config_manager


def reset_config_manager() -> None:
    """Reset the global configuration manager (for testing)."""
    global _config_manager
    _config_manager = None