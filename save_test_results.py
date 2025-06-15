#!/usr/bin/env python3
"""
Simplified query state inconsistency test that saves results to a file.

This script tests the hypothesis that the database connection query state
inconsistency bug is related to transaction state not being properly reset
during reconnection.
"""

import os
import sys
import time
import tempfile
import json
import traceback
from pathlib import Path

# Add project directory to path
project_dir = Path(__file__).parent
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

# Import required components
try:
    import duckdb
except ImportError:
    print("Error: DuckDB not installed. Please install with: pip install duckdb")
    sys.exit(1)


def setup_test_database():
    """Create a test database with known content."""
    print("Setting up test database...")

    # Create temp dir and database
    temp_dir = Path(tempfile.mkdtemp(prefix="ch_query_state_test_"))
    db_path = temp_dir / "test.db"

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
        VALUES (1, '/test/file.py', 'file.py', 'py', 'python')
    """)

    conn.execute("""
        INSERT INTO chunks (id, file_id, chunk_type, code, start_line, end_line, language)
        VALUES (1, 1, 'function', 'def test_function():\n    return "UNIQUE_TEST_MARKER"', 1, 2, 'python')
    """)

    # Verify data
    count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"Database created with {count} chunks")

    conn.close()
    return temp_dir, db_path


def test_standard_reconnect(db_path):
    """Test standard reconnection without transaction control."""
    print("TEST 1: Standard Reconnection")

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
    print("TEST 2: Transaction-Aware Reconnection")

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


def test_modified_database(db_path):
    """Test behavior with a database modified after connection is established."""
    print("TEST 3: Modified Database Test")

    # First connection (simulating MCP server)
    print("Creating first connection (MCP server)...")
    conn1 = duckdb.connect(str(db_path))

    # Initial check
    initial_count = conn1.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"First connection sees {initial_count} chunks")

    # Second connection (simulating CLI)
    print("Creating second connection (CLI)...")
    conn2 = duckdb.connect(str(db_path))

    # Add new content via second connection
    print("Adding new content via second connection...")
    conn2.execute("""
        INSERT INTO chunks (id, file_id, chunk_type, code, start_line, end_line, language)
        VALUES (2, 1, 'function', 'def new_function():\n    return "NEW_MARKER"', 4, 5, 'python')
    """)

    # Verify content in second connection
    cli_count = conn2.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"Second connection sees {cli_count} chunks")
    conn2.close()

    # Check if first connection sees new content
    direct_count = conn1.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"First connection direct check sees {direct_count} chunks")

    # Reconnect first connection
    print("Reconnecting first connection...")
    conn1.close()
    conn1 = duckdb.connect(str(db_path))

    # Check after standard reconnect
    std_reconnect_count = conn1.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"After standard reconnect: {std_reconnect_count} chunks")
    conn1.close()

    # Reconnect with transaction
    print("Reconnecting with transaction...")
    conn1 = duckdb.connect(str(db_path))
    conn1.execute("BEGIN TRANSACTION")
    txn_reconnect_count = conn1.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn1.execute("COMMIT")
    print(f"After transaction reconnect: {txn_reconnect_count} chunks")
    conn1.close()

    return {
        "initial": initial_count,
        "cli": cli_count,
        "direct": direct_count,
        "std_reconnect": std_reconnect_count,
        "txn_reconnect": txn_reconnect_count
    }


def save_results(results, file_path):
    """Save test results to a file."""
    with open(file_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {file_path}")


def main():
    """Run the test and save results."""
    try:
        results = {}

        # Setup
        temp_dir, db_path = setup_test_database()

        try:
            # Standard reconnect test
            std_initial, std_after = test_standard_reconnect(db_path)
            results["standard_reconnect"] = {
                "initial": std_initial,
                "after": std_after
            }

            # Transaction reconnect test
            txn_initial, txn_during, txn_after = test_transaction_reconnect(db_path)
            results["transaction_reconnect"] = {
                "initial": txn_initial,
                "during_transaction": txn_during,
                "after_transaction": txn_after
            }

            # Modified database test
            results["modified_database"] = test_modified_database(db_path)

            # Analysis
            hypothesis_validated = (
                (std_initial > 0 and std_after == 0 and txn_during > 0) or
                (results["modified_database"]["direct"] < results["modified_database"]["cli"] and
                 results["modified_database"]["txn_reconnect"] == results["modified_database"]["cli"])
            )

            results["hypothesis_validated"] = hypothesis_validated

            # Save results
            output_file = Path("query_state_test_results.json")
            save_results(results, output_file)

            # Generate summary
            summary = f"""
QUERY STATE INCONSISTENCY TEST RESULTS

Standard reconnect: {std_initial} → {std_after} results
Transaction reconnect: {txn_initial} → {txn_during} → {txn_after} results

Modified database test:
- Initial connection: {results["modified_database"]["initial"]} chunks
- After CLI adds content: {results["modified_database"]["cli"]} chunks
- Direct check: {results["modified_database"]["direct"]} chunks
- Standard reconnect: {results["modified_database"]["std_reconnect"]} chunks
- Transaction reconnect: {results["modified_database"]["txn_reconnect"]} chunks

CONCLUSION: Hypothesis {"VALIDATED" if hypothesis_validated else "NOT VALIDATED"}
"""
            print(summary)

            # Save summary
            with open("query_state_test_summary.txt", "w") as f:
                f.write(summary)

        finally:
            # Clean up
            import shutil
            shutil.rmtree(temp_dir)
            print(f"Cleaned up test directory: {temp_dir}")

    except Exception as e:
        print(f"Test failed: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
