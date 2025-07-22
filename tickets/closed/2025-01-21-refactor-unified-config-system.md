# 2025-01-21 - [REFACTOR] Unified Config System
**Priority**: High

## Overview
Refactor the configuration system to provide a single, unified entry point that automatically handles precedence rules across all execution contexts (CLI, MCP stdio, MCP HTTP).

## Goal
Create a Config class where each flow simply calls `config = Config(args=args)` without needing to understand precedence rules, project detection, or initialization patterns.

## Precedence Order (Automatic)
1. **CLI arguments** (highest) - from argparse.Namespace if provided
2. **Environment variables** - override config files but not CLI args
3. **Config file** - resolved via: explicit path → env var → local .chunkhound.json
4. **Defaults** (lowest)

## Design

### Single Entry Point
```python
class Config:
    def __init__(self, 
                 args: argparse.Namespace = None,  # Optional CLI arguments
                 **kwargs):                        # Direct overrides for testing
        """
        Universal config initialization that handles all contexts.
        Automatically applies correct precedence order.
        Config file resolution and local detection happen automatically.
        """
```

### Usage Pattern (All Flows)
```python
# CLI commands
def run_command(args: argparse.Namespace):
    config = Config(args=args)  # That's it!

# MCP servers  
def main():
    parser = argparse.ArgumentParser()
    # ... add arguments ...
    args = parser.parse_args()
    config = Config(args=args)  # Same pattern!

# Tests
config = Config(database={"path": ":memory:"})
```

### Smart Config File Resolution (Automatic)
1. `--config` from args (if args provided)
2. `CHUNKHOUND_CONFIG_FILE` environment variable
3. Local `.chunkhound.json` in project directory (auto-detected from args.path or cwd)

### Key Changes

#### Remove
- `Config.from_cli_args()` class method
- `args_to_config()` helper function
- Manual `find_project_root()` calls in each flow
- `._config` property workarounds
- Environment variable preservation logic (current bug)

#### Add
- Argument parsing to MCP servers
- Automatic project directory detection from args.path
- Unified precedence handling inside Config
- Smart config file resolution chain

#### Fix
- Environment variables currently override CLI args (wrong)
- Inconsistent initialization patterns across flows
- Complex test setup requirements

## Benefits
1. **Zero knowledge required** - flows don't understand precedence
2. **Consistent behavior** - same rules everywhere automatically
3. **Flexible deployment** - works for local dev, CI/CD, containers
4. **Simpler code** - remove helper functions and special cases
5. **MCP compliant** - supports both stateless and convenient modes

## Migration Steps
1. Fix Config.__init__ precedence order
2. Add argument parsing to MCP servers
3. Update all flows to use `Config(args=args)`
4. Remove deprecated methods and helpers
5. Update tests to use unified pattern
6. Update registry to accept Config directly

## Success Criteria
- All flows use identical `Config(args=args)` pattern
- Precedence order is automatically correct everywhere
- No manual project detection in calling code
- Tests pass without complex mocking
- MCP servers support optional CLI arguments

# History

## 2025-01-21
Created ticket after analyzing config system test failures. The current system has multiple initialization patterns, incorrect precedence order (env vars override CLI args), and requires each flow to understand config complexity. The proposed unified system hides all complexity behind a single intelligent Config class that automatically handles context detection and precedence rules.

## 2025-01-21 - COMPLETED
Successfully refactored the configuration system to provide a unified entry point:
- Implemented new Config.__init__ that accepts optional args parameter
- Fixed precedence order: CLI args > env vars > config file > defaults  
- Added smart config file resolution (--config, CHUNKHOUND_CONFIG_FILE, local .chunkhound.json)
- Added argument parsing to both MCP stdio and HTTP servers
- Updated all flows (CLI, MCP stdio, MCP HTTP) to use Config(args=args)
- Removed deprecated methods: from_cli_args(), from_environment()
- Simplified args_to_config() to just call Config(args=args)
- All smoke tests pass, precedence order verified working correctly

The system now provides zero-knowledge configuration - flows simply call Config(args=args) without understanding precedence rules or project detection.