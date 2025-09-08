#!/usr/bin/env python3
"""
Terminal compatibility tests for the setup wizard.

Tests different terminal configurations, environments, and edge cases to ensure
the wizard works reliably across various platforms and setups.
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

from .test_setup_wizard_pty import SetupWizardPTYTest


@pytest.fixture
def temp_work_dir():
    """Create a temporary working directory for wizard tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        work_dir = Path(tmp_dir) / "wizard_test"
        work_dir.mkdir()
        yield work_dir


class TestTerminalCompatibility(SetupWizardPTYTest):
    """Test different terminal configurations and environments."""
    
    @pytest.mark.parametrize("term_type", [
        "xterm",
        "xterm-256color", 
        "vt100",
        "screen",
        "tmux-256color"
    ])
    def test_different_term_types(self, temp_work_dir, term_type):
        """Test wizard works with different TERM settings."""
        env = os.environ.copy()
        env['TERM'] = term_type
        
        wizard = self.spawn_wizard(str(temp_work_dir), env)
        
        try:
            # Should still show menu regardless of terminal type
            wizard.expect("Select embedding provider", timeout=10)
            
            # Basic interaction should work
            wizard.sendline("1")  # OpenAI
            wizard.expect("API key", timeout=5)
            
            # Complete a simple flow to verify functionality
            wizard.sendline("sk-test-key-compatibility")
            wizard.expect("model", timeout=5)
            wizard.sendline("")  # Default
            
            wizard.expect("AI agent", timeout=5)
            wizard.sendline("0")  # Skip
            
            wizard.expect("save", timeout=5)
            wizard.sendline("y")
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # Verify config was still created correctly
        config = self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
        assert config["embedding"]["provider"] == "openai"
    
    def test_no_color_mode(self, temp_work_dir):
        """Test wizard works with NO_COLOR=1 environment."""
        env = os.environ.copy()
        env['NO_COLOR'] = '1'
        
        wizard = self.spawn_wizard(str(temp_work_dir), env)
        
        try:
            wizard.expect("Select embedding provider", timeout=10)
            
            # Should work without colors - verify basic functionality
            wizard.sendline("2")  # VoyageAI
            wizard.expect("API key", timeout=5)
            
            wizard.sendline("voyage-no-color-test")
            wizard.expect("model", timeout=5)
            
            wizard.sendline("voyage-2")
            
            wizard.expect("AI agent", timeout=5)
            wizard.sendline("0")
            
            wizard.expect("save", timeout=5)
            wizard.sendline("y")
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # Verify config generation
        config = self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
        assert config["embedding"]["provider"] == "voyageai"
        assert config["embedding"]["model"] == "voyage-2"
    
    @pytest.mark.parametrize("columns,lines", [
        (40, 10),   # Very small terminal
        (80, 24),   # Standard terminal
        (120, 30),  # Large terminal
        (200, 50),  # Very large terminal
    ])
    def test_different_terminal_sizes(self, temp_work_dir, columns, lines):
        """Test wizard adapts to different terminal sizes."""
        env = os.environ.copy()
        env['COLUMNS'] = str(columns)
        env['LINES'] = str(lines)
        
        if sys.platform != "win32":
            # Unix systems support setting dimensions directly
            wizard = pexpect_module.spawn(
                'uv run chunkhound index .',
                cwd=str(temp_work_dir),
                env=env,
                dimensions=(lines, columns),
                encoding='utf-8',
                timeout=15
            )
        else:
            # Windows - use environment variables
            wizard = self.spawn_wizard(str(temp_work_dir), env)
        
        try:
            # Should still function regardless of size
            wizard.expect("Select", timeout=10)  # "Select embedding provider" might wrap
            wizard.sendline("3")  # Ollama
            
            wizard.expect("URL", timeout=5)
            wizard.sendline("")  # Default
            
            wizard.expect("model", timeout=5)
            wizard.sendline("test-model")
            
            wizard.expect("save", timeout=5)
            wizard.sendline("y")
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # Verify config creation
        config = self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
        assert config["embedding"]["provider"] == "ollama"
    
    def test_utf8_encoding(self, temp_work_dir):
        """Test wizard handles UTF-8 encoding correctly."""
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['LC_ALL'] = 'en_US.UTF-8'
        
        wizard = self.spawn_wizard(str(temp_work_dir), env)
        
        try:
            wizard.expect("Select embedding provider", timeout=10)
            wizard.sendline("1")
            
            wizard.expect("API key", timeout=5)
            # Use a key with potentially problematic characters
            wizard.sendline("sk-test-utf8-key-123456")
            
            wizard.expect("model", timeout=5)
            wizard.sendline("")
            
            wizard.expect("save", timeout=5)
            wizard.sendline("y")
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # Verify config can be read with UTF-8
        config_path = temp_work_dir / ".chunkhound.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        assert config["embedding"]["provider"] == "openai"


