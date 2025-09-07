# CLI Module Context

## MODULE_PURPOSE
The CLI module provides all command-line interfaces including the interactive setup wizard,
keyboard input handling, and terminal output formatting. This module directly interacts with
users via terminal interfaces.

## TERMINAL_OUTPUT_ARCHITECTURE

### Rich Console Pattern
```python
# PATTERN: Global console instance for consistent colored output
_console = Console()

# ANTI-PATTERN: Direct print() statements bypass Rich formatting
print("message")  # ❌ No colors, bypasses Rich

# CORRECT: Use console_print helper or formatter methods
console_print("message", "green")  # ✅ Colors work
formatter.info("message")  # ✅ Colors work
```

### Console Print Helper
```python
def console_print(message: str, style: str = None) -> None:
    """Print with colors using Rich console or fallback to plain print."""
    try:
        if style:
            _console.print(f"[{style}]{message}[/{style}]")
        else:
            _console.print(message)
    except Exception:
        # Fallback to plain print if Rich fails
        print(message)
```

### RichOutputFormatter Integration
```python
# PATTERN: Always use formatter methods when available
formatter.section_header("Title")  # Creates colored bordered box
formatter.info("Info message")     # Blue [INFO] prefix
formatter.success("Success!")      # Green [SUCCESS] prefix
formatter.error("Error occurred")  # Red [ERROR] prefix
formatter.warning("Warning")       # Yellow [WARN] prefix

# PRINCIPLE: Formatter handles both Rich and fallback modes
# - Rich mode: Full colors and formatting
# - Fallback mode: Plain text with prefixes
```

## SETUP_WIZARD_PATTERNS

### Interactive Input Fallback
```python
# PATTERN: Rich interactive mode with graceful fallback
async def rich_text(question: str, default: str = "", validate=None) -> str:
    try:
        # Try Rich interactive mode first
        return await _rich_text_interactive(question, default, validate)
    except Exception as e:
        # IMPORTANT: Use console_print for colored fallback messages
        console_print("Using standard input mode...", "dim")
        # Fallback implementation...
```

### Validation Error Display
```python
# PATTERN: Colored error messages in fallback mode
if isinstance(validation_result, str):
    console_print(f"Error: {validation_result}", "red")  # ✅
    # NOT: print(f"Error: {validation_result}")  # ❌
```

## KEYBOARD_INPUT_ARCHITECTURE

### Terminal Setup Pattern
```python
# PATTERN: Lazy initialization for terminal input
# - Only setup terminal when actually needed
# - Always cleanup in finally blocks
# - Handle platform-specific differences transparently
```

## COMMON_PITFALLS

### Direct Print Statements
- **DON'T**: Use `print()` directly for user-facing messages
- **DO**: Use `console_print()` helper or formatter methods
- **WHY**: Direct print bypasses Rich console, losing all colors

### Multiple Console Instances
- **DON'T**: Create new `Console()` instances everywhere
- **DO**: Use the global `_console` instance
- **WHY**: Multiple consoles can conflict and increase overhead

### Missing Formatter Parameter
- **DON'T**: Forget to pass formatter to functions that output text
- **DO**: Accept and use formatter parameter for all output functions
- **WHY**: Formatter ensures consistent styling across all output

### Unhandled Rich Failures
- **DON'T**: Assume Rich will always work
- **DO**: Always provide fallback for non-Rich terminals
- **WHY**: Some environments don't support Rich (CI, basic terminals)

## TESTING_PATTERNS

### Color Output Testing
```bash
# Test with Rich enabled (default)
python setup_wizard.py

# Test fallback mode without Rich
CHUNKHOUND_NO_RICH=1 python setup_wizard.py

# Test with debug output
CHUNKHOUND_DEBUG=1 python setup_wizard.py
```

## DEBUGGING_TIPS

### Rich Mode Failures
1. Set `CHUNKHOUND_DEBUG=1` to see exact exception
2. Check terminal compatibility with `sys.stdout.isatty()`
3. Verify TERM environment variable isn't "dumb"
4. Test Rich console creation directly

### Color Not Showing
1. Check if using direct `print()` instead of console methods
2. Verify formatter is being passed and used
3. Ensure using global console instance
4. Test with `CHUNKHOUND_NO_RICH=1` to compare

## BEST_PRACTICES

1. **Always use formatter or console_print** for user-facing output
2. **Pass formatter parameter** through the call chain
3. **Provide graceful fallbacks** for non-Rich environments
4. **Log exceptions** for debugging (use logger, not print)
5. **Test both Rich and fallback modes** during development
6. **Document color usage** in function docstrings