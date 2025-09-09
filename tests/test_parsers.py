"""
Parser validation tests.

Tests that all parsers can parse minimal valid code samples.
"""

import pytest
from chunkhound.core.types.common import Language
from chunkhound.parsers.parser_factory import get_parser_factory

# Minimal valid code snippets for each language
LANGUAGE_SAMPLES = {
    Language.PYTHON: "def hello(): pass",
    Language.JAVA: "class Test { }",
    Language.CSHARP: "class Test { }",
    Language.TYPESCRIPT: "const x = 1;",
    Language.JAVASCRIPT: "const x = 1;",
    Language.TSX: "const x = <div>hello</div>;",
    Language.JSX: "const x = <div>hello</div>;",
    Language.GROOVY: "def hello() { }",
    Language.KOTLIN: "fun hello() { }",
    Language.GO: "package main\nfunc main() { }",
    Language.RUST: "fn main() { }",
    Language.BASH: "echo hello",
    Language.MAKEFILE: "all:\n\techo hello",
    Language.C: "int main() { return 0; }",
    Language.CPP: "int main() { return 0; }",
    Language.MATLAB: "function result = hello()\nresult = 1;\nend",
    Language.MARKDOWN: "# Hello\nWorld",
    Language.JSON: '{"hello": "world"}',
    Language.YAML: "hello: world",
    Language.TOML: "hello = 'world'",
    Language.TEXT: "hello world",
    Language.PDF: "hello world",  # PDF parser handles text content
}


class TestParserValidation:
    """Test that all parsers can parse minimal valid code."""

    @pytest.mark.parametrize("language", [lang for lang in Language if lang != Language.UNKNOWN])
    def test_parser_can_parse_minimal_code(self, language):
        """Test that each parser can parse a minimal valid code sample."""
        factory = get_parser_factory()
        
        # Create parser
        parser = factory.create_parser(language)
        assert parser is not None, f"Failed to create parser for {language.value}"
        
        # Get sample code
        sample_code = LANGUAGE_SAMPLES.get(language)
        assert sample_code is not None, f"No sample code defined for {language.value}"
        
        # Parse the sample
        try:
            from chunkhound.core.types.common import FileId
            chunks = parser.parse_content(sample_code, "test_file", FileId(1))
            assert isinstance(chunks, list), f"Parser for {language.value} didn't return a list"
            # Don't require chunks - some parsers might return empty for minimal code
        except Exception as e:
            pytest.fail(f"Parser for {language.value} failed to parse minimal code: {e}")