#!/usr/bin/env python3
"""
Minimal test script for the query state inconsistency bug.

This script directly tests the hypothesis that database reconnection
doesn't properly reset query state, and that explicit transaction control fixes it.
"""

import os
import sys
import time
import tempfile
from pathlib import Path
import duckdb

# Define test data
TEST_CONTENT = """
def test_function():
    '''This is a test function with a unique marker: UNIQUE_TEST_MARKER'''
    return "UNIQUE_TEST_MARKER"
"""

def setup_test_database():
    """Create a test database with known content."""
    print("\n🔧 Setting up test database...")

    # Create temp dir and database
    temp_dir = Path(tempfile.mkdtemp(prefix="ch_query_state_test_"))
    db_path = temp_dir / "test.db"
    test_file = temp_dir / "test_file.py"

    # Create test file
    test_file.write_text(TEST_CONTENT)
    print(f"Created test file: {test_file}")

    # Create database with schema
    conn = duckdb.connect(str(db_path))

    # Create minimal schema
    conn.execute("""
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            path VARCHAR,
            name VARCHAR,
            extension VARCHAR,
            language VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            chunk_type VARCHAR,
            code VARCHAR,
            start_line INTEGER,
            end_line INTEGER,
            language VARCHAR,
            FOREIGN KEY (file_id) REFERENCES files(id)
        )
    """)

    # Insert test data
    conn.execute("""
        INSERT INTO files (id, path, name, extension, language)
        VALUES (1, ?, 'test_file.py', 'py', 'python')
    """, [str(test_file)])

    conn.execute("""
        INSERT INTO chunks (id, file_id, chunk_type, code, start_line, end_line, language)
        VALUES (1, 1, 'function', ?, 1, 4, 'python')
    """, [TEST_CONTENT])

    # Verify data
    count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"Database created with {count} chunks")

    conn.close()
    return temp_dir, db_path

def test_standard_reconnect(db_path):
    """Test standard reconnection without transaction control."""
    print("\n🔄 TEST 1: Standard Reconnection")

    # Initial connection
    print("Initial connection...")
    conn = duckdb.connect(str(db_path))

    # Verify initial state
    initial_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"Initial connection sees {initial_count} chunks")

    # Search for unique marker
    initial_results = conn.execute(
        "SELECT * FROM chunks WHERE code LIKE '%UNIQUE_TEST_MARKER%'"
    ).fetchall()
    print(f"Initial search found {len(initial_results)} results")

    # Disconnect
    print("Disconnecting...")
    conn.close()

    # Reconnect
    print("Reconnecting...")
    conn = duckdb.connect(str(db_path))

    # Search again
    reconnect_results = conn.execute(
        "SELECT * FROM chunks WHERE code LIKE '%UNIQUE_TEST_MARKER%'"
    ).fetchall()
    print(f"After standard reconnect: {len(reconnect_results)} results")

    # Close connection
    conn.close()

    return len(initial_results), len(reconnect_results)

def test_transaction_reconnect(db_path):
    """Test reconnection with explicit transaction control."""
    print("\n🔒 TEST 2: Transaction-Aware Reconnection")

    # Initial connection
    print("Initial connection...")
    conn = duckdb.connect(str(db_path))

    # Verify initial state
    initial_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"Initial connection sees {initial_count} chunks")

    # Search for unique marker
    initial_results = conn.execute(
        "SELECT * FROM chunks WHERE code LIKE '%UNIQUE_TEST_MARKER%'"
    ).fetchall()
    print(f"Initial search found {len(initial_results)} results")

    # Disconnect
    print("Disconnecting...")
    conn.close()

    # Reconnect with transaction
    print("Reconnecting with transaction control...")
    conn = duckdb.connect(str(db_path))

    # Begin transaction
    print("Beginning transaction...")
    conn.execute("BEGIN TRANSACTION")

    # Search within transaction
    txn_results = conn.execute(
        "SELECT * FROM chunks WHERE code LIKE '%UNIQUE_TEST_MARKER%'"
    ).fetchall()
    print(f"Search within transaction: {len(txn_results)} results")

    # Commit transaction
    print("Committing transaction...")
    conn.execute("COMMIT")

    # Search after transaction
    post_txn_results = conn.execute(
        "SELECT * FROM chunks WHERE code LIKE '%UNIQUE_TEST_MARKER%'"
    ).fetchall()
    print(f"Search after transaction: {len(post_txn_results)} results")

    # Close connection
    conn.close()

    return len(initial_results), len(txn_results), len(post_txn_results)

def cleanup(temp_dir):
    """Clean up test resources."""
    print("\n🧹 Cleaning up...")
    import shutil
    shutil.rmtree(temp_dir)
    print(f"Removed test directory: {temp_dir}")

def main():
    """Run the minimal test."""
    print("=" * 60)
    print("QUERY STATE INCONSISTENCY MINIMAL TEST")
    print("=" * 60)

    try:
        # Setup
        temp_dir, db_path = setup_test_database()

        # Test standard reconnection
        std_initial, std_after = test_standard_reconnect(db_path)

        # Test transaction reconnection
        txn_initial, txn_during, txn_after = test_transaction_reconnect(db_path)

        # Analyze results
        print("\n" + "=" * 60)
        print("TEST RESULTS:")
        print("=" * 60)
        print(f"Standard reconnect: {std_initial} → {std_after} results")
        print(f"Transaction reconnect: {txn_initial} → {txn_during} → {txn_after} results")

        # Determine if hypothesis is validated
        hypothesis_validated = (
            (std_initial > 0) and  # Initial data exists
            (std_after == 0) and   # Standard reconnect loses data
            (txn_during > 0)       # Transaction reconnect sees data
        )

        if hypothesis_validated:
            print("\n✅ HYPOTHESIS VALIDATED:")
            print("   Standard reconnection loses query state")
            print("   Transaction control fixes the issue")
            print("\nRECOMMENDED FIX: Add explicit transaction control to:")
            print("1. Database.reconnect() method")
            print("2. All search methods")
        else:
            if std_after > 0 and txn_during > 0:
                print("\n❓ HYPOTHESIS NOT VALIDATED:")
                print("   Both standard and transaction reconnections work correctly")
                print("   Issue may be intermittent or environment-dependent")
            else:
                print("\n❓ INCONCLUSIVE RESULTS:")
                print("   Test behavior doesn't match hypothesis expectations")
                print("   Further investigation needed")

        # Update notes
        mem_dir = Path(".mem")
        if mem_dir.exists():
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            with open(mem_dir / "query-state-minimal-test-results.md", "w") as f:
                f.write(f"Title: Query State Minimal Test Results\n")
                f.write(f"Created: {timestamp}\n")
                f.write(f"Updated: {timestamp}\n")
                f.write(f"Tags: [database][bug][query_state][test]\n\n")
                f.write(f"## Minimal Test Results\n\n")
                f.write(f"Standard reconnect: {std_initial} → {std_after} results\n")
                f.write(f"Transaction reconnect: {txn_initial} → {txn_during} → {txn_after} results\n\n")
                f.write(f"Hypothesis {'VALIDATED' if hypothesis_validated else 'NOT VALIDATED'}\n")

    except Exception as e:
        import traceback
        print(f"\n❌ Test failed: {e}")
        traceback.print_exc()
    finally:
        # Clean up
        if 'temp_dir' in locals():
            cleanup(temp_dir)

if __name__ == "__main__":
    main()
