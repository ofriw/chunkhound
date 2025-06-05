"""
Test process coordination functionality.

Tests the signal-based coordination system between MCP server and CLI.
"""

import os
import signal
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from chunkhound.database import Database
from chunkhound.cli import detect_mcp_server, coordinate_database_access, restore_database_access


class TestProcessDetection:
    """Test MCP server process detection."""
    
    def test_detect_mcp_server_no_pid_file(self):
        """Test detection when no PID file exists."""
        db_path = "/tmp/test.db"
        result = detect_mcp_server(db_path)
        assert result is None
    
    def test_detect_mcp_server_with_valid_pid(self):
        """Test detection with valid PID file."""
        temp_dir = Path(tempfile.gettempdir())
        db_path = "/tmp/test.db"
        db_hash = hash(str(db_path))
        pid_file = temp_dir / f"chunkhound-mcp-{abs(db_hash)}.pid"
        
        try:
            # Create PID file with current process PID
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
            
            result = detect_mcp_server(db_path)
            assert result == os.getpid()
            
        finally:
            if pid_file.exists():
                pid_file.unlink()
    
    def test_detect_mcp_server_with_invalid_pid(self):
        """Test detection with invalid PID file."""
        temp_dir = Path(tempfile.gettempdir())
        db_path = "/tmp/test.db"
        db_hash = hash(str(db_path))
        pid_file = temp_dir / f"chunkhound-mcp-{abs(db_hash)}.pid"
        
        try:
            # Create PID file with non-existent PID
            with open(pid_file, 'w') as f:
                f.write("99999")
            
            result = detect_mcp_server(db_path)
            assert result is None
            
            # PID file should be cleaned up
            assert not pid_file.exists()
            
        finally:
            if pid_file.exists():
                pid_file.unlink()


class TestCoordination:
    """Test database coordination functionality."""
    
    def test_coordinate_database_access_timeout(self):
        """Test coordination timeout when no signal response."""
        db_path = "/tmp/test.db"
        fake_pid = 99999  # Use non-existent PID
        
        with patch('os.kill') as mock_kill, \
             patch('time.sleep') as mock_sleep:
            # Mock kill to avoid sending real signals
            mock_kill.return_value = None
            mock_sleep.return_value = None
            
            result = coordinate_database_access(db_path, fake_pid)
            assert result is False
            
            # Should have called sleep 100 times (timeout logic)
            assert mock_sleep.call_count == 100
            
            # Should have tried to send signal
            mock_kill.assert_called_once_with(fake_pid, signal.SIGUSR1)
    
    def test_coordinate_database_access_success(self):
        """Test successful coordination."""
        temp_dir = Path(tempfile.gettempdir())
        db_path = "/tmp/test.db"
        db_hash = hash(str(db_path))
        ready_file = temp_dir / f"chunkhound-ready-{abs(db_hash)}.signal"
        fake_pid = 99999  # Use non-existent PID
        
        try:
            # Mock successful coordination by creating ready file immediately
            with patch('os.kill') as mock_kill:
                
                def create_ready_file(*args):
                    ready_file.touch()
                
                mock_kill.side_effect = create_ready_file
                
                result = coordinate_database_access(db_path, fake_pid)
                assert result is True
                
                # Should have sent SIGUSR1 signal
                mock_kill.assert_called_once_with(fake_pid, signal.SIGUSR1)
                
        finally:
            if ready_file.exists():
                ready_file.unlink()
    
    def test_restore_database_access(self):
        """Test database access restoration."""
        temp_dir = Path(tempfile.gettempdir())
        db_path = "/tmp/test.db"
        db_hash = hash(str(db_path))
        ready_file = temp_dir / f"chunkhound-ready-{abs(db_hash)}.signal"
        fake_pid = 99999  # Use non-existent PID

        try:
            # Create ready file to test cleanup
            ready_file.touch()

            with patch('os.kill') as mock_kill:
                restore_database_access(db_path, fake_pid)

                # Should have sent SIGUSR2 signal
                mock_kill.assert_called_once_with(fake_pid, signal.SIGUSR2)

                # Ready file should be cleaned up
                assert not ready_file.exists()

        finally:
            if ready_file.exists():
                ready_file.unlink()

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
        """Test the full coordination workflow."""
        temp_dir = Path(tempfile.gettempdir())
        
        with tempfile.TemporaryDirectory() as test_dir:
            db_path = str(Path(test_dir) / "test.db")
            
            # Simulate MCP server setup
            db_hash = hash(str(db_path))
            pid_file = temp_dir / f"chunkhound-mcp-{abs(db_hash)}.pid"
            ready_file = temp_dir / f"chunkhound-ready-{abs(db_hash)}.signal"
            
            try:
                # Create PID file with fake PID
                fake_pid = 99999
                with open(pid_file, 'w') as f:
                    f.write(str(fake_pid))
                
                # Mock os.kill to avoid process checks
                with patch('os.kill') as mock_kill:
                    mock_kill.return_value = None  # Simulate process exists
                    
                    # Test detection
                    detected_pid = detect_mcp_server(db_path)
                    assert detected_pid == fake_pid
                    
                    # Reset mock for coordination test
                    mock_kill.reset_mock()
                    
                    def create_ready_file(*args):
                        ready_file.touch()
                    
                    mock_kill.side_effect = create_ready_file
                    
                    # Test coordination
                    result = coordinate_database_access(db_path, detected_pid)
                    assert result is True
                    
                    # Reset side effect for restoration test
                    mock_kill.side_effect = None
                    
                    # Test restoration
                    restore_database_access(db_path, detected_pid)
                    
                    # Verify signals were sent
                    assert mock_kill.call_count == 2
                    mock_kill.assert_any_call(detected_pid, signal.SIGUSR1)
                    mock_kill.assert_any_call(detected_pid, signal.SIGUSR2)
                    
            finally:
                # Cleanup
                for file_path in [pid_file, ready_file]:
                    if file_path.exists():
                        file_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__])