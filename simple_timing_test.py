#!/usr/bin/env python3
"""
Simplified timing test for realtime file sync coordination.
Tests database operations directly to isolate timing issues.
"""

import os
import sys
import time
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, Any

# Add the chunkhound module to the path
sys.path.insert(0, str(Path(__file__).parent))

from providers.database.duckdb_provider import DuckDBProvider


class SimpleTimingTest:
    """Test database timing coordination directly."""

    def __init__(self):
        self.test_dir = None
        self.database = None
        self.db_path = None
        self.results = []

    def setup(self):
        """Set up test environment."""
        print("Setting up simple timing test...")

        # Create temporary test directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="chunkhound_simple_test_"))
        print(f"Test directory: {self.test_dir}")

        # Create temporary database
        self.db_path = self.test_dir / "test.duckdb"
        self.database = DuckDBProvider(str(self.db_path))

        # Connect and initialize database
        self.database.connect()
        self.database.create_schema()
        print(f"Test database: {self.db_path}")

        # Create test file
        self.test_file = self.test_dir / "test_file.py"
        self.test_file.write_text("# Test Python file\nprint('Hello World')\n")
        print(f"Created test file: {self.test_file}")

        print("Setup complete.\n")

    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        self.results.append((test_name, success, details))

    def test_mtime_comparison_logic(self):
        """Test the mtime comparison logic that's at the heart of incremental updates."""
        print("=== Testing Mtime Comparison Logic ===")

        # Get current file mtime
        file_stat = self.test_file.stat()
        current_mtime = file_stat.st_mtime

        # Test 1: File doesn't exist in database (should process)
        existing_file = self.database.get_file_by_path(str(self.test_file))
        if existing_file is None:
            self.log_result("New File Detection", True, "File correctly detected as new")
        else:
            self.log_result("New File Detection", False, "File incorrectly found in empty database")
            return False

        # Test 2: Add file to database and check mtime storage
        try:
            # Simulate adding file using the actual API
            # First add the file record
            self.database.connection.execute("""
                INSERT INTO files (path, name, extension, size, modified_time, language, created_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, [
                str(self.test_file),
                self.test_file.name,
                self.test_file.suffix,
                self.test_file.stat().st_size,
                current_mtime,
                'python'
            ])

            # Get the file ID
            file_record = self.database.connection.execute(
                "SELECT id FROM files WHERE path = ?", [str(self.test_file)]
            ).fetchone()
            file_id = file_record[0] if file_record else None

            # Verify file was added with correct mtime
            stored_file = self.database.get_file_by_path(str(self.test_file))
            if stored_file:
                stored_mtime = stored_file.get('mtime', 0)
                mtime_diff = abs(current_mtime - stored_mtime)

                if mtime_diff < 0.001:  # Within 1ms tolerance
                    self.log_result("Mtime Storage", True, f"Mtime stored correctly (diff: {mtime_diff:.6f}s)")
                else:
                    self.log_result("Mtime Storage", False, f"Mtime storage issue (diff: {mtime_diff:.6f}s)")
                    return False
            else:
                self.log_result("Mtime Storage", False, "File not found after adding")
                return False
        except Exception as e:
            self.log_result("Mtime Storage", False, f"Exception: {e}")
            return False

        # Test 3: Modify file and test mtime comparison
        time.sleep(1.1)  # Ensure mtime changes
        modified_content = "# Modified file\nprint('Modified')\n"
        self.test_file.write_text(modified_content)

        new_file_stat = self.test_file.stat()
        new_mtime = new_file_stat.st_mtime

        # Check if the mtime comparison logic would detect this as modified
        existing_file = self.database.get_file_by_path(str(self.test_file))
        if existing_file:
            db_mtime = existing_file.get('mtime', 0)

            # This is the core logic from process_file_incremental
            should_update = abs(new_mtime - db_mtime) > 1.0

            print(f"File system mtime: {new_mtime:.6f}")
            print(f"Database mtime: {db_mtime:.6f}")
            print(f"Difference: {abs(new_mtime - db_mtime):.6f}s")
            print(f"Should update: {should_update}")

            if should_update:
                self.log_result("Mtime Change Detection", True, f"Change correctly detected (diff: {abs(new_mtime - db_mtime):.6f}s)")
            else:
                self.log_result("Mtime Change Detection", False, f"Change NOT detected (diff: {abs(new_mtime - db_mtime):.6f}s)")
                return False
        else:
            self.log_result("Mtime Change Detection", False, "File not found for comparison")
            return False

        return True

    def test_deletion_logic(self):
        """Test file deletion logic."""
        print("\n=== Testing Deletion Logic ===")

        # Create a file specifically for deletion testing
        delete_file = self.test_dir / "delete_test.py"
        delete_file.write_text("# File to delete\nprint('Delete me')\n")

        # Add to database
        file_stat = delete_file.stat()
        self.database.connection.execute("""
            INSERT INTO files (path, name, extension, size, modified_time, language, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, [
            str(delete_file),
            delete_file.name,
            delete_file.suffix,
            file_stat.st_size,
            file_stat.st_mtime,
            'python'
        ])

        # Verify it exists
        existing_file = self.database.get_file_by_path(str(delete_file))
        if not existing_file:
            self.log_result("Pre-deletion Check", False, "File not found in database")
            return False

        self.log_result("Pre-deletion Check", True, f"File found with ID: {existing_file.get('id', 'unknown')}")

        # Delete from database
        try:
            result = self.database.delete_file_completely(str(delete_file))
            print(f"Deletion result: {result}")

            # Check if file is gone
            deleted_file = self.database.get_file_by_path(str(delete_file))
            if deleted_file is None:
                self.log_result("File Deletion", True, "File successfully removed from database")
                return True
            else:
                self.log_result("File Deletion", False, "File still exists in database")
                return False
        except Exception as e:
            self.log_result("File Deletion", False, f"Exception during deletion: {e}")
            return False

    def test_sub_second_precision(self):
        """Test sub-second mtime precision issues."""
        print("\n=== Testing Sub-second Precision ===")

        # Create multiple files with sub-second intervals
        precision_files = []
        for i in range(3):
            precision_file = self.test_dir / f"precision_test_{i}.py"
            precision_file.write_text(f"# Precision test {i}\nprint('Test {i}')\n")
            precision_files.append(precision_file)

            # Add small delay to create sub-second differences
            time.sleep(0.1)

        # Add all files to database and check precision
        mtimes = []
        for i, pfile in enumerate(precision_files):
            file_stat = pfile.stat()
            current_mtime = file_stat.st_mtime
            mtimes.append(current_mtime)

            self.database.connection.execute("""
                INSERT INTO files (path, name, extension, size, modified_time, language, created_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, [
                str(pfile),
                pfile.name,
                pfile.suffix,
                file_stat.st_size,
                current_mtime,
                'python'
            ])

            # Retrieve and compare
            stored_file = self.database.get_file_by_path(str(pfile))
            if stored_file:
                stored_mtime = stored_file.get('mtime', 0)
                precision_diff = abs(current_mtime - stored_mtime)

                print(f"File {i}: fs_mtime={current_mtime:.6f}, db_mtime={stored_mtime:.6f}, diff={precision_diff:.6f}s")

                if precision_diff > 0.001:  # More than 1ms difference
                    self.log_result(f"Precision Test {i}", False, f"High precision loss: {precision_diff:.6f}s")
                    return False

        # Check if we can distinguish between files with sub-second differences
        mtime_diffs = [abs(mtimes[i] - mtimes[i-1]) for i in range(1, len(mtimes))]
        min_diff = min(mtime_diffs)

        if min_diff < 0.1:
            self.log_result("Sub-second Precision", True, f"Minimum difference detected: {min_diff:.6f}s")
        else:
            self.log_result("Sub-second Precision", False, f"No sub-second precision achieved: {min_diff:.6f}s")

        return True

    def run_all_tests(self):
        """Run all tests."""
        print("🔍 Starting Simple Timing Tests")
        print("=" * 50)

        self.setup()

        # Run tests
        tests = [
            ("Mtime Comparison Logic", self.test_mtime_comparison_logic),
            ("Deletion Logic", self.test_deletion_logic),
            ("Sub-second Precision", self.test_sub_second_precision),
        ]

        for test_name, test_func in tests:
            try:
                success = test_func()
                if not success:
                    print(f"❌ {test_name} failed")
            except Exception as e:
                self.log_result(test_name, False, f"Exception: {e}")
                import traceback
                traceback.print_exc()

        # Summary
        print("\n" + "=" * 50)
        print("🎯 TEST RESULTS SUMMARY")
        print("=" * 50)

        passed = sum(1 for _, success, _ in self.results if success)
        total = len(self.results)

        for test_name, success, details in self.results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {test_name}")
            if details and not success:
                print(f"    {details}")

        print(f"\nOverall: {passed}/{total} tests passed")

        # Hypothesis evaluation
        print("\n🔍 HYPOTHESIS EVALUATION")
        print("=" * 50)

        if passed == total:
            print("HYPOTHESIS STATUS: DISPROVEN")
            print("Database timing operations work correctly.")
            print("Bug likely in file watcher event processing or search result caching.")
        else:
            print("HYPOTHESIS STATUS: SUPPORTED")
            print("Database timing coordination issues found.")
            print("The multi-layer timing synchronization hypothesis is supported.")

        return passed == total

    def cleanup(self):
        """Clean up test environment."""
        print("\n🧹 Cleaning up...")

        if self.database:
            try:
                self.database.close()
            except:
                pass

        if self.test_dir and self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir, ignore_errors=True)
            print(f"Removed test directory: {self.test_dir}")


def main():
    """Main test runner."""
    test = SimpleTimingTest()

    try:
        success = test.run_all_tests()
        return success
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        test.cleanup()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
