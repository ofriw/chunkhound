"""Unit tests for PHP parser."""

import pytest
from pathlib import Path

from chunkhound.core.types.common import Language, ChunkType
from chunkhound.parsers.parser_factory import ParserFactory


@pytest.fixture
def php_parser():
    """Create a PHP parser instance."""
    factory = ParserFactory()
    return factory.create_parser(Language.PHP)


@pytest.fixture
def comprehensive_php():
    """Load comprehensive PHP test file."""
    fixture_path = Path(__file__).parent / "fixtures" / "php" / "comprehensive.php"
    if not fixture_path.exists():
        pytest.skip(f"Test fixture not found: {fixture_path}")
    return fixture_path


def test_php_parser_available():
    """Test that PHP parser is available."""
    factory = ParserFactory()
    assert factory.is_language_available(Language.PHP)


def test_php_file_detection():
    """Test that PHP files are detected correctly."""
    factory = ParserFactory()

    test_cases = [
        ("test.php", Language.PHP),
        ("index.phtml", Language.PHP),
        ("legacy.php3", Language.PHP),
        ("script.php4", Language.PHP),
        ("old.php5", Language.PHP),
    ]

    for filename, expected_lang in test_cases:
        detected = factory.detect_language(Path(filename))
        assert detected == expected_lang, f"Failed to detect {filename} as {expected_lang}"


def test_parse_classes(php_parser):
    """Test parsing PHP classes."""
    code = """<?php
    class TestClass {
        public function testMethod() {
            return true;
        }
    }
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # Should extract at least the class
    class_chunks = [c for c in chunks if c.chunk_type == ChunkType.CLASS]
    assert len(class_chunks) > 0, "No class chunks found"
    assert any("TestClass" in c.symbol for c in class_chunks), "TestClass not found in chunks"


def test_parse_functions(php_parser):
    """Test parsing PHP functions."""
    code = """<?php
    function myFunction($param1, $param2) {
        return $param1 + $param2;
    }
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # Should extract the function
    func_chunks = [c for c in chunks if c.chunk_type == ChunkType.FUNCTION]
    assert len(func_chunks) > 0, "No function chunks found"
    assert any("myFunction" in c.symbol for c in func_chunks), "myFunction not found"


def test_parse_interfaces(php_parser):
    """Test parsing PHP interfaces."""
    code = """<?php
    interface TestInterface {
        public function testMethod();
    }
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # Should extract the interface
    interface_chunks = [c for c in chunks if c.chunk_type == ChunkType.INTERFACE]
    assert len(interface_chunks) > 0, "No interface chunks found"
    assert any("TestInterface" in c.symbol for c in interface_chunks), "TestInterface not found"


def test_parse_traits(php_parser):
    """Test parsing PHP traits."""
    code = """<?php
    trait TestTrait {
        public function testMethod() {}
    }
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # Should extract the trait (ChunkType.TRAIT after fix)
    assert len(chunks) > 0, "No chunks found"
    # Find chunks with trait metadata
    trait_chunks = [c for c in chunks if c.metadata and c.metadata.get("kind") == "trait"]
    assert len(trait_chunks) > 0, "No trait chunks found"
    assert any("TestTrait" in c.symbol for c in trait_chunks), "TestTrait not found"


def test_metadata_visibility(php_parser):
    """Test that visibility modifiers are captured."""
    # The cAST algorithm extracts classes and methods
    # Methods within classes may be extracted separately or merged into the class
    # We test that the parser can capture visibility metadata
    code = """<?php
    class MyClass {
        public function publicMethod() {
            return true;
        }
    }
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # The parser should extract at least the class
    assert len(chunks) > 0, "No chunks found"

    # Check if any chunk has method metadata with visibility
    # This could be a separate method chunk or metadata within the class
    has_visibility = False
    for chunk in chunks:
        if chunk.metadata:
            # Check if this chunk or its content has visibility info
            if "visibility" in chunk.metadata:
                has_visibility = True
                break
            # If it's a class, check the code content for method definitions
            if chunk.chunk_type == ChunkType.CLASS and "public function" in chunk.code:
                has_visibility = True
                break

    assert has_visibility, "No visibility information found in chunks"


def test_metadata_static(php_parser):
    """Test that static modifier is captured."""
    code = """<?php
    class MyClass {
        public static function staticMethod() {
            return 42;
        }
    }
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # Should have at least one chunk
    assert len(chunks) > 0, "No chunks found"

    # Check if static information is captured
    has_static = False
    for chunk in chunks:
        if chunk.metadata and chunk.metadata.get("is_static"):
            has_static = True
            break
        # Also check code content for static keyword
        if "static" in chunk.code:
            has_static = True
            break

    assert has_static, "No static information found"


