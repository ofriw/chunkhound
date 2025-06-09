"""Tests for configuration management system."""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
import aiohttp
from aiohttp import web

from chunkhound.config import (
    ConfigManager,
    ServerConfig,
    ServerHealth,
    ServerRegistry,
    get_config_manager,
    reset_config_manager,
)


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_config():
    """Sample configuration data."""
    return {
        'default_server': 'local-tei',
        'servers': {
            'local-tei': {
                'type': 'tei',
                'base_url': 'http://localhost:8080',
                'model': 'sentence-transformers/all-MiniLM-L6-v2',
                'enabled': True,
                'health_check_interval': 300,
                'timeout': 30,
                'max_retries': 3
            },
            'openai-compatible': {
                'type': 'openai-compatible',
                'base_url': 'http://localhost:8081',
                'model': 'text-embedding-ada-002',
                'api_key': 'test-key',
                'enabled': True,
                'batch_size': 100,
                'metadata': {'description': 'Local OpenAI-compatible server'}
            },
            'disabled-server': {
                'type': 'openai-compatible',
                'base_url': 'http://localhost:8082',
                'model': 'test-model',
                'enabled': False
            }
        }
    }


@pytest.fixture
def mock_http_server():
    """Mock HTTP server for health checks."""
    async def health_handler(request):
        return web.json_response({'status': 'healthy'})
    
    async def models_handler(request):
        return web.json_response({
            'data': [
                {'id': 'test-model', 'object': 'model'}
            ]
        })
    
    app = web.Application()
    app.router.add_get('/health', health_handler)
    app.router.add_get('/v1/models', models_handler)
    app.router.add_get('/', health_handler)  # fallback
    
    return app


class TestServerConfig:
    """Test ServerConfig dataclass."""
    
    def test_valid_config(self):
        """Test creating valid server config."""
        config = ServerConfig(
            name='test-server',
            type='openai-compatible',
            base_url='http://localhost:8080',
            model='test-model'
        )
        
        assert config.name == 'test-server'
        assert config.type == 'openai-compatible'
        assert config.base_url == 'http://localhost:8080'
        assert config.model == 'test-model'
        assert config.enabled is True
        assert config.health_check_interval == 300
        assert config.timeout == 30
        assert config.max_retries == 3
    
    def test_invalid_server_type(self):
        """Test invalid server type raises error."""
        with pytest.raises(ValueError, match="Invalid server type"):
            ServerConfig(
                name='test',
                type='invalid-type',
                base_url='http://localhost:8080',
                model='test-model'
            )
    
    def test_missing_base_url(self):
        """Test missing base_url raises error."""
        with pytest.raises(ValueError, match="base_url is required"):
            ServerConfig(
                name='test',
                type='openai-compatible',
                base_url='',
                model='test-model'
            )
    
    def test_missing_model_for_non_tei(self):
        """Test missing model for non-TEI server raises error."""
        with pytest.raises(ValueError, match="model is required"):
            ServerConfig(
                name='test',
                type='openai-compatible',
                base_url='http://localhost:8080',
                model=''
            )
    
    def test_tei_without_model_allowed(self):
        """Test TEI server without model is allowed."""
        config = ServerConfig(
            name='test',
            type='tei',
            base_url='http://localhost:8080',
            model=''
        )
        assert config.model == ''


