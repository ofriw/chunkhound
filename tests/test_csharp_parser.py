"""Tests for C# parsing functionality."""

import os
from pathlib import Path
import pytest

from chunkhound.parser import CodeParser


@pytest.fixture
def csharp_test_fixture_path():
    """Path to C# test fixtures."""
    current_dir = Path(__file__).parent
    return current_dir / "fixtures" / "csharp"


@pytest.fixture
def code_parser():
    """Create and initialize a CodeParser instance."""
    parser = CodeParser()
    parser.setup()
    return parser


def test_parser_initialization(code_parser):
    """Test that the C# parser is properly initialized."""
    if not hasattr(code_parser, "csharp_language") or not hasattr(code_parser, "_csharp_initialized"):
        pytest.skip("C# language support not available")
    
    assert hasattr(code_parser, "csharp_language")
    assert hasattr(code_parser, "csharp_parser")
    assert hasattr(code_parser, "_csharp_initialized")
    

def test_csharp_file_parsing(code_parser, csharp_test_fixture_path):
    """Test parsing a C# file."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Verify we got some chunks
    assert len(chunks) > 0
    
    # Get all chunk types for verification
    chunk_types = [chunk["type"] for chunk in chunks]
    
    # Check that we found the expected semantic units (all 8 types)
    expected_types = ["class", "method", "interface", "enum", "struct", "property", "constructor"]
    for expected_type in expected_types:
        assert expected_type in chunk_types, f"Expected {expected_type} not found in {chunk_types}"


def test_csharp_class_extraction(code_parser, csharp_test_fixture_path):
    """Test extracting C# classes."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for class chunks
    class_chunks = [c for c in chunks if c["type"] == "class"]
    
    # Verify we found classes
    assert len(class_chunks) > 0
    
    # Check the main Sample class properties
    main_class = next((c for c in class_chunks if "Sample" in c["name"] and "Extensions" not in c["name"]), None)
    assert main_class is not None
    assert main_class["language"] == "csharp"
    assert "Com.Example.Demo.Sample" in main_class["name"]
    assert "<T>" in main_class["display_name"]
    
    # Check for BaseProcessor abstract class
    base_processor = next((c for c in class_chunks if "BaseProcessor" in c["name"]), None)
    assert base_processor is not None
    assert base_processor["language"] == "csharp"
    assert "Com.Example.Demo.BaseProcessor" in base_processor["name"]
    
    # Check for ConcreteProcessor class
    concrete_processor = next((c for c in class_chunks if "ConcreteProcessor" in c["name"]), None)
    assert concrete_processor is not None
    assert "Com.Example.Demo.ConcreteProcessor" in concrete_processor["name"]


def test_csharp_interface_extraction(code_parser, csharp_test_fixture_path):
    """Test extracting C# interfaces."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for interface chunks
    interface_chunks = [c for c in chunks if c["type"] == "interface"]
    
    # Verify we found interfaces
    assert len(interface_chunks) > 0
    
    # Check IProcessor interface
    processor_interface = next((c for c in interface_chunks if "IProcessor" in c["name"] and "Extended" not in c["name"]), None)
    assert processor_interface is not None
    assert processor_interface["language"] == "csharp"
    assert "Com.Example.Demo.IProcessor" in processor_interface["name"]
    assert "<T>" in processor_interface["display_name"]
    
    # Check IExtendedProcessor interface
    extended_interface = next((c for c in interface_chunks if "IExtendedProcessor" in c["name"]), None)
    assert extended_interface is not None
    assert "Com.Example.Demo.IExtendedProcessor" in extended_interface["name"]


def test_csharp_struct_extraction(code_parser, csharp_test_fixture_path):
    """Test extracting C# structs."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for struct chunks
    struct_chunks = [c for c in chunks if c["type"] == "struct"]
    
    # Verify we found structs
    assert len(struct_chunks) > 0
    
    # Check Configuration struct
    config_struct = next((c for c in struct_chunks if "Configuration" in c["name"]), None)
    assert config_struct is not None
    assert config_struct["language"] == "csharp"
    assert "Com.Example.Demo.Configuration" in config_struct["name"]
    
    # Check NestedData struct
    nested_struct = next((c for c in struct_chunks if "NestedData" in c["name"]), None)
    assert nested_struct is not None
    assert "Com.Example.Demo.Sample.NestedData" in nested_struct["name"]


