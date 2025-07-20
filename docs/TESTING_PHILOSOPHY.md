# Testing Philosophy for AI-Developed Projects

## The ChunkHound Testing Pyramid

### 1. Smoke Tests (Foundation - 10 seconds)
**Purpose**: Prevent embarrassing failures before they reach users

ChunkHound's smoke tests are designed as guardrails for AI development:
- **Import Tests**: Catch syntax/type annotation errors at module load time
- **CLI Tests**: Ensure basic commands don't crash
- **Startup Tests**: Verify servers can at least start

**Key Insight**: The forward reference bug (`"Config" | None`) that crashed MCP HTTP server would have been caught by a simple import test. This type of error is particularly common in AI-generated code where type annotations might be added without full context.

### 2. Unit Tests (Core Logic)
- Parser functionality
- Chunking algorithms
- Database operations

### 3. Integration Tests (Component Interaction)
- Provider implementations
- End-to-end workflows

## Why Smoke Tests Matter for AI Development

1. **AI agents don't experience runtime errors** - They generate code but don't feel the crash
2. **Type annotation errors are subtle** - Valid-looking code that crashes at import
3. **Fast feedback loops** - 10-second tests fit AI development cycles
4. **Clear boundaries** - Import failures are unambiguous bugs

## The Forward Reference Bug: A Case Study

```python
# What AI generated (looks correct but crashes):
_server_config: "Config" | None = None

# Why it crashed:
# - Python tries to evaluate "Config" | None at import time
# - Can't use | operator between string and None
# - Even though Config was imported, quotes made it a string literal

# The fix (what smoke tests enforce):
_server_config: Config | None = None
```

## Testing Commandments for AI Agents

1. **ALWAYS run smoke tests before marking tasks complete**
2. **NEVER commit without running `uv run pytest tests/test_smoke.py`**
3. **ADD new modules to critical imports list in smoke tests**
4. **TRUST the smoke tests** - If they fail, the code is broken

## Implementation Pattern

```python
# tests/test_smoke.py core structure:
class TestModuleImports:
    def test_all_modules_import(self):
        # Walk all modules and import them
        # Catches syntax/type errors immediately

class TestCLICommands:
    def test_cli_help_commands(self):
        # Run all commands with --help
        # Ensures basic CLI functionality

class TestServerStartup:
    async def test_mcp_http_server_starts(self):
        # Start server, wait 2 seconds
        # If it crashes, test fails
```

## Metrics That Matter

- **Smoke test runtime**: < 10 seconds (currently ~10s)
- **Coverage**: 100% of user-facing modules
- **False positive rate**: 0% (only catches real crashes)
- **Developer friction**: Minimal (one command)

## Future Evolution

As ChunkHound grows:
1. Keep smoke tests under 15 seconds
2. Add new critical paths as they emerge
3. Never make smoke tests dependent on external services
4. Maintain focus on import/startup failures

Remember: In an AI-developed project, smoke tests are your first and most important line of defense against obvious but devastating bugs.