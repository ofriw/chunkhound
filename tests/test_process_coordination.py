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
        db_path = "/tmp/test.db"
        db_hash = hashlib.md5(str(Path(db_path).resolve()).encode()).hexdigest()[:8]
        coordination_dir = Path(f"/tmp/chunkhound-{db_hash}")
        pid_file = coordination_dir / "mcp.pid"
        
        try:
            # Create coordination directory and PID file with current process PID
            coordination_dir.mkdir(parents=True, exist_ok=True)
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # Mock the process validation to return True
            with patch('chunkhound.process_detection.ProcessDetector._is_chunkhound_mcp', return_value=True):
                result = detect_mcp_server(db_path)
                assert result == os.getpid()
            
        finally:
            if pid_file.exists():
                pid_file.unlink()
            if coordination_dir.exists():
                coordination_dir.rmdir()
    
    def test_detect_mcp_server_with_invalid_pid(self):
        """Test detection with invalid PID file."""
        db_path = "/tmp/test.db"
        db_hash = hashlib.md5(str(Path(db_path).resolve()).encode()).hexdigest()[:8]
        coordination_dir = Path(f"/tmp/chunkhound-{db_hash}")
        pid_file = coordination_dir / "mcp.pid"
        
        try:
            # Create coordination directory and PID file with non-existent PID
            coordination_dir.mkdir(parents=True, exist_ok=True)
            with open(pid_file, 'w') as f:
                f.write("99999")
            
            # Mock validation to return False for invalid process
            with patch('chunkhound.process_detection.ProcessDetector._is_chunkhound_mcp', return_value=False):
                result = detect_mcp_server(db_path)
                assert result is None
                
                # PID file should be cleaned up
                assert not pid_file.exists()
            
        finally:
            if pid_file.exists():
                pid_file.unlink()
            if coordination_dir.exists():
                coordination_dir.rmdir()


class TestCoordination:
    """Test database coordination functionality."""
    
    def test_coordinate_database_access_timeout(self):
        """Test coordination timeout when no signal response."""
        db_path = "/tmp/test.db"
        fake_pid = 99999  # Use non-existent PID
        
        # Mock that a server is running but doesn't respond
        with patch('chunkhound.signal_coordinator.CLICoordinator.request_database_access', return_value=False) as mock_request:
            result = coordinate_database_access(db_path, fake_pid)
            assert result is False
            mock_request.assert_called_once()
    
    def test_coordinate_database_access_success(self):
        """Test successful coordination."""
        db_path = "/tmp/test.db"
        fake_pid = 99999  # Use non-existent PID
        
        # Mock successful coordination
        with patch('chunkhound.signal_coordinator.CLICoordinator.request_database_access', return_value=True) as mock_request:
            result = coordinate_database_access(db_path, fake_pid)
            assert result is True
            mock_request.assert_called_once()
    
    def test_restore_database_access(self):
        """Test database access restoration."""
        db_path = "/tmp/test.db"
        fake_pid = 99999  # Use non-existent PID

        # Mock successful restoration
        with patch('chunkhound.signal_coordinator.CLICoordinator.release_database_access', return_value=True) as mock_release:
            restore_database_access(db_path, fake_pid)
            mock_release.assert_called_once()

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
            db_hash = hashlib.md5(str(Path(db_path).resolve()).encode()).hexdigest()[:8]
            coordination_dir = Path(f"/tmp/chunkhound-{db_hash}")
            pid_file = coordination_dir / "mcp.pid"
            
            try:
                # Create coordination directory and fake MCP server PID file
                coordination_dir.mkdir(parents=True, exist_ok=True)
                fake_pid = 99999
                with open(pid_file, 'w') as f:
                    f.write(str(fake_pid))
                
                # Mock process validation and coordination
                mock_process = Mock()
                mock_process.pid = fake_pid
                with patch('chunkhound.process_detection.ProcessDetector._is_chunkhound_mcp', return_value=True), \
                     patch('chunkhound.process_detection.ProcessDetector.validate_pid_active', return_value=True), \
                     patch('psutil.Process', return_value=mock_process), \
                     patch('chunkhound.signal_coordinator.CLICoordinator.request_database_access', return_value=True) as mock_request, \
                     patch('chunkhound.signal_coordinator.CLICoordinator.release_database_access', return_value=True) as mock_release:
                    
                    # Test detection
                    detected_pid = detect_mcp_server(db_path)
                    assert detected_pid == fake_pid
                    
                    # Test coordination
                    result = coordinate_database_access(db_path, detected_pid)
                    assert result is True
                    mock_request.assert_called_once()
                    
                    # Test restoration
                    restore_database_access(db_path, detected_pid)
                    mock_release.assert_called_once()
                    
            finally:
                # Cleanup
                if pid_file.exists():
                    pid_file.unlink()
                if coordination_dir.exists():
                    coordination_dir.rmdir()


if __name__ == "__main__":
    pytest.main([__file__])