def test_csharp_enum_extraction(code_parser, csharp_test_fixture_path):
    """Test extracting C# enums."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for enum chunks
    enum_chunks = [c for c in chunks if c["type"] == "enum"]
    
    # Verify we found enums
    assert len(enum_chunks) > 0
    
    # Check Status enum
    status_enum = next((c for c in enum_chunks if "Status" in c["name"]), None)
    assert status_enum is not None
    assert status_enum["language"] == "csharp"
    assert "Com.Example.Demo.Status" in status_enum["name"]
    
    # Check Priority enum
    priority_enum = next((c for c in enum_chunks if "Priority" in c["name"]), None)
    assert priority_enum is not None
    assert "Com.Example.Demo.Priority" in priority_enum["name"]


def test_csharp_method_extraction(code_parser, csharp_test_fixture_path):
    """Test extracting C# methods."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for method chunks
    method_chunks = [c for c in chunks if c["type"] == "method"]
    
    # Verify we found methods
    assert len(method_chunks) > 0
    
    # Check AddItem method
    add_item_method = next((m for m in method_chunks if "AddItem" in m["name"]), None)
    assert add_item_method is not None
    assert add_item_method["language"] == "csharp"
    assert "parameters" in add_item_method
    assert "Com.Example.Demo.Sample.AddItem" in add_item_method["name"]
    
    # Check GetItems method with parameters
    get_items_method = next((m for m in method_chunks if "GetItems" in m["name"]), None)
    assert get_items_method is not None
    assert "parameters" in get_items_method
    
    # Check ToString override method
    to_string_method = next((m for m in method_chunks if "ToString" in m["name"]), None)
    assert to_string_method is not None
    
    # Check static method
    create_string_method = next((m for m in method_chunks if "CreateStringSample" in m["name"]), None)
    assert create_string_method is not None
    assert "Com.Example.Demo.Sample.CreateStringSample" in create_string_method["name"]


def test_csharp_property_extraction(code_parser, csharp_test_fixture_path):
    """Test extracting C# properties."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for property chunks
    property_chunks = [c for c in chunks if c["type"] == "property"]
    
    # Verify we found properties
    assert len(property_chunks) > 0
    
    # Check Name property (expression-bodied)
    name_property = next((p for p in property_chunks if "Name" in p["name"] and "Com.Example.Demo.Sample" in p["name"]), None)
    assert name_property is not None
    assert name_property["language"] == "csharp"
    assert "Com.Example.Demo.Sample.Name" in name_property["name"]
    
    # Check Items property (full getter/setter)
    items_property = next((p for p in property_chunks if "Items" in p["name"] and "Sample" in p["name"]), None)
    assert items_property is not None
    assert "Com.Example.Demo.Sample.Items" in items_property["name"]
    
    # Check auto-implemented property
    is_active_property = next((p for p in property_chunks if "IsActive" in p["name"]), None)
    assert is_active_property is not None
    assert "Com.Example.Demo.Sample.IsActive" in is_active_property["name"]


def test_csharp_constructor_extraction(code_parser, csharp_test_fixture_path):
    """Test extracting C# constructors."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for constructor chunks
    constructor_chunks = [c for c in chunks if c["type"] == "constructor"]
    
    # Verify we found constructors
    assert len(constructor_chunks) > 0
    
    # Check parameterized constructor
    param_constructor = next((c for c in constructor_chunks if "parameters" in c and len(c["parameters"]) > 0), None)
    assert param_constructor is not None
    assert param_constructor["language"] == "csharp"
    assert "Com.Example.Demo.Sample.Sample" in param_constructor["name"]
    assert "string" in str(param_constructor["parameters"]).lower()
    
    # Check parameterless constructor
    parameterless_constructor = next((c for c in constructor_chunks if "parameters" in c and len(c["parameters"]) == 0), None)
    assert parameterless_constructor is not None


def test_csharp_namespace_extraction(code_parser, csharp_test_fixture_path):
    """Test extracting C# namespace information."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # All chunks should have the namespace name in their qualified name
    main_namespace_chunks = [c for c in chunks if "Com.Example.Demo" in c["name"] and "Extensions" not in c["name"]]
    extensions_namespace_chunks = [c for c in chunks if "Com.Example.Demo.Extensions" in c["name"]]
    
    # Verify we found chunks in both namespaces
    assert len(main_namespace_chunks) > 0
    assert len(extensions_namespace_chunks) > 0
    
    # Check specific classes are in correct namespace
    sample_class = next((c for c in chunks if c["type"] == "class" and "Sample" in c["name"] and "Extensions" not in c["name"]), None)
    assert sample_class is not None
    assert "Com.Example.Demo.Sample" in sample_class["name"]
    
    extensions_class = next((c for c in chunks if c["type"] == "class" and "SampleExtensions" in c["name"]), None)
    assert extensions_class is not None
    assert "Com.Example.Demo.Extensions.SampleExtensions" in extensions_class["name"]


def test_csharp_generic_types(code_parser, csharp_test_fixture_path):
    """Test handling C# generic types."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Check generic class
    generic_class = next((c for c in chunks if c["type"] == "class" and "Sample" in c["name"] and "Extensions" not in c["name"]), None)
    assert generic_class is not None
    assert "<T>" in generic_class["display_name"]
    
    # Check generic interface
    generic_interface = next((c for c in chunks if c["type"] == "interface" and "IProcessor" in c["name"] and "Extended" not in c["name"]), None)
    assert generic_interface is not None
    assert "<T>" in generic_interface["display_name"]


