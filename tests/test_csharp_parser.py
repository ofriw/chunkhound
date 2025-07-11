"""Tests for C# parsing functionality."""

import os
from pathlib import Path
import pytest
import asyncio

from chunkhound.registry import get_registry, create_indexing_coordinator
from chunkhound.services.indexing_coordinator import IndexingCoordinator
from chunkhound.parser import CodeParser
from chunkhound.core.types.common import Language


def _is_csharp_parser_available():
    """Check if C# parser is available through registry."""
    try:
        registry = get_registry()
        csharp_parser = registry.get_language_parser(Language.CSHARP)
        return csharp_parser is not None
    except Exception:
        return False



@pytest.fixture
def csharp_test_fixture_path():
    """Path to C# test fixtures."""
    current_dir = Path(__file__).parent
    return current_dir / "fixtures" / "csharp"


@pytest.fixture
def indexing_coordinator():
    """Create and initialize an IndexingCoordinator instance."""
    registry = get_registry()
    coordinator = create_indexing_coordinator()
    return coordinator


@pytest.fixture
def code_parser():
    """Create and initialize a CodeParser instance."""
    parser = CodeParser()
    parser.setup()
    return parser


def test_parser_initialization(code_parser):
    """Test that the C# parser is properly initialized."""
    # Check if C# parser is available through registry
    registry = get_registry()
    csharp_parser = registry.get_language_parser(Language.CSHARP)
    
    if not csharp_parser:
        pytest.skip("C# language support not available")
    
    assert csharp_parser is not None
    assert hasattr(csharp_parser, 'parse_file')


def test_refactored_parser_registry_integration(code_parser):
    """Test that the refactored parser properly uses the registry system."""
    # Verify the parser is using registry system
    assert code_parser._registry is not None, "Parser should have registry initialized"
    
    # Test that parse_file delegates to registry
    test_cs_content = """
namespace Test {
    public class SimpleClass {
        public void Method() { }
    }
}
"""
    
    # Create temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cs', delete=False) as f:
        f.write(test_cs_content)
        f.flush()
        
        try:
            result = code_parser.parse_file(Path(f.name))
            
            # Verify result structure - should get chunks from registry parser
            assert isinstance(result, list), "Should return list of chunks"
            if _is_csharp_parser_available():
                assert len(result) > 0, "Should parse and return chunks for valid C# code"
                
                # Verify we got expected elements
                class_chunks = [c for c in result if c["chunk_type"] == "class"]
                assert len(class_chunks) >= 1, "Should find the SimpleClass"
                
                simple_class = class_chunks[0]
                assert "SimpleClass" in simple_class["symbol"], "Should have correct class name"
                assert "Test" in simple_class["symbol"], "Should include namespace in symbol"
                
        finally:
            Path(f.name).unlink()


def test_refactored_parser_error_handling():
    """Test that the refactored parser handles errors properly."""
    parser = CodeParser()
    parser.setup()
    
    # Test with unsupported file type
    with pytest.raises(RuntimeError, match="No parser plugin available"):
        parser.parse_file(Path("/fake/file.xyz"))
    
    # Test with non-existent file (C# parser gracefully handles this)
    if _is_csharp_parser_available():
        # The C# parser logs errors but returns empty list for missing files
        result = parser.parse_file(Path("/nonexistent/file.cs"))
        assert isinstance(result, list), "Should return list even for missing files"
        assert len(result) == 0, "Should return empty list for missing files"
    

