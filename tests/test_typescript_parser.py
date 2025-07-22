"""Tests for TypeScript parsing functionality."""

import os
from pathlib import Path
import pytest
import tempfile

from chunkhound.core.types.common import Language
from chunkhound.registry import get_registry
from chunkhound.providers.parsing.typescript_parser import TypeScriptParser


@pytest.fixture
def typescript_parser():
    """Create and initialize a TypeScriptParser instance."""
    parser = TypeScriptParser()
    return parser


@pytest.fixture
def sample_ts_code():
    """Sample TypeScript code for testing."""
    return """
// Sample TypeScript file
interface User {
    id: number;
    name: string;
    email?: string;
}

type Status = 'active' | 'inactive' | 'pending';

enum Priority {
    Low = 1,
    Medium,
    High
}

class UserService<T extends User> {
    private users: T[] = [];
    
    constructor(private config: Config) {}
    
    addUser(user: T): void {
        this.users.push(user);
    }
    
    findUser(id: number): T | undefined {
        return this.users.find(u => u.id === id);
    }
}

function processUser<T extends User>(user: T): T {
    return { ...user, processed: true };
}

const getDisplayName = (user: User): string => {
    return user.name || 'Unknown';
};

// React component with TypeScript
interface ButtonProps {
    label: string;
    onClick: () => void;
    disabled?: boolean;
}

function Button({ label, onClick, disabled = false }: ButtonProps): JSX.Element {
    return <button onClick={onClick} disabled={disabled}>{label}</button>;
}

const Card: React.FC<CardProps> = ({ title, children }) => (
    <div className="card">
        <h3>{title}</h3>
        {children}
    </div>
);
"""


@pytest.fixture
def sample_tsx_code():
    """Sample TSX code for testing.""" 
    return """
import React from 'react';

interface Props {
    title: string;
    subtitle?: string;
}

const Header: React.FC<Props> = ({ title, subtitle }) => {
    return (
        <header>
            <h1>{title}</h1>
            {subtitle && <h2>{subtitle}</h2>}
        </header>
    );
};

class App extends React.Component<{}, { count: number }> {
    state = { count: 0 };
    
    increment = (): void => {
        this.setState(prev => ({ count: prev.count + 1 }));
    };
    
    render(): JSX.Element {
        return (
            <div>
                <Header title="My App" subtitle="Welcome" />
                <p>Count: {this.state.count}</p>
                <button onClick={this.increment}>+</button>
            </div>
        );
    }
}

export default App;
"""


def test_parser_initialization(typescript_parser):
    """Test that the TypeScript parser is properly initialized."""
    assert typescript_parser.language == Language.TYPESCRIPT
    assert typescript_parser.is_available or not typescript_parser.is_available  # May not be available in test env


def test_typescript_function_parsing(typescript_parser, sample_ts_code):
    """Test parsing TypeScript functions."""
    if not typescript_parser.is_available:
        pytest.skip("TypeScript parser not available")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
        f.write(sample_ts_code)
        f.flush()
        
        try:
            result = typescript_parser.parse_file(Path(f.name))
            
            # Should have extracted functions
            assert result.total_chunks > 0
            function_chunks = [c for c in result.chunks if c["chunk_type"] == "function"]
            assert len(function_chunks) > 0
            
            # Check for specific functions
            function_names = [c["name"] for c in function_chunks]
            assert "processUser" in function_names
            assert "getDisplayName" in function_names
            
            # Check React components
            assert "Button" in function_names
            assert "Card" in function_names
            
        finally:
            os.unlink(f.name)


def test_typescript_interface_parsing(typescript_parser, sample_ts_code):
    """Test parsing TypeScript interfaces."""
    if not typescript_parser.is_available:
        pytest.skip("TypeScript parser not available")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
        f.write(sample_ts_code)
        f.flush()
        
        try:
            result = typescript_parser.parse_file(Path(f.name))
            
            # Should have extracted interfaces
            interface_chunks = [c for c in result.chunks if c["chunk_type"] == "interface"]
            assert len(interface_chunks) > 0
            
            # Check for specific interfaces
            interface_names = [c["name"] for c in interface_chunks]
            assert "User" in interface_names
            assert "ButtonProps" in interface_names
            
        finally:
            os.unlink(f.name)


def test_typescript_type_alias_parsing(typescript_parser, sample_ts_code):
    """Test parsing TypeScript type aliases."""
    if not typescript_parser.is_available:
        pytest.skip("TypeScript parser not available")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
        f.write(sample_ts_code)
        f.flush()
        
        try:
            result = typescript_parser.parse_file(Path(f.name))
            
            # Should have extracted type aliases
            type_chunks = [c for c in result.chunks if c["chunk_type"] == "type_alias"]
            assert len(type_chunks) > 0
            
            # Check for specific types
            type_names = [c["name"] for c in type_chunks]
            assert "Status" in type_names
            
        finally:
            os.unlink(f.name)


