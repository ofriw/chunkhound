#!/usr/bin/env python3
"""
Direct Database Real-time Indexing Test

Based on investigation findings from realtime-indexing-file-watcher-null-2025-06-14.md:
- MCP server binary is running with --watch flag
- Need to test if files are actually being indexed by checking database directly
- This bypasses CLI issues and tests the core functionality

Test approach:
1. Create test file with unique markers
2. Wait for indexing
3. Query database directly for the markers
4. Determine if real-time indexing is working
"""

import os
import sys
import time
import uuid
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

def log_with_timestamp(message, level="INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {level}: {message}")

def find_database_path():
    """Find the database path used by the running MCP server"""
    try:
        # Check common database locations
        possible_paths = [
            Path.home() / ".cache" / "chunkhound" / "chunks.duckdb",
            Path.cwd() / "chunks.duckdb",
            Path.cwd() / ".chunkhound" / "chunks.duckdb",
        ]

        for db_path in possible_paths:
            if db_path.exists():
                log_with_timestamp(f"Found database at: {db_path}")
                return db_path

        log_with_timestamp("No database found in common locations", "WARNING")
        return None

    except Exception as e:
        log_with_timestamp(f"Error finding database: {e}", "ERROR")
        return None

def query_database_for_content(db_path, search_term):
    """Query database for specific content"""
    try:
        # Try DuckDB first
        try:
            import duckdb
            conn = duckdb.connect(str(db_path))

            # Query for content containing the search term
            query = """
            SELECT file_path, chunk_text, chunk_type
            FROM chunks
            WHERE chunk_text LIKE ?
            OR file_path LIKE ?
            LIMIT 10
            """

            results = conn.execute(query, [f"%{search_term}%", f"%{search_term}%"]).fetchall()
            conn.close()

            return results

        except ImportError:
            log_with_timestamp("DuckDB not available, trying SQLite", "WARNING")

        # Fallback to SQLite
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Query for content containing the search term
        query = """
        SELECT file_path, chunk_text, chunk_type
        FROM chunks
        WHERE chunk_text LIKE ?
        OR file_path LIKE ?
        LIMIT 10
        """

        cursor.execute(query, (f"%{search_term}%", f"%{search_term}%"))
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        log_with_timestamp(f"Database query failed: {e}", "ERROR")
        return None

def create_test_file(content, filename=None):
    """Create a test file with unique content"""
    if filename is None:
        unique_id = str(uuid.uuid4())[:8]
        filename = f"realtime_test_{unique_id}_{int(time.time())}.py"

    test_file = Path(filename)
    test_file.write_text(content)
    log_with_timestamp(f"Created test file: {test_file}")
    return test_file

def test_realtime_indexing():
    """Test real-time indexing by directly querying database"""

    log_with_timestamp("=== Direct Database Real-time Indexing Test ===")

    # Find database
    db_path = find_database_path()
    if not db_path:
        log_with_timestamp("❌ Cannot find database path", "ERROR")
        return False

    # Check if MCP server is running
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )

        if "chunkhound" in result.stdout and "--watch" in result.stdout:
            log_with_timestamp("✅ MCP server with --watch flag is running", "SUCCESS")
        else:
            log_with_timestamp("❌ MCP server with --watch flag not found", "ERROR")
            return False

    except Exception as e:
        log_with_timestamp(f"Process check failed: {e}", "ERROR")
        return False

    # Create unique test markers
    test_marker_1 = f"REALTIME_TEST_MARKER_{uuid.uuid4().hex[:16]}"
    test_marker_2 = f"REALTIME_TEST_FUNCTION_{uuid.uuid4().hex[:16]}"
    test_marker_3 = f"REALTIME_TEST_CLASS_{uuid.uuid4().hex[:16]}"

    log_with_timestamp(f"Test markers: {test_marker_1}, {test_marker_2}, {test_marker_3}")

    # Test file content
    test_content = f'''
"""Test file for real-time indexing verification"""

def {test_marker_2}():
    """Test function with unique marker"""
    marker_value = "{test_marker_1}"
    return marker_value

class {test_marker_3}:
    """Test class with unique marker"""

    def __init__(self):
        self.marker = "{test_marker_1}"

    def get_marker(self):
        return self.marker

# Comment with marker: {test_marker_1}
'''

    # Create test file
    test_file = create_test_file(test_content)

    try:
        # Wait for indexing
        log_with_timestamp("Waiting 15 seconds for real-time indexing...")
        time.sleep(15)

        # Test database queries
        results = {}

        for i, marker in enumerate([test_marker_1, test_marker_2, test_marker_3], 1):
            log_with_timestamp(f"Querying database for marker {i}: {marker}")

            db_results = query_database_for_content(db_path, marker)

            if db_results is not None:
                found = len(db_results) > 0
                results[marker] = found
                log_with_timestamp(f"Marker {i} found in database: {found}")

                if found:
                    log_with_timestamp(f"Marker {i} database entries: {len(db_results)}")
                    # Show first result for debugging
                    if db_results:
                        first_result = db_results[0]
                        log_with_timestamp(f"First match: {first_result[0]} ({first_result[2]})")
            else:
                results[marker] = False
                log_with_timestamp(f"Marker {i} database query failed")

        # Also check if the test file itself is indexed
        log_with_timestamp(f"Checking if test file is indexed: {test_file.name}")
        file_results = query_database_for_content(db_path, test_file.name)
        file_indexed = file_results is not None and len(file_results) > 0
        log_with_timestamp(f"Test file indexed: {file_indexed}")

        # Evaluate results
        found_count = sum(results.values())
        total_count = len(results)

        log_with_timestamp(f"=== RESULTS ===")
        log_with_timestamp(f"Found {found_count}/{total_count} markers in database")
        log_with_timestamp(f"Test file indexed: {file_indexed}")

        if found_count == total_count and file_indexed:
            log_with_timestamp("✅ HYPOTHESIS DISPROVEN: Real-time indexing is working", "SUCCESS")
            log_with_timestamp("   → All test markers found in database", "SUCCESS")
            log_with_timestamp("   → Test file is properly indexed", "SUCCESS")
            return True
        elif found_count == 0 and not file_indexed:
            log_with_timestamp("🎯 HYPOTHESIS CONFIRMED: Real-time indexing is broken", "CRITICAL")
            log_with_timestamp("   → No test markers found in database", "CRITICAL")
            log_with_timestamp("   → Test file not indexed", "CRITICAL")
            return False
        else:
            log_with_timestamp("⚠️  PARTIAL RESULTS: Real-time indexing partially working", "WARNING")
            log_with_timestamp(f"   → {found_count}/{total_count} markers found", "WARNING")
            log_with_timestamp(f"   → File indexed: {file_indexed}", "WARNING")
            return False

    finally:
        # Cleanup
        try:
            if test_file.exists():
                test_file.unlink()
                log_with_timestamp(f"Cleaned up test file: {test_file}")
        except Exception as e:
            log_with_timestamp(f"Cleanup failed: {e}", "ERROR")

def main():
    """Run the direct database real-time indexing test"""

    try:
        # Change to chunkhound directory
        os.chdir(Path(__file__).parent)

        success = test_realtime_indexing()

        if success:
            log_with_timestamp("🎉 TEST PASSED: Real-time indexing is working")
        else:
            log_with_timestamp("💥 TEST FAILED: Real-time indexing is not working")

        return success

    except KeyboardInterrupt:
        log_with_timestamp("⚠️  Test interrupted by user", "WARNING")
        return False
    except Exception as e:
        log_with_timestamp(f"💥 Test crashed: {e}", "ERROR")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