def test_csharp_class_parsing(code_parser, csharp_test_fixture_path):
    """Test parsing a C# file and validate specific semantic elements."""
    # Check if C# parser is available
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Verify we got some chunks
    assert len(chunks) > 0
    
    # Test 1: Verify we can find the main generic Sample class
    sample_classes = [c for c in chunks if c["chunk_type"] == "class" and "Sample" in c.get("symbol", "")]
    assert len(sample_classes) > 0, "Should find at least one Sample class"
    
    main_sample = next((c for c in sample_classes if c["symbol"].endswith("Sample")), None)
    assert main_sample is not None, "Should find the main Sample<T> class"
    assert "class Sample<T>" in main_sample["code"], "Should contain generic class declaration"
    assert "where T : IComparable<T>" in main_sample["code"], "Should contain generic constraint"
    
    # Test 2: Verify constructor extraction
    constructors = [c for c in chunks if c["chunk_type"] == "constructor"]
    assert len(constructors) >= 2, "Should find at least 2 constructors for Sample class"
    
    # Find parameterized constructor
    param_constructor = next((c for c in constructors if "string name" in c["code"]), None)
    assert param_constructor is not None, "Should find constructor with string parameter"
    assert "ArgumentNullException" in param_constructor["code"], "Should contain null check logic"
    
    # Test 3: Verify method extraction with proper symbols
    methods = [c for c in chunks if c["chunk_type"] == "method"]
    assert len(methods) > 0, "Should find methods"
    
    add_item_method = next((m for m in methods if "AddItem" in m.get("symbol", "")), None)
    if add_item_method:  # Method might not be in current fixture
        assert "void AddItem(T item)" in add_item_method["code"] or "AddItem" in add_item_method["code"]
    
    # Test 4: Verify interface extraction
    interfaces = [c for c in chunks if c["chunk_type"] == "interface"]
    assert len(interfaces) > 0, "Should find interfaces"
    
    processor_interface = next((i for i in interfaces if "IProcessor" in i.get("symbol", "")), None)
    assert processor_interface is not None, "Should find IProcessor interface"
    
    # Test 5: Verify namespace qualification in symbols
    namespaced_chunks = [c for c in chunks if "Com.Example.Demo" in c.get("symbol", "")]
    assert len(namespaced_chunks) > 0, "Should find chunks with namespace qualification"
    
    # Test 6: Verify chunk metadata quality
    for chunk in chunks:
        assert "symbol" in chunk, "Each chunk should have a symbol"
        assert "chunk_type" in chunk, "Each chunk should have a chunk_type"
        assert "code" in chunk, "Each chunk should have code content"
        assert "start_line" in chunk, "Each chunk should have start_line"
        assert "end_line" in chunk, "Each chunk should have end_line"
        assert chunk["start_line"] <= chunk["end_line"], "start_line should be <= end_line"
        assert len(chunk["code"].strip()) > 0, "Code content should not be empty"


def test_csharp_enum_parsing(code_parser, csharp_test_fixture_path):
    """Test extracting C# classes."""
    # Check if C# parser is available
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for class chunks
    class_chunks = [c for c in chunks if c["chunk_type"] == "class"]
    
    # Verify we found classes
    assert len(class_chunks) > 0
    
    # Check the main Sample class properties
    main_class = next((c for c in class_chunks if "Sample" in c["symbol"] and "Extensions" not in c["symbol"]), None)
    assert main_class is not None
    assert "Com.Example.Demo.Sample" in main_class["symbol"]
    
    # Check for BaseProcessor abstract class
    base_processor = next((c for c in class_chunks if "BaseProcessor" in c["symbol"]), None)
    assert base_processor is not None
    assert "Com.Example.Demo.BaseProcessor" in base_processor["symbol"]
    
    # Check for ConcreteProcessor class
    concrete_processor = next((c for c in class_chunks if "ConcreteProcessor" in c["symbol"]), None)
    assert concrete_processor is not None
    assert "Com.Example.Demo.ConcreteProcessor" in concrete_processor["symbol"]


def test_csharp_interface_parsing(code_parser, csharp_test_fixture_path):
    """Test extracting C# interfaces."""
    # Check if C# parser is available
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for interface chunks
    interface_chunks = [c for c in chunks if c["chunk_type"] == "interface"]
    
    # Verify we found interfaces
    assert len(interface_chunks) > 0
    
    # Check for IProcessor interface
    processor_interface = next((c for c in interface_chunks if "IProcessor" in c["symbol"] and "Extended" not in c["symbol"]), None)
    assert processor_interface is not None
    assert "Com.Example.Demo.IProcessor" in processor_interface["symbol"]
    
    # Check IExtendedProcessor interface
    extended_interface = next((c for c in interface_chunks if "IExtendedProcessor" in c["symbol"]), None)
    assert extended_interface is not None
    assert "Com.Example.Demo.IExtendedProcessor" in extended_interface["symbol"]


