#!/usr/bin/env python3
"""Demo script showing path filtering feature for MCP search tools."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunkhound.database import Database


async def main():
    """Demonstrate path filtering functionality."""
    # Create in-memory database
    db = Database(":memory:")
    db.connect()

    # Process the chunkhound codebase
    project_root = Path(__file__).parent.parent
    print(f"Processing files in {project_root}...")
    await db.process_directory(project_root)

    stats = db.get_stats()
    print(f"\nDatabase stats: {stats['files']} files, {stats['chunks']} chunks")

    # Demo 1: Search for class definitions in all files
    print("\n=== Demo 1: Search for class definitions (no path filter) ===")
    results, pagination = db.search_regex(r"class\s+\w+", page_size=5)
    print(f"Found {pagination['total']} total results, showing first {len(results)}:")
    for r in results:
        print(f"  - {r['file_path']}: {r['symbol']} (line {r['start_line']})")

    # Demo 2: Search for class definitions only in providers/ directory
    print("\n=== Demo 2: Search for class definitions in providers/ ===")
    results, pagination = db.search_regex(
        r"class\s+\w+", page_size=10, path_filter="providers/"
    )
    print(f"Found {pagination['total']} results:")
    for r in results:
        print(f"  - {r['file_path']}: {r['symbol']} (line {r['start_line']})")

    # Demo 3: Search for test functions
    print("\n=== Demo 3: Search for test functions in tests/ ===")
    results, pagination = db.search_regex(
        r"def\s+test_\w+", page_size=10, path_filter="tests/"
    )
    print(f"Found {pagination['total']} test functions:")
    for r in results[:5]:  # Show first 5
        print(f"  - {r['file_path']}: {r['symbol']} (line {r['start_line']})")
    if pagination["total"] > 5:
        print(f"  ... and {pagination['total'] - 5} more")

    # Demo 4: Search in specific file
    print("\n=== Demo 4: Search in specific file ===")
    results, pagination = db.search_regex(
        r"def\s+\w+", page_size=20, path_filter="chunkhound/mcp_server.py"
    )
    print(f"Found {pagination['total']} functions in mcp_server.py:")
    for r in results[:3]:
        print(f"  - {r['symbol']} (line {r['start_line']})")
    if pagination["total"] > 3:
        print(f"  ... and {pagination['total'] - 3} more")

    # Demo 5: Invalid path patterns (security)
    print("\n=== Demo 5: Security validation ===")
    dangerous_patterns = ["../etc/passwd", "~/secrets", "path/../../../"]
    for pattern in dangerous_patterns:
        try:
            db.search_regex("def", path_filter=pattern)
            print(f"  ❌ SECURITY ISSUE: Pattern '{pattern}' was not blocked!")
        except ValueError as e:
            print(f"  ✅ Pattern '{pattern}' correctly blocked: {e}")

    db.close()
    print("\n✅ Path filtering demo completed!")


if __name__ == "__main__":
    asyncio.run(main())
