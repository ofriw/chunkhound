"""
Test utilities and assertion helpers for file watching functionality.
"""

import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import pytest

from chunkhound.database import Database


class FileWatchingAssertions:
    """Assertion helpers for file watching tests."""

    def __init__(self, db_path: Path, timeout: float = 10.0):
        self.db_path = db_path
        self.timeout = timeout

    async def assert_file_indexed_within_timeout(
        self, file_path: Path, timeout: Optional[float] = None
    ) -> bool:
        """Verify file appears in search results within timeout."""
        if timeout is None:
            timeout = self.timeout

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                db = Database(str(self.db_path))
                db.connect()

                # Search for file path
                results, _ = db.search_regex(str(file_path), page_size=10)

                if results:
                    for result in results:
                        if str(file_path) in result.get("file_path", ""):
                            db.close()
                            return True

                db.close()

            except Exception as e:
                # Database might be locked or not ready
                pass

            await asyncio.sleep(0.5)

        return False

    async def assert_content_searchable_within_timeout(
        self, content: str, timeout: Optional[float] = None
    ) -> bool:
        """Verify content appears in search results within timeout."""
        if timeout is None:
            timeout = self.timeout

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                db = Database(str(self.db_path))
                db.connect()

                # Search for content
                results, _ = db.search_regex(content, page_size=10)

                if results:
                    for result in results:
                        chunk_content = (
                            result.get("content", "")
                            or result.get("code", "")
                            or result.get("chunk_content", "")
                        )
                        if content in chunk_content:
                            db.close()
                            return True

                db.close()

            except Exception:
                # Database might be locked
                pass

            await asyncio.sleep(0.5)

        return False

    async def assert_content_not_searchable_within_timeout(
        self, content: str, timeout: Optional[float] = None
    ) -> bool:
        """Verify content no longer appears in search results within timeout."""
        if timeout is None:
            timeout = self.timeout

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                db = Database(str(self.db_path))
                db.connect()

                # Search for content
                results, _ = db.search_regex(content, page_size=10)

                found = False
                if results:
                    for result in results:
                        chunk_content = (
                            result.get("content", "")
                            or result.get("code", "")
                            or result.get("chunk_content", "")
                        )
                        if content in chunk_content:
                            found = True
                            break

                db.close()

                if not found:
                    return True

            except Exception:
                # Database might be locked
                pass

            await asyncio.sleep(0.5)

        return False

    async def assert_chunks_updated_correctly(
        self, file_path: Path, expected_chunks: List[str]
    ) -> bool:
        """Verify database chunks match expected content."""
        try:
            db = Database(str(self.db_path))
            db.connect()

            # Get chunks for file
            chunks = db.get_chunks_for_file(str(file_path))

            if len(chunks) != len(expected_chunks):
                db.close()
                return False

            # Check each chunk content
            for i, expected in enumerate(expected_chunks):
                if i < len(chunks):
                    chunk_content = chunks[i].get("content", "") or chunks[i].get(
                        "code", ""
                    )
                    if expected not in chunk_content:
                        db.close()
                        return False
                else:
                    db.close()
                    return False

            db.close()
            return True

        except Exception as e:
            print(f"Error checking chunks: {e}")
            return False

    async def get_embedding_count_for_file(self, file_path: Path) -> int:
        """Get number of embeddings for a file."""
        try:
            db = Database(str(self.db_path))
            db.connect()

            chunks = db.get_chunks_for_file(str(file_path))
            embedding_count = sum(
                1 for chunk in chunks if chunk.get("embedding") is not None
            )

            db.close()
            return embedding_count

        except Exception:
            return 0

    async def assert_embeddings_preserved(
        self, file_path: Path, unchanged_chunks: List[str]
    ) -> bool:
        """Verify embeddings not regenerated unnecessarily."""
        # This is a complex test that would require tracking embedding IDs
        # For now, we'll just check that embeddings exist
        try:
            db = Database(str(self.db_path))
            db.connect()

            chunks = db.get_chunks_for_file(str(file_path))

            for unchanged_chunk in unchanged_chunks:
                found = False
                for chunk in chunks:
                    chunk_content = chunk.get("content", "") or chunk.get("code", "")
                    if unchanged_chunk in chunk_content and chunk.get("embedding"):
                        found = True
                        break
                if not found:
                    db.close()
                    return False

            db.close()
            return True

        except Exception:
            return False