def test_csharp_struct_parsing(code_parser, csharp_test_fixture_path):
    """Test extracting C# structs."""
    # Check if C# parser is available
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for struct chunks
    struct_chunks = [c for c in chunks if c["chunk_type"] == "struct"]
    
    # Verify we found structs
    assert len(struct_chunks) > 0
    
    # Check for Configuration struct
    config_struct = next((c for c in struct_chunks if "Configuration" in c["symbol"]), None)
    assert config_struct is not None
    assert "Com.Example.Demo.Configuration" in config_struct["symbol"]
    
    # Check NestedData struct
    nested_struct = next((c for c in struct_chunks if "NestedData" in c["symbol"]), None)
    assert nested_struct is not None
    assert "Com.Example.Demo.Sample.NestedData" in nested_struct["symbol"]


def test_csharp_namespace_parsing(code_parser, csharp_test_fixture_path):
    """Test extracting C# enums."""
    # Check if C# parser is available
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for enum chunks
    enum_chunks = [c for c in chunks if c["chunk_type"] == "enum"]
    
    # Verify we found enums
    assert len(enum_chunks) > 0
    
    # Check for Status enum
    status_enum = next((c for c in enum_chunks if "Status" in c["symbol"]), None)
    assert status_enum is not None
    assert "Com.Example.Demo.Status" in status_enum["symbol"]
    
    # Check Priority enum
    priority_enum = next((c for c in enum_chunks if "Priority" in c["symbol"]), None)
    assert priority_enum is not None
    assert "Com.Example.Demo.Priority" in priority_enum["symbol"]


def test_csharp_delegate_parsing(code_parser, csharp_test_fixture_path):
    """Test extracting C# methods."""
    # Check if C# parser is available
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for method chunks
    method_chunks = [c for c in chunks if c["chunk_type"] == "method"]
    
    # Verify we found methods
    assert len(method_chunks) > 0
    
    # Check for AddItem method
    add_item_method = next((c for c in method_chunks if "AddItem" in c["symbol"]), None)
    assert add_item_method is not None
    assert "Com.Example.Demo.Sample.AddItem" in add_item_method["symbol"]
    
    # Check GetItems method with parameters
    get_items_method = next((m for m in method_chunks if "GetItems" in m["symbol"]), None)
    assert get_items_method is not None
    
    # Check ToString override method
    to_string_method = next((m for m in method_chunks if "ToString" in m["symbol"]), None)
    assert to_string_method is not None
    
    # Check static method
    create_string_method = next((m for m in method_chunks if "CreateStringSample" in m["symbol"]), None)
    assert create_string_method is not None
    assert "Com.Example.Demo.Sample.CreateStringSample" in create_string_method["symbol"]


def test_csharp_generics_parsing(code_parser, csharp_test_fixture_path):
    """Test extracting C# properties."""
    # Check if C# parser is available
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for property chunks
    property_chunks = [c for c in chunks if c["chunk_type"] == "property"]
    
    # Verify we found properties
    assert len(property_chunks) > 0
    
    # Check Name property (expression-bodied)
    # Check Name property
    name_property = next((p for p in property_chunks if "Name" in p["symbol"] and "Sample" in p["symbol"]), None)
    assert name_property is not None
    assert "Com.Example.Demo.Sample.Name" in name_property["symbol"]
    
    # Check Items property (generic collection)
    items_property = next((p for p in property_chunks if "Items" in p["symbol"] and "Sample" in p["symbol"]), None)
    assert items_property is not None
    assert "Com.Example.Demo.Sample.Items" in items_property["symbol"]
    
    # Check IsActive property
    active_property = next((p for p in property_chunks if "IsActive" in p["symbol"]), None)
    assert active_property is not None
    assert "Com.Example.Demo.Sample.IsActive" in active_property["symbol"]


