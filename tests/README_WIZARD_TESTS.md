# Setup Wizard Testing Documentation

This document explains how to run and maintain the comprehensive setup wizard tests for ChunkHound.

## Overview

The wizard tests use PTY (pseudo-terminal) technology to test the actual interactive setup wizard across platforms, ensuring reliable terminal UI behavior, keyboard handling, and configuration file generation.

**Note**: The setup wizard is automatically triggered when running `chunkhound index` without proper configuration, so tests use `chunkhound index .` to invoke the wizard.

## Test Files

- `test_setup_wizard_pty.py` - Core wizard flow tests with validation
- `test_setup_wizard_compatibility.py` - Terminal compatibility and environment tests

## Running Tests Locally

### Prerequisites

Install PTY testing dependencies:

```bash
# For Unix/Linux/macOS
uv pip install pexpect

# For Windows 
uv pip install wexpect pywinpty

# Or install dev dependencies which include PTY support
uv sync --group dev
```

### Running All Wizard Tests

```bash
# Run all wizard tests
uv run pytest tests/test_setup_wizard_pty.py tests/test_setup_wizard_compatibility.py -v

# Run just the core wizard tests
uv run pytest tests/test_setup_wizard_pty.py -v

# Run just compatibility tests
uv run pytest tests/test_setup_wizard_compatibility.py -v
```

### Running Specific Test Categories

```bash
# Run tests by marker
uv run pytest -m "wizard" -v
uv run pytest -m "pty" -v

# Skip slow tests
uv run pytest -m "not slow" tests/test_setup_wizard_compatibility.py -v

# Run only slow tests (comprehensive scenarios)
uv run pytest -m "slow" tests/test_setup_wizard_compatibility.py -v
```

### Running Individual Tests

```bash
# Test specific provider setup
uv run pytest tests/test_setup_wizard_pty.py::TestWizardWithValidation::test_openai_complete_with_claude_code -v

# Test keyboard navigation
uv run pytest tests/test_setup_wizard_pty.py::TestWizardNavigation::test_menu_navigation_with_arrow_keys -v

# Test error recovery
uv run pytest tests/test_setup_wizard_pty.py::TestWizardErrorHandling::test_invalid_api_key_retry -v
```

## Test Structure

### Core Test Classes

#### `SetupWizardPTYTest` (Base Class)
- `spawn_wizard()` - Creates PTY subprocess for wizard
- `send_arrow_key()` - Simulates arrow key navigation
- `send_special_key()` - Simulates Enter, Escape, Ctrl+C, etc.
- `validate_chunkhound_config()` - Validates `.chunkhound.json` structure and content
- `validate_mcp_config()` - Validates `.mcp.json` for IDE integration
- `validate_vscode_config()` - Validates `.vscode/mcp.json`
- `validate_env_variables()` - Checks API key handling in `.env` files
- `verify_config_works()` - Tests that generated config loads in ChunkHound

#### `TestWizardWithValidation`
Tests complete wizard flows with comprehensive validation:
- OpenAI provider with Claude Code integration
- VoyageAI provider with VS Code integration  
- Ollama local provider setup
- Configuration file generation and validation

#### `TestWizardNavigation`
Tests keyboard and cursor interactions:
- Arrow key menu navigation
- Text input editing (cursor movement, insertion, deletion)
- Home/End key handling

#### `TestWizardErrorHandling`
Tests error scenarios and recovery:
- Invalid API key retry logic
- Escape key cancellation (no artifacts left)
- Ctrl+C interruption handling

#### `TestTerminalCompatibility`
Tests different terminal environments:
- Various TERM settings (xterm, vt100, screen, etc.)
- NO_COLOR environment support
- Different terminal sizes
- UTF-8 encoding handling

## What Gets Validated

### Configuration Files

#### `.chunkhound.json`
- Valid JSON structure
- Required embedding provider fields
- Correct model names for each provider
- API keys NOT stored in config (security check)
- Config can be loaded by ChunkHound's Config class

#### `.mcp.json` (Claude Code integration)
- Valid MCP server configuration
- Correct command structure using `uv`
- Proper directory argument
- Server name and args validation

#### `.vscode/mcp.json` (VS Code integration)
- Same validation as `.mcp.json`
- Proper VS Code directory structure creation

#### `.env` (Environment variables)
- API keys stored securely outside config
- Correct key formats (OpenAI: sk-*, VoyageAI: any string)
- No sensitive data in config files

### Provider-Specific Validation