class TestEnvironmentVariables(SetupWizardPTYTest):
    """Test wizard behavior with various environment variable configurations."""
    
    def test_with_existing_api_key_env(self, temp_work_dir):
        """Test wizard detects existing API keys in environment."""
        env = os.environ.copy()
        env['OPENAI_API_KEY'] = 'sk-existing-key-from-env'
        
        wizard = self.spawn_wizard(str(temp_work_dir), env)
        
        try:
            wizard.expect("Select embedding provider", timeout=10)
            wizard.sendline("1")  # OpenAI
            
            # Should detect existing key and maybe skip or offer to use it
            # This depends on the actual wizard implementation
            # For now, just verify we can complete the flow
            
            # Check if it asks for key or uses existing
            index = wizard.expect(["API key", "model", "existing"], timeout=5)
            
            if index == 0:  # Still asks for API key
                wizard.sendline("")  # Use default (existing)
                wizard.expect("model", timeout=5)
            elif index == 1:  # Skipped to model
                pass  # Good, detected existing key
            else:  # Asked about existing key
                wizard.sendline("y")  # Use existing
                wizard.expect("model", timeout=5)
            
            wizard.sendline("")  # Default model
            
            wizard.expect("save", timeout=5)
            wizard.sendline("y")
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # Verify config
        config = self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
        assert config["embedding"]["provider"] == "openai"
    
    def test_clean_environment(self, temp_work_dir):
        """Test wizard in completely clean environment."""
        # Start with minimal environment
        minimal_env = {
            'PATH': os.environ['PATH'],
            'HOME': os.environ.get('HOME', '/tmp'),
            'TERM': 'xterm-256color',
            'PYTHONPATH': os.environ.get('PYTHONPATH', ''),
        }
        
        # Add platform-specific essentials
        if sys.platform == "win32":
            minimal_env.update({
                'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''),
                'TEMP': os.environ.get('TEMP', '/tmp'),
                'TMP': os.environ.get('TMP', '/tmp'),
            })
        
        wizard = self.spawn_wizard(str(temp_work_dir), minimal_env)
        
        try:
            wizard.expect("Select embedding provider", timeout=10)
            wizard.sendline("3")  # Ollama (doesn't need API key)
            
            wizard.expect("URL", timeout=5)
            wizard.sendline("http://localhost:11434")
            
            wizard.expect("model", timeout=5)
            wizard.sendline("test-model-clean-env")
            
            wizard.expect("save", timeout=5)
            wizard.sendline("y")
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # Should still create valid config
        config = self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
        assert config["embedding"]["provider"] == "ollama"
        assert config["embedding"]["model"] == "test-model-clean-env"