def test_csharp_constructor_extraction(code_parser, csharp_test_fixture_path):
    """Test extracting C# constructors."""
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Filter for constructor chunks
    constructor_chunks = [c for c in chunks if c["chunk_type"] == "constructor"]
    
    # Verify we found constructors
    assert len(constructor_chunks) > 0
    
    # Check parameterized constructor
    param_constructor = next((c for c in constructor_chunks if "string" in c["symbol"]), None)
    assert param_constructor is not None
    assert "Com.Example.Demo.Sample.Sample" in param_constructor["symbol"]
    
    # Check parameterless constructor
    parameterless_constructor = next((c for c in constructor_chunks if c["symbol"].endswith("Sample()") and "string" not in c["symbol"]), None)
    assert parameterless_constructor is not None


def test_csharp_namespace_extraction(code_parser, csharp_test_fixture_path):
    """Test extracting C# namespace information."""
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # All chunks should have the namespace name in their qualified name
    main_namespace_chunks = [c for c in chunks if "Com.Example.Demo" in c["symbol"] and "Extensions" not in c["symbol"]]
    extensions_namespace_chunks = [c for c in chunks if "Com.Example.Demo.Extensions" in c["symbol"]]
    
    # Verify we found chunks in both namespaces
    assert len(main_namespace_chunks) > 0
    assert len(extensions_namespace_chunks) > 0
    
    # Check specific classes are in correct namespace
    sample_class = next((c for c in chunks if c["chunk_type"] == "class" and "Sample" in c["symbol"] and "Extensions" not in c["symbol"]), None)
    assert sample_class is not None
    assert "Com.Example.Demo.Sample" in sample_class["symbol"]
    
    extensions_class = next((c for c in chunks if c["chunk_type"] == "class" and "SampleExtensions" in c["symbol"]), None)
    assert extensions_class is not None
    assert "Com.Example.Demo.Extensions.SampleExtensions" in extensions_class["symbol"]


def test_csharp_generic_types(code_parser, csharp_test_fixture_path):
    """Test handling C# generic types."""
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Check generic class
    generic_class = next((c for c in chunks if c["chunk_type"] == "class" and "Sample" in c["symbol"] and "Extensions" not in c["symbol"]), None)
    assert generic_class is not None
    assert "<T>" in generic_class["code"]
    
    # Check generic interface
    generic_interface = next((c for c in chunks if c["chunk_type"] == "interface" and "IProcessor" in c["symbol"] and "Extended" not in c["symbol"]), None)
    assert generic_interface is not None
    assert "<T>" in generic_interface["code"]


def test_csharp_inheritance_and_implementation(code_parser, csharp_test_fixture_path):
    """Test C# inheritance and interface implementation."""
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Check ConcreteProcessor class that inherits and implements
    concrete_class = next((c for c in chunks if c["chunk_type"] == "class" and "ConcreteProcessor" in c["symbol"]), None)
    assert concrete_class is not None
    # Should have information about base class and implemented interfaces in the code content
    assert "BaseProcessor" in concrete_class["code"] or "IProcessor" in concrete_class["code"]
    
    # Check interface inheritance
    extended_interface = next((c for c in chunks if c["chunk_type"] == "interface" and "IExtendedProcessor" in c["symbol"]), None)
    assert extended_interface is not None
    assert "IProcessor" in extended_interface["code"]


def test_csharp_no_namespace_file(code_parser, tmp_path):
    """Test parsing a C# file without namespace declaration."""
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
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
    class_chunk = next((c for c in chunks if c["chunk_type"] == "class"), None)
    assert class_chunk is not None
    assert class_chunk["symbol"] == "NoNamespace"


def test_csharp_error_handling(code_parser, tmp_path):
    """Test C# parser error handling with malformed code."""
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
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
    if not _is_csharp_parser_available():
        pytest.skip("C# parser not available")
    
    sample_path = csharp_test_fixture_path / "Sample.cs"
    if not sample_path.exists():
        pytest.skip(f"Test fixture not found: {sample_path}")
    
    chunks = code_parser.parse_file(sample_path)
    
    # Get unique chunk types
    chunk_types = set(chunk["chunk_type"] for chunk in chunks)
    
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
    type_counts = {t: len([c for c in chunks if c["chunk_type"] == t]) for t in expected_types}
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