#### OpenAI
- Model must be valid embedding model
- API key format validation (starts with 'sk-')
- No API key in JSON config

#### VoyageAI
- Model must be valid VoyageAI model
- API key stored in environment
- Proper model selection handling

#### Ollama
- Valid URL format for base_url
- Model name can be any string
- No API key required

#### OpenAI-Compatible
- Base URL validation
- Model and API key handling
- Custom endpoint support

## Cross-Platform Considerations

### Windows (ConPTY/winpty)
- Uses `wexpect` and `pywinpty` for PTY functionality
- ConPTY support on Windows 10 1903+
- Fallback to winpty on older versions

### Linux/macOS (Native PTY)
- Uses `pexpect` with native pseudo-terminal support
- Full escape sequence support
- Terminal size control

### CI/CD Environments
- Works in GitHub Actions across all platforms
- Handles headless environments
- Consistent terminal settings via environment variables

## Environment Variables

The tests set consistent environment variables:

```bash
TERM=xterm-256color          # Consistent terminal type
PYTHONIOENCODING=utf-8       # Unicode support
COLUMNS=80                   # Fixed terminal width
LINES=24                     # Fixed terminal height
NO_COLOR=0                   # Enable colors for Rich testing
LC_ALL=en_US.UTF-8          # English locale
LANG=en_US.UTF-8            # English language
```

## Debugging Tests

### Verbose Output

```bash
# Maximum verbosity
uv run pytest tests/test_setup_wizard_pty.py -vvv --tb=long

# Show stdout/stderr from wizard
uv run pytest tests/test_setup_wizard_pty.py -v -s
```

### Test Timeouts

Each test has timeouts to prevent hanging:
- Default wizard spawn timeout: 15 seconds
- Individual expect timeouts: 5-10 seconds
- Overall test timeout: 60 seconds (in CI)

### Common Issues

#### PTY Not Available
```
ImportError: No module named 'pexpect'
```
**Solution:** Install PTY dependencies for your platform

#### Wizard Hangs
```
TIMEOUT: wizard.expect() timed out
```
**Solutions:**
- Check that wizard can start: `uv run chunkhound init --help`
- Verify terminal environment variables
- Check for prompts that changed in wizard code

#### Config Validation Fails
```
AssertionError: Config cannot be loaded by ChunkHound
```
**Solutions:**
- Check that generated config has correct structure
- Verify ChunkHound imports work
- Check for breaking changes in Config class

## Maintenance

### Adding New Provider Tests

1. Add test method to `TestWizardWithValidation`
2. Follow pattern: spawn → interact → validate
3. Add provider-specific validation in `validate_chunkhound_config()`
4. Test both config creation and loading

### Adding New Terminal Types

1. Add to `test_different_term_types` parametrize list
2. Verify wizard works with new terminal type
3. Update CI matrix if needed

### Updating for Wizard Changes

1. Update interaction patterns in tests
2. Check timeout values if new prompts added
3. Update validation if config structure changes
4. Verify error messages still match expectations

## CI/CD Integration

### GitHub Actions Workflow

The `.github/workflows/test-setup-wizard.yml` workflow:

- Tests on Ubuntu 20.04, Ubuntu latest, macOS, Windows
- Tests Python 3.10, 3.11, 3.12
- Installs platform-specific PTY dependencies
- Runs core tests and compatibility tests
- Collects artifacts on failure
- Validates all provider configurations

### Running Locally Like CI

```bash
# Simulate CI environment
export TERM=xterm-256color
export PYTHONIOENCODING=utf-8
export COLUMNS=80
export LINES=24
export LC_ALL=en_US.UTF-8

# Run with CI timeouts
uv run pytest tests/test_setup_wizard_pty.py -v --tb=short --timeout=60
```

## Best Practices

### Writing New Tests

1. **Use base class methods** - Don't reinvent PTY interaction
2. **Validate everything** - Config files, environment, loading
3. **Clean up** - Use temp directories, ensure no artifacts
4. **Handle timeouts** - Set appropriate expect timeouts
5. **Test real behavior** - No mocks, test actual wizard

### Debugging Strategy

1. **Start simple** - Test wizard manually first
2. **Check environment** - Verify PTY works on your platform
3. **Use verbose mode** - See exact wizard output
4. **Add debug prints** - In base class methods if needed
5. **Test isolation** - Run single test to isolate issues

This testing approach ensures the setup wizard works reliably across all platforms and provides users with correctly configured ChunkHound installations.