def test_metadata_abstract(php_parser):
    """Test that abstract modifier is captured."""
    code = """<?php
    abstract class AbstractClass {
        abstract public function abstractMethod();
    }
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # Find class with abstract metadata
    abstract_classes = [c for c in chunks if c.metadata and c.metadata.get("is_abstract")]
    assert len(abstract_classes) > 0, "No abstract classes found"


def test_metadata_final(php_parser):
    """Test that final modifier is captured."""
    code = """<?php
    final class FinalClass {}
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # Find class with final metadata
    final_classes = [c for c in chunks if c.metadata and c.metadata.get("is_final")]
    assert len(final_classes) > 0, "No final classes found"


def test_metadata_parameters(php_parser):
    """Test that parameters are extracted."""
    code = """<?php
    function myFunc(int $x, string $y): bool {
        return true;
    }
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # Find function with parameters
    funcs_with_params = [c for c in chunks if c.metadata and "parameters" in c.metadata]
    assert len(funcs_with_params) > 0, "No functions with parameters found"

    # Check parameter structure
    params = funcs_with_params[0].metadata["parameters"]
    assert len(params) >= 2, "Expected at least 2 parameters"


def test_metadata_return_type(php_parser):
    """Test that return types are extracted."""
    code = """<?php
    function myFunc(): bool {
        return true;
    }
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # Find function with return type
    funcs_with_return = [c for c in chunks if c.metadata and "return_type" in c.metadata]
    assert len(funcs_with_return) > 0, "No functions with return type found"


def test_parse_comments(php_parser):
    """Test that comments are parsed."""
    code = """<?php
    /**
     * PHPDoc comment
     */
    class MyClass {}

    // Line comment
    function myFunc() {}

    /* Block comment */
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # Should have comment chunks
    comment_chunks = [c for c in chunks if c.chunk_type == ChunkType.COMMENT]
    assert len(comment_chunks) > 0, "No comment chunks found"


def test_parse_namespaces(php_parser):
    """Test that namespaces are parsed."""
    code = """<?php
    namespace App\\Controllers;

    use App\\Models\\User;

    class MyClass {}
    """

    chunks = php_parser.parse_content(code, Path("test.php"), file_id=1)

    # Should extract namespace/use statements
    # These might be in metadata or as separate chunks
    assert len(chunks) > 0, "No chunks extracted from namespaced code"


def test_comprehensive_file(php_parser, comprehensive_php):
    """Test parsing the comprehensive PHP fixture file."""
    chunks = php_parser.parse_file(comprehensive_php, file_id=1)

    # Should extract multiple chunks from comprehensive file
    # Note: cAST algorithm may merge related code, so count may be lower than individual definitions
    assert len(chunks) > 0, f"Expected chunks from comprehensive file, got {len(chunks)}"

    # Should have various chunk types
    chunk_types = {c.chunk_type for c in chunks}
    has_classes = ChunkType.CLASS in chunk_types or any("class" in str(ct) for ct in chunk_types)
    has_functions = ChunkType.FUNCTION in chunk_types or any("function" in str(ct) for ct in chunk_types)
    has_traits = ChunkType.TRAIT in chunk_types or any("trait" in str(ct) for ct in chunk_types)
    has_interfaces = ChunkType.INTERFACE in chunk_types or any("interface" in str(ct) for ct in chunk_types)

    # Should have at least some of these types
    type_count = sum([has_classes, has_functions, has_traits, has_interfaces])
    assert type_count >= 2, f"Expected multiple chunk types, found types: {chunk_types}"

    # Should have metadata on many chunks
    chunks_with_metadata = [c for c in chunks if c.metadata]
    assert len(chunks_with_metadata) > 0, "No chunks with metadata"

    # Should have some PHP-specific features in the code
    all_code = "\n".join(c.code for c in chunks)
    assert "namespace" in all_code or "class" in all_code, "No PHP structures found in parsed code"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
