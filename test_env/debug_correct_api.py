#!/usr/bin/env python3
"""
Debug Correct Tree-sitter API

This script tests the correct tree-sitter API based on actual documentation
to understand how to properly initialize the Python parser.
"""

import sys
from pathlib import Path

# Add chunkhound to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_correct_api():
    """Test the correct tree-sitter API."""
    print("=== Testing Correct Tree-sitter API ===")

    try:
        import tree_sitter_python as tspython
        import tree_sitter
        print("✓ Imports successful")

        # Method 1: Using tree_sitter.Language.from_library
        parser = None
        try:
            language = tree_sitter.Language(tspython.language())
            parser = tree_sitter.Parser()
            parser.language = language
            print(f"✓ Method 1 - Language created: {language}")
            print(f"  Type: {type(language)}")
        except Exception as e:
            print(f"❌ Method 1 failed: {e}")
            language = None

        # Method 2: Check if we need to use the language directly
        if language is None:
            try:
                # Some versions expect direct assignment
                parser = tree_sitter.Parser()
                parser.language = tspython.language()
                print("✓ Method 2 - Direct language assignment worked")
                language = tspython.language()
            except Exception as e:
                print(f"❌ Method 2 failed: {e}")

        # Method 3: Check current tree-sitter version and API
        try:
            print(f"tree_sitter version: {tree_sitter.__version__ if hasattr(tree_sitter, '__version__') else 'unknown'}")
            print(f"tree_sitter_python version: {tspython.__version__ if hasattr(tspython, '__version__') else 'unknown'}")
        except:
            pass

        # If we have a working setup, test parsing
        if language is not None and parser is not None:
            test_parsing(parser, language)

    except ImportError as e:
        print(f"❌ Import failed: {e}")

def test_parsing(parser, language):
    """Test actual parsing with the working setup."""
    print("\n=== Testing Parsing ===")

    test_code = '''
def hello_world():
    """A simple function."""
    print("Hello, world!")
    return True

class TestClass:
    def method(self):
        return "test"
'''

    try:
        tree = parser.parse(bytes(test_code, 'utf8'))
        print(f"✓ Parsing successful: {tree}")
        print(f"  Root node: {tree.root_node}")
        print(f"  Root type: {tree.root_node.type}")

        # Test query
        print("\n--- Testing Queries ---")

        # Simple function query
        try:
            query = language.query('(function_definition) @func')
            matches = query.matches(tree.root_node)
            print(f"✓ Simple function query: {len(matches)} matches")
        except Exception as e:
            print(f"❌ Simple function query failed: {e}")

        # Function with name query
        try:
            query = language.query('(function_definition name: (identifier) @name) @func')
            matches = query.matches(tree.root_node)
            print(f"✓ Function name query: {len(matches)} matches")

            for match in matches:
                captures = {}
                for capture in match.captures:
                    node = capture.node
                    name = capture.name
                    text = test_code[node.start_byte:node.end_byte]
                    captures[name] = text
                print(f"  Captures: {captures}")

        except Exception as e:
            print(f"❌ Function name query failed: {e}")

        # Class query
        try:
            query = language.query('(class_definition name: (identifier) @name) @class')
            matches = query.matches(tree.root_node)
            print(f"✓ Class query: {len(matches)} matches")
        except Exception as e:
            print(f"❌ Class query failed: {e}")

        # Manual traversal to understand structure
        print("\n--- AST Structure ---")
        traverse_tree(tree.root_node, test_code, max_depth=2)

    except Exception as e:
        print(f"❌ Parsing failed: {e}")

def traverse_tree(node, source, depth=0, max_depth=3):
    """Traverse and print tree structure."""
    if depth > max_depth:
        return

    indent = "  " * depth
    text = source[node.start_byte:node.end_byte]
    text_preview = repr(text[:30] + "..." if len(text) > 30 else text)

    print(f"{indent}{node.type} [{node.start_point}-{node.end_point}] {text_preview}")

    # For function and class definitions, find their names
    if node.type in ['function_definition', 'class_definition']:
        for child in node.children:
            if child.type == 'identifier':
                name = source[child.start_byte:child.end_byte]
                print(f"{indent}  -> Name: {name}")
                break

    # Recurse on children
    for child in node.children:
        traverse_tree(child, source, depth + 1, max_depth)

def test_minimal_working_example():
    """Create a minimal working example."""
    print("\n=== Minimal Working Example ===")

    try:
        import tree_sitter_python as tspython
        import tree_sitter

        # Try the most likely correct approach
        parser = tree_sitter.Parser()

        # Test different ways to set language
        language_obj = None

        # Approach 1: Direct assignment (newer API)
        try:
            parser.language = tspython.language()
            language_obj = tspython.language()
            print("✓ Direct assignment worked")
        except Exception as e:
            print(f"❌ Direct assignment failed: {e}")

        # Approach 2: Wrapper (older API)
        if language_obj is None:
            try:
                lang = tree_sitter.Language(tspython.language())
                parser.language = lang
                language_obj = lang
                print("✓ Language wrapper worked")
            except Exception as e:
                print(f"❌ Language wrapper failed: {e}")

        # Test simple parse
        if language_obj is not None:
            code = "def test(): pass"
            tree = parser.parse(bytes(code, 'utf8'))
            print(f"✓ Simple parse: {tree.root_node.type}")

            # Test query
            query = language_obj.query('(function_definition)')
            matches = query.matches(tree.root_node)
            print(f"✓ Query found {len(matches)} functions")

            return True
        else:
            print("❌ No working language setup found")
            return False

    except Exception as e:
        print(f"❌ Minimal example failed: {e}")
        return False

def main():
    """Run all API tests."""
    print("Tree-sitter Correct API Test")
    print("=" * 40)

    # Test correct API
    test_correct_api()

    # Test minimal working example
    success = test_minimal_working_example()

    print(f"\n{'✓ SUCCESS' if success else '❌ FAILED'}: Tree-sitter API test")

if __name__ == "__main__":
    main()