class FileOperationGenerator:
    """Generate controlled sequences of file operations for testing."""

    @staticmethod
    def create_rapid_changes(
        file_path: Path, num_changes: int = 10, delay_between: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Generate rapid file changes."""
        operations = []

        for i in range(num_changes):
            operations.append(
                {
                    "type": "modify",
                    "file_path": file_path,
                    "content": f"# Change {i}\ndef function_{i}(): pass\n",
                    "delay_after": delay_between,
                }
            )

        return operations

    @staticmethod
    def create_bulk_operations(
        project_dir: Path, num_files: int = 50
    ) -> List[Dict[str, Any]]:
        """Generate bulk file operations."""
        operations = []

        for i in range(num_files):
            file_path = project_dir / f"bulk_test_{i}.py"
            operations.append(
                {
                    "type": "create",
                    "file_path": file_path,
                    "content": f"# Bulk file {i}\ndef bulk_function_{i}(): return {i}\n",
                    "delay_after": 0.01,
                }
            )

        return operations

    @staticmethod
    def create_mixed_operations(project_dir: Path) -> List[Dict[str, Any]]:
        """Generate mixed file operations."""
        operations = []

        # Create files
        for i in range(5):
            file_path = project_dir / f"mixed_{i}.py"
            operations.append(
                {
                    "type": "create",
                    "file_path": file_path,
                    "content": f"# Mixed file {i}\ndef mixed_function_{i}(): pass\n",
                    "delay_after": 0.1,
                }
            )

        # Modify some files
        for i in range(3):
            file_path = project_dir / f"mixed_{i}.py"
            operations.append(
                {
                    "type": "modify",
                    "file_path": file_path,
                    "content": f"# Modified mixed file {i}\ndef modified_function_{i}(): return 'modified'\n",
                    "delay_after": 0.1,
                }
            )

        # Delete some files
        for i in range(2):
            file_path = project_dir / f"mixed_{i}.py"
            operations.append(
                {"type": "delete", "file_path": file_path, "delay_after": 0.1}
            )

        return operations


async def execute_file_operations(operations: List[Dict[str, Any]]):
    """Execute a sequence of file operations."""
    for operation in operations:
        op_type = operation["type"]
        file_path = operation["file_path"]
        delay_after = operation.get("delay_after", 0)

        if op_type == "create":
            file_path.write_text(operation["content"])
        elif op_type == "modify":
            file_path.write_text(operation["content"])
        elif op_type == "delete":
            if file_path.exists():
                file_path.unlink()
        elif op_type == "move":
            if file_path.exists():
                file_path.rename(operation["new_path"])

        if delay_after > 0:
            await asyncio.sleep(delay_after)


def generate_unique_content(prefix: str = "test") -> str:
    """Generate unique content for testing."""
    timestamp = int(time.time() * 1000)
    return f"""# {prefix}_content_{timestamp}
def {prefix}_function_{timestamp}():
    '''Test function generated at {timestamp}'''
    return "{prefix}_result_{timestamp}"

class {prefix.title()}Class_{timestamp}:
    def method(self):
        return "{prefix}_method_{timestamp}"
"""


async def wait_for_file_processing(
    file_path: Path, content: str, db_path: Path, timeout: float = 10.0
) -> bool:
    """Wait for file to be processed and indexed."""
    assertions = FileWatchingAssertions(db_path, timeout)

    # Wait for both file indexing and content searchability
    file_indexed = await assertions.assert_file_indexed_within_timeout(file_path)
    content_searchable = await assertions.assert_content_searchable_within_timeout(
        content
    )

    return file_indexed and content_searchable


async def wait_for_file_removal(
    content: str, db_path: Path, timeout: float = 10.0
) -> bool:
    """Wait for content to be removed from index."""
    assertions = FileWatchingAssertions(db_path, timeout)
    return await assertions.assert_content_not_searchable_within_timeout(content)


class DebugHelper:
    """Helper for debugging test failures."""

    @staticmethod
    def print_database_state(db_path: Path):
        """Print current database state for debugging."""
        try:
            db = Database(str(db_path))
            db.connect()

            # Get all files
            files = db.get_indexed_files()
            print(f"Database contains {len(files)} files:")

            for file_info in files[:10]:  # Limit output
                file_path = file_info.get("file_path", "Unknown")
                chunk_count = file_info.get("chunk_count", 0)
                print(f"  {file_path}: {chunk_count} chunks")

            if len(files) > 10:
                print(f"  ... and {len(files) - 10} more files")

            db.close()

        except Exception as e:
            print(f"Error reading database state: {e}")

    @staticmethod
    def print_search_results(db_path: Path, query: str, max_results: int = 5):
        """Print search results for debugging."""
        try:
            db = Database(str(db_path))
            db.connect()

            results, _ = db.search_regex(query, page_size=max_results)

            print(f"Search for '{query}' returned {len(results)} results:")

            for i, result in enumerate(results):
                file_path = result.get("file_path", "Unknown")
                content = result.get("content", result.get("code", ""))[:100]
                print(f"  {i + 1}. {file_path}: {content}...")

            db.close()

        except Exception as e:
            print(f"Error searching database: {e}")