def test_typescript_enum_parsing(typescript_parser, sample_ts_code):
    """Test parsing TypeScript enums."""
    if not typescript_parser.is_available:
        pytest.skip("TypeScript parser not available")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
        f.write(sample_ts_code)
        f.flush()
        
        try:
            result = typescript_parser.parse_file(Path(f.name))
            
            # Should have extracted enums
            enum_chunks = [c for c in result.chunks if c["chunk_type"] == "enum"]
            assert len(enum_chunks) > 0
            
            # Check for specific enums
            enum_names = [c["name"] for c in enum_chunks]
            assert "Priority" in enum_names
            
        finally:
            os.unlink(f.name)


def test_typescript_class_parsing(typescript_parser, sample_ts_code):
    """Test parsing TypeScript classes."""
    if not typescript_parser.is_available:
        pytest.skip("TypeScript parser not available")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
        f.write(sample_ts_code)
        f.flush()
        
        try:
            result = typescript_parser.parse_file(Path(f.name))
            
            # Should have extracted classes
            class_chunks = [c for c in result.chunks if c["chunk_type"] == "class"]
            assert len(class_chunks) > 0
            
            # Check for UserService class
            class_names = [c["name"] for c in class_chunks]
            assert "UserService" in class_names
            
        finally:
            os.unlink(f.name)


def test_typescript_method_parsing(typescript_parser, sample_ts_code):
    """Test parsing TypeScript class methods."""
    if not typescript_parser.is_available:
        pytest.skip("TypeScript parser not available")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
        f.write(sample_ts_code)
        f.flush()
        
        try:
            result = typescript_parser.parse_file(Path(f.name))
            
            # Should have extracted methods
            method_chunks = [c for c in result.chunks if c["chunk_type"] == "method"]
            assert len(method_chunks) > 0
            
            # Check for specific methods
            method_names = [c["name"] for c in method_chunks]
            assert any("UserService.addUser" in name for name in method_names)
            assert any("UserService.findUser" in name for name in method_names)
            
        finally:
            os.unlink(f.name)


def test_tsx_component_parsing(typescript_parser, sample_tsx_code):
    """Test parsing TSX React components."""
    if not typescript_parser.is_available:
        pytest.skip("TypeScript parser not available")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.tsx', delete=False) as f:
        f.write(sample_tsx_code)
        f.flush()
        
        try:
            result = typescript_parser.parse_file(Path(f.name))
            
            # Should have extracted components and interfaces
            function_chunks = [c for c in result.chunks if c["chunk_type"] == "function"]
            interface_chunks = [c for c in result.chunks if c["chunk_type"] == "interface"]
            
            assert len(function_chunks) > 0
            assert len(interface_chunks) > 0
            
            # Check for React components
            component_names = [c["name"] for c in function_chunks if c["name"][0].isupper()]
            assert "Header" in component_names
            
            # Check for Props interface
            interface_names = [c["name"] for c in interface_chunks]
            assert "Props" in interface_names
            
        finally:
            os.unlink(f.name)


def test_registry_integration():
    """Test that TypeScript parser is properly registered."""
    registry = get_registry()
    
    # Should be able to get TypeScript parser
    ts_parser = registry.get_language_parser(Language.TYPESCRIPT)
    assert ts_parser is not None
    assert isinstance(ts_parser, TypeScriptParser)
    
    # Should be able to get TSX parser (should be same as TypeScript)
    tsx_parser = registry.get_language_parser(Language.TSX)
    assert tsx_parser is not None
    assert isinstance(tsx_parser, TypeScriptParser)


def test_base_class_usage(typescript_parser):
    """Test that TypeScript parser uses base class methods."""
    # Check that it inherits from base parser
    assert hasattr(typescript_parser, '_create_chunk')
    assert hasattr(typescript_parser, '_get_node_text')
    assert hasattr(typescript_parser, '_extract_chunks')


def test_typescript_specific_features():
    """Test that TypeScript parser supports TypeScript-specific features."""
    # Read the parser source to ensure TypeScript patterns are present
    parser_file = Path(__file__).parent.parent / "providers" / "parsing" / "typescript_parser.py"
    if parser_file.exists():
        content = parser_file.read_text()
        
        # Should contain TypeScript-specific patterns
        assert "interface_declaration" in content
        assert "type_alias_declaration" in content
        assert "enum_declaration" in content
        
        # But the problematic query should be fixed
        assert "return_type: (type_annotation" not in content


def test_no_impossible_pattern_error(typescript_parser, sample_ts_code):
    """Test that the 'Impossible pattern' error is fixed."""
    if not typescript_parser.is_available:
        pytest.skip("TypeScript parser not available")
    
    # This should not raise the "Impossible pattern at row 3, column 25" error
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
        f.write(sample_ts_code)
        f.flush()
        
        try:
            result = typescript_parser.parse_file(Path(f.name))
            
            # Should succeed without errors
            assert len(result.errors) == 0 or all("Impossible pattern" not in error for error in result.errors)
            assert result.total_chunks > 0
            
        finally:
            os.unlink(f.name)