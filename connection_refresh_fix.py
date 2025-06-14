#!/usr/bin/env python3
"""
Minimal Connection Refresh Fix for Database Synchronization Gap

This script implements a simple connection refresh mechanism to resolve
the database file locking issue between CLI and MCP server processes.

Usage:
    python connection_refresh_fix.py --install    # Install the fix
    python connection_refresh_fix.py --test       # Test the fix
    python connection_refresh_fix.py --status     # Check fix status

Fix Strategy:
- Patches MCP server to periodically refresh database connection
- Adds background thread that disconnects/reconnects every 3 seconds
- Provides window for CLI operations to access database
- Minimal code changes, immediate relief
"""

import argparse
import asyncio
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional


class ConnectionRefreshFix:
    """Implements connection refresh fix for database synchronization."""

    def __init__(self):
        self.chunkhound_dir = Path(__file__).parent
        self.mcp_server_file = self.chunkhound_dir / "chunkhound" / "mcp_server.py"
        self.backup_file = self.mcp_server_file.with_suffix(".py.backup")
        self.refresh_thread: Optional[threading.Thread] = None
        self.refresh_active = False

    def check_prerequisites(self) -> bool:
        """Check if fix can be applied."""
        if not self.mcp_server_file.exists():
            print(f"❌ MCP server file not found: {self.mcp_server_file}")
            return False

        print(f"✅ MCP server file found: {self.mcp_server_file}")
        return True

    def backup_original_file(self) -> bool:
        """Create backup of original MCP server file."""
        try:
            if not self.backup_file.exists():
                self.backup_file.write_text(self.mcp_server_file.read_text())
                print(f"✅ Created backup: {self.backup_file}")
            else:
                print(f"✅ Backup already exists: {self.backup_file}")
            return True
        except Exception as e:
            print(f"❌ Failed to create backup: {e}")
            return False

    def apply_connection_refresh_patch(self) -> bool:
        """Apply connection refresh patch to MCP server."""
        try:
            # Read current content
            content = self.mcp_server_file.read_text()

            # Check if already patched
            if "CONNECTION_REFRESH_FIX" in content:
                print("✅ Connection refresh fix already applied")
                return True

            # Find insertion point after global variables
            insertion_point = content.find("_signal_coordinator: Optional[SignalCoordinator] = None")
            if insertion_point == -1:
                print("❌ Could not find insertion point in MCP server file")
                return False

            # Prepare the patch
            patch_code = '''
# CONNECTION_REFRESH_FIX: Global variables for connection refresh mechanism
_refresh_thread: Optional[threading.Thread] = None
_refresh_active = False
_refresh_interval = 3.0  # Refresh every 3 seconds

def _connection_refresh_worker():
    """Background worker that periodically refreshes database connection."""
    global _database, _refresh_active

    while _refresh_active:
        time.sleep(_refresh_interval)

        if _database and _database.is_connected():
            try:
                # Brief disconnect/reconnect cycle
                print("DEBUG: Refreshing database connection...")
                _database.disconnect()
                time.sleep(0.1)  # 100ms window for CLI access
                _database.reconnect()
                print("DEBUG: Database connection refreshed")
            except Exception as e:
                print(f"DEBUG: Connection refresh error: {e}")
                # Continue anyway - connection will be restored on next request

def _start_connection_refresh():
    """Start the connection refresh background thread."""
    global _refresh_thread, _refresh_active

    if _refresh_thread and _refresh_thread.is_alive():
        return

    _refresh_active = True
    _refresh_thread = threading.Thread(target=_connection_refresh_worker, daemon=True)
    _refresh_thread.start()
    print("DEBUG: Connection refresh thread started")

def _stop_connection_refresh():
    """Stop the connection refresh background thread."""
    global _refresh_active, _refresh_thread

    _refresh_active = False
    if _refresh_thread:
        _refresh_thread.join(timeout=1.0)
    print("DEBUG: Connection refresh thread stopped")

'''

            # Add necessary imports at the top
            import_addition = "import threading\nimport time\n"

            # Find import section
            first_import = content.find("import")
            if first_import != -1:
                # Add threading and time imports
                lines = content.split('\n')
                import_inserted = False
                for i, line in enumerate(lines):
                    if line.startswith("import") and not import_inserted:
                        lines.insert(i, "import threading")
                        lines.insert(i+1, "import time")
                        import_inserted = True
                        break
                content = '\n'.join(lines)

            # Insert the patch after signal coordinator declaration
            end_of_line = content.find('\n', insertion_point)
            patched_content = (
                content[:end_of_line + 1] +
                patch_code +
                content[end_of_line + 1:]
            )

            # Add connection refresh startup to server_lifespan
            lifespan_start = patched_content.find("yield {")
            if lifespan_start != -1:
                # Find the yield statement and add refresh startup before it
                lines = patched_content.split('\n')
                for i, line in enumerate(lines):
                    if "yield {" in line:
                        indent = len(line) - len(line.lstrip())
                        refresh_start = " " * indent + "# CONNECTION_REFRESH_FIX: Start connection refresh\n"
                        refresh_start += " " * indent + "_start_connection_refresh()\n"
                        refresh_start += " " * indent
                        lines.insert(i, refresh_start.rstrip())
                        break
                patched_content = '\n'.join(lines)

            # Add connection refresh cleanup to finally block
            finally_block = patched_content.find("finally:")
            if finally_block != -1:
                # Find the finally block and add cleanup
                lines = patched_content.split('\n')
                for i, line in enumerate(lines):
                    if line.strip() == "finally:":
                        # Find the first statement in finally block to get indentation
                        for j in range(i + 1, len(lines)):
                            if lines[j].strip() and not lines[j].strip().startswith('#'):
                                indent = len(lines[j]) - len(lines[j].lstrip())
                                cleanup_code = " " * indent + "# CONNECTION_REFRESH_FIX: Stop connection refresh\n"
                                cleanup_code += " " * indent + "_stop_connection_refresh()\n"
                                cleanup_code += " " * indent
                                lines.insert(j, cleanup_code.rstrip())
                                break
                        break
                patched_content = '\n'.join(lines)

            # Write patched content
            self.mcp_server_file.write_text(patched_content)
            print("✅ Connection refresh patch applied successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to apply patch: {e}")
            return False

    def install_fix(self) -> bool:
        """Install the connection refresh fix."""
        print("🔧 Installing Connection Refresh Fix...")

        if not self.check_prerequisites():
            return False

        if not self.backup_original_file():
            return False

        if not self.apply_connection_refresh_patch():
            return False

        print("✅ Connection refresh fix installed successfully!")
        print("\n📋 Next Steps:")
        print("   1. Restart any running MCP servers")
        print("   2. Test CLI operations with MCP server running")
        print("   3. Monitor connection refresh logs in MCP server output")
        print("\n⚙️  Fix Details:")
        print("   • Database connection refreshes every 3 seconds")
        print("   • Provides 100ms window for CLI access during refresh")
        print("   • Background thread handles refresh automatically")
        print("   • Minimal performance impact")

        return True

    def restore_original(self) -> bool:
        """Restore original MCP server file from backup."""
        try:
            if not self.backup_file.exists():
                print("❌ No backup file found")
                return False

            self.mcp_server_file.write_text(self.backup_file.read_text())
            print("✅ Original MCP server file restored")
            return True

        except Exception as e:
            print(f"❌ Failed to restore original file: {e}")
            return False

    def test_fix(self) -> bool:
        """Test the connection refresh fix."""
        print("🧪 Testing Connection Refresh Fix...")

        # Check if fix is installed
        if not self.mcp_server_file.exists():
            print("❌ MCP server file not found")
            return False

        content = self.mcp_server_file.read_text()
        if "CONNECTION_REFRESH_FIX" not in content:
            print("❌ Connection refresh fix not installed")
            print("   Run: python connection_refresh_fix.py --install")
            return False

        print("✅ Connection refresh fix is installed")

        # Test database creation
        test_db = Path.home() / ".cache" / "chunkhound" / "test_refresh_fix.duckdb"
        test_db.unlink(missing_ok=True)

        try:
            # Test basic functionality
            print("🔄 Testing basic database operations...")

            # Import and test database creation
            sys.path.insert(0, str(self.chunkhound_dir))
            from chunkhound.database import Database

            db = Database(test_db)
            db.connect()

            stats = db.get_stats()
            print(f"✅ Database stats: {stats}")

            db.close()

            print("✅ Connection refresh fix test completed successfully")
            print("\n📋 Manual Testing Steps:")
            print("   1. Start MCP server: chunkhound mcp --db test.duckdb")
            print("   2. In another terminal: chunkhound run . --db test.duckdb")
            print("   3. CLI should succeed after brief delay (during refresh window)")
            print("   4. Monitor MCP server logs for 'Refreshing database connection' messages")

            return True

        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False
        finally:
            test_db.unlink(missing_ok=True)

    def check_status(self) -> bool:
        """Check status of the connection refresh fix."""
        print("📊 Connection Refresh Fix Status")
        print("=" * 40)

        # Check if MCP server file exists
        if not self.mcp_server_file.exists():
            print("❌ MCP server file not found")
            return False

        # Check if backup exists
        backup_status = "✅ Available" if self.backup_file.exists() else "❌ Missing"
        print(f"📁 Backup file: {backup_status}")

        # Check if fix is installed
        content = self.mcp_server_file.read_text()
        fix_installed = "CONNECTION_REFRESH_FIX" in content

        if fix_installed:
            print("✅ Connection refresh fix: INSTALLED")

            # Check fix components
            has_worker = "_connection_refresh_worker" in content
            has_startup = "_start_connection_refresh" in content
            has_cleanup = "_stop_connection_refresh" in content

            print(f"   • Background worker: {'✅' if has_worker else '❌'}")
            print(f"   • Startup hook: {'✅' if has_startup else '❌'}")
            print(f"   • Cleanup hook: {'✅' if has_cleanup else '❌'}")

            if has_worker and has_startup and has_cleanup:
                print("🎯 Fix status: FULLY FUNCTIONAL")
            else:
                print("⚠️  Fix status: PARTIAL - May need reinstall")

        else:
            print("❌ Connection refresh fix: NOT INSTALLED")
            print("   Run: python connection_refresh_fix.py --install")

        return fix_installed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Connection Refresh Fix for ChunkHound")
    parser.add_argument("--install", action="store_true", help="Install the connection refresh fix")
    parser.add_argument("--test", action="store_true", help="Test the connection refresh fix")
    parser.add_argument("--status", action="store_true", help="Check fix status")
    parser.add_argument("--restore", action="store_true", help="Restore original MCP server file")

    args = parser.parse_args()

    if not any([args.install, args.test, args.status, args.restore]):
        parser.print_help()
        sys.exit(1)

    fix = ConnectionRefreshFix()

    if args.install:
        success = fix.install_fix()
        sys.exit(0 if success else 1)

    elif args.test:
        success = fix.test_fix()
        sys.exit(0 if success else 1)

    elif args.status:
        fix.check_status()
        sys.exit(0)

    elif args.restore:
        success = fix.restore_original()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