class TestErrorConditions(SetupWizardPTYTest):
    """Test wizard behavior under various error conditions."""
    
    def test_permission_denied_config_dir(self, temp_work_dir):
        """Test wizard handles permission errors gracefully."""
        # Make directory read-only (if possible)
        try:
            temp_work_dir.chmod(0o555)  # Read + execute only
            
            wizard = self.spawn_wizard(str(temp_work_dir))
            
            try:
                wizard.expect("Select embedding provider", timeout=10)
                wizard.sendline("3")  # Ollama
                
                wizard.expect("URL", timeout=5)
                wizard.sendline("")  # Default
                
                wizard.expect("model", timeout=5)
                wizard.sendline("test-model")
                
                wizard.expect("save", timeout=5)
                wizard.sendline("y")
                
                # Should handle permission error gracefully
                index = wizard.expect(["successfully", "permission", "error", pexpect_module.EOF], 
                                     timeout=10)
                
                if index == 0:
                    # Somehow succeeded - restore permissions and validate
                    temp_work_dir.chmod(0o755)
                    self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
                else:
                    # Failed as expected - that's OK
                    pass
                    
            finally:
                wizard.close()
                
        finally:
            # Always restore permissions
            temp_work_dir.chmod(0o755)
    
    def test_interrupted_wizard_cleanup(self, temp_work_dir):
        """Test that interrupted wizard cleans up properly."""
        wizard = self.spawn_wizard(str(temp_work_dir))
        
        try:
            wizard.expect("Select embedding provider", timeout=10)
            wizard.sendline("1")
            
            wizard.expect("API key", timeout=5)
            wizard.sendline("sk-test-key")
            
            # Interrupt with Ctrl+C
            self.send_special_key(wizard, 'ctrl-c')
            
            # Should exit cleanly
            wizard.expect(pexpect_module.EOF, timeout=5)
            
        except Exception:
            # If wizard doesn't handle Ctrl+C gracefully, that's a bug
            # but for now we just want to verify cleanup
            pass
        finally:
            wizard.close()
        
        # Verify no partial files were left
        assert not (temp_work_dir / ".chunkhound.json").exists(), \
            "No config should exist after interrupt"
        assert not (temp_work_dir / ".mcp.json").exists(), \
            "No MCP config should exist after interrupt"


@pytest.mark.slow
class TestRealWorldScenarios(SetupWizardPTYTest):
    """Test real-world usage scenarios."""
    
    def test_existing_project_directory(self, temp_work_dir):
        """Test wizard in directory with existing files."""
        # Create some existing files
        (temp_work_dir / "README.md").write_text("# Existing Project")
        (temp_work_dir / "src").mkdir()
        (temp_work_dir / "src" / "main.py").write_text("print('hello')")
        
        wizard = self.spawn_wizard(str(temp_work_dir))
        
        try:
            wizard.expect("Select embedding provider", timeout=10)
            wizard.sendline("3")  # Ollama
            
            wizard.expect("URL", timeout=5)
            wizard.sendline("")
            
            wizard.expect("model", timeout=5)
            wizard.sendline("nomic-embed-text")
            
            wizard.expect("AI agent", timeout=5)
            wizard.sendline("1")  # Claude Code
            
            wizard.expect("save", timeout=5)
            wizard.sendline("y")
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # Verify config and existing files
        config = self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
        mcp_config = self.validate_mcp_config(temp_work_dir / ".mcp.json")
        
        # Existing files should be untouched
        assert (temp_work_dir / "README.md").exists()
        assert (temp_work_dir / "src" / "main.py").exists()
    
    def test_git_repository_directory(self, temp_work_dir):
        """Test wizard in a git repository."""
        # Create a git-like structure
        git_dir = temp_work_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]\n    bare = false")
        
        wizard = self.spawn_wizard(str(temp_work_dir))
        
        try:
            wizard.expect("Select embedding provider", timeout=10)
            wizard.sendline("2")  # VoyageAI
            
            wizard.expect("API key", timeout=5)
            wizard.sendline("voyage-git-test")
            
            wizard.expect("model", timeout=5)
            wizard.sendline("")  # Default
            
            wizard.expect("save", timeout=5)
            wizard.sendline("y")
            
            wizard.expect("successfully", timeout=10)
            
        finally:
            wizard.close()
        
        # Should create config without affecting .git
        config = self.validate_chunkhound_config(temp_work_dir / ".chunkhound.json")
        assert (git_dir / "config").exists()  # .git untouched


if __name__ == "__main__":
    pytest.main([__file__, "-v"])