# ChunkHound Configuration System Protection

<AI_AGENT_CRITICAL_SYSTEM>
🚨 PROTECTED CONFIGURATION PATTERNS - EXPLICIT USER APPROVAL REQUIRED 🚨

The configuration system has been hardened with prompt engineering guardrails to prevent 
AI agents from accidentally breaking critical system patterns.

## PROTECTED FUNCTIONS - USER APPROVAL REQUIRED

### 1. `args_to_config()` - CLI Configuration Gateway
**Location**: `chunkhound/api/cli/utils/config_helpers.py`
**Purpose**: Single source of truth for CLI configuration
**Protection**: Explicit user approval required for changes

**PROTECTED BEHAVIORS**:
- Must detect local `.chunkhound.json` files
- Must merge CLI args with local config
- Must return `ChunkHoundConfig` wrapper with `._config` property

**NEVER CHANGE WITHOUT USER APPROVAL**:
```python
# ✅ CORRECT: CLI configuration pattern
project_dir = Path(args.path) if hasattr(args, "path") else Path.cwd()
unified_config = args_to_config(args, project_dir)

# ❌ FORBIDDEN: Direct Config() in CLI
config = Config()  # Breaks local config detection
```

### 2. `validate_config_for_command()` - Security Gateway
**Location**: `chunkhound/api/cli/utils/config_helpers.py`
**Purpose**: Mandatory validation for all configuration
**Protection**: Explicit user approval required for changes

**PROTECTED BEHAVIORS**:
- Must validate ALL config before system use
- Must return list of specific error messages
- Must check provider-specific requirements
- Must be called by BOTH CLI and MCP paths

**NEVER SKIP VALIDATION**:
```python
# ✅ CORRECT: Mandatory validation
validation_errors = validate_config_for_command(unified_config, "index")
if validation_errors:
    for error in validation_errors:
        logger.error(f"Configuration error: {error}")
    raise ValueError("Invalid configuration")

# ❌ FORBIDDEN: Skip validation
configure_registry(config)  # No validation!
```

### 3. `create_database_with_dependencies()` - Database Factory
**Location**: `chunkhound/database_factory.py`
**Purpose**: Unified database creation across all code paths
**Protection**: Explicit user approval required for changes

**PROTECTED BEHAVIORS**:
- Must configure registry before creating components
- Must create all components through registry
- Must inject all dependencies into Database constructor
- Must be used by CLI, MCP stdio, and MCP HTTP

**NEVER CREATE Database() DIRECTLY**:
```python
# ✅ CORRECT: Use unified factory
database = create_database_with_dependencies(
    db_path=db_path,
    config=config,
    embedding_manager=embedding_manager,
)

# ❌ FORBIDDEN: Direct Database() instantiation
database = Database(db_path)  # Breaks consistency
```

## PROTECTED CODE PATTERNS

### CLI Command Pattern (PROTECTED)
```python
# <CLI_CONFIG_STEP_1>
project_dir = Path(args.path) if hasattr(args, "path") else Path.cwd()
unified_config = args_to_config(args, project_dir)

# <CLI_CONFIG_STEP_2>
validation_errors = validate_config_for_command(unified_config, "index")
if validation_errors:
    for error in validation_errors:
        logger.error(f"Configuration error: {error}")
    raise ValueError("Invalid configuration")

# <CLI_CONFIG_STEP_3>
configure_registry(unified_config._config)
```

### MCP Server Pattern (PROTECTED)
```python
# <MCP_CONFIG_STEP_1>
config = Config()  # Environment-based only - no target_dir
# 🚨 MISSING: validate_config_for_command() call - ADD THIS IN REFACTOR

# <MCP_CONFIG_STEP_2>
database = create_database_with_dependencies(
    db_path=Path(config.database.path),
    config=config,
    embedding_manager=embedding_manager,
)
```

## APPROVAL PROCESS FOR CHANGES

### If you need to modify protected patterns:

1. **Ask Explicitly**: "Should I modify the protected config patterns?"
2. **Explain Change**: Describe specific modification and risks
3. **Wait for Approval**: Do not proceed without explicit user approval
4. **Update Consistently**: Modify all related code paths together

### Example Approval Request:
```
"I need to modify the protected config pattern in args_to_config() to add 
support for environment variable overrides. This change would:
- Add env var checking after local config loading
- Maintain existing precedence: CLI args > local config > env vars
- Risk: Could break if precedence logic is incorrect

Should I proceed with this protected pattern modification?"
```

## PROTECTED FILES WITH GUARDRAILS

1. **`chunkhound/api/cli/utils/config_helpers.py`** - CLI configuration functions
2. **`chunkhound/database_factory.py`** - Database factory function
3. **`chunkhound/api/cli/commands/run.py`** - CLI command pattern
4. **`chunkhound/mcp_server.py`** - MCP stdio server pattern
5. **`chunkhound/mcp_http_server.py`** - MCP HTTP server pattern
6. **`tests/test_config_unification.py`** - TDD specification tests

## PROTECTED TESTS - DO NOT MODIFY

The TDD tests in `tests/test_config_unification.py` define the expected behavior and act as:
- **Specification**: What the system should do after refactor
- **Protection**: Guard against regressions
- **Documentation**: Show correct patterns

**Test modification requires explicit user approval**

## WHAT HAPPENS IF PROTECTIONS ARE IGNORED

Breaking protected patterns without approval will cause:
- **Local config detection failures**
- **Security vulnerabilities from skipped validation**
- **Inconsistent database initialization**
- **Silent runtime failures**
- **Production system failures**

## EMERGENCY OVERRIDE

If you must modify protected patterns in an emergency:
1. **Document the emergency** - explain why approval can't be obtained
2. **Minimize changes** - make smallest possible modification
3. **Test thoroughly** - verify all code paths still work
4. **Request post-hoc approval** - get approval as soon as possible
5. **Update all related code** - maintain consistency

## BENEFITS OF PROTECTION SYSTEM

1. **Prevents Regressions**: Guards against accidental pattern changes
2. **Maintains Consistency**: Ensures all code paths follow same patterns
3. **Improves Security**: Prevents validation bypass
4. **Guides Development**: Makes correct patterns obvious
5. **Reduces Bugs**: Prevents common configuration errors

This protection system uses soft guardrails embedded in the code itself, making it zero-maintenance and naturally visible to anyone working with the configuration system.
</AI_AGENT_CRITICAL_SYSTEM>