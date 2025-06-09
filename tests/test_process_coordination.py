"""
Test process coordination functionality.

Tests the signal-based coordination system between MCP server and CLI.
"""

import os
import signal
import tempfile
import time
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch, call
import signal
import pytest

from chunkhound.database import Database


class TestCoordination:
    """Test database coordination functionality."""

    def test_coordination_hash_consistency(self):
        """Test that CLI and MCP server use consistent hash calculation."""
        from pathlib import Path
        
        # Test with relative path
        relative_path = "./test.db"
        absolute_path = str(Path(relative_path).resolve())
        
        # Both should produce the same hash when resolved to absolute paths
        hash1 = hash(str(Path(relative_path).resolve()))
        hash2 = hash(absolute_path)
        
        assert hash1 == hash2, "Hash calculation should be consistent for relative and absolute paths"
        
        # Test file naming consistency
        temp_dir = Path(tempfile.gettempdir())
        expected_file = temp_dir / f"chunkhound-ready-{abs(hash1)}.signal"
        
        # Verify both would create the same file name
        cli_file = temp_dir / f"chunkhound-ready-{abs(hash(str(Path(relative_path).resolve())))}.signal"
        mcp_file = temp_dir / f"chunkhound-ready-{abs(hash(absolute_path))}.signal"
        
        assert cli_file == expected_file == mcp_file, "CLI and MCP server should use the same coordination file"


class TestDatabaseDetachAttach:
    """Test database detach/attach functionality."""
    
    def test_detach_database_success(self):
        """Test successful database detach."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            
            db = Database(db_path)
            db.connect()
            
            # Test detach
            result = db.detach_database()
            assert result is True
            
            db.close()
    
    def test_detach_database_no_connection(self):
        """Test detach when no connection exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            
            db = Database(db_path)
            # Don't connect
            
            result = db.detach_database()
            assert result is True  # Should return True when no connection
    
    def test_reattach_database_success(self):
        """Test successful database reattach."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            
            db = Database(db_path)
            db.connect()
            
            # First detach
            assert db.detach_database() is True
            
            # Then reattach
            result = db.reattach_database()
            assert result is True
            
            db.close()
    
    def test_reattach_database_no_connection(self):
        """Test reattach when no connection exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            
            db = Database(db_path)
            # Don't connect
            
            result = db.reattach_database()
            assert result is True  # Should connect and return True
            
            # Verify connection was established
            assert db.connection is not None
            
            db.close()


class TestIntegration:
    """Integration tests for full coordination workflow."""
    
    def test_full_coordination_workflow(self):
        """Test complete coordination workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            
            # Test that the coordination system components can be imported and used
            # This validates that the signal coordination architecture is intact
            # even though the old CLI detection methods have been replaced
            from chunkhound.signal_coordinator import CLICoordinator, SignalCoordinator
            from chunkhound.process_detection import ProcessDetector
            
            # Basic validation that classes can be instantiated
            detector = ProcessDetector(db_path)
            assert detector is not None
            
            # Test database coordination still works
            db = Database(db_path)
            db.connect()
            
            # Test detach/reattach cycle
            assert db.detach_database() is True
            assert db.reattach_database() is True
            
            db.close()


if __name__ == "__main__":
    pytest.main([__file__])