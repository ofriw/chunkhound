"""Tests for Java parsing functionality."""

import os
from pathlib import Path
import pytest

from chunkhound.parser import CodeParser


@pytest.fixture
def java_test_fixture_path():
    """Path to Java test fixtures."""
    current_dir = Path(__file__).parent
    return current_dir / "fixtures" / "java"


@pytest.fixture
def code_parser():
    """Create and initialize a CodeParser instance."""
    parser = CodeParser()
    parser.setup()
    return parser


def test_parser_initialization(code_parser):
    """Test that the Java parser is properly initialized."""
    if not hasattr(code_parser, "java_language") or not hasattr(code_parser, "_java_initialized"):
        pytest.skip("Java language support not available")
    
    assert hasattr(code_parser, "java_language")
    assert hasattr(code_parser, "java_parser")
    assert hasattr(code_parser, "_java_initialized")
    

def test_java_file_parsing(code_parser, java_test_fixture_path):
    """Test parsing a Java file."""
    if not code_parser._java_initialized:
        pytest.skip("Java parser not initialized")
    
    sample_path = java_test_fixture_path / "Sample.java"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Verify we got some chunks
    assert len(chunks) > 0
    
    # Get all chunk types for verification
    chunk_types = [chunk["type"] for chunk in chunks]
    
    # Check that we found the expected semantic units
    assert "class" in chunk_types
    assert "method" in chunk_types
    assert "interface" in chunk_types
    assert "enum" in chunk_types


def test_java_class_extraction(code_parser, java_test_fixture_path):
    """Test extracting Java classes."""
    if not code_parser._java_initialized:
        pytest.skip("Java parser not initialized")
    
    sample_path = java_test_fixture_path / "Sample.java"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for class chunks
    class_chunks = [c for c in chunks if c["type"] == "class"]
    
    # Verify we found at least one class
    assert len(class_chunks) > 0
    
    # Check the main class properties
    main_class = next((c for c in class_chunks if "Sample" in c["name"]), None)
    assert main_class is not None
    assert main_class["language"] == "java"
    assert "com.example.demo.Sample" in main_class["name"]
    assert "<T extends Comparable<T>>" in main_class["display_name"]
    assert "SuppressWarnings" in str(main_class.get("annotations", []))


def test_java_inner_class_extraction(code_parser, java_test_fixture_path):
    """Test extracting Java inner classes."""
    if not code_parser._java_initialized:
        pytest.skip("Java parser not initialized")
    
    sample_path = java_test_fixture_path / "Sample.java"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for inner class chunks
    inner_class_chunks = [c for c in chunks if c["type"] == "inner_class"]
    
    # Verify we found at least one inner class
    assert len(inner_class_chunks) > 0
    
    # Check the inner class properties
    inner_class = next((c for c in inner_class_chunks if "InnerSample" in c["name"]), None)
    assert inner_class is not None
    assert inner_class["language"] == "java"
    assert "com.example.demo.Sample.InnerSample" in inner_class["name"]
    assert "parent_class" in inner_class


def test_java_method_extraction(code_parser, java_test_fixture_path):
    """Test extracting Java methods."""
    if not code_parser._java_initialized:
        pytest.skip("Java parser not initialized")
    
    sample_path = java_test_fixture_path / "Sample.java"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for method chunks
    method_chunks = [c for c in chunks if c["type"] == "method"]
    
    # Verify we found methods
    assert len(method_chunks) > 0
    
    # Check for specific methods
    add_item_method = next((m for m in method_chunks if "addItem" in m["name"]), None)
    assert add_item_method is not None
    assert add_item_method["language"] == "java"
    assert "parameters" in add_item_method
    
    to_string_method = next((m for m in method_chunks if "toString" in m["name"]), None)
    assert to_string_method is not None
    assert "Override" in str(to_string_method.get("annotations", []))


def test_java_constructor_extraction(code_parser, java_test_fixture_path):
    """Test extracting Java constructors."""
    if not code_parser._java_initialized:
        pytest.skip("Java parser not initialized")
    
    sample_path = java_test_fixture_path / "Sample.java"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for constructor chunks
    constructor_chunks = [c for c in chunks if c["type"] == "constructor"]
    
    # Verify we found at least one constructor
    assert len(constructor_chunks) > 0
    
    # Check constructor properties
    constructor = constructor_chunks[0]
    assert constructor["language"] == "java"
    assert "com.example.demo.Sample.Sample" in constructor["name"]
    assert "String" in str(constructor["parameters"])


def test_java_enum_extraction(code_parser, java_test_fixture_path):
    """Test extracting Java enums."""
    if not code_parser._java_initialized:
        pytest.skip("Java parser not initialized")
    
    sample_path = java_test_fixture_path / "Sample.java"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for enum chunks
    enum_chunks = [c for c in chunks if c["type"] == "enum"]
    
    # Verify we found at least one enum
    assert len(enum_chunks) > 0
    
    # Check enum properties
    enum = enum_chunks[0]
    assert enum["language"] == "java"
    assert "Status" in enum["name"]
    assert "constants" in enum


def test_java_interface_extraction(code_parser, java_test_fixture_path):
    """Test extracting Java interfaces."""
    if not code_parser._java_initialized:
        pytest.skip("Java parser not initialized")
    
    sample_path = java_test_fixture_path / "Sample.java"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for interface chunks
    interface_chunks = [c for c in chunks if c["type"] == "interface"]
    
    # Verify we found at least one interface
    assert len(interface_chunks) > 0
    
    # Check interface properties
    interface = interface_chunks[0]
    assert interface["language"] == "java"
    assert "Processor" in interface["name"]
    assert "<T>" in interface["display_name"]


def test_java_package_extraction(code_parser, java_test_fixture_path):
    """Test extracting Java package information."""
    if not code_parser._java_initialized:
        pytest.skip("Java parser not initialized")
    
    sample_path = java_test_fixture_path / "Sample.java"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # All chunks should have the package name in their qualified name
    for chunk in chunks:
        if chunk["type"] not in ["inner_class", "inner_interface"]:
            assert "com.example.demo" in chunk["name"]


def test_java_no_package_file(code_parser, java_test_fixture_path, tmp_path):
    """Test parsing a Java file without package declaration."""
    if not code_parser._java_initialized:
        pytest.skip("Java parser not initialized")
    
    # Create a temporary Java file without package
    no_package_path = tmp_path / "NoPackage.java"
    with open(no_package_path, "w") as f:
        f.write("""
public class NoPackage {
    public void doSomething() {
        System.out.println("Hello");
    }
}
        """)
    
    chunks = code_parser.parse_file(no_package_path)
    
    # Verify parsing works without package
    assert len(chunks) > 0
    
    # Check that class name doesn't have package prefix
    class_chunk = next((c for c in chunks if c["type"] == "class"), None)
    assert class_chunk is not None
    assert class_chunk["name"] == "NoPackage"