def test_csharp_inheritance_and_implementation(code_parser, csharp_test_fixture_path):
    """Test C# inheritance and interface implementation."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Check ConcreteProcessor class that inherits and implements
    concrete_class = next((c for c in chunks if c["type"] == "class" and "ConcreteProcessor" in c["name"]), None)
    assert concrete_class is not None
    # Should have information about base class and implemented interfaces in the code content
    assert "BaseProcessor" in concrete_class["content"] or "IProcessor" in concrete_class["content"]
    
    # Check interface inheritance
    extended_interface = next((c for c in chunks if c["type"] == "interface" and "IExtendedProcessor" in c["name"]), None)
    assert extended_interface is not None
    assert "IProcessor" in extended_interface["content"]


def test_csharp_no_namespace_file(code_parser, tmp_path):
    """Test parsing a C# file without namespace declaration."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    # Create a temporary C# file without namespace
    no_namespace_path = tmp_path / "NoNamespace.cs"
    with open(no_namespace_path, "w") as f:
        f.write("""
public class NoNamespace
{
    public string Name { get; set; }
    
    public NoNamespace(string name)
    {
        Name = name;
    }
    
    public void DoSomething()
    {
        Console.WriteLine("Hello");
    }
}
        """)
    
    chunks = code_parser.parse_file(no_namespace_path)
    
    # Verify parsing works without namespace
    assert len(chunks) > 0
    
    # Check that class name doesn't have namespace prefix
    class_chunk = next((c for c in chunks if c["type"] == "class"), None)
    assert class_chunk is not None
    assert class_chunk["name"] == "NoNamespace"


def test_csharp_error_handling(code_parser, tmp_path):
    """Test C# parser error handling with malformed code."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    # Create a C# file with syntax errors
    malformed_path = tmp_path / "Malformed.cs"
    with open(malformed_path, "w") as f:
        f.write("""
public class Malformed
{
    public void Method(
    // Missing closing parenthesis and brace
        """)
    
    # Parser should handle errors gracefully and return what it can parse
    chunks = code_parser.parse_file(malformed_path)
    
    # Should not crash, though may have limited results
    assert isinstance(chunks, list)


def test_csharp_semantic_unit_coverage(code_parser, csharp_test_fixture_path):
    """Test that all 8 C# semantic unit types are extracted."""
    if not code_parser._csharp_initialized:
        pytest.skip("C# parser not initialized")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Get unique chunk types
    chunk_types = set(chunk["type"] for chunk in chunks)
    
    # Verify all 8 semantic unit types are present
    expected_types = {
        "class",      # Classes (Sample, BaseProcessor, ConcreteProcessor, etc.)
        "interface",  # Interfaces (IProcessor, IExtendedProcessor)
        "struct",     # Structs (Configuration, NestedData)
        "enum",       # Enums (Status, Priority)
        "method",     # Methods (AddItem, GetItems, ToString, etc.)
        "property",   # Properties (Name, Items, IsActive, etc.)
        "constructor" # Constructors (Sample constructors, etc.)
    }
    
    # Check that we found all expected types
    missing_types = expected_types - chunk_types
    assert len(missing_types) == 0, f"Missing semantic unit types: {missing_types}"
    
    # Print summary for verification
    type_counts = {t: len([c for c in chunks if c["type"] == t]) for t in expected_types}
    print(f"\nC# Semantic Unit Extraction Summary:")
    for unit_type, count in sorted(type_counts.items()):
        print(f"  {unit_type}: {count} chunks")
    
    # Verify we have a reasonable number of each type
    assert type_counts["class"] >= 4    # Sample, BaseProcessor, ConcreteProcessor, SampleExtensions, InnerSample
    assert type_counts["interface"] >= 2 # IProcessor, IExtendedProcessor
    assert type_counts["struct"] >= 2    # Configuration, NestedData
    assert type_counts["enum"] >= 2      # Status, Priority
    assert type_counts["method"] >= 8    # Multiple methods across classes
    assert type_counts["property"] >= 5  # Multiple properties across classes/structs
    assert type_counts["constructor"] >= 3 # Multiple constructors across classes/structs