#!/usr/bin/env python3
"""
Debug Match Structure

This script investigates the exact structure of tree-sitter query matches
to understand how to properly access captures.
"""

import sys
from pathlib import Path

# Add chunkhound to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def debug_match_structure():
    """Debug the exact structure of tree-sitter matches."""
    print("=== Match Structure Debug ===")

    try:
        import tree_sitter_python as tspython
        import tree_sitter

        # Set up parser
        language = tree_sitter.Language(tspython.language())
        parser = tree_sitter.Parser()
        parser.language = language

        # Test code with functions and classes
        test_code = '''
def hello_world():
    """A simple function."""
    print("Hello, world!")
    return True

def calculate(x, y):
    """Calculate something."""
    return x + y

class TestClass:
    def method(self):
        return "test"

class AnotherClass:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name
'''

        # Parse
        tree = parser.parse(bytes(test_code, 'utf8'))
        print(f"✓ Parsed successfully: {tree.root_node.type}")

        # Test different query patterns
        queries_to_test = [
            ('Simple function', '(function_definition) @func'),
            ('Function with name', '(function_definition name: (identifier) @name) @func'),
            ('Class', '(class_definition) @class'),
            ('Class with name', '(class_definition name: (identifier) @name) @class'),
            ('Method in class', '(class_definition (block (function_definition) @method))'),
        ]

        for query_name, query_str in queries_to_test:
            print(f"\n--- {query_name} ---")
            print(f"Query: {query_str}")

            try:
                query = language.query(query_str)
                matches = query.matches(tree.root_node)
                print(f"Matches found: {len(matches)}")

                for i, match in enumerate(matches[:2]):  # Show first 2 matches
                    print(f"\nMatch {i+1}:")
                    print(f"  Type: {type(match)}")
                    print(f"  Dir: {[attr for attr in dir(match) if not attr.startswith('_')]}")

                    # Try different ways to access match data
                    try:
                        print(f"  Has .captures: {hasattr(match, 'captures')}")
                        if hasattr(match, 'captures'):
                            captures = match.captures
                            print(f"  Captures type: {type(captures)}")
                            print(f"  Captures length: {len(captures)}")

                            for j, capture in enumerate(captures):
                                print(f"    Capture {j}: {type(capture)}")
                                print(f"    Capture dir: {[attr for attr in dir(capture) if not attr.startswith('_')]}")
                                if hasattr(capture, 'name') and hasattr(capture, 'node'):
                                    name = capture.name
                                    node = capture.node
                                    text = test_code[node.start_byte:node.end_byte]
                                    print(f"    Name: {name}")
                                    print(f"    Text: {repr(text[:50])}")
                    except Exception as e:
                        print(f"  Capture access error: {e}")

                    # Try tuple unpacking (old API?)
                    try:
                        if len(match) == 2:
                            pattern_idx, captures_dict = match
                            print(f"  Tuple unpacking: pattern={pattern_idx}, captures={type(captures_dict)}")
                    except Exception as e:
                        print(f"  Tuple unpacking error: {e}")

                    # Try indexing
                    try:
                        print(f"  Match[0]: {type(match[0])} - {match[0]}")
                        if len(match) > 1:
                            print(f"  Match[1]: {type(match[1])} - {match[1]}")
                    except Exception as e:
                        print(f"  Indexing error: {e}")

            except Exception as e:
                print(f"❌ Query failed: {e}")

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()

def test_working_approach():
    """Test a working approach based on findings."""
    print("\n=== Working Approach Test ===")

    try:
        import tree_sitter_python as tspython
        import tree_sitter

        # Set up parser
        language = tree_sitter.Language(tspython.language())
        parser = tree_sitter.Parser()
        parser.language = language

        test_code = '''
def test_function(param):
    return param * 2

class TestClass:
    def method(self):
        pass
'''

        tree = parser.parse(bytes(test_code, 'utf8'))

        # Function query
        query = language.query('(function_definition name: (identifier) @name) @func')
        matches = query.matches(tree.root_node)

        print(f"Function matches: {len(matches)}")
        for match in matches:
            print(f"Match type: {type(match)}")

            # Method 1: Try .captures attribute (newer API)
            if hasattr(match, 'captures'):
                print("Using .captures attribute:")
                for capture in match.captures:
                    name = capture.name
                    node = capture.node
                    text = test_code[node.start_byte:node.end_byte]
                    print(f"  {name}: {text}")

            # Method 2: Try as tuple (older API)
            elif len(match) == 2:
                print("Using tuple unpacking:")
                pattern_idx, captures = match
                print(f"  Pattern: {pattern_idx}")
                print(f"  Captures: {captures}")

            break  # Just test first match

    except Exception as e:
        print(f"❌ Working approach test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_match_structure()
    test_working_approach()
