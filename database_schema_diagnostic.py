#!/usr/bin/env python3
"""
Database Schema Diagnostic - Investigation of Missing 'chunks' Table
===================================================================

PURPOSE: Investigate why the 'chunks' table doesn't exist in the database
DISCOVERY: Previous diagnostic found "no such table: chunks" error
HYPOTHESIS: Database schema not initialized or corrupted

INVESTIGATION STRATEGY:
1. Check database file existence and permissions
2. Examine database schema and tables
3. Compare expected vs actual schema
4. Identify initialization failure point

USAGE: python database_schema_diagnostic.py
"""

import os
import sys
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime

class DatabaseSchemaDiagnostic:
    def __init__(self):
        self.project_root = Path("/Users/ofri/Documents/GitHub/chunkhound")
        self.db_path = self.project_root / "chunkhound.db"
        self.cli_db_path = self.project_root / ".chunkhound" / "chunkhound.db"
        self.diagnostic_results = []

    def log(self, message, level="INFO"):
        """Log diagnostic message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {level}: {message}"
        print(log_entry)
        self.diagnostic_results.append(log_entry)

    def check_database_file(self, db_path, name):
        """Check database file existence and basic properties"""
        self.log(f"=== CHECKING {name} DATABASE ===")

        if not db_path.exists():
            self.log(f"{name} database does not exist: {db_path}", "ERROR")
            return False

        stat_info = db_path.stat()
        self.log(f"{name} database exists: {db_path}")
        self.log(f"File size: {stat_info.st_size} bytes")
        self.log(f"Permissions: {oct(stat_info.st_mode)[-3:]}")
        self.log(f"Modified: {datetime.fromtimestamp(stat_info.st_mtime)}")

        return True

    def examine_database_schema(self, db_path, name):
        """Examine database schema and tables"""
        self.log(f"=== EXAMINING {name} DATABASE SCHEMA ===")

        try:
            # Try to connect with short timeout
            conn = sqlite3.connect(str(db_path), timeout=2.0)
            cursor = conn.cursor()

            # List all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            if not tables:
                self.log(f"{name}: No tables found in database", "WARNING")
            else:
                self.log(f"{name}: Found {len(tables)} tables:")
                for table in tables:
                    self.log(f"  - {table[0]}")

            # Check for chunks table specifically
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'")
            chunks_table = cursor.fetchone()

            if chunks_table:
                self.log(f"{name}: 'chunks' table exists")

                # Get chunks table schema
                cursor.execute("PRAGMA table_info(chunks)")
                columns = cursor.fetchall()
                self.log(f"{name}: 'chunks' table has {len(columns)} columns:")
                for col in columns:
                    self.log(f"  - {col[1]} ({col[2]})")

                # Get row count
                cursor.execute("SELECT COUNT(*) FROM chunks")
                count = cursor.fetchone()[0]
                self.log(f"{name}: 'chunks' table has {count} rows")

            else:
                self.log(f"{name}: 'chunks' table does NOT exist", "CRITICAL")

            conn.close()
            return True

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                self.log(f"{name}: Database is locked (expected for active MCP server)", "INFO")
                return "locked"
            else:
                self.log(f"{name}: Database error: {e}", "ERROR")
                return False
        except Exception as e:
            self.log(f"{name}: Unexpected error: {e}", "ERROR")
            return False

    def check_database_integrity(self, db_path, name):
        """Check database integrity"""
        self.log(f"=== CHECKING {name} DATABASE INTEGRITY ===")

        try:
            conn = sqlite3.connect(str(db_path), timeout=2.0)
            cursor = conn.cursor()

            # Run integrity check
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()

            if result and result[0] == "ok":
                self.log(f"{name}: Database integrity check PASSED")
            else:
                self.log(f"{name}: Database integrity check FAILED: {result}", "ERROR")

            conn.close()
            return True

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                self.log(f"{name}: Cannot check integrity - database locked", "INFO")
                return "locked"
            else:
                self.log(f"{name}: Integrity check error: {e}", "ERROR")
                return False
        except Exception as e:
            self.log(f"{name}: Integrity check unexpected error: {e}", "ERROR")
            return False

    def compare_databases(self):
        """Compare project and CLI database schemas"""
        self.log("=== DATABASE COMPARISON ===")

        project_exists = self.db_path.exists()
        cli_exists = self.cli_db_path.exists()

        if project_exists and cli_exists:
            self.log("Both project and CLI databases exist")

            # Compare file sizes
            project_size = self.db_path.stat().st_size
            cli_size = self.cli_db_path.stat().st_size

            self.log(f"Project DB size: {project_size} bytes")
            self.log(f"CLI DB size: {cli_size} bytes")

            if abs(project_size - cli_size) > 1000:  # Significant difference
                self.log("Significant size difference between databases", "WARNING")

        elif project_exists and not cli_exists:
            self.log("Only project database exists", "WARNING")
        elif cli_exists and not project_exists:
            self.log("Only CLI database exists", "WARNING")
        else:
            self.log("Neither database exists", "CRITICAL")

    def test_schema_hypothesis(self):
        """Test hypothesis about missing chunks table"""
        self.log("=== SCHEMA HYPOTHESIS TESTING ===")

        # Test 1: Check if project database has chunks table
        project_schema = self.examine_database_schema(self.db_path, "PROJECT")

        # Test 2: Check if CLI database has chunks table
        cli_schema = self.examine_database_schema(self.cli_db_path, "CLI")

        # Analyze results
        if project_schema == "locked":
            self.log("PROJECT DB LOCKED: MCP server actively using database")
            if cli_schema and cli_schema != "locked":
                self.log("HYPOTHESIS: MCP server using project DB, CLI using separate DB")
            else:
                self.log("HYPOTHESIS: Database initialization incomplete")
        elif not project_schema:
            self.log("PROJECT DB CORRUPTED: Cannot read database schema", "CRITICAL")
        else:
            self.log("PROJECT DB ACCESSIBLE: Schema can be read")

    def run_diagnostic(self):
        """Run the complete database schema diagnostic"""
        self.log("=== DATABASE SCHEMA DIAGNOSTIC START ===")

        try:
            # Check database files
            project_exists = self.check_database_file(self.db_path, "PROJECT")
            cli_exists = self.check_database_file(self.cli_db_path, "CLI")

            if not project_exists and not cli_exists:
                self.log("CRITICAL: No database files found", "CRITICAL")
                return False

            # Compare databases
            self.compare_databases()

            # Check integrity
            if project_exists:
                self.check_database_integrity(self.db_path, "PROJECT")
            if cli_exists:
                self.check_database_integrity(self.cli_db_path, "CLI")

            # Test schema hypothesis
            self.test_schema_hypothesis()

            # Save results
            results_file = self.project_root / f"database_schema_diagnostic_{int(datetime.now().timestamp())}.log"
            with open(results_file, 'w') as f:
                f.write('\n'.join(self.diagnostic_results))
            self.log(f"Diagnostic results saved to: {results_file.name}")

            self.log("=== DATABASE SCHEMA DIAGNOSTIC COMPLETE ===")
            return True

        except Exception as e:
            self.log(f"Diagnostic failed with error: {e}", "ERROR")
            return False

if __name__ == "__main__":
    print("Database Schema Diagnostic - Missing 'chunks' Table Investigation")
    print("=================================================================")
    print()

    diagnostic = DatabaseSchemaDiagnostic()
    success = diagnostic.run_diagnostic()

    print()
    print("=================================================================")
    if success:
        print("✅ Database schema diagnostic completed")
        print("📋 Check log file for detailed analysis")
    else:
        print("❌ Database schema diagnostic failed")
        print("🔍 Check error messages above for details")
