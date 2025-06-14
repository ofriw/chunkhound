#!/usr/bin/env python3
"""
Debug Tree-sitter API

This script investigates the tree-sitter API to find the correct method names
and understand why the Python parser isn't working.
"""

import sys
from pathlib import Path

# Add chunkhound to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def debug_tree_sitter_imports():
    """Debug tree-sitter imports and available modules."""
    print("=== Tree-sitter Import Debug ===")

    try:
        import tree_sitter_python as tspython
        print("✓ tree_sitter_python imported successfully")
        print(f"  Module: {tspython}")
        print(f"  Dir: {dir(tspython)}")

        # Try to get language
        language = tspython.language()
        print(f"✓ Language obtained: {language}")
        print(f"  Language type: {type(language)}")
        print(f"  Language dir: {dir(language)}")

    except ImportError as e:
        print(f"❌ tree_sitter_python import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ tree_sitter_python error: {e}")
        return False

    try:
        from tree_sitter import Language, Parser, Node
        print("✓ tree_sitter core imported successfully")
        print(f"  Language: {Language}")
        print(f"  Parser: {Parser}")
        print(f"  Node: {Node}")

        # Check Parser methods
        parser = Parser()
        print(f"✓ Parser created: {parser}")
        print(f"  Parser type: {type(parser)}")
        print(f"  Parser methods: {[m for m in dir(parser) if not m.startswith('_')]}")

        return True

    except ImportError as e:
        print(f"❌ tree_sitter core import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ tree_sitter core error: {e}")
        return False

def test_parser_setup():
    """Test different ways to set up the parser."""
    print("\n=== Parser Setup Debug ===")

    try:
        import tree_sitter_python as tspython
        from tree_sitter import Parser

        language = tspython.language()
        parser = Parser()

        # Try different ways to set the language
        print("Testing parser.set_language()...")
        try:
            parser.set_language(language)
            print("✓ set_language() worked")
        except AttributeError:
            print("❌ set_language() not available")
        except Exception as e:
            print(f"❌ set_language() error: {e}")

        print("Testing parser.language = ...")
        try:
            parser.language = language
            print("✓ parser.language assignment worked")
        except Exception as e:
            print(f"❌ parser.language assignment error: {e}")

        print("Testing Parser(language)...")
        try:
            parser2 = Parser(language)
            print("✓ Parser(language) constructor worked")
            parser = parser2
        except Exception as e:
            print(f"❌ Parser(language) constructor error: {e}")

        # Try to parse something simple
        print("\nTesting simple parse...")
        try:
            test_code = "def test(): pass"
            tree = parser.parse(bytes(test_code, 'utf8'))
            print(f"✓ Parse successful: {tree}")
            print(f"  Root node: {tree.root_node}")
            print(f"  Root type: {tree.root_node.type}")
            return parser, language
        except Exception as e:
            print(f"❌ Parse failed: {e}")
            return None, None

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return None, None

def test_query_syntax():
    """Test tree-sitter query syntax."""
    print("\n=== Query Syntax Debug ===")

    parser, language = test_parser_setup()
    if not parser or not language:
        print("❌ Cannot test queries - parser setup failed")
        return

    test_code = '''
def hello():
    print("hello")

def calculate(x, y):
    return x + y

class MyClass:
    def method(self):
        pass
'''

    try:
        tree = parser.parse(bytes(test_code, 'utf8'))
        print(f"✓ Test code parsed: {tree.root_node}")

        # Test different query approaches
        queries_to_test = [
            # Original query from parser
            '''(function_definition
                name: (identifier) @function_name
            ) @function_def''',

            # Simpler queries
            '(function_definition) @function',
            '(function_definition name: (identifier) @name)',
            '(class_definition) @class',
            '(class_definition name: (identifier) @name)',
        ]

        for i, query_str in enumerate(queries_to_test):
            print(f"\nTesting query {i+1}: {repr(query_str)}")
            try:
                query = language.query(query_str)
                matches = query.matches(tree.root_node)
                print(f"✓ Query compiled and executed, matches: {len(matches)}")

                for j, match in enumerate(matches[:3]):  # Show first 3 matches
                    print(f"  Match {j+1}: {match}")

            except Exception as e:
                print(f"❌ Query failed: {e}")

    except Exception as e:
        print(f"❌ Query testing failed: {e}")

def test_node_traversal():
    """Test manual node traversal without queries."""
    print("\n=== Node Traversal Debug ===")

    parser, language = test_parser_setup()
    if not parser or not language:
        print("❌ Cannot test traversal - parser setup failed")
        return

    test_code = '''
def hello():
    print("hello")

class MyClass:
    def method(self):
        pass
'''

    try:
        tree = parser.parse(bytes(test_code, 'utf8'))
        root = tree.root_node

        def traverse_node(node, depth=0):
            indent = "  " * depth
            print(f"{indent}{node.type} [{node.start_point}-{node.end_point}]")

            if node.type in ['function_definition', 'class_definition']:
                # Try to find the name
                for child in node.children:
                    if child.type == 'identifier':
                        name = test_code[child.start_byte:child.end_byte]
                        print(f"{indent}  -> Name: {name}")
                        break

            # Recurse on children (limit depth)
            if depth < 3:
                for child in node.children:
                    traverse_node(child, depth + 1)

        print("AST Structure:")
        traverse_node(root)

    except Exception as e:
        print(f"❌ Node traversal failed: {e}")

def main():
    """Run all tree-sitter debug tests."""
    print("Tree-sitter API Debug Suite")
    print("=" * 50)

    # Test 1: Import debug
    if not debug_tree_sitter_imports():
        print("❌ Basic imports failed - stopping")
        return

    # Test 2: Parser setup
    test_parser_setup()

    # Test 3: Query syntax
    test_query_syntax()

    # Test 4: Node traversal
    test_node_traversal()

    print("\n" + "=" * 50)
    print("Debug complete. Check output above for issues.")

if __name__ == "__main__":
    main()
