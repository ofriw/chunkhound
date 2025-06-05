#!/usr/bin/env python3
"""
Java AST Explorer - Tree-sitter grammar analysis tool

This script explores the tree-sitter AST structure for Java code to help understand
the grammar structure and node types for implementing Java parsing in ChunkHound.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

try:
    from tree_sitter_language_pack import get_language, get_parser
    JAVA_AVAILABLE = True
except ImportError:
    print("Error: tree-sitter-language-pack not installed.")
    print("Install with: pip install tree-sitter-language-pack")
    JAVA_AVAILABLE = False
    sys.exit(1)

# Sample Java code for testing
SAMPLE_JAVA_CODE = """
package com.example.demo;

import java.util.ArrayList;
import java.util.List;
import static java.util.Collections.sort;

/**
 * Example Java class for AST analysis
 */
@SuppressWarnings("unused")
public class Sample<T extends Comparable<T>> {
    
    private final String name;
    private List<T> items = new ArrayList<>();
    
    public Sample(String name) {
        this.name = name;
    }
    
    /**
     * Add an item to the collection
     */
    public void addItem(T item) {
        items.add(item);
    }
    
    public List<T> getItems() {
        return new ArrayList<>(items);
    }
    
    @Override
    public String toString() {
        return "Sample(" + name + ", items=" + items.size() + ")";
    }
    
    // Inner class example
    private class InnerSample {
        void process() {
            System.out.println("Processing " + name);
        }
    }
    
    // Enum example
    public enum Status {
        ACTIVE, INACTIVE, PENDING;
        
        public boolean isActive() {
            return this == ACTIVE;
        }
    }
    
    // Interface example
    public interface Processor<T> {
        void process(T item);
    }
}
"""

def print_node(node, source_code: str, depth: int = 0):
    """Print a node and its children with indentation."""
    indent = "  " * depth
    node_text = source_code[node.start_byte:node.end_byte]
    # Truncate very long node text for display
    if len(node_text) > 100:
        node_text = node_text[:97] + "..."
    
    # Clean up newlines for display
    node_text = node_text.replace("\n", "\\n")
    
    print(f"{indent}{node.type}: [{node.start_point[0]},{node.start_point[1]}] - "
          f"[{node.end_point[0]},{node.end_point[1]}] '{node_text}'")
    
    for child in node.children:
        print_node(child, source_code, depth + 1)

def explore_query(language, node, source_code: str, query_string: str, name: str):
    """Execute a query and print the results."""
    print(f"\n--- Executing Query: {name} ---")
    print(f"Query: {query_string}\n")
    
    query = language.query(query_string)
    matches = query.matches(node)
    
    print(f"Found {len(matches)} matches:")
    for i, match in enumerate(matches):
        capture_dict = {}
        for capture_index, (name, capture_node) in enumerate(match[1].items()):
            if isinstance(capture_node, list):
                # Handle case where multiple nodes match the same capture name
                capture_node = capture_node[0]
            
            capture_dict[name] = capture_node
            node_text = source_code[capture_node.start_byte:capture_node.end_byte]
            if len(node_text) > 100:
                node_text = node_text[:97] + "..."
            node_text = node_text.replace("\n", "\\n")
            
            print(f"{i+1}.{capture_index} {name} [{capture_node.start_point[0]},{capture_node.start_point[1]}] - "
                  f"[{capture_node.end_point[0]},{capture_node.end_point[1]}]: {node_text}")

def main():
    """Main function to run the Java AST explorer."""
    if not JAVA_AVAILABLE:
        return
    
    print("Java AST Explorer")
    print("=" * 80)
    
    # Get Java language and parser
    java_language = get_language('java')
    java_parser = get_parser('java')
    
    if not java_language or not java_parser:
        print("Error: Failed to initialize Java parser")
        return
    
    print("Java parser initialized successfully")
    
    # Parse the sample code
    tree = java_parser.parse(bytes(SAMPLE_JAVA_CODE, "utf8"))
    root_node = tree.root_node
    
    # Print the AST
    print("\n--- Full AST ---")
    # Uncomment to see full AST (can be very verbose)
    # print_node(root_node, SAMPLE_JAVA_CODE)
    print("(AST display suppressed - uncomment line in code to show)")
    
    # Try different queries to explore the Java grammar
    
    # 1. Find class declarations
    class_query = """
    (class_declaration
      name: (identifier) @class_name
    ) @class_def
    """
    explore_query(java_language, root_node, SAMPLE_JAVA_CODE, class_query, "Classes")
    
    # 2. Find method declarations
    method_query = """
    (method_declaration
      name: (identifier) @method_name
    ) @method_def
    """
    explore_query(java_language, root_node, SAMPLE_JAVA_CODE, method_query, "Methods")
    
    # 3. Find package declaration
    package_query = """
    (package_declaration) @package_def
    """
    explore_query(java_language, root_node, SAMPLE_JAVA_CODE, package_query, "Package")
    
    # 4. Find imports
    import_query = """
    (import_declaration) @import
    """
    explore_query(java_language, root_node, SAMPLE_JAVA_CODE, import_query, "Imports")
    
    # 5. Find interfaces
    interface_query = """
    (interface_declaration
      name: (identifier) @interface_name
    ) @interface_def
    """
    explore_query(java_language, root_node, SAMPLE_JAVA_CODE, interface_query, "Interfaces")
    
    # 6. Find enums
    enum_query = """
    (enum_declaration
      name: (identifier) @enum_name
    ) @enum_def
    """
    explore_query(java_language, root_node, SAMPLE_JAVA_CODE, enum_query, "Enums")
    
    # 7. Find fields
    field_query = """
    (field_declaration
      declarator: (variable_declarator
        name: (identifier) @field_name
      )
    ) @field_def
    """
    explore_query(java_language, root_node, SAMPLE_JAVA_CODE, field_query, "Fields")
    
    # 8. Find annotations
    annotation_query = """
    (annotation
      name: (_) @annotation_name
    ) @annotation_def
    """
    explore_query(java_language, root_node, SAMPLE_JAVA_CODE, annotation_query, "Annotations")
    
    # 9. Find inner classes
    inner_class_query = """
    (class_declaration
      (class_body
        (class_declaration
          name: (identifier) @inner_class_name
        ) @inner_class_def
      )
    )
    """
    explore_query(java_language, root_node, SAMPLE_JAVA_CODE, inner_class_query, "Inner Classes")
    
    # 10. Find type parameters (generics)
    generic_query = """
    (type_parameters
      (type_parameter) @type_param
    ) @type_params
    """
    explore_query(java_language, root_node, SAMPLE_JAVA_CODE, generic_query, "Type Parameters")

if __name__ == "__main__":
    main()