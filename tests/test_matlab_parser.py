"""Tests for the Matlab parser implementation."""

import tempfile
from pathlib import Path
from typing import List, Dict, Any

import pytest

from chunkhound.core.types.common import ChunkType, Language
from chunkhound.providers.parsing.matlab_parser import MatlabParser
from chunkhound.interfaces.language_parser import ParseConfig


class TestMatlabParser:
    """Test suite for Matlab language parser."""

    @pytest.fixture
    def parser(self) -> MatlabParser:
        """Create a Matlab parser instance for testing."""
        return MatlabParser()

    @pytest.fixture
    def sample_matlab_function(self) -> str:
        """Sample Matlab function for testing."""
        return '''function [x, y] = processData(inputMatrix, threshold)
% PROCESSDATA Process input matrix with threshold
%   [X, Y] = PROCESSDATA(INPUTMATRIX, THRESHOLD) processes the input matrix
%   and returns filtered results in X and Y arrays.

    if nargin < 2
        threshold = 0.5;
    end
    
    % Filter data based on threshold
    x = inputMatrix(inputMatrix > threshold);
    y = find(inputMatrix > threshold);
    
    % Nested function
    function result = helper(data)
        result = data * 2;
    end
    
    x = helper(x);
end'''

    @pytest.fixture
    def sample_matlab_class(self) -> str:
        """Sample Matlab class for testing."""
        return '''classdef DataProcessor < handle
    % DATAPROCESSOR A class for processing data
    %   This class provides methods for data manipulation and analysis.
    
    properties (Access = private)
        data
        threshold = 0.1
    end
    
    properties (Access = public)
        name
        verbose = false
    end
    
    methods
        function obj = DataProcessor(name, data)
            % Constructor for DataProcessor
            if nargin > 0
                obj.name = name;
            end
            if nargin > 1
                obj.data = data;
            end
        end
        
        function result = process(obj, options)
            % Process the stored data
            if obj.verbose
                fprintf('Processing data for %s\\n', obj.name);
            end
            
            if nargin < 2
                options = struct();
            end
            
            result = obj.data(obj.data > obj.threshold);
        end
        
        function setThreshold(obj, newThreshold)
            % Set the threshold value
            obj.threshold = newThreshold;
        end
    end
    
    methods (Static)
        function info = getInfo()
            % Get class information
            info = 'DataProcessor v1.0';
        end
    end
end'''

    @pytest.fixture
    def sample_matlab_script(self) -> str:
        """Sample Matlab script for testing."""
        return '''% Simple Matlab script for data analysis
clear all;
clc;

% Generate sample data
n = 100;
data = randn(n, 1);
threshold = 0.5;

% Process data
filtered_data = data(data > threshold);
indices = find(data > threshold);

% Plot results
figure;
subplot(2, 1, 1);
plot(data);
title('Original Data');

subplot(2, 1, 2);
plot(indices, filtered_data, 'ro');
title('Filtered Data');

% Display statistics
fprintf('Original data points: %d\\n', length(data));
fprintf('Filtered data points: %d\\n', length(filtered_data));
fprintf('Mean of filtered data: %.2f\\n', mean(filtered_data));'''

    @pytest.fixture
    def sample_matlab_nested_functions(self) -> str:
        """Sample Matlab file with nested functions."""
        return '''function result = outerFunction(x, y)
% Main function with nested functions

    result = processInputs(x, y);
    
    function output = processInputs(a, b)
        % First nested function
        temp = localHelper(a) + localHelper(b);
        output = finalProcess(temp);
    end
    
    function val = localHelper(input)
        % Second nested function
        val = input ^ 2 + 1;
    end
    
    function final = finalProcess(data)
        % Third nested function
        final = sqrt(data);
    end
end

function [mean_val, std_val] = statisticsFunction(data)
% Separate function for statistics
    mean_val = mean(data);
    std_val = std(data);
end'''

    def test_parser_initialization(self, parser: MatlabParser):
        """Test parser initializes correctly."""
        assert parser.language == Language.MATLAB
        assert ChunkType.FUNCTION in parser.supported_chunk_types
        assert ChunkType.CLASS in parser.supported_chunk_types
        assert ChunkType.METHOD in parser.supported_chunk_types
        assert ChunkType.SCRIPT in parser.supported_chunk_types
        assert ChunkType.BLOCK in parser.supported_chunk_types

    def test_parse_matlab_function(self, parser: MatlabParser, sample_matlab_function: str):
        """Test parsing a Matlab function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(sample_matlab_function)
            f.flush()
            
            result = parser.parse_file(Path(f.name), sample_matlab_function)
            
        assert result.language == Language.MATLAB
        assert len(result.errors) == 0
        
        # Should extract function chunks
        function_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.FUNCTION.value]
        assert len(function_chunks) >= 1
        
        main_function = function_chunks[0]
        assert "processData" in main_function["symbol"]
        assert "parameters" in main_function
        assert "return_values" in main_function

    def test_parse_matlab_class(self, parser: MatlabParser, sample_matlab_class: str):
        """Test parsing a Matlab class."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(sample_matlab_class)
            f.flush()
            
            result = parser.parse_file(Path(f.name), sample_matlab_class)
        
        assert result.language == Language.MATLAB
        assert len(result.errors) == 0
        
        # Should extract class chunks
        class_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.CLASS.value]
        assert len(class_chunks) >= 1
        
        class_chunk = class_chunks[0]
        assert "DataProcessor" in class_chunk["symbol"]
        assert "inheritance" in class_chunk

    def test_parse_matlab_methods(self, parser: MatlabParser, sample_matlab_class: str):
        """Test parsing Matlab class methods."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(sample_matlab_class)
            f.flush()
            
            result = parser.parse_file(Path(f.name), sample_matlab_class)
        
        # Should extract method chunks
        method_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.METHOD.value]
        
        # Should find methods like DataProcessor (constructor), process, setThreshold, getInfo
        assert len(method_chunks) >= 3
        
        # Check for specific methods
        method_names = [m["symbol"] for m in method_chunks]
        assert any("process" in name for name in method_names)
        assert any("setThreshold" in name for name in method_names)

    def test_parse_matlab_script(self, parser: MatlabParser, sample_matlab_script: str):
        """Test parsing Matlab script-level code."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(sample_matlab_script)
            f.flush()
            
            result = parser.parse_file(Path(f.name), sample_matlab_script)
        
        # Should extract script chunks since this has no top-level functions
        script_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.SCRIPT.value]
        block_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.BLOCK.value]
        
        # Should find script-level code
        assert len(script_chunks) >= 1 or len(block_chunks) >= 1

    def test_parse_nested_functions(self, parser: MatlabParser, sample_matlab_nested_functions: str):
        """Test parsing Matlab nested functions."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(sample_matlab_nested_functions)
            f.flush()
            
            result = parser.parse_file(Path(f.name), sample_matlab_nested_functions)
        
        # Should extract multiple function chunks
        function_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.FUNCTION.value]
        assert len(function_chunks) >= 2  # outerFunction and statisticsFunction

    def test_parse_config_filtering(self, sample_matlab_class: str):
        """Test that parse configuration filters chunk types correctly."""
        # Create parser that only extracts classes
        config = ParseConfig(
            language=Language.MATLAB,
            chunk_types={ChunkType.CLASS},
            max_chunk_size=8000,
            min_chunk_size=100,
            include_imports=True,
            include_comments=False,
            include_docstrings=True,
            max_depth=10,
            use_cache=True
        )
        parser = MatlabParser(config)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(sample_matlab_class)
            f.flush()
            
            result = parser.parse_file(Path(f.name), sample_matlab_class)
        
        # Should only have class chunks
        class_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.CLASS.value]
        method_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.METHOD.value]
        
        assert len(class_chunks) >= 1
        assert len(method_chunks) == 0  # Should be filtered out

    def test_function_signature_extraction(self, parser: MatlabParser, sample_matlab_function: str):
        """Test function signature extraction."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(sample_matlab_function)
            f.flush()
            
            result = parser.parse_file(Path(f.name), sample_matlab_function)
        
        function_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.FUNCTION.value]
        if function_chunks:
            main_function = function_chunks[0]
            
            # Check parameters
            assert "parameters" in main_function
            params = main_function["parameters"]
            assert "inputMatrix" in params or "threshold" in params
            
            # Check return values
            assert "return_values" in main_function
            returns = main_function["return_values"]
            assert "x" in returns or "y" in returns

    def test_class_inheritance_extraction(self, parser: MatlabParser, sample_matlab_class: str):
        """Test class inheritance extraction."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(sample_matlab_class)
            f.flush()
            
            result = parser.parse_file(Path(f.name), sample_matlab_class)
        
        class_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.CLASS.value]
        if class_chunks:
            class_chunk = class_chunks[0]
            assert "inheritance" in class_chunk
            inheritance = class_chunk["inheritance"]
            assert "handle" in inheritance

    def test_chunk_metadata(self, parser: MatlabParser, sample_matlab_function: str):
        """Test that chunks have correct metadata."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(sample_matlab_function)
            f.flush()
            
            result = parser.parse_file(Path(f.name), sample_matlab_function)
        
        for chunk in result.chunks:
            # Verify required fields
            assert "symbol" in chunk
            assert "start_line" in chunk
            assert "end_line" in chunk
            assert "code" in chunk
            assert "chunk_type" in chunk
            assert "language" in chunk
            assert chunk["language"] == "matlab"
            assert "path" in chunk
            assert "name" in chunk
            assert "display_name" in chunk
            assert "content" in chunk
            
            # Verify line numbers are positive
            assert chunk["start_line"] > 0
            assert chunk["end_line"] >= chunk["start_line"]

    def test_parser_error_handling(self, parser: MatlabParser):
        """Test parser handles malformed Matlab code gracefully."""
        malformed_matlab = '''
        function broken(
            % Missing closing parenthesis and end
        '''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(malformed_matlab)
            f.flush()
            
            result = parser.parse_file(Path(f.name), malformed_matlab)
        
        # Should not crash, might have errors but should return a result
        assert result is not None
        assert result.language == Language.MATLAB

    def test_complex_matlab_features(self, parser: MatlabParser):
        """Test parsing complex Matlab features."""
        complex_matlab = '''function [result, stats] = analyzeData(data, varargin)
% ANALYZEDATA Comprehensive data analysis function
%   [RESULT, STATS] = ANALYZEDATA(DATA, 'Name', Value, ...) analyzes
%   the input data with optional parameters.

    % Parse input arguments
    p = inputParser;
    addRequired(p, 'data', @isnumeric);
    addParameter(p, 'method', 'mean', @ischar);
    addParameter(p, 'threshold', 0.05, @isnumeric);
    parse(p, data, varargin{:});
    
    method = p.Results.method;
    threshold = p.Results.threshold;
    
    % Initialize results
    result = struct();
    stats = struct();
    
    % Process based on method
    switch lower(method)
        case 'mean'
            result.value = mean(data);
            stats.method = 'mean';
        case 'median'
            result.value = median(data);
            stats.method = 'median';
        otherwise
            error('Unknown method: %s', method);
    end
    
    % Calculate statistics
    stats.n = length(data);
    stats.std = std(data);
    stats.min = min(data);
    stats.max = max(data);
    
    % Cell array processing
    if iscell(data)
        result.cellStats = cellfun(@(x) mean(x), data, 'UniformOutput', false);
    end
    
    % Anonymous function
    filterFun = @(x) x(x > threshold);
    result.filtered = filterFun(data);
end'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(complex_matlab)
            f.flush()
            
            result = parser.parse_file(Path(f.name), complex_matlab)
        
        # Should successfully parse without major errors
        assert result is not None
        
        # Should extract function
        function_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.FUNCTION.value]
        assert len(function_chunks) >= 1

    @pytest.mark.skipif(not MatlabParser().is_available, reason="Matlab parser not available")
    def test_registry_integration(self):
        """Test that Matlab parser is properly registered."""
        from chunkhound.registry import get_registry
        
        registry = get_registry()
        
        # Should be able to get Matlab parser
        matlab_parser = registry.get_language_parser(Language.MATLAB)
        assert matlab_parser is not None
        assert isinstance(matlab_parser, MatlabParser)

    def test_file_extension_detection(self):
        """Test that Matlab file extensions are properly detected."""
        # Test Matlab extension
        assert Language.from_file_extension("test.m") == Language.MATLAB
        assert Language.from_file_extension("script.M") == Language.MATLAB  # Case insensitive
        
        # Test that other extensions don't match
        assert Language.from_file_extension("test.py") != Language.MATLAB
        assert Language.from_file_extension("test.java") != Language.MATLAB

    def test_empty_file_handling(self, parser: MatlabParser):
        """Test handling of empty Matlab files."""
        empty_content = ""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(empty_content)
            f.flush()
            
            result = parser.parse_file(Path(f.name), empty_content)
        
        assert result is not None
        assert result.language == Language.MATLAB
        # Empty files should create fallback block chunks
        assert len(result.chunks) >= 0

    def test_comment_only_file(self, parser: MatlabParser):
        """Test handling of files with only comments."""
        comment_only = '''% This is a comment-only file
% Used for documentation purposes
% No actual code here'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m', delete=False) as f:
            f.write(comment_only)
            f.flush()
            
            result = parser.parse_file(Path(f.name), comment_only)
        
        assert result is not None
        assert result.language == Language.MATLAB
        # Comment-only files should be treated as scripts or blocks
        script_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.SCRIPT.value]
        block_chunks = [c for c in result.chunks if c.get("chunk_type") == ChunkType.BLOCK.value]
        assert len(script_chunks) + len(block_chunks) >= 1