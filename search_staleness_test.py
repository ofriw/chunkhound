#!/usr/bin/env python3
"""
Search Staleness Test - Focused test for realtime file sync bug.
Tests whether search results become stale after file modifications/deletions.
"""

import os
import sys
import time
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, Any, List

# Add the chunkhound module to the path
sys.path.insert(0, str(Path(__file__).parent))

from providers.database.duckdb_provider import DuckDBProvider


class SearchStalenessTest:
    """Test search result staleness after file operations."""

    def __init__(self):
        self.test_dir = None
        self.database = None
        self.db_path = None
        self.results = []

    def setup(self):
        """Set up test environment."""
        print("Setting up search staleness test...")

        # Create temporary test directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="chunkhound_search_test_"))
        print(f"Test directory: {self.test_dir}")

        # Create temporary database
        self.db_path = self.test_dir / "test.duckdb"
        self.database = DuckDBProvider(str(self.db_path))

        # Connect and initialize database
        self.database.connect()
        self.database.create_schema()
        print(f"Test database: {self.db_path}")

        print("Setup complete.\n")

    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        self.results.append((test_name, success, details))

    def create_test_file_with_content(self, filename: str, content: str) -> Path:
        """Create a test file with specific searchable content."""
        test_file = self.test_dir / filename
        test_file.write_text(content)
        return test_file

    async def process_file_with_coordinator(self, file_path: Path) -> Dict[str, Any]:
        """Process file using the incremental processing method."""
        try:
            result = await self.database.process_file_incremental(file_path)
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def search_for_content(self, pattern: str) -> List[Dict[str, Any]]:
        """Search for content using regex search."""
        try:
            results = self.database.search_regex(pattern=pattern, limit=10)
            return results if results else []
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def test_search_after_file_creation(self):
        """Test search results after creating a new file."""
        print("=== Testing Search After File Creation ===")

        # Create file with unique searchable content
        unique_content = f"UNIQUE_CREATION_TEST_{int(time.time())}"
        test_file = self.create_test_file_with_content(
            "creation_test.py",
            f"# Test file created for search test\n# {unique_content}\nprint('Hello World')\n"
        )

        # Process the file
        result = asyncio.run(self.process_file_with_coordinator(test_file))

        if result.get("status") != "success":
            self.log_result("File Creation Processing", False, f"Processing failed: {result}")
            return False

        # Wait a moment for any async processing
        time.sleep(0.5)

        # Search for the unique content
        search_results = self.search_for_content(unique_content)

        if search_results:
            self.log_result("Search After Creation", True, f"Found {len(search_results)} results")
            return True
        else:
            self.log_result("Search After Creation", False, "Content not found in search results")
            return False

    def test_search_after_file_modification(self):
        """Test search results after modifying an existing file."""
        print("\n=== Testing Search After File Modification ===")

        # Create initial file
        original_content = "ORIGINAL_MODIFICATION_TEST_CONTENT"
        test_file = self.create_test_file_with_content(
            "modification_test.py",
            f"# Original content\n# {original_content}\nprint('Original')\n"
        )

        # Process initial file
        initial_result = asyncio.run(self.process_file_with_coordinator(test_file))
        if initial_result.get("status") != "success":
            self.log_result("Initial File Processing", False, "Failed to process initial file")
            return False

        # Wait for processing
        time.sleep(0.5)

        # Verify original content is searchable
        initial_search = self.search_for_content(original_content)
        if not initial_search:
            self.log_result("Initial Content Search", False, "Original content not found")
            return False

        # Modify the file with new content
        time.sleep(1.1)  # Ensure mtime changes
        modified_content = f"MODIFIED_CONTENT_{int(time.time())}"
        test_file.write_text(f"# Modified content\n# {modified_content}\nprint('Modified')\n")

        # Process the modified file
        modified_result = asyncio.run(self.process_file_with_coordinator(test_file))
        if modified_result.get("status") != "success":
            self.log_result("Modified File Processing", False, f"Processing failed: {modified_result}")
            return False

        # Wait for processing
        time.sleep(0.5)

        # Search for new content - this should be found
        new_search = self.search_for_content(modified_content)
        new_content_found = len(new_search) > 0

        # Search for old content - this should NOT be found (staleness test)
        old_search = self.search_for_content(original_content)
        old_content_gone = len(old_search) == 0

        if new_content_found and old_content_gone:
            self.log_result("Search After Modification", True, "New content found, old content properly removed")
            return True
        elif new_content_found and not old_content_gone:
            self.log_result("Search After Modification", False, "STALENESS DETECTED: Old content still in search results")
            return False
        elif not new_content_found:
            self.log_result("Search After Modification", False, "New content not found in search results")
            return False
        else:
            self.log_result("Search After Modification", False, "Unexpected search state")
            return False

    def test_search_after_file_deletion(self):
        """Test search results after deleting a file."""
        print("\n=== Testing Search After File Deletion ===")

        # Create file with unique content
        deletion_content = f"DELETION_TEST_CONTENT_{int(time.time())}"
        test_file = self.create_test_file_with_content(
            "deletion_test.py",
            f"# File to be deleted\n# {deletion_content}\nprint('Delete me')\n"
        )

        # Process the file
        creation_result = asyncio.run(self.process_file_with_coordinator(test_file))
        if creation_result.get("status") != "success":
            self.log_result("Deletion Test File Processing", False, "Failed to process file for deletion test")
            return False

        # Wait for processing
        time.sleep(0.5)

        # Verify content is searchable before deletion
        pre_deletion_search = self.search_for_content(deletion_content)
        if not pre_deletion_search:
            self.log_result("Pre-deletion Content Search", False, "Content not found before deletion")
            return False

        # Delete the file
        test_file.unlink()

        # Process the deletion (this simulates the file watcher detecting deletion)
        try:
            # Use the database's delete_file_completely method directly
            deletion_result = self.database.delete_file_completely(str(test_file))
            print(f"Deletion operation result: {deletion_result}")
        except Exception as e:
            self.log_result("File Deletion Operation", False, f"Deletion failed: {e}")
            return False

        # Wait for processing
        time.sleep(0.5)

        # Search for content - should NOT be found after deletion
        post_deletion_search = self.search_for_content(deletion_content)
        content_properly_removed = len(post_deletion_search) == 0

        if content_properly_removed:
            self.log_result("Search After Deletion", True, "Content properly removed from search results")
            return True
        else:
            self.log_result("Search After Deletion", False, f"STALENESS DETECTED: Deleted content still in search results ({len(post_deletion_search)} results)")
            return False

    def test_rapid_modifications_search_consistency(self):
        """Test search consistency during rapid file modifications."""
        print("\n=== Testing Rapid Modifications Search Consistency ===")

        # Create file for rapid modification test
        test_file = self.create_test_file_with_content(
            "rapid_test.py",
            "# Initial content for rapid test\nprint('Initial')\n"
        )

        # Process initial file
        initial_result = asyncio.run(self.process_file_with_coordinator(test_file))
        if initial_result.get("status") != "success":
            self.log_result("Rapid Test Initial Processing", False, "Failed to process initial file")
            return False

        # Perform rapid modifications
        final_content = None
        for i in range(3):
            time.sleep(1.1)  # Ensure mtime changes
            content = f"RAPID_MODIFICATION_ITERATION_{i}_{int(time.time())}"
            test_file.write_text(f"# Rapid modification {i}\n# {content}\nprint('Iteration {i}')\n")
            final_content = content

            # Process each modification
            result = asyncio.run(self.process_file_with_coordinator(test_file))
            if result.get("status") != "success":
                print(f"Warning: Iteration {i} processing failed: {result}")

        # Wait for all processing to complete
        time.sleep(1.0)

        # Search for the final content
        final_search = self.search_for_content(final_content)
        final_content_found = len(final_search) > 0

        # Search for earlier content to ensure it's not stale
        earlier_content = "RAPID_MODIFICATION_ITERATION_0"
        earlier_search = self.search_for_content(earlier_content)
        earlier_content_gone = len(earlier_search) == 0

        if final_content_found and earlier_content_gone:
            self.log_result("Rapid Modifications Consistency", True, "Only final content found, no stale results")
            return True
        elif final_content_found and not earlier_content_gone:
            self.log_result("Rapid Modifications Consistency", False, "STALENESS DETECTED: Earlier content still present")
            return False
        elif not final_content_found:
            self.log_result("Rapid Modifications Consistency", False, "Final content not found")
            return False
        else:
            self.log_result("Rapid Modifications Consistency", False, "Unexpected state")
            return False

    def run_all_tests(self):
        """Run all search staleness tests."""
        print("🔍 Starting Search Staleness Tests")
        print("=" * 60)

        self.setup()

        # Run tests
        tests = [
            ("Search After File Creation", self.test_search_after_file_creation),
            ("Search After File Modification", self.test_search_after_file_modification),
            ("Search After File Deletion", self.test_search_after_file_deletion),
            ("Rapid Modifications Consistency", self.test_rapid_modifications_search_consistency),
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
        print("\n" + "=" * 60)
        print("🎯 SEARCH STALENESS TEST RESULTS")
        print("=" * 60)

        passed = sum(1 for _, success, _ in self.results if success)
        total = len(self.results)

        for test_name, success, details in self.results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {test_name}")
            if details and not success:
                print(f"    {details}")

        print(f"\nOverall: {passed}/{total} tests passed")

        # Hypothesis evaluation
        print("\n🔍 SEARCH STALENESS HYPOTHESIS EVALUATION")
        print("=" * 60)

        staleness_detected = any("STALENESS DETECTED" in details for _, success, details in self.results if not success)

        if passed == total:
            print("RESULT: NO SEARCH STALENESS DETECTED")
            print("Search results properly reflect file changes.")
            print("Bug may be in file watcher event processing or MCP server caching.")
        elif staleness_detected:
            print("RESULT: SEARCH STALENESS CONFIRMED")
            print("Search results are stale after file operations.")
            print("This confirms the search result caching hypothesis.")
        else:
            print("RESULT: SEARCH FUNCTIONALITY ISSUES")
            print("Problems with search functionality itself, not necessarily staleness.")

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
    test = SearchStalenessTest()

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
