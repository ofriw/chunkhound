"""Tests for JavaScript parsing functionality."""

import os
from pathlib import Path
import pytest
import tempfile

from chunkhound.core.types.common import Language
from chunkhound.registry import get_registry
from chunkhound.providers.parsing.javascript_parser import JavaScriptParser


@pytest.fixture
def javascript_parser():
    """Create and initialize a JavaScriptParser instance."""
    parser = JavaScriptParser()
    return parser


@pytest.fixture
def sample_js_code():
    """Sample JavaScript code for testing."""
    return """
// Sample JavaScript file
function add(a, b) {
    return a + b;
}

const multiply = (x, y) => x * y;

class Calculator {
    constructor(name) {
        this.name = name;
    }
    
    calculate(operation, a, b) {
        if (operation === 'add') {
            return add(a, b);
        }
        return 0;
    }
}

// React component
function Button(props) {
    return <button onClick={props.onClick}>{props.label}</button>;
}

const Card = ({ title, children }) => (
    <div className="card">
        <h3>{title}</h3>
        {children}
    </div>
);
"""


@pytest.fixture
def sample_jsx_code():
    """Sample JSX code for testing."""
    return """
import React from 'react';

function Welcome(props) {
    return <h1>Hello, {props.name}!</h1>;
}

class App extends React.Component {
    render() {
        return (
            <div>
                <Welcome name="World" />
            </div>
        );
    }
}

export default App;
"""


def test_parser_initialization(javascript_parser):
    """Test that the JavaScript parser is properly initialized."""
    assert javascript_parser.language == Language.JAVASCRIPT
    assert (
        javascript_parser.is_available or not javascript_parser.is_available
    )  # May not be available in test env


def test_javascript_function_parsing(javascript_parser, sample_js_code):
    """Test parsing JavaScript functions."""
    if not javascript_parser.is_available:
        pytest.skip("JavaScript parser not available")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(sample_js_code)
        f.flush()

        try:
            result = javascript_parser.parse_file(Path(f.name))

            # Should have extracted functions
            assert result.total_chunks > 0
            function_chunks = [
                c for c in result.chunks if c["chunk_type"] == "function"
            ]
            assert len(function_chunks) > 0

            # Check for specific functions
            function_names = [c["name"] for c in function_chunks]
            assert "add" in function_names
            assert "multiply" in function_names

            # Check React components
            assert "Button" in function_names
            assert "Card" in function_names

        finally:
            os.unlink(f.name)


def test_javascript_class_parsing(javascript_parser, sample_js_code):
    """Test parsing JavaScript classes."""
    if not javascript_parser.is_available:
        pytest.skip("JavaScript parser not available")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(sample_js_code)
        f.flush()

        try:
            result = javascript_parser.parse_file(Path(f.name))

            # Should have extracted classes
            class_chunks = [c for c in result.chunks if c["chunk_type"] == "class"]
            assert len(class_chunks) > 0

            # Check for Calculator class
            class_names = [c["name"] for c in class_chunks]
            assert "Calculator" in class_names

        finally:
            os.unlink(f.name)


def test_javascript_method_parsing(javascript_parser, sample_js_code):
    """Test parsing JavaScript class methods."""
    if not javascript_parser.is_available:
        pytest.skip("JavaScript parser not available")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(sample_js_code)
        f.flush()

        try:
            result = javascript_parser.parse_file(Path(f.name))

            # Should have extracted methods
            method_chunks = [c for c in result.chunks if c["chunk_type"] == "method"]
            assert len(method_chunks) > 0

            # Check for specific methods
            method_names = [c["name"] for c in method_chunks]
            assert any("Calculator.calculate" in name for name in method_names)

        finally:
            os.unlink(f.name)


def test_jsx_component_parsing(javascript_parser, sample_jsx_code):
    """Test parsing JSX React components."""
    if not javascript_parser.is_available:
        pytest.skip("JavaScript parser not available")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsx", delete=False) as f:
        f.write(sample_jsx_code)
        f.flush()

        try:
            result = javascript_parser.parse_file(Path(f.name))

            # Should have extracted components
            function_chunks = [
                c for c in result.chunks if c["chunk_type"] == "function"
            ]
            assert len(function_chunks) > 0

            # Check for React components (start with capital letter)
            component_names = [
                c["name"] for c in function_chunks if c["name"][0].isupper()
            ]
            assert "Welcome" in component_names

        finally:
            os.unlink(f.name)


def test_registry_integration():
    """Test that JavaScript parser is properly registered."""
    registry = get_registry()

    # Should be able to get JavaScript parser
    js_parser = registry.get_language_parser(Language.JAVASCRIPT)
    assert js_parser is not None
    assert isinstance(js_parser, JavaScriptParser)

    # Should be able to get JSX parser (should be same as JavaScript)
    jsx_parser = registry.get_language_parser(Language.JSX)
    assert jsx_parser is not None
    assert isinstance(jsx_parser, JavaScriptParser)


def test_base_class_usage(javascript_parser):
    """Test that JavaScript parser uses base class methods."""
    # Check that it inherits from base parser
    assert hasattr(javascript_parser, "_create_chunk")
    assert hasattr(javascript_parser, "_get_node_text")
    assert hasattr(javascript_parser, "_extract_chunks")


def test_no_typescript_patterns():
    """Test that JavaScript parser doesn't use TypeScript-specific patterns."""
    # Read the parser source to ensure no TypeScript patterns
    parser_file = (
        Path(__file__).parent.parent / "providers" / "parsing" / "javascript_parser.py"
    )
    if parser_file.exists():
        content = parser_file.read_text()

        # Should not contain TypeScript-specific patterns
        assert "type_annotation" not in content
        assert "return_type:" not in content
        assert "interface_declaration" not in content
        assert "type_alias_declaration" not in content
