#!/usr/bin/env python3
"""
CLI Database Verification Script

This script checks what database the CLI is using and prints information
about it to help debug the search tools QA bug.
"""

import os
import sys
from pathlib import Path

# Add the current directory to the path
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Try importing the Database class
    from chunkhound.database import Database

    # Import service layer components if available
    try:
        from registry import create_indexing_coordinator, configure_registry
    except ImportError:
        create_indexing_coordinator = None
        configure_registry = None
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this script from the chunkhound directory")
    sys.exit(1)


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60)


def check_database_file(db_path):
    """Check database file existence and details."""
    print_section("Database File Check")

    path = Path(db_path)
    print(f"Database path: {path}")
    print(f"Absolute path: {path.absolute()}")

    if path.exists():
        print(f"✅ File exists")
        print(f"File size: {path.stat().st_size:,} bytes")
        print(f"Last modified: {path.stat().st_mtime}")
    else:
        print(f"❌ File does not exist")

    # Check parent directory
    parent = path.parent
    print(f"\nParent directory: {parent}")
    print(f"Parent exists: {parent.exists()}")

    if parent.exists():
        # List other database files in the same directory
        print("\nOther database files in same directory:")
        for file in parent.glob("*.duckdb*"):
            if file != path:
                print(f"  - {file.name} ({file.stat().st_size:,} bytes)")


def check_database_connection(db_path):
    """Check database connection and content."""
    print_section("Database Connection Check")

    try:
        # Create database instance
        db = Database(db_path)
        print(f"Database instance created")

        # Connect to database
        db.connect()
        print(f"✅ Connected to database")

        # Check stats
        stats = db.get_stats()
        print(f"\nDatabase statistics:")
        print(f"  Files indexed: {stats.get('files', 0):,}")
        print(f"  Chunks stored: {stats.get('chunks', 0):,}")
        print(f"  Embeddings: {stats.get('embeddings', 0):,}")

        # Check if test files are indexed
        print("\nChecking for QA test files:")
        qa_file_patterns = [
            "qa_search_test_unique_content_2025_06_14.py",
            "qa_test_unique_content_2025_06_13.py",
            "qa_test_new_file_2025_06_13.py"
        ]

        for pattern in qa_file_patterns:
            # Try to find files with this name in the database
            if hasattr(db, "search_regex"):
                results = db.search_regex(pattern=pattern, limit=1)
                found = len(results) > 0
            else:
                # Fallback method
                found = False

            print(f"  {pattern}: {'✅ Found' if found else '❌ Not found'}")

        # Disconnect
        db.disconnect()
        print("\nDatabase disconnected")

    except Exception as e:
        print(f"❌ Database connection error: {e}")
        import traceback
        traceback.print_exc()


def check_with_service_layer(db_path):
    """Check database using the service layer if available."""
    if not create_indexing_coordinator:
        print("\nService layer not available, skipping service layer check")
        return

    print_section("Service Layer Check")

    try:
        # Configure registry
        config = {
            'database': {
                'path': str(db_path),
                'type': 'duckdb'
            },
            'embedding': {
                'batch_size': 50,
                'max_concurrent_batches': 3,
            }
        }

        configure_registry(config)

        # Create service
        indexing_coordinator = create_indexing_coordinator()
        print(f"✅ Created indexing coordinator service")

        # Get stats
        import asyncio
        stats = asyncio.run(indexing_coordinator.get_stats())

        print(f"\nService layer statistics:")
        print(f"  Files indexed: {stats.get('files', 0):,}")
        print(f"  Chunks stored: {stats.get('chunks', 0):,}")
        print(f"  Embeddings: {stats.get('embeddings', 0):,}")

    except Exception as e:
        print(f"❌ Service layer error: {e}")
        import traceback
        traceback.print_exc()


def check_environment_variables():
    """Check relevant environment variables."""
    print_section("Environment Variables")

    relevant_vars = [
        "CHUNKHOUND_DB_PATH",
        "CHUNKHOUND_MCP_MODE",
        "OPENAI_API_KEY",
        "PYTHONPATH"
    ]

    for var in relevant_vars:
        value = os.environ.get(var, "(not set)")
        if var == "OPENAI_API_KEY" and value != "(not set)":
            # Mask API key for security
            value = value[:4] + "..." + value[-4:] if len(value) > 8 else "****"
        print(f"{var}: {value}")


def main():
    """Main function."""
    print_section("ChunkHound CLI Database Verification")
    print("This script checks what database the CLI is using")

    # Get default and custom database paths
    default_db = Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"
    env_db = os.environ.get("CHUNKHOUND_DB_PATH")
    local_db = Path(".chunkhound.db")

    # Check environment variables
    check_environment_variables()

    # Check specified database path if set
    if env_db:
        print(f"\nUsing database path from CHUNKHOUND_DB_PATH: {env_db}")
        check_database_file(env_db)
        check_database_connection(env_db)
        check_with_service_layer(env_db)

    # Check local database if it exists
    if local_db.exists():
        print(f"\nLocal database found: {local_db}")
        check_database_file(local_db)
        check_database_connection(local_db)
        check_with_service_layer(local_db)

    # Check default database
    print(f"\nChecking default database: {default_db}")
    check_database_file(default_db)
    check_database_connection(default_db)
    check_with_service_layer(default_db)

    print("\nVerification complete!")


if __name__ == "__main__":
    main()
