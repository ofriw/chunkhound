# ChunkHound Configuration Patterns

This document explains the different configuration loading patterns used in ChunkHound and when to use each one.

## Overview

ChunkHound uses different configuration loading patterns depending on the execution context:

- **CLI commands**: Use `ApplicationContext.from_cli_args()` to respect local `.chunkhound.json` files
- **MCP servers**: Use `ApplicationContext.from_environment()` to use environment variables only
- **File change processing**: Must match the pattern used for initial indexing

## Configuration Sources (in order of precedence)

1. **CLI arguments** (highest priority) - only for CLI commands
2. **Local .chunkhound.json files** - only detected by `from_cli_args()`
3. **Environment variables** - used by both patterns
4. **Default values** (lowest priority)

## Usage Patterns

### CLI Commands Pattern

```python
# Used by: chunkhound run, chunkhound index, etc.
project_dir = Path(args.path) if hasattr(args, "path") else Path.cwd()
app_context = ApplicationContext.from_cli_args(args, project_dir)
```

**Behavior:**
- Detects local `.chunkhound.json` files in project directories
- Merges CLI args with local config (CLI args take precedence)
- Respects user expectations for local configuration

### MCP Server Pattern

```python
# Used by: MCP stdio server, MCP HTTP server
project_root = find_project_root()
app_context = ApplicationContext.from_environment(project_root)
```

**Behavior:**
- Uses environment variables only
- Ignores local `.chunkhound.json` files
- Designed for launcher-controlled environments

## Critical Integration Requirements

### File Change Processing Configuration

**CRITICAL:** File change processing must use the same configuration pattern as initial indexing to ensure consistency.

**Current Bug:** The MCP server uses `ApplicationContext.from_environment()` for file change processing, which creates configuration mismatches when initial indexing used `from_cli_args()`.

**Example of the Problem:**
```python
# Initial indexing (CLI): Uses local .chunkhound.json
app_context = ApplicationContext.from_cli_args(args, project_dir)

# File change processing (MCP): Ignores local .chunkhound.json
app_context = ApplicationContext.from_environment(project_root)  # ❌ MISMATCH
```

**Solution:** File change processing must use the same configuration loading pattern as initial indexing.

### Configuration Validation

All configuration must be validated before use:

```python
validation_errors = app_context.validate_for_command("mcp")
if validation_errors:
    # Handle validation errors
    pass
```

## Common Issues and Solutions

### File Modifications Not Reflected in Search

**Symptom:** File changes are detected but not reflected in search results

**Root Cause:** Configuration mismatch between initial indexing and file change processing

**Solution:** Ensure file change processing uses same configuration pattern as initial indexing

### Local .chunkhound.json Files Ignored

**Symptom:** Local configuration files are not being respected

**Root Cause:** Using `ApplicationContext.from_environment()` instead of `from_cli_args()`

**Solution:** Use `from_cli_args()` for CLI commands that should respect local config

### Configuration Validation Failures

**Symptom:** Runtime errors about missing configuration

**Root Cause:** Skipping `validate_for_command()` call

**Solution:** Always call validation before using configuration

## Testing Requirements

When modifying configuration patterns, test:

1. **End-to-end file modification workflow** (create → modify → search)
2. **Configuration consistency** across components
3. **Local .chunkhound.json detection** for CLI commands
4. **Environment variable precedence** for MCP servers

## Decision Tree: Which Pattern to Use

```
Are you implementing a CLI command?
├── Yes: Use ApplicationContext.from_cli_args()
│   └── Users expect local .chunkhound.json files to be respected
└── No: Are you implementing an MCP server?
    ├── Yes: Use ApplicationContext.from_environment()
    │   └── Launcher controls environment variables
    └── No: Are you implementing file change processing?
        └── Use the SAME pattern as initial indexing
            ├── If initial indexing used from_cli_args() → use from_cli_args()
            └── If initial indexing used from_environment() → use from_environment()
```

## Architecture Notes

The configuration system uses multiple layers:

1. **Config** - Core configuration loading with file detection
2. **ChunkHoundConfig** - Wrapper for registry compatibility
3. **ApplicationContext** - High-level interface for different execution contexts

Each layer serves a specific purpose and should not be bypassed.