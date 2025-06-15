#!/usr/bin/env python3
"""
MCP Database Verification Script

This script verifies what database the MCP server is using and helps debug
the search tools QA bug by checking database paths and connection states.
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60)


def get_db_paths():
    """Get all possible database paths."""
    # Default path
    default_db = Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"

    # Local path
    local_db = Path(".chunkhound.db").absolute()

    # Environment variable path
    env_db = os.environ.get("CHUNKHOUND_DB_PATH")
    env_db_path = Path(env_db).absolute() if env_db else None

    paths = {
        "default": str(default_db),
        "local": str(local_db),
        "env": str(env_db_path) if env_db_path else None
    }

    return paths


def check_database_files(db_paths):
    """Check database files existence and details."""
    print_section("Database Files Check")

    for name, path in db_paths.items():
        if not path:
            continue

        print(f"\n{name.upper()} DATABASE:")
        print(f"Path: {path}")

        path_obj = Path(path)
        if path_obj.exists():
            size_mb = path_obj.stat().st_size / (1024 * 1024)
            print(f"✅ File exists ({size_mb:.2f} MB)")
            print(f"Last modified: {time.ctime(path_obj.stat().st_mtime)}")
        else:
            print(f"❌ File does not exist")


def create_mcp_debug_script():
    """Create a temporary script to run the MCP server with debug logging."""
    script = """
import os
import sys
from pathlib import Path

# Set up path to find chunkhound module
sys.path.insert(0, str(Path(__file__).parent))

# Print debugging information
print("MCP_DEBUG: Starting debug session")
print(f"MCP_DEBUG: Python executable: {sys.executable}")
print(f"MCP_DEBUG: Working directory: {os.getcwd()}")
print(f"MCP_DEBUG: CHUNKHOUND_DB_PATH: {os.environ.get('CHUNKHOUND_DB_PATH', 'Not set')}")

# Import database module
try:
    from chunkhound.database import Database
    print("MCP_DEBUG: Successfully imported Database class")
except ImportError as e:
    print(f"MCP_DEBUG: Import error: {e}")
    sys.exit(1)

# Check database paths
default_db = Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"
local_db = Path(".chunkhound.db").absolute()
env_db = os.environ.get("CHUNKHOUND_DB_PATH")
env_db_path = Path(env_db) if env_db else None

print(f"MCP_DEBUG: Default DB path: {default_db}")
print(f"MCP_DEBUG: Local DB path: {local_db}")
print(f"MCP_DEBUG: Env DB path: {env_db_path}")

# Determine which database to use (same logic as MCP server)
db_path = Path(os.environ.get("CHUNKHOUND_DB_PATH", Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"))
print(f"MCP_DEBUG: Selected DB path: {db_path}")
print(f"MCP_DEBUG: DB exists: {db_path.exists()}")
if db_path.exists():
    print(f"MCP_DEBUG: DB size: {db_path.stat().st_size / (1024 * 1024):.2f} MB")

# Try to connect to the database
try:
    print(f"MCP_DEBUG: Connecting to database at {db_path}")
    db = Database(db_path)
    db.connect()
    print("MCP_DEBUG: Connected successfully")

    # Get stats
    stats = db.get_stats()
    print(f"MCP_DEBUG: Database stats: {stats}")

    # Try search
    if hasattr(db, 'search_regex'):
        results = db.search_regex(pattern="qa_test", limit=5)
        print(f"MCP_DEBUG: Search results: {len(results)} items found")
        if results:
            print(f"MCP_DEBUG: First result: {results[0]}")

    db.disconnect()
    print("MCP_DEBUG: Database disconnected")

except Exception as e:
    print(f"MCP_DEBUG: Database error: {e}")
    import traceback
    traceback.print_exc()

print("MCP_DEBUG: Debug session complete")
    """

    with NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp:
        temp.write(script)
        return temp.name


def run_mcp_debug(script_path, db_path=None):
    """Run the MCP debug script with the specified database path."""
    print_section("MCP Server Database Debug")

    env = os.environ.copy()
    if db_path:
        env["CHUNKHOUND_DB_PATH"] = db_path
        print(f"Setting CHUNKHOUND_DB_PATH to: {db_path}")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )

        print(result.stdout)

        if result.stderr:
            print("\nERROR OUTPUT:")
            print(result.stderr)

    except subprocess.TimeoutExpired:
        print("❌ Process timed out after 10 seconds")
    except Exception as e:
        print(f"❌ Error running debug script: {e}")
    finally:
        # Clean up temporary script
        try:
            os.unlink(script_path)
        except:
            pass


def test_mcp_launcher(db_path=None):
    """Test the MCP launcher with specified database path."""
    print_section("MCP Launcher Test")

    launcher_path = Path("mcp_launcher.py")
    if not launcher_path.exists():
        print(f"❌ MCP launcher not found at {launcher_path}")
        return

    env = os.environ.copy()
    if db_path:
        env["CHUNKHOUND_DB_PATH"] = db_path
        print(f"Setting CHUNKHOUND_DB_PATH to: {db_path}")

    cmd = [sys.executable, str(launcher_path)]
    if db_path:
        cmd.extend(["--db", db_path])

    print(f"Running command: {' '.join(cmd)}")

    try:
        # Start process but kill it after a short time
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait a bit to capture startup output
        time.sleep(1)

        # Kill the process
        process.terminate()

        # Get output
        stdout, stderr = process.communicate(timeout=2)

        print("\nSTANDARD OUTPUT:")
        print(stdout)

        if stderr:
            print("\nERROR OUTPUT:")
            print(stderr)

    except subprocess.TimeoutExpired:
        print("❌ Process timed out")
        process.kill()
    except Exception as e:
        print(f"❌ Error running MCP launcher: {e}")


def main():
    """Main function."""
    print_section("ChunkHound MCP Database Verification")
    print("This script verifies what database the MCP server is using")

    # Get database paths
    db_paths = get_db_paths()
    print(f"Possible database paths:")
    for name, path in db_paths.items():
        print(f"  {name}: {path}")

    # Check database files
    check_database_files(db_paths)

    # Create and run MCP debug script for each database
    debug_script = create_mcp_debug_script()
    print(f"Created debug script: {debug_script}")

    # Test with local database
    print_section("Testing with LOCAL database")
    run_mcp_debug(debug_script, db_paths["local"])

    # Test with default database
    print_section("Testing with DEFAULT database")
    run_mcp_debug(debug_script, db_paths["default"])

    # Test MCP launcher
    test_mcp_launcher(db_paths["local"])

    print("\nVerification complete!")


if __name__ == "__main__":
    main()
