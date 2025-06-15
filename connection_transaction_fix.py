#!/usr/bin/env python3
"""
Test patch for database connection query state inconsistency bug.

This module provides a patch that replaces the database.reconnect() method
with an enhanced version that includes explicit transaction control to ensure
query state is properly reset after reconnection.

The hypothesis is that when reconnecting to the database, the query state
is not properly reset, causing searches to return empty results despite the
database containing indexed content.

Usage:
    import connection_transaction_fix
    connection_transaction_fix.apply_patches()
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable
import functools

# Add project directory to path if needed
project_dir = Path(__file__).parent
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

# Import Database classes for patching
from chunkhound.database import Database
from providers.database.duckdb_provider import DuckDBProvider


# Original methods to be stored for reference
original_database_reconnect = None
original_provider_connect = None


def enhanced_database_reconnect(self) -> bool:
    """
    Enhanced reconnect method with explicit transaction control.

    This patched version ensures query state is properly reset by:
    1. Fully disconnecting from the database
    2. Reconnecting with a clean connection
    3. Explicitly starting a new transaction
    4. Validating the connection with a test query
    5. Committing the transaction to ensure clean state

    Returns:
        bool: True if reconnection successful, False otherwise
    """
    print(f"PATCH: Enhanced reconnect called for database at {self.db_path}")

    try:
        # Fully disconnect first
        if hasattr(self, "_provider") and self._provider:
            self._provider.disconnect()
        self.connection = None

        # Brief pause to ensure clean reconnection
        time.sleep(0.1)

        # Reconnect with the enhanced provider method
        if hasattr(self, "_provider") and self._provider:
            self._provider.connect()
            self.connection = self._provider.connection

            # Validate connection with explicit transaction and test query
            if self.connection:
                try:
                    # Begin a new transaction
                    self.connection.execute("BEGIN TRANSACTION")

                    # Execute a test query to ensure connection works
                    test_result = self.connection.execute("SELECT COUNT(*) FROM chunks").fetchone()
                    chunk_count = test_result[0] if test_result else 0
                    print(f"PATCH: Reconnected successfully, found {chunk_count} chunks")

                    # Commit the transaction to ensure clean state
                    self.connection.execute("COMMIT")

                    # Log database stats after reconnection
                    try:
                        stats = self.get_stats()
                        print(f"PATCH: Database stats after reconnect: {stats}")
                    except Exception as stats_e:
                        print(f"PATCH: Failed to get stats after reconnect: {stats_e}")

                except Exception as txn_e:
                    print(f"PATCH: Transaction validation failed: {txn_e}")
                    # Try to clean up if transaction fails
                    try:
                        self.connection.execute("ROLLBACK")
                    except:
                        pass

            return self.connection is not None
        else:
            print("PATCH: No provider available for reconnection")
            return False

    except Exception as e:
        print(f"PATCH: Enhanced reconnect failed: {e}")
        return False


def enhanced_provider_connect(self) -> None:
    """
    Enhanced connect method for DuckDBProvider with explicit transaction control.

    This patched version adds transaction validation to ensure the connection
    is fully functional and query state is clean.
    """
    # Call the original connect method first
    original_provider_connect(self)

    # Additional validation with transaction control
    if self.connection is not None:
        try:
            # Begin a test transaction
            self.connection.execute("BEGIN TRANSACTION")

            # Run a test query to verify the connection
            test_result = self.connection.execute("SELECT 1").fetchone()
            if test_result and test_result[0] == 1:
                print("PATCH: Provider connection validated with test query")

            # Commit the transaction
            self.connection.execute("COMMIT")
        except Exception as e:
            print(f"PATCH: Provider connect validation failed: {e}")
            try:
                # Try to rollback if transaction failed
                self.connection.execute("ROLLBACK")
            except:
                pass


def enhanced_search_regex(original_method):
    """
    Decorator to enhance search_regex with explicit transaction control.

    This ensures each search operation has a clean query state.
    """
    @functools.wraps(original_method)
    def wrapper(self, *args, **kwargs):
        print("PATCH: Enhanced search_regex with transaction control")

        # Skip transaction control if no connection
        if not hasattr(self, "connection") or self.connection is None:
            return original_method(self, *args, **kwargs)

        try:
            # Begin a new transaction
            self.connection.execute("BEGIN TRANSACTION")

            # Execute the search within the transaction
            result = original_method(self, *args, **kwargs)

            # Commit the transaction
            self.connection.execute("COMMIT")

            return result

        except Exception as e:
            print(f"PATCH: Enhanced search_regex failed: {e}")
            # Try to rollback the transaction
            try:
                self.connection.execute("ROLLBACK")
            except:
                pass
            # Re-raise the exception
            raise

    return wrapper


def enhanced_search_semantic(original_method):
    """
    Decorator to enhance search_semantic with explicit transaction control.

    This ensures each search operation has a clean query state.
    """
    @functools.wraps(original_method)
    def wrapper(self, *args, **kwargs):
        print("PATCH: Enhanced search_semantic with transaction control")

        # Skip transaction control if no connection
        if not hasattr(self, "connection") or self.connection is None:
            return original_method(self, *args, **kwargs)

        try:
            # Begin a new transaction
            self.connection.execute("BEGIN TRANSACTION")

            # Execute the search within the transaction
            result = original_method(self, *args, **kwargs)

            # Commit the transaction
            self.connection.execute("COMMIT")

            return result

        except Exception as e:
            print(f"PATCH: Enhanced search_semantic failed: {e}")
            # Try to rollback the transaction
            try:
                self.connection.execute("ROLLBACK")
            except:
                pass
            # Re-raise the exception
            raise

    return wrapper


def enhanced_get_stats(original_method):
    """
    Decorator to enhance get_stats with explicit transaction control.

    This ensures the stats reflect the current database state.
    """
    @functools.wraps(original_method)
    def wrapper(self, *args, **kwargs):
        print("PATCH: Enhanced get_stats with transaction control")

        # Skip transaction control if no connection
        if not hasattr(self, "connection") or self.connection is None:
            return original_method(self, *args, **kwargs)

        try:
            # Begin a new transaction
            self.connection.execute("BEGIN TRANSACTION")

            # Execute the stats query within the transaction
            result = original_method(self, *args, **kwargs)

            # Commit the transaction
            self.connection.execute("COMMIT")

            return result

        except Exception as e:
            print(f"PATCH: Enhanced get_stats failed: {e}")
            # Try to rollback the transaction
            try:
                self.connection.execute("ROLLBACK")
            except:
                pass
            # Re-raise the exception
            raise

    return wrapper


def apply_patches():
    """Apply all patches to fix the query state inconsistency."""
    global original_database_reconnect, original_provider_connect

    print("=" * 80)
    print("APPLYING CONNECTION TRANSACTION FIX PATCHES")
    print("=" * 80)

    # Patch Database.reconnect
    if not original_database_reconnect:
        original_database_reconnect = Database.reconnect
        Database.reconnect = enhanced_database_reconnect
        print("✅ Patched Database.reconnect with transaction control")

    # Patch DuckDBProvider.connect
    if not original_provider_connect:
        original_provider_connect = DuckDBProvider.connect
        DuckDBProvider.connect = enhanced_provider_connect
        print("✅ Patched DuckDBProvider.connect with validation")

    # Patch search methods with transaction control
    if hasattr(DuckDBProvider, "search_regex"):
        DuckDBProvider.search_regex = enhanced_search_regex(DuckDBProvider.search_regex)
        print("✅ Patched DuckDBProvider.search_regex with transaction control")

    if hasattr(DuckDBProvider, "search_semantic"):
        DuckDBProvider.search_semantic = enhanced_search_semantic(DuckDBProvider.search_semantic)
        print("✅ Patched DuckDBProvider.search_semantic with transaction control")

    if hasattr(DuckDBProvider, "get_stats"):
        DuckDBProvider.get_stats = enhanced_get_stats(DuckDBProvider.get_stats)
        print("✅ Patched DuckDBProvider.get_stats with transaction control")

    print("All patches applied successfully!")
    print("=" * 80)


def remove_patches():
    """Remove all patches and restore original functionality."""
    global original_database_reconnect, original_provider_connect

    print("=" * 80)
    print("REMOVING CONNECTION TRANSACTION FIX PATCHES")
    print("=" * 80)

    # Restore original methods
    if original_database_reconnect:
        Database.reconnect = original_database_reconnect
        original_database_reconnect = None
        print("✅ Restored original Database.reconnect")

    if original_provider_connect:
        DuckDBProvider.connect = original_provider_connect
        original_provider_connect = None
        print("✅ Restored original DuckDBProvider.connect")

    # Note: We can't easily restore decorated methods,
    # a restart of the application would be required

    print("Patches removed!")
    print("=" * 80)


if __name__ == "__main__":
    apply_patches()
    print("Connection transaction fix patches applied.")
    print("To use in another module:")
    print("    import connection_transaction_fix")
    print("    connection_transaction_fix.apply_patches()")
