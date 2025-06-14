#!/usr/bin/env python3
"""
Debug Python Parser

This script tests the Python parser directly to understand why chunks aren't being extracted.
"""

import os
import sys
from pathlib import Path

# Add chunkhound to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from providers.parsing.python_parser import PythonParser
from interfaces.language_parser import ParseConfig
from core.types import ChunkType, Language

def test_parser_initialization():
    """Test if the Python parser initializes correctly."""
    print("=== Testing Parser Initialization ===")

    parser = PythonParser()
    print(f"Parser created: {parser}")
    print(f"Parser available: {parser.is_available}")
    print(f"Parser language: {parser.language}")

    return parser

def test_simple_function_parsing():
    """Test parsing a simple Python function."""
    print("\n=== Testing Simple Function Parsing ===")

    # Create test content
    test_content = '''
def hello_world():
    """A simple test function."""
    print("Hello, world!")
    return "success"

def calculate_sum(a, b):
    """Calculate sum of two numbers."""
    return a + b
'''

    # Create temporary file
    test_file = Path("./test_simple.py")
    test_file.write_text(test_content)

    try:
        parser = PythonParser()
        result = parser.parse_file(test_file, test_content)

        print(f"Parse result: {result}")
        print(f"Chunks found: {result.total_chunks}")
        print(f"Errors: {result.errors}")
        print(f"Warnings: {result.warnings}")

        if result.chunks:
            print("\n--- Extracted Chunks ---")
            for i, chunk in enumerate(result.chunks):
                print(f"Chunk {i+1}:")
                print(f"  Symbol: {chunk.get('symbol', 'N/A')}")
                print(f"  Type: {chunk.get('chunk_type', 'N/A')}")
                print(f"  Lines: {chunk.get('start_line', 'N/A')}-{chunk.get('end_line', 'N/A')}")
                print(f"  Code length: {len(chunk.get('code', ''))}")
        else:
            print("No chunks extracted!")

    finally:
        if test_file.exists():
            test_file.unlink()

    return result

def test_class_parsing():
    """Test parsing a Python class."""
    print("\n=== Testing Class Parsing ===")

    # Create test content with class
    test_content = '''
class TestClass:
    """A simple test class."""

    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hello, {self.name}!"

    def calculate(self, x, y):
        """Calculate something."""
        return x * y + len(self.name)
'''

    # Create temporary file
    test_file = Path("./test_class.py")
    test_file.write_text(test_content)

    try:
        parser = PythonParser()
        result = parser.parse_file(test_file, test_content)

        print(f"Parse result: {result}")
        print(f"Chunks found: {result.total_chunks}")
        print(f"Errors: {result.errors}")
        print(f"Warnings: {result.warnings}")

        if result.chunks:
            print("\n--- Extracted Chunks ---")
            for i, chunk in enumerate(result.chunks):
                print(f"Chunk {i+1}:")
                print(f"  Symbol: {chunk.get('symbol', 'N/A')}")
                print(f"  Type: {chunk.get('chunk_type', 'N/A')}")
                print(f"  Lines: {chunk.get('start_line', 'N/A')}-{chunk.get('end_line', 'N/A')}")
                print(f"  Display: {chunk.get('display_name', 'N/A')}")
        else:
            print("No chunks extracted!")

    finally:
        if test_file.exists():
            test_file.unlink()

    return result

def test_fallback_block():
    """Test fallback BLOCK chunk creation."""
    print("\n=== Testing Fallback Block Creation ===")

    # Create test content with no functions or classes
    test_content = '''
# This is just a script with no functions or classes
import os
import sys

print("Hello from script")
x = 42
y = "test"
result = x + len(y)
print(f"Result: {result}")
'''

    # Create temporary file
    test_file = Path("./test_script.py")
    test_file.write_text(test_content)

    try:
        parser = PythonParser()
        result = parser.parse_file(test_file, test_content)

        print(f"Parse result: {result}")
        print(f"Chunks found: {result.total_chunks}")
        print(f"Errors: {result.errors}")
        print(f"Warnings: {result.warnings}")

        if result.chunks:
            print("\n--- Extracted Chunks ---")
            for i, chunk in enumerate(result.chunks):
                print(f"Chunk {i+1}:")
                print(f"  Symbol: {chunk.get('symbol', 'N/A')}")
                print(f"  Type: {chunk.get('chunk_type', 'N/A')}")
                print(f"  Lines: {chunk.get('start_line', 'N/A')}-{chunk.get('end_line', 'N/A')}")
                print(f"  Code preview: {chunk.get('code', '')[:100]}...")
        else:
            print("No chunks extracted - fallback failed!")

    finally:
        if test_file.exists():
            test_file.unlink()

    return result

