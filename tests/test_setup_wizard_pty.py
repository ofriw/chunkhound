#!/usr/bin/env python3
"""
PTY-based testing for the setup wizard with comprehensive validation.

This module tests the actual setup wizard using pseudo-terminals (PTY) to ensure
reliable cross-platform testing of terminal UI, keyboard handling, and cursor
movement without mocks. It validates all generated configuration files and IDE
setup files to ensure they are correct and usable.
"""

import sys
import os
import json
import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

# Cross-platform PTY support
if sys.platform == "win32":
    try:
        import wexpect as pexpect_module
    except ImportError:
        pytest.skip("wexpect not available on Windows", allow_module_level=True)
else:
    try:
        import pexpect as pexpect_module
    except ImportError:
        pytest.skip("pexpect not available", allow_module_level=True)


class SetupWizardPTYTest:
    """Base class for PTY-based setup wizard testing with validation."""
    
    def spawn_wizard(self, cwd: str, env: Optional[Dict[str, str]] = None) -> Any:
        """Spawn the wizard in a PTY with proper terminal settings."""
        if env is None:
            env = os.environ.copy()
        
        # Force consistent terminal settings
        env['TERM'] = 'xterm-256color'
        env['COLUMNS'] = '80'
        env['LINES'] = '24'
        env['PYTHONIOENCODING'] = 'utf-8'
        env['NO_COLOR'] = '0'  # Enable colors for Rich testing
        
        # Ensure we're testing the wizard, not using existing config
        env.pop('CHUNKHOUND_CONFIG_PATH', None)
        
        # Make sure we trigger the wizard by ensuring no valid config exists
        # and no conflicting database locks
        env['CHUNKHOUND_DATABASE__PATH'] = str(Path(cwd) / '.chunkhound' / 'test.db')
        
        if sys.platform == "win32":
            wizard = pexpect_module.spawn(
                'uv run chunkhound index .',
                cwd=cwd,
                env=env,
                timeout=15
            )
        else:
            wizard = pexpect_module.spawn(
                'uv run chunkhound index .',
                cwd=cwd,
                env=env,
                dimensions=(24, 80),
                encoding='utf-8',
                timeout=15
            )
        
        return wizard
    
    def send_arrow_key(self, wizard: Any, direction: str) -> None:
        """Send arrow key with proper escape sequences."""
        arrows = {
            'up': '\x1b[A',
            'down': '\x1b[B', 
            'right': '\x1b[C',
            'left': '\x1b[D'
        }
        wizard.send(arrows[direction])
    
    def send_special_key(self, wizard: Any, key: str) -> None:
        """Send special keys like Enter, Escape, Backspace."""
        keys = {
            'enter': '\r',
            'escape': '\x1b',
            'backspace': '\x7f',
            'delete': '\x1b[3~',
            'home': '\x1b[H',
            'end': '\x1b[F',
            'ctrl-c': '\x03',
            'ctrl-d': '\x04'
        }
        wizard.send(keys[key])
    
    def validate_chunkhound_config(self, config_path: Path) -> Dict[str, Any]:
        """Validate that .chunkhound.json is correct and usable."""
        # Check file exists
        assert config_path.exists(), f"Config file not found at {config_path}"
        
        # Load and parse JSON
        try:
            config = json.loads(config_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in config file: {e}")
        
        # Validate required structure
        assert "embedding" in config, "Missing 'embedding' section"
        assert "provider" in config["embedding"], "Missing embedding provider"
        
        # Validate provider-specific fields
        provider = config["embedding"]["provider"]
        
        if provider == "openai":
            assert "model" in config["embedding"], "OpenAI config missing model"
            assert config["embedding"]["model"] in [
                "text-embedding-3-small",
                "text-embedding-3-large", 
                "text-embedding-ada-002"
            ], f"Invalid OpenAI model: {config['embedding']['model']}"
            
            # API key should NOT be in config (should be in env)
            assert "api_key" not in config["embedding"], \
                "API key should not be stored in config file"
        
        elif provider == "voyageai":
            assert "model" in config["embedding"], "VoyageAI config missing model"
            expected_models = [
                "voyage-2", "voyage-large-2", "voyage-3", "voyage-large-2-instruct"
            ]
            assert config["embedding"]["model"] in expected_models, \
                f"Invalid VoyageAI model: {config['embedding']['model']}"
            
            # API key should NOT be in config
            assert "api_key" not in config["embedding"], \
                "API key should not be stored in config file"
        
        elif provider == "ollama":
            assert "base_url" in config["embedding"], "Ollama config missing base_url"
            assert "model" in config["embedding"], "Ollama config missing model"
            
            # Validate URL format
            url = config["embedding"]["base_url"]
            assert url.startswith("http://") or url.startswith("https://"), \
                f"Invalid URL format: {url}"
        
        elif provider == "openai-compatible":
            assert "base_url" in config["embedding"], "Missing base_url"
            assert "model" in config["embedding"], "Missing model"
            if "api_key" in config["embedding"]:
                assert config["embedding"]["api_key"] != "", "Empty API key"
        
        # Test that config can actually be loaded by ChunkHound
        try:
            # Add the parent directory to path to import chunkhound
            sys.path.insert(0, str(Path(__file__).parent.parent))
            
            # Clear any environment variables that might interfere
            original_env = {}
            for key in list(os.environ.keys()):
                if 'RERANK' in key.upper() or 'CHUNKHOUND' in key.upper():
                    original_env[key] = os.environ[key]
                    del os.environ[key]
            
            try:
                from chunkhound.core.config.config import Config
                
                # This will validate the config structure
                test_config = Config(**config)
                assert test_config.embedding.provider == provider
                
            finally:
                # Restore environment variables
                for key, value in original_env.items():
                    os.environ[key] = value
                    
        except Exception as e:
            pytest.fail(f"Config cannot be loaded by ChunkHound: {e}")
        
        return config
    
    def validate_mcp_config(self, mcp_path: Path) -> Dict[str, Any]:
        """Validate MCP integration files."""
        assert mcp_path.exists(), f"MCP config not found at {mcp_path}"
        
        try:
            mcp_config = json.loads(mcp_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in MCP config: {e}")
        
        # Validate MCP structure
        assert "mcpServers" in mcp_config, "Missing 'mcpServers' section"
        assert "chunkhound" in mcp_config["mcpServers"], \
            "ChunkHound not configured in MCP servers"
        
        server_config = mcp_config["mcpServers"]["chunkhound"]
        
        # Validate command
        assert "command" in server_config, "Missing command in MCP config"
        assert "uv" in server_config["command"], \
            "MCP command should use 'uv'"
        
        # Validate args
        assert "args" in server_config, "Missing args in MCP config"
        args = server_config["args"]
        assert "run" in args, "Missing 'run' in args"
        assert "chunkhound" in args, "Missing 'chunkhound' in args"
        assert "mcp" in args, "Missing 'mcp' in args"
        
        # Check for directory argument
        has_dir = any(Path(arg).exists() or arg == "." for arg in args 
                      if not arg.startswith("-"))
        assert has_dir, "MCP config missing directory argument"
        
        return mcp_config
    
    def validate_vscode_config(self, vscode_path: Path) -> Dict[str, Any]:
        """Validate VS Code MCP configuration."""
        assert vscode_path.exists(), f"VS Code config not found at {vscode_path}"
        
        try:
            vscode_config = json.loads(vscode_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in VS Code config: {e}")
        
        # Should have same structure as regular MCP config
        assert "mcpServers" in vscode_config
        assert "chunkhound" in vscode_config["mcpServers"]
        
        return vscode_config
    
    def validate_env_variables(self, work_dir: Path) -> None:
        """Validate environment variable handling."""
        env_file = work_dir / ".env"
        
        if env_file.exists():
            env_content = env_file.read_text(encoding='utf-8')
            
            # Check for API keys format
            if "OPENAI_API_KEY=" in env_content:
                # OpenAI keys should start with sk- and be reasonably long
                key_line = [line for line in env_content.split('\n') 
                           if line.startswith('OPENAI_API_KEY=')]
                if key_line:
                    key_value = key_line[0].split('=', 1)[1]
                    assert key_value.startswith('sk-'), "Invalid OpenAI key format"
                    assert len(key_value) > 10, "OpenAI key too short"
            
            if "VOYAGE_API_KEY=" in env_content:
                key_line = [line for line in env_content.split('\n') 
                           if line.startswith('VOYAGE_API_KEY=')]
                if key_line:
                    key_value = key_line[0].split('=', 1)[1]
                    assert len(key_value) > 10, "VoyageAI key too short"
        
        # Also check if keys are in environment for providers that need them
        chunkhound_json = work_dir / ".chunkhound.json"
        if chunkhound_json.exists():
            config = json.loads(chunkhound_json.read_text(encoding='utf-8'))
            provider = config["embedding"]["provider"]
            
            # These providers need API keys
            if provider in ["openai", "voyageai"]:
                # Key should be either in .env or environment
                if not env_file.exists():
                    if provider == "openai":
                        assert os.getenv("OPENAI_API_KEY"), \
                            "OpenAI API key not found in .env or environment"
                    elif provider == "voyageai":
                        assert os.getenv("VOYAGE_API_KEY"), \
                            "VoyageAI API key not found in .env or environment"
    
    def verify_config_works(self, work_dir: Path) -> None:
        """Verify the generated config actually works with ChunkHound."""
        import subprocess
        
        # Try to run chunkhound with the config to check basic loading
        result = subprocess.run(
            ["uv", "run", "chunkhound", "--help"],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=15
        )
        
        assert result.returncode == 0, \
            f"ChunkHound failed to run with generated config: {result.stderr}"
        
        # Try to load the config programmatically
        original_cwd = os.getcwd()
        try:
            os.chdir(str(work_dir))
            
            # Add the parent directory to path to import chunkhound
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from chunkhound.core.config.config import Config
            
            config = Config.from_file(str(work_dir / ".chunkhound.json"))
            
            # Verify basic config structure
            assert config.embedding.provider in ["openai", "voyageai", "ollama", "openai-compatible"]
            assert config.embedding.model is not None
            
        except Exception as e:
            pytest.fail(f"Failed to use generated config: {e}")
        finally:
            os.chdir(original_cwd)


@pytest.fixture
def temp_work_dir():
    """Create a temporary working directory for wizard tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        work_dir = Path(tmp_dir) / "wizard_test"
        work_dir.mkdir()
        yield work_dir


class TestWizardWithValidation(SetupWizardPTYTest):
    """Test wizard flows with comprehensive output validation."""
    
    def test_openai_complete_with_claude_code(self, temp_work_dir):
        """Test OpenAI + Claude Code setup with full validation."""
        wizard = self.spawn_wizard(str(temp_work_dir))
        
        try:
            # Complete the wizard flow - look for provider list instead of specific text
            wizard.expect("OpenAI", timeout=10)  # Wait for provider options to appear
            wizard.sendline("1")  # OpenAI
            
            wizard.expect("API key", timeout=5)
            test_key = "sk-proj-test-valid-key-format-123456"
            wizard.sendline(test_key)
            
            wizard.expect("model", timeout=5)
            wizard.sendline("")  # Default (text-embedding-3-small)
            
            wizard.expect("Reranking", timeout=5)
            wizard.sendline("n")  # No reranking
            
            wizard.expect("AI agent", timeout=5)  
            wizard.sendline("1")  # Claude Code
            
            wizard.expect("save", timeout=5)
            wizard.sendline("y")
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # VALIDATION PHASE
        
        # 1. Validate .chunkhound.json
        config = self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
        assert config["embedding"]["provider"] == "openai"
        assert config["embedding"]["model"] == "text-embedding-3-small"
        
        # 2. Validate MCP config for Claude Code
        mcp_config = self.validate_mcp_config(temp_work_dir / ".mcp.json")
        
        # 3. Check environment setup
        self.validate_env_variables(temp_work_dir)
        
        # 4. Test that ChunkHound can actually use this config
        self.verify_config_works(temp_work_dir)
    
    def test_voyage_complete_with_vscode(self, temp_work_dir):
        """Test VoyageAI + VS Code setup with full validation."""
        wizard = self.spawn_wizard(str(temp_work_dir))
        
        try:
            wizard.expect("OpenAI", timeout=10)  # Wait for provider options
            wizard.sendline("2")  # VoyageAI
            
            wizard.expect("API key", timeout=5)
            test_key = "voyage-test-key-abc123"
            wizard.sendline(test_key)
            
            wizard.expect("model", timeout=5)
            wizard.sendline("voyage-2")
            
            wizard.expect("Reranking", timeout=5)
            wizard.sendline("n")
            
            wizard.expect("AI agent", timeout=5)
            wizard.sendline("2")  # VS Code
            
            wizard.expect("save", timeout=5)
            wizard.sendline("y")
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # VALIDATION
        
        # 1. Validate .chunkhound.json
        config = self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
        assert config["embedding"]["provider"] == "voyageai"
        assert config["embedding"]["model"] == "voyage-2"
        
        # 2. Validate VS Code MCP config
        vscode_config_path = temp_work_dir / ".vscode" / "mcp.json"
        vscode_config = self.validate_vscode_config(vscode_config_path)
        
        # 3. Verify directory structure
        assert (temp_work_dir / ".vscode").is_dir()
        
        # 4. Check API key handling
        self.validate_env_variables(temp_work_dir)
        
        # 5. Verify config works
        self.verify_config_works(temp_work_dir)
    
    def test_ollama_local_setup(self, temp_work_dir):
        """Test Ollama local setup with validation."""
        wizard = self.spawn_wizard(str(temp_work_dir))
        
        try:
            wizard.expect("OpenAI", timeout=10)  # Wait for provider options
            wizard.sendline("3")  # Ollama
            
            # Wizard might auto-detect Ollama or ask for confirmation
            index = wizard.expect(["URL", "Yes", "Ollama at"], timeout=5)
            if index == 0:  # Asked for URL
                wizard.sendline("http://localhost:11434")
            elif index in [1, 2]:  # Auto-detected, asking for confirmation
                wizard.sendline("y")  # Confirm
            
            wizard.expect("model", timeout=5)
            wizard.sendline("nomic-embed-text")
            
            # Look for either AI agent setup or save configuration
            index = wizard.expect(["AI agent", "Save configuration", "VS Code", "Skip"], timeout=5)
            
            if index in [0, 2, 3]:  # AI agent setup is showing
                wizard.sendline("3")  # Skip - Configure manually later
                wizard.expect("Save configuration", timeout=5)
                wizard.sendline("y")  # Save
            elif index == 1:  # Direct to save (no AI agent step)
                wizard.sendline("y")  # Save
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # VALIDATION
        
        config = self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
        assert config["embedding"]["provider"] == "ollama"
        assert config["embedding"]["base_url"] == "http://localhost:11434"
        assert config["embedding"]["model"] == "nomic-embed-text"
        
        # Verify config works
        self.verify_config_works(temp_work_dir)


class TestWizardNavigation(SetupWizardPTYTest):
    """Test keyboard navigation and cursor handling."""
    
    def test_menu_navigation_with_arrow_keys(self, temp_work_dir):
        """Test menu navigation using arrow keys."""
        wizard = self.spawn_wizard(str(temp_work_dir))
        
        try:
            wizard.expect("OpenAI", timeout=10)  # Wait for provider options
            
            # Navigate down twice to reach Ollama (assuming order: OpenAI, VoyageAI, Ollama)
            self.send_arrow_key(wizard, 'down')
            self.send_arrow_key(wizard, 'down')
            
            # Select with Enter
            self.send_special_key(wizard, 'enter')
            
            # Should be at Ollama configuration
            wizard.expect("URL", timeout=5)
            
        finally:
            wizard.close()
    
    def test_text_input_editing(self, temp_work_dir):
        """Test cursor movement and text editing in input fields."""
        wizard = self.spawn_wizard(str(temp_work_dir))
        
        try:
            wizard.expect("OpenAI", timeout=10)  # Wait for provider options
            wizard.sendline("1")  # OpenAI
            
            wizard.expect("API key", timeout=5)
            
            # Type initial text
            wizard.send("sk-test")
            
            # Move cursor left 4 positions
            for _ in range(4):
                self.send_arrow_key(wizard, 'left')
            
            # Insert text in the middle
            wizard.send("MIDDLE")
            
            # Move to end
            self.send_special_key(wizard, 'end')
            
            # Add more text
            wizard.send("-end")
            
            # Delete last character
            self.send_special_key(wizard, 'backspace')
            
            # Submit
            self.send_special_key(wizard, 'enter')
            
            # Should proceed to model selection if key format is valid
            # (The actual key doesn't need to be real for this test)
            wizard.expect("model", timeout=5)
            
        finally:
            wizard.close()


class TestWizardErrorHandling(SetupWizardPTYTest):
    """Test error scenarios and recovery with validation."""
    
    def test_invalid_api_key_retry(self, temp_work_dir):
        """Test handling of invalid API key with retry."""
        wizard = self.spawn_wizard(str(temp_work_dir))
        
        try:
            wizard.expect("OpenAI", timeout=10)  # Wait for provider options
            wizard.sendline("1")  # OpenAI
            
            wizard.expect("API key", timeout=5)
            
            # Enter invalid key (too short)
            wizard.sendline("bad")
            
            # Should show error
            wizard.expect("Invalid", timeout=5)
            
            # Retry with valid format
            valid_key = "sk-proj-retry-valid-key-test"
            wizard.sendline(valid_key)
            
            # Should proceed
            wizard.expect("model", timeout=5)
            wizard.sendline("")  # Default model
            
            wizard.expect("AI agent", timeout=5)
            wizard.sendline("0")  # Skip
            
            wizard.expect("save", timeout=5)
            wizard.sendline("y")
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # Validate the config is correct despite retry
        config = self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
        assert config["embedding"]["provider"] == "openai"
        
        # Verify the valid key was saved, not the invalid one
        env_file = temp_work_dir / ".env"
        if env_file.exists():
            env_content = env_file.read_text(encoding='utf-8')
            assert "bad" not in env_content
            assert valid_key in env_content
    
    def test_escape_cancellation_no_artifacts(self, temp_work_dir):
        """Test that canceling doesn't create partial configs."""
        wizard = self.spawn_wizard(str(temp_work_dir))
        
        try:
            wizard.expect("OpenAI", timeout=10)  # Wait for provider options
            wizard.sendline("1")
            
            wizard.expect("API key", timeout=5)
            wizard.sendline("sk-test-key")
            
            wizard.expect("model", timeout=5)
            
            # Cancel here with Escape
            self.send_special_key(wizard, 'escape')
            
            wizard.expect(pexpect_module.EOF, timeout=5)
            
        except Exception:
            # Even if wizard crashes, we still want to check no artifacts
            pass
        finally:
            wizard.close()
        
        # Verify NO config files were created
        assert not (temp_work_dir / ".chunkhound.json").exists(), \
            "Config should not exist after cancellation"
        assert not (temp_work_dir / ".mcp.json").exists(), \
            "MCP config should not exist after cancellation"
        assert not (temp_work_dir / ".vscode").exists(), \
            "VS Code dir should not exist after cancellation"
        assert not (temp_work_dir / ".env").exists(), \
            "Env file should not exist after cancellation"


if __name__ == "__main__":
    # Allow running directly for debugging
    pytest.main([__file__, "-v"])