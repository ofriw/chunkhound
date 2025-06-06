"""Tests for IncrementalChunker differential chunk update functionality."""

import pytest
from pathlib import Path
from typing import List, Dict, Any

from chunkhound.chunker import IncrementalChunker, ChunkDiff, Chunker


class TestIncrementalChunker:
    """Test cases for IncrementalChunker class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = IncrementalChunker()
        self.test_file_path = Path("test_file.py")
    
    def test_initialization(self):
        """Test IncrementalChunker initialization."""
        assert self.chunker is not None
        assert isinstance(self.chunker.base_chunker, Chunker)
    
    def test_no_changes_preserves_all_chunks(self):
        """Test that no changed ranges results in no modifications."""
        old_chunks = [
            {"id": 1, "symbol": "func1", "start_line": 1, "end_line": 5, "code": "def func1(): pass"},
            {"id": 2, "symbol": "func2", "start_line": 7, "end_line": 10, "code": "def func2(): pass"},
        ]
        changed_ranges = []  # No changes
        new_parsed_data = []
        
        diff = self.chunker.chunk_file_differential(
            self.test_file_path, old_chunks, changed_ranges, new_parsed_data
        )
        
        assert diff.chunks_to_delete == []
        assert diff.chunks_to_insert == []
        assert diff.chunks_to_update == []
        assert diff.unchanged_count == 2
    
    def test_structural_change_replaces_all_chunks(self):
        """Test that structural changes trigger complete replacement."""
        old_chunks = [
            {"id": 1, "symbol": "func1", "start_line": 1, "end_line": 5, "code": "def func1(): pass"},
            {"id": 2, "symbol": "func2", "start_line": 7, "end_line": 10, "code": "def func2(): pass"},
        ]
        changed_ranges = [{"type": "structural_change", "start_byte": 0, "end_byte": 1000}]
        new_parsed_data = [
            {"name": "new_func", "start_line": 1, "end_line": 8, "content": "def new_func(): return 42", "type": "function"}
        ]
        
        diff = self.chunker.chunk_file_differential(
            self.test_file_path, old_chunks, changed_ranges, new_parsed_data
        )
        
        assert diff.chunks_to_delete == [1, 2]
        assert len(diff.chunks_to_insert) == 1
        assert diff.chunks_to_insert[0]["symbol"] == "new_func"
        assert diff.chunks_to_update == []
        assert diff.unchanged_count == 0
    
    def test_full_change_replaces_all_chunks(self):
        """Test that full file changes trigger complete replacement."""
        old_chunks = [
            {"id": 1, "symbol": "func1", "start_line": 1, "end_line": 5, "code": "def func1(): pass"},
        ]
        changed_ranges = [{"type": "full_change", "start_byte": 0, "end_byte": float('inf')}]
        new_parsed_data = [
            {"name": "replacement_func", "start_line": 1, "end_line": 3, "content": "def replacement_func(): return True", "type": "function"}
        ]
        
        diff = self.chunker.chunk_file_differential(
            self.test_file_path, old_chunks, changed_ranges, new_parsed_data
        )
        
        assert diff.chunks_to_delete == [1]
        assert len(diff.chunks_to_insert) == 1
        assert diff.chunks_to_insert[0]["symbol"] == "replacement_func"
        assert diff.unchanged_count == 0
    
    def test_identify_affected_chunks_line_overlap(self):
        """Test identification of chunks affected by line-based changes."""
        old_chunks = [
            {"id": 1, "symbol": "func1", "start_line": 1, "end_line": 5, "code": "def func1(): pass"},
            {"id": 2, "symbol": "func2", "start_line": 10, "end_line": 15, "code": "def func2(): pass"},
            {"id": 3, "symbol": "func3", "start_line": 20, "end_line": 25, "code": "def func3(): pass"},
        ]
        # Change affects lines around 12-13 (approximately bytes 600-650)
        changed_ranges = [{"start_byte": 600, "end_byte": 650, "type": "node_change"}]
        
        affected_ids = self.chunker.identify_affected_chunks(old_chunks, changed_ranges)
        
        # func2 (lines 10-15) should be affected, others should not
        assert 2 in affected_ids
        assert 1 not in affected_ids
        assert 3 not in affected_ids
    
    def test_identify_affected_chunks_multiple_ranges(self):
        """Test identification with multiple changed ranges."""
        old_chunks = [
            {"id": 1, "symbol": "func1", "start_line": 1, "end_line": 5, "code": "def func1(): pass"},
            {"id": 2, "symbol": "func2", "start_line": 10, "end_line": 15, "code": "def func2(): pass"},
            {"id": 3, "symbol": "func3", "start_line": 20, "end_line": 25, "code": "def func3(): pass"},
        ]
        # Changes affect both func1 and func3 regions
        changed_ranges = [
            {"start_byte": 50, "end_byte": 100, "type": "node_change"},   # ~lines 1-2
            {"start_byte": 1000, "end_byte": 1100, "type": "node_change"} # ~lines 20-22
        ]
        
        affected_ids = self.chunker.identify_affected_chunks(old_chunks, changed_ranges)
        
        assert 1 in affected_ids  # func1 affected by first range
        assert 2 not in affected_ids  # func2 not affected
        assert 3 in affected_ids  # func3 affected by second range
    
    def test_identify_new_chunks_in_ranges(self):
        """Test identification of new chunks within changed ranges."""
        new_chunks = [
            {"symbol": "func1", "start_line": 1, "end_line": 5, "code": "def func1(): pass"},
            {"symbol": "func2", "start_line": 10, "end_line": 15, "code": "def func2(): pass"},
            {"symbol": "func3", "start_line": 20, "end_line": 25, "code": "def func3(): pass"},
        ]
        # Change range covers func2 area
        changed_ranges = [{"start_byte": 500, "end_byte": 750, "type": "node_change"}]  # ~lines 10-15
        
        chunks_in_ranges = self.chunker.identify_new_chunks_in_ranges(new_chunks, changed_ranges)
        
        assert len(chunks_in_ranges) == 1
        assert chunks_in_ranges[0]["symbol"] == "func2"
    
    def test_partial_file_change_differential_update(self):
        """Test differential update with partial file changes."""
        old_chunks = [
            {"id": 1, "symbol": "func1", "start_line": 1, "end_line": 5, "code": "def func1(): pass"},
            {"id": 2, "symbol": "func2", "start_line": 10, "end_line": 15, "code": "def func2(): pass"},
            {"id": 3, "symbol": "func3", "start_line": 20, "end_line": 25, "code": "def func3(): pass"},
        ]
        # Change affects only the middle function
        changed_ranges = [{"start_byte": 500, "end_byte": 750, "type": "node_change"}]  # ~lines 10-15
        new_parsed_data = [
            {"name": "func1", "start_line": 1, "end_line": 5, "content": "def func1(): pass", "type": "function"},
            {"name": "func2_modified", "start_line": 10, "end_line": 16, "content": "def func2_modified(): return 42", "type": "function"},
            {"name": "func3", "start_line": 20, "end_line": 25, "content": "def func3(): pass", "type": "function"},
        ]
        
        diff = self.chunker.chunk_file_differential(
            self.test_file_path, old_chunks, changed_ranges, new_parsed_data
        )
        
        # Should delete func2 and insert modified version
        assert 2 in diff.chunks_to_delete
        assert 1 not in diff.chunks_to_delete
        assert 3 not in diff.chunks_to_delete
        
        assert len(diff.chunks_to_insert) == 1
        assert diff.chunks_to_insert[0]["symbol"] == "func2_modified"
        
        # Two chunks (func1 and func3) should remain unchanged
        assert diff.unchanged_count == 2
    
    def test_empty_old_chunks_new_file(self):
        """Test processing a completely new file with no existing chunks."""
        old_chunks = []
        changed_ranges = [{"type": "full_change", "start_byte": 0, "end_byte": float('inf')}]
        new_parsed_data = [
            {"name": "new_func", "start_line": 1, "end_line": 3, "content": "def new_func(): pass", "type": "function"}
        ]
        
        diff = self.chunker.chunk_file_differential(
            self.test_file_path, old_chunks, changed_ranges, new_parsed_data
        )
        
        assert diff.chunks_to_delete == []
        assert len(diff.chunks_to_insert) == 1
        assert diff.chunks_to_insert[0]["symbol"] == "new_func"
        assert diff.unchanged_count == 0
    
    def test_empty_new_parsed_data(self):
        """Test handling when new parsed data is empty."""
        old_chunks = [
            {"id": 1, "symbol": "func1", "start_line": 1, "end_line": 5, "code": "def func1(): pass"},
        ]
        changed_ranges = [{"type": "full_change", "start_byte": 0, "end_byte": float('inf')}]
        new_parsed_data = []  # File became empty or unparseable
        
        diff = self.chunker.chunk_file_differential(
            self.test_file_path, old_chunks, changed_ranges, new_parsed_data
        )
        
        # Should delete all old chunks and insert nothing
        assert diff.chunks_to_delete == [1]
        assert diff.chunks_to_insert == []
        assert diff.unchanged_count == 0
    
    def test_chunk_diff_dataclass(self):
        """Test ChunkDiff dataclass functionality."""
        diff = ChunkDiff(
            chunks_to_delete=[1, 2],
            chunks_to_insert=[{"symbol": "new_func", "code": "def new_func(): pass"}],
            chunks_to_update=[],
            unchanged_count=5
        )
        
        assert diff.chunks_to_delete == [1, 2]
        assert len(diff.chunks_to_insert) == 1
        assert diff.chunks_to_insert[0]["symbol"] == "new_func"
        assert diff.chunks_to_update == []
        assert diff.unchanged_count == 5
    
    def test_overlapping_changes_merge_correctly(self):
        """Test that overlapping changes are handled correctly."""
        old_chunks = [
            {"id": 1, "symbol": "func1", "start_line": 1, "end_line": 10, "code": "def func1(): pass"},
            {"id": 2, "symbol": "func2", "start_line": 15, "end_line": 25, "code": "def func2(): pass"},
        ]
        # Overlapping changes that affect both functions
        changed_ranges = [
            {"start_byte": 200, "end_byte": 600, "type": "node_change"},  # affects func1
            {"start_byte": 500, "end_byte": 900, "type": "node_change"},  # overlaps and affects func2
        ]
        new_parsed_data = [
            {"name": "func1_new", "start_line": 1, "end_line": 8, "content": "def func1_new(): return 1", "type": "function"},
            {"name": "func2_new", "start_line": 15, "end_line": 20, "content": "def func2_new(): return 2", "type": "function"},
        ]
        
        diff = self.chunker.chunk_file_differential(
            self.test_file_path, old_chunks, changed_ranges, new_parsed_data
        )
        
        # Both functions should be affected
        assert set(diff.chunks_to_delete) == {1, 2}
        assert len(diff.chunks_to_insert) == 2
        assert {chunk["symbol"] for chunk in diff.chunks_to_insert} == {"func1_new", "func2_new"}
        assert diff.unchanged_count == 0


class TestChunkDiff:
    """Test cases for ChunkDiff dataclass."""
    
    def test_chunk_diff_creation(self):
        """Test basic ChunkDiff creation and access."""
        diff = ChunkDiff(
            chunks_to_delete=[1, 2, 3],
            chunks_to_insert=[
                {"symbol": "new_func1", "code": "def new_func1(): pass"},
                {"symbol": "new_func2", "code": "def new_func2(): pass"},
            ],
            chunks_to_update=[
                {"id": 4, "symbol": "updated_func", "code": "def updated_func(): return 42"},
            ],
            unchanged_count=10
        )
        
        assert diff.chunks_to_delete == [1, 2, 3]
        assert len(diff.chunks_to_insert) == 2
        assert len(diff.chunks_to_update) == 1
        assert diff.unchanged_count == 10
    
    def test_chunk_diff_empty(self):
        """Test ChunkDiff with empty collections."""
        diff = ChunkDiff(
            chunks_to_delete=[],
            chunks_to_insert=[],
            chunks_to_update=[],
            unchanged_count=0
        )
        
        assert diff.chunks_to_delete == []
        assert diff.chunks_to_insert == []
        assert diff.chunks_to_update == []
        assert diff.unchanged_count == 0
    
    def test_chunk_diff_statistics(self):
        """Test calculating statistics from ChunkDiff."""
        diff = ChunkDiff(
            chunks_to_delete=[1, 2],
            chunks_to_insert=[{"symbol": "func1"}, {"symbol": "func2"}, {"symbol": "func3"}],
            chunks_to_update=[{"symbol": "func4"}],
            unchanged_count=5
        )
        
        # Calculate total operations
        total_deletions = len(diff.chunks_to_delete)
        total_insertions = len(diff.chunks_to_insert)
        total_updates = len(diff.chunks_to_update)
        total_unchanged = diff.unchanged_count
        
        assert total_deletions == 2
        assert total_insertions == 3
        assert total_updates == 1
        assert total_unchanged == 5
        
        # Calculate efficiency (percentage of chunks preserved)
        total_chunks = total_unchanged + total_deletions
        efficiency = total_unchanged / total_chunks if total_chunks > 0 else 0
        assert efficiency == 5/7  # 5 unchanged out of 7 original chunks


if __name__ == "__main__":
    pytest.main([__file__])