def test_tree_sitter_availability():
    """Test tree-sitter availability and initialization."""
    print("\n=== Testing Tree-sitter Availability ===")

    try:
        import tree_sitter_python as tspython
        from tree_sitter import Language, Parser, Node
        print("✓ tree-sitter-python import successful")

        # Try to get the language
        language = tspython.language()
        print(f"✓ Python language loaded: {language}")

        # Try to create parser
        parser = Parser()
        parser.set_language(language)
        print("✓ Parser created and language set")

        # Try a simple parse
        test_code = "def test(): pass"
        tree = parser.parse(bytes(test_code, 'utf8'))
        print(f"✓ Simple parse successful: {tree.root_node}")

        # Try query
        query = language.query('(function_definition name: (identifier) @name)')
        matches = query.matches(tree.root_node)
        print(f"✓ Query successful, matches: {len(matches)}")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Other error: {e}")
        return False

def test_exact_test_file():
    """Test the exact content from our failed test."""
    print("\n=== Testing Exact Test File Content ===")

    # This is the exact content from our test that failed
    test_content = '''
def calculate_fibonacci(n):
    """Calculate fibonacci number efficiently."""
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

# This is a unique marker: INITIAL_VERSION_12345
print("Hello from initial version")
'''

    # Create temporary file
    test_file = Path("./test_fibonacci.py")
    test_file.write_text(test_content)

    try:
        parser = PythonParser()

        print("Parser configuration:")
        print(f"  Available: {parser.is_available}")
        print(f"  Language: {parser.language}")
        print(f"  Chunk types: {parser._config.chunk_types if hasattr(parser, '_config') else 'N/A'}")

        result = parser.parse_file(test_file, test_content)

        print(f"Parse result: {result}")
        print(f"Chunks found: {result.total_chunks}")
        print(f"Parse time: {result.parse_time:.4f}s")
        print(f"Errors: {result.errors}")
        print(f"Warnings: {result.warnings}")
        print(f"Metadata: {result.metadata}")

        if result.chunks:
            print("\n--- Extracted Chunks ---")
            for i, chunk in enumerate(result.chunks):
                print(f"Chunk {i+1}:")
                for key, value in chunk.items():
                    if key == 'code':
                        print(f"  {key}: {len(value)} chars - {repr(value[:50])}...")
                    else:
                        print(f"  {key}: {value}")
        else:
            print("❌ No chunks extracted from fibonacci function!")

    finally:
        if test_file.exists():
            test_file.unlink()

    return result

def main():
    """Run all parser debug tests."""
    print("Python Parser Debug Test Suite")
    print("=" * 50)

    # Test 1: Tree-sitter availability
    ts_available = test_tree_sitter_availability()
    if not ts_available:
        print("❌ Tree-sitter not available - stopping tests")
        return

    # Test 2: Parser initialization
    parser = test_parser_initialization()
    if not parser.is_available:
        print("❌ Parser not available - stopping tests")
        return

    # Test 3: Simple function parsing
    result1 = test_simple_function_parsing()

    # Test 4: Class parsing
    result2 = test_class_parsing()

    # Test 5: Fallback block
    result3 = test_fallback_block()

    # Test 6: Exact test file content
    result4 = test_exact_test_file()

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Simple functions: {result1.total_chunks} chunks")
    print(f"Class parsing: {result2.total_chunks} chunks")
    print(f"Fallback block: {result3.total_chunks} chunks")
    print(f"Fibonacci test: {result4.total_chunks} chunks")

    if any(r.total_chunks == 0 for r in [result1, result2, result3, result4]):
        print("\n❌ PARSER ISSUE CONFIRMED - Some tests extracted 0 chunks")
    else:
        print("\n✅ PARSER WORKING - All tests extracted chunks")

if __name__ == "__main__":
    main()