class TestServerRegistry:
    """Test ServerRegistry class."""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh server registry."""
        return ServerRegistry()
    
    @pytest.fixture
    def sample_server_config(self):
        """Sample server configuration."""
        return ServerConfig(
            name='test-server',
            type='openai-compatible',
            base_url='http://localhost:8080',
            model='test-model'
        )
    
    def test_register_server(self, registry, sample_server_config):
        """Test registering a server."""
        registry.register_server(sample_server_config)
        
        assert 'test-server' in registry.list_servers()
        assert registry._default_server == 'test-server'
        assert 'test-server' in registry._health_status
    
    def test_register_multiple_servers(self, registry):
        """Test registering multiple servers."""
        config1 = ServerConfig(
            name='server1',
            type='tei',
            base_url='http://localhost:8080',
            model='model1'
        )
        config2 = ServerConfig(
            name='server2',
            type='openai-compatible',
            base_url='http://localhost:8081',
            model='model2'
        )
        
        registry.register_server(config1)
        registry.register_server(config2, set_default=True)
        
        assert len(registry.list_servers()) == 2
        assert registry._default_server == 'server2'
    
    def test_unregister_server(self, registry, sample_server_config):
        """Test unregistering a server."""
        registry.register_server(sample_server_config)
        assert 'test-server' in registry.list_servers()
        
        registry.unregister_server('test-server')
        assert 'test-server' not in registry.list_servers()
        assert registry._default_server is None
    
    def test_unregister_nonexistent_server(self, registry):
        """Test unregistering nonexistent server raises error."""
        with pytest.raises(ValueError, match="Server not found"):
            registry.unregister_server('nonexistent')
    
    def test_get_server(self, registry, sample_server_config):
        """Test getting server by name."""
        registry.register_server(sample_server_config)
        
        # Get by name
        server = registry.get_server('test-server')
        assert server.name == 'test-server'
        
        # Get default
        server = registry.get_server()
        assert server.name == 'test-server'
    
    def test_get_nonexistent_server(self, registry):
        """Test getting nonexistent server raises error."""
        with pytest.raises(ValueError, match="Server not found"):
            registry.get_server('nonexistent')
    
    def test_get_server_no_default(self, registry):
        """Test getting server with no default raises error."""
        with pytest.raises(ValueError, match="No default server set"):
            registry.get_server()
    
    def test_get_healthy_servers(self, registry, sample_server_config):
        """Test getting healthy servers."""
        registry.register_server(sample_server_config)
        
        # No healthy servers initially
        assert registry.get_healthy_servers() == []
        
        # Mark as healthy
        registry._health_status['test-server'].is_healthy = True
        assert registry.get_healthy_servers() == ['test-server']
        
        # Disable server
        registry._servers['test-server'].enabled = False
        assert registry.get_healthy_servers() == []


class TestServerHealth:
    """Test server health checking."""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh server registry."""
        return ServerRegistry()
    
    async def test_check_server_health_success(self, registry, mock_http_server):
        """Test successful health check."""
        # Start mock server
        runner = web.AppRunner(mock_http_server)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 8080)
        await site.start()
        
        try:
            config = ServerConfig(
                name='test-server',
                type='tei',
                base_url='http://localhost:8080',
                model='test-model',
                timeout=5
            )
            registry.register_server(config)
            
            health = await registry.check_server_health('test-server')
            
            assert health.is_healthy is True
            assert health.response_time_ms > 0
            assert health.error_message is None
            assert health.last_check > 0
            
        finally:
            await runner.cleanup()
    
    async def test_check_server_health_failure(self, registry):
        """Test failed health check."""
        config = ServerConfig(
            name='test-server',
            type='tei',
            base_url='http://localhost:9999',  # Non-existent server
            model='test-model',
            timeout=1
        )
        registry.register_server(config)
        
        health = await registry.check_server_health('test-server')
        
        assert health.is_healthy is False
        assert health.response_time_ms > 0
        assert health.error_message is not None
        assert health.last_check > 0
    
    async def test_health_monitoring_loop(self, registry):
        """Test health monitoring loop."""
        config = ServerConfig(
            name='test-server',
            type='tei',
            base_url='http://localhost:9999',
            model='test-model',
            health_check_interval=1,  # Check every second
            timeout=1
        )
        registry.register_server(config)
        
        # Start monitoring
        await registry.start_health_monitoring('test-server')
        assert 'test-server' in registry._health_check_tasks
        
        # Wait for at least one health check
        await asyncio.sleep(1.5)
        
        # Stop monitoring
        await registry.stop_health_monitoring('test-server')
        assert 'test-server' not in registry._health_check_tasks
        
        # Check that health status was updated
        health = registry.get_health_status('test-server')
        assert health.last_check > 0
    
    def test_get_health_status(self, registry):
        """Test getting health status."""
        config = ServerConfig(
            name='test-server',
            type='tei',
            base_url='http://localhost:8080',
            model='test-model'
        )
        registry.register_server(config)
        
        # Get single server status
        health = registry.get_health_status('test-server')
        assert isinstance(health, ServerHealth)
        assert health.is_healthy is False  # Initial state
        
        # Get all statuses
        all_health = registry.get_health_status()
        assert isinstance(all_health, dict)
        assert 'test-server' in all_health


