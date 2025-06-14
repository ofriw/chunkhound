#!/usr/bin/env python3
"""
DuckDB Database Initialization Debug Script
Focused test to identify the specific database initialization issue causing MCP server startup failure.

Based on diagnostic results showing:
- Database Init fails with "not a valid DuckDB database file"
- Issue occurs with temporary file creation
- Root cause of MCP server startup failure
"""

import os
import sys
import tempfile
import duckdb
from pathlib import Path


def test_duckdb_basic():
    """Test 1: Basic DuckDB functionality"""
    print("=== TEST 1: Basic DuckDB ===")

    try:
        # Test in-memory database
        conn = duckdb.connect(':memory:')
        result = conn.execute('SELECT 1 as test').fetchone()
        conn.close()
        print(f"✅ In-memory DuckDB: {result}")
        return True
    except Exception as e:
        print(f"❌ In-memory DuckDB failed: {e}")
        return False


def test_duckdb_file_creation():
    """Test 2: DuckDB file database creation"""
    print("\n=== TEST 2: DuckDB File Creation ===")

    # Test with proper file creation
    test_db = Path("test_duckdb_init.db")

    try:
        # Clean up any existing file
        if test_db.exists():
            test_db.unlink()

        # Create new database file
        conn = duckdb.connect(str(test_db))
        conn.execute('CREATE TABLE test (id INTEGER)')
        conn.execute('INSERT INTO test VALUES (1)')
        result = conn.execute('SELECT * FROM test').fetchone()
        conn.close()

        print(f"✅ File database creation: {result}")
        print(f"   Database file size: {test_db.stat().st_size} bytes")

        return True

    except Exception as e:
        print(f"❌ File database creation failed: {e}")
        return False
    finally:
        # Cleanup
        if test_db.exists():
            test_db.unlink()


def test_tempfile_issue():
    """Test 3: Reproduce tempfile issue"""
    print("\n=== TEST 3: Tempfile Issue Reproduction ===")

    try:
        # This mimics the failing test from the component diagnostic
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_db_path = tmp.name

        print(f"Tempfile created: {tmp_db_path}")
        print(f"File exists: {Path(tmp_db_path).exists()}")
        print(f"File size: {Path(tmp_db_path).stat().st_size} bytes")

        # Try to connect to the tempfile
        conn = duckdb.connect(tmp_db_path)
        conn.execute('SELECT 1')
        conn.close()

        print("✅ Tempfile DuckDB connection successful")
        return True

    except Exception as e:
        print(f"❌ Tempfile DuckDB failed: {e}")
        print("   This reproduces the MCP server initialization failure!")
        return False
    finally:
        try:
            os.unlink(tmp_db_path)
        except:
            pass


def test_proper_tempfile():
    """Test 4: Proper temporary database creation"""
    print("\n=== TEST 4: Proper Temp Database ===")

    try:
        # Create temp directory and proper database file
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_db_path = Path(tmp_dir) / "test.db"

            # Create database properly
            conn = duckdb.connect(str(tmp_db_path))
            conn.execute('CREATE TABLE test (id INTEGER)')
            conn.execute('INSERT INTO test VALUES (42)')
            result = conn.execute('SELECT * FROM test').fetchone()
            conn.close()

            print(f"✅ Proper temp database: {result}")
            print(f"   Database file size: {tmp_db_path.stat().st_size} bytes")
            return True

    except Exception as e:
        print(f"❌ Proper temp database failed: {e}")
        return False


def test_existing_database():
    """Test 5: Test with existing .chunkhound.db"""
    print("\n=== TEST 5: Existing Database Test ===")

    db_path = Path(".chunkhound.db")

    if not db_path.exists():
        print("❌ .chunkhound.db does not exist")
        return False

    try:
        print(f"Database exists: {db_path.stat().st_size} bytes")

        # Test connection
        conn = duckdb.connect(str(db_path))

        # Test basic query
        tables = conn.execute("SHOW TABLES").fetchall()
        print(f"   Tables in database: {len(tables)}")

        # Test VSS extension
        try:
            conn.execute("LOAD vss")
            print("   VSS extension loaded successfully")
        except Exception as e:
            print(f"   VSS extension failed: {e}")

        conn.close()
        print("✅ Existing database connection successful")
        return True

    except Exception as e:
        print(f"❌ Existing database failed: {e}")
        return False


def test_duckdb_provider():
    """Test 6: Test actual DuckDBProvider class"""
    print("\n=== TEST 6: DuckDBProvider Class ===")

    # Add the chunkhound path to Python path for imports
    sys.path.insert(0, str(Path(__file__).parent))

    try:
        from providers.database.duckdb_provider import DuckDBProvider

        # Test with existing database
        db_path = Path(".chunkhound.db")
        if not db_path.exists():
            print("❌ .chunkhound.db required for this test")
            return False

        # Create provider
        provider = DuckDBProvider(str(db_path))

        # Test connection
        provider.connect()
        print("✅ DuckDBProvider connected")

        # Test query
        result = provider.execute("SELECT 1 as test")
        print(f"   Query result: {result}")

        # Test disconnect
        provider.disconnect()
        print("✅ DuckDBProvider disconnected")

        return True

    except Exception as e:
        print(f"❌ DuckDBProvider failed: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def main():
    """Run all DuckDB initialization tests"""
    print("ChunkHound DuckDB Initialization Diagnostic")
    print("=" * 50)

    tests = [
        ("Basic DuckDB", test_duckdb_basic),
        ("File Creation", test_duckdb_file_creation),
        ("Tempfile Issue", test_tempfile_issue),
        ("Proper Tempfile", test_proper_tempfile),
        ("Existing Database", test_existing_database),
        ("DuckDBProvider", test_duckdb_provider),
    ]

    results = {}
    critical_failure = None

    for test_name, test_func in tests:
        print(f"\nRunning {test_name}...")
        try:
            result = test_func()
            results[test_name] = result

            if not result and "Tempfile Issue" in test_name:
                critical_failure = "Tempfile database creation"

        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False

    # Summary
    print("\n" + "=" * 50)
    print("DUCKDB DIAGNOSTIC SUMMARY")
    print("=" * 50)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")

    # Root cause analysis
    print("\nROOT CAUSE ANALYSIS:")
    if critical_failure:
        print(f"🎯 IDENTIFIED: {critical_failure}")
        print("   The MCP server fails because tempfile.NamedTemporaryFile creates")
        print("   empty files that DuckDB cannot open as database files")
        print("\n   SOLUTION: Use proper database file creation instead of tempfiles")
    elif results.get("DuckDBProvider", False):
        print("✅ DuckDB works correctly - issue must be elsewhere")
    else:
        print("❓ Multiple DuckDB issues detected - investigation needed")

    # Recommendations
    if not results.get("Tempfile Issue", True):  # If tempfile test failed
        print("\nRECOMMENDATIONS:")
        print("1. Fix tempfile database creation in test code")
        print("2. Use proper database file paths instead of empty tempfiles")
        print("3. Ensure database files are properly initialized before connection")

    return 0 if not critical_failure else 1


if __name__ == "__main__":
    sys.exit(main())
