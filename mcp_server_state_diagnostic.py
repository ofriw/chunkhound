#!/usr/bin/env python3
"""
MCP Server File Watcher State Diagnostic

Based on realtime-indexing-file-watcher-null-2025-06-14.md notes:
- Need to check actual MCP server _file_watcher global variable state
- Previous investigation shows _file_watcher = None despite initialization code existing
- This diagnostic will inspect the exact state of MCP server globals
"""

import sys
import time
import inspect
import importlib
from pathlib import Path

def log_with_timestamp(message, level="INFO"):
    """Log message with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")

def main():
    """Diagnose MCP server file watcher state"""

    log_with_timestamp("=== MCP Server File Watcher State Diagnostic ===", "INFO")

    # Add chunkhound to path
    sys.path.insert(0, str(Path(__file__).parent))

    try:
        # Import MCP server module
        log_with_timestamp("Importing MCP server module...", "INFO")
        from chunkhound import mcp_server
        log_with_timestamp("✅ MCP server module imported successfully", "SUCCESS")

        # Check if module has _file_watcher attribute
        has_file_watcher_attr = hasattr(mcp_server, '_file_watcher')
        log_with_timestamp(f"MCP server has _file_watcher attribute: {has_file_watcher_attr}", "INFO")

        if has_file_watcher_attr:
            # Get current value
            file_watcher_value = getattr(mcp_server, '_file_watcher')
            log_with_timestamp(f"_file_watcher current value: {file_watcher_value}", "INFO")
            log_with_timestamp(f"_file_watcher type: {type(file_watcher_value)}", "INFO")

            # Check if it's None/null
            if file_watcher_value is None:
                log_with_timestamp("🎯 HYPOTHESIS CONFIRMED: _file_watcher is None", "CRITICAL")
            else:
                log_with_timestamp("✅ HYPOTHESIS DISPROVEN: _file_watcher is not None", "SUCCESS")

                # If not None, check its state
                if hasattr(file_watcher_value, 'watcher'):
                    watcher_state = getattr(file_watcher_value, 'watcher', 'NO_ATTR')
                    log_with_timestamp(f"FileWatcherManager.watcher: {watcher_state}", "INFO")

                if hasattr(file_watcher_value, 'processing_task'):
                    task_state = getattr(file_watcher_value, 'processing_task', 'NO_ATTR')
                    log_with_timestamp(f"FileWatcherManager.processing_task: {task_state}", "INFO")

                if hasattr(file_watcher_value, 'event_queue'):
                    queue_state = getattr(file_watcher_value, 'event_queue', 'NO_ATTR')
                    log_with_timestamp(f"FileWatcherManager.event_queue: {queue_state}", "INFO")

        # Check all module globals for debugging
        log_with_timestamp("--- MCP Server Module Globals ---", "DEBUG")
        module_globals = dir(mcp_server)
        relevant_globals = [name for name in module_globals if 'watch' in name.lower() or name.startswith('_')]

        for global_name in relevant_globals:
            try:
                global_value = getattr(mcp_server, global_name)
                log_with_timestamp(f"{global_name}: {global_value} (type: {type(global_value)})", "DEBUG")
            except Exception as e:
                log_with_timestamp(f"{global_name}: ERROR - {e}", "DEBUG")

        # Check if server has been started (lifespan called)
        log_with_timestamp("--- MCP Server Initialization State ---", "INFO")

        # Look for initialization functions
        init_functions = [name for name in dir(mcp_server) if 'lifespan' in name.lower() or 'init' in name.lower()]
        log_with_timestamp(f"Initialization functions found: {init_functions}", "DEBUG")

        # Try to determine if server was initialized
        database_state = getattr(mcp_server, '_database', 'NO_ATTR')
        embedding_manager_state = getattr(mcp_server, '_embedding_manager', 'NO_ATTR')

        log_with_timestamp(f"_database state: {database_state}", "INFO")
        log_with_timestamp(f"_embedding_manager state: {embedding_manager_state}", "INFO")

        # Determine initialization status
        if database_state is None and embedding_manager_state is None and file_watcher_value is None:
            log_with_timestamp("🔍 SERVER STATE: Not initialized (all globals are None)", "INFO")
        elif database_state is not None or embedding_manager_state is not None:
            log_with_timestamp("🔍 SERVER STATE: Partially initialized", "INFO")
        else:
            log_with_timestamp("🔍 SERVER STATE: Unknown", "INFO")

    except ImportError as e:
        log_with_timestamp(f"❌ Failed to import MCP server: {e}", "ERROR")
        return False
    except Exception as e:
        log_with_timestamp(f"💥 Diagnostic failed: {e}", "ERROR")
        return False

    log_with_timestamp("=== Diagnostic Complete ===", "INFO")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