class TestConfigManager:
    """Test ConfigManager class."""
    
    @pytest.fixture
    def config_manager(self, temp_config_dir, monkeypatch):
        """Create a config manager with temporary directory."""
        reset_config_manager()  # Reset global state
        # Patch DEFAULT_CONFIG_PATHS to only look in temp directory
        monkeypatch.setattr(ConfigManager, 'DEFAULT_CONFIG_PATHS', [str(temp_config_dir / "config.yaml")])
        return ConfigManager()
    
    def test_find_config_file_explicit_path(self, temp_config_dir, config_manager):
        """Test finding config file with explicit path."""
        config_file = temp_config_dir / 'test-config.yaml'
        config_file.write_text('test: value')
        
        config_manager.config_path = str(config_file)
        found = config_manager.find_config_file()
        
        assert found == config_file
    
    def test_find_config_file_not_found(self, config_manager):
        """Test config file not found."""
        config_manager.config_path = '/nonexistent/config.yaml'
        
        with pytest.raises(FileNotFoundError):
            config_manager.find_config_file()
    
    def test_find_config_file_default_locations(self, temp_config_dir, config_manager):
        """Test finding config file in default locations."""
        # Mock the default paths to include our temp directory
        config_file = temp_config_dir / 'config.yaml'
        config_file.write_text('test: value')
        
        with patch.object(ConfigManager, 'DEFAULT_CONFIG_PATHS', [str(config_file)]):
            found = config_manager.find_config_file()
            assert found == config_file
    
    def test_load_config(self, temp_config_dir, config_manager, sample_config):
        """Test loading configuration from file."""
        config_file = temp_config_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(sample_config, f)
        
        config_manager.config_path = str(config_file)
        config_manager.load_config()
        
        # Check that servers were registered
        servers = config_manager.registry.list_servers()
        assert 'local-tei' in servers
        assert 'openai-compatible' in servers
        assert 'disabled-server' in servers
        
        # Check default server
        assert config_manager.registry._default_server == 'local-tei'
    
    def test_load_config_no_file(self, config_manager):
        """Test loading config when no file exists."""
        # Should not raise an error
        config_manager.load_config()
        assert len(config_manager.registry.list_servers()) == 0
    
    def test_save_config(self, temp_config_dir, config_manager):
        """Test saving configuration to file."""
        # Add some servers
        config_manager.add_server(
            name='test-server',
            server_type='tei',
            base_url='http://localhost:8080',
            model='test-model',
            set_default=True
        )
        
        config_file = temp_config_dir / 'config.yaml'
        config_manager.save_config(str(config_file))
        
        # Check file was created and contains expected data
        assert config_file.exists()
        
        with open(config_file, 'r') as f:
            saved_config = yaml.safe_load(f)
        
        assert saved_config['default_server'] == 'test-server'
        assert 'test-server' in saved_config['servers']
        assert saved_config['servers']['test-server']['type'] == 'tei'
    
    def test_add_server(self, config_manager):
        """Test adding a server."""
        config_manager.add_server(
            name='test-server',
            server_type='openai-compatible',
            base_url='http://localhost:8080',
            model='test-model',
            api_key='test-key',
            set_default=True
        )
        
        assert 'test-server' in config_manager.registry.list_servers()
        server = config_manager.registry.get_server('test-server')
        assert server.type == 'openai-compatible'
        assert server.api_key == 'test-key'
    
    def test_remove_server(self, config_manager):
        """Test removing a server."""
        config_manager.add_server(
            name='test-server',
            server_type='tei',
            base_url='http://localhost:8080',
            model='test-model'
        )
        
        assert 'test-server' in config_manager.registry.list_servers()
        
        config_manager.remove_server('test-server')
        assert 'test-server' not in config_manager.registry.list_servers()
    
    async def test_start_stop_monitoring(self, config_manager):
        """Test starting and stopping health monitoring."""
        config_manager.add_server(
            name='test-server',
            server_type='tei',
            base_url='http://localhost:8080',
            model='test-model'
        )
        
        # Start monitoring
        await config_manager.start_monitoring()
        assert len(config_manager.registry._health_check_tasks) > 0
        
        # Stop monitoring
        await config_manager.stop_monitoring()
        assert len(config_manager.registry._health_check_tasks) == 0


class TestConfigIntegration:
    """Integration tests for configuration system."""
    
    @pytest.fixture(autouse=True)
    def patch_default_config_paths(self, temp_config_dir, monkeypatch):
        """Patch DEFAULT_CONFIG_PATHS to use temp directory for test isolation."""
        monkeypatch.setattr(ConfigManager, 'DEFAULT_CONFIG_PATHS', [str(temp_config_dir / "config.yaml")])
    
    async def test_full_config_workflow(self, temp_config_dir, sample_config):
        """Test complete configuration workflow."""
        reset_config_manager()
        
        # Create config file
        config_file = temp_config_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(sample_config, f)
        
        # Get config manager and load config
        config_manager = get_config_manager(str(config_file))
        
        # Check servers were loaded
        servers = config_manager.registry.list_servers()
        assert len(servers) == 3
        assert 'local-tei' in servers
        
        # Get a provider (mocked)
        with patch('chunkhound.config.create_tei_provider') as mock_create:
            mock_provider = MagicMock()
            mock_create.return_value = mock_provider
            
            provider = await config_manager.registry.get_provider('local-tei')
            assert provider == mock_provider
    
    def test_global_config_manager(self, temp_config_dir, sample_config):
        """Test global config manager singleton behavior."""
        reset_config_manager()
        
        # Create config file
        config_file = temp_config_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(sample_config, f)
        
        # First call should create and load config
        manager1 = get_config_manager(str(config_file))
        assert len(manager1.registry.list_servers()) == 3
        
        # Second call should return same instance
        manager2 = get_config_manager()
        assert manager1 is manager2
        
        # Reset should clear the global instance
        reset_config_manager()
        # Remove the config file to test behavior when no config exists
        config_file.unlink()
        manager3 = get_config_manager()
        assert manager3 is not manager1
        assert len(manager3.registry.list_servers()) == 0  # No config loaded


class TestConfigErrorHandling:
    """Test error handling in configuration system."""
    
    def test_invalid_yaml_syntax(self, temp_config_dir):
        """Test handling of invalid YAML syntax."""
        reset_config_manager()
        
        config_file = temp_config_dir / 'config.yaml'
        config_file.write_text('invalid: yaml: [unclosed')
        
        config_manager = ConfigManager(str(config_file))
        
        with pytest.raises(yaml.YAMLError):
            config_manager.load_config()
    
    def test_invalid_server_config(self, temp_config_dir):
        """Test handling of invalid server configuration."""
        reset_config_manager()
        
        invalid_config = {
            'servers': {
                'invalid-server': {
                    'type': 'invalid-type',  # Invalid type
                    'base_url': 'http://localhost:8080'
                }
            }
        }
        
        config_file = temp_config_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(invalid_config, f)
        
        config_manager = ConfigManager(str(config_file))
        config_manager.load_config()  # Should not raise, but log error
        
        # Server should not be registered
        assert len(config_manager.registry.list_servers()) == 0
    
    def test_missing_required_fields(self, temp_config_dir):
        """Test handling of missing required fields."""
        reset_config_manager()
        
        invalid_config = {
            'servers': {
                'incomplete-server': {
                    'type': 'openai-compatible',
                    # Missing base_url and model
                }
            }
        }
        
        config_file = temp_config_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(invalid_config, f)
        
        config_manager = ConfigManager(str(config_file))
        config_manager.load_config()  # Should not raise, but log error
        
        # Server should not be registered
        assert len(config_manager.registry.list_servers()) == 0


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    @pytest.fixture(autouse=True)
    def patch_default_config_paths(self, temp_config_dir, monkeypatch):
        """Patch DEFAULT_CONFIG_PATHS to use temp directory for test isolation."""
        monkeypatch.setattr(ConfigManager, 'DEFAULT_CONFIG_PATHS', [str(temp_config_dir / "config.yaml")])
    
    def test_multiple_tei_servers(self, temp_config_dir):
        """Test configuration with multiple TEI servers."""
        reset_config_manager()
        
        config = {
            'default_server': 'tei-small',
            'servers': {
                'tei-small': {
                    'type': 'tei',
                    'base_url': 'http://localhost:8080',
                    'model': 'sentence-transformers/all-MiniLM-L6-v2',
                    'batch_size': 32
                },
                'tei-large': {
                    'type': 'tei',
                    'base_url': 'http://localhost:8081',
                    'model': 'sentence-transformers/all-mpnet-base-v2',
                    'batch_size': 16
                }
            }
        }
        
        config_file = temp_config_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        
        config_manager = get_config_manager(str(config_file))
        
        assert len(config_manager.registry.list_servers()) == 2
        assert config_manager.registry._default_server == 'tei-small'
        
        small_server = config_manager.registry.get_server('tei-small')
        assert small_server.batch_size == 32
        
        large_server = config_manager.registry.get_server('tei-large')
        assert large_server.batch_size == 16
    
    def test_mixed_server_types(self, temp_config_dir):
        """Test configuration with mixed server types."""
        reset_config_manager()
        
        config = {
            'default_server': 'local-tei',
            'servers': {
                'local-tei': {
                    'type': 'tei',
                    'base_url': 'http://localhost:8080',
                    'model': 'sentence-transformers/all-MiniLM-L6-v2'
                },
                'openai-prod': {
                    'type': 'openai',
                    'base_url': 'https://api.openai.com/v1',
                    'model': 'text-embedding-3-small',
                    'api_key': '${OPENAI_API_KEY}'  # Environment variable reference
                },
                'local-ollama': {
                    'type': 'openai-compatible',
                    'base_url': 'http://localhost:11434/v1',
                    'model': 'nomic-embed-text',
                    'enabled': False  # Disabled by default
                }
            }
        }
        
        config_file = temp_config_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        
        config_manager = get_config_manager(str(config_file))
        
        assert len(config_manager.registry.list_servers()) == 3
        
        # Check server types
        tei_server = config_manager.registry.get_server('local-tei')
        assert tei_server.type == 'tei'
        
        openai_server = config_manager.registry.get_server('openai-prod')
        assert openai_server.type == 'openai'
        
        ollama_server = config_manager.registry.get_server('local-ollama')
        assert ollama_server.type == 'openai-compatible'
        assert ollama_server.enabled is False
    
    async def test_dynamic_server_management(self, temp_config_dir):
        """Test dynamic addition and removal of servers."""
        reset_config_manager()
        
        config_manager = get_config_manager()
        
        # Start with no servers
        assert len(config_manager.registry.list_servers()) == 0
        
        # Add servers dynamically
        config_manager.add_server(
            name='dynamic-1',
            server_type='tei',
            base_url='http://localhost:8080',
            model='test-model-1',
            set_default=True
        )
        
        config_manager.add_server(
            name='dynamic-2',
            server_type='openai-compatible',
            base_url='http://localhost:8081',
            model='test-model-2'
        )
        
        assert len(config_manager.registry.list_servers()) == 2
        assert config_manager.registry._default_server == 'dynamic-1'
        
        # Save configuration
        config_file = temp_config_dir / 'dynamic-config.yaml'
        config_manager.save_config(str(config_file))
        
        # Load in new manager to verify persistence
        new_manager = ConfigManager(str(config_file))
        new_manager.load_config()
        
        assert len(new_manager.registry.list_servers()) == 2
        assert new_manager.registry._default_server == 'dynamic-1'
        
        # Remove a server
        new_manager.remove_server('dynamic-2')
        assert len(new_manager.registry.list_servers()) == 1
        
        # Save again
        new_manager.save_config()
        
        # Verify removal persisted
        final_manager = ConfigManager(str(config_file))
        final_manager.load_config()
        assert len(final_manager.registry.list_servers()) == 1
        assert 'dynamic-1' in final_manager.registry.list_servers()
        assert 'dynamic-2' not in final_manager.registry.list_servers()