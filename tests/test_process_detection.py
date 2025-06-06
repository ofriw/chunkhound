"""Tests for process detection functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import psutil

from chunkhound.process_detection import ProcessDetector, ProcessInfo


class TestProcessInfo:
    """Test ProcessInfo class."""
    
    def test_process_info_creation(self):
        """Test ProcessInfo object creation."""
        mock_process = Mock(spec=psutil.Process)
        mock_process.pid = 12345
        pid_file = Path("/tmp/test.pid")
        
        info = ProcessInfo(pid=12345, process=mock_process, pid_file=pid_file)
        
        assert info.pid == 12345
        assert info.process == mock_process
        assert info.pid_file == pid_file
    
    def test_process_info_repr(self):
        """Test ProcessInfo string representation."""
        mock_process = Mock(spec=psutil.Process)
        pid_file = Path("/tmp/test.pid")
        
        info = ProcessInfo(pid=12345, process=mock_process, pid_file=pid_file)
        
        assert "ProcessInfo(pid=12345" in repr(info)
        assert "test.pid" in repr(info)


class TestProcessDetector:
    """Test ProcessDetector class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_db = self.temp_dir / "test.db"
        self.detector = ProcessDetector(self.test_db)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Clean up coordination files
        try:
            self.detector.cleanup_coordination_files()
        except Exception:
            pass
    
    def test_init_creates_coordination_dir(self):
        """Test that initialization creates coordination directory."""
        assert self.detector.coordination_dir.exists()
        assert self.detector.coordination_dir.is_dir()
    
    def test_coordination_dir_hash_consistency(self):
        """Test that coordination directory hash is consistent."""
        # Create another detector with same DB path
        detector2 = ProcessDetector(self.test_db)
        
        assert self.detector.coordination_dir == detector2.coordination_dir
    
    def test_absolute_path_resolution(self):
        """Test that relative paths are resolved to absolute."""
        relative_path = Path("./test.db")
        detector = ProcessDetector(relative_path)
        
        assert detector.db_path.is_absolute()
    
    def test_no_mcp_server_running(self):
        """Test detection when no MCP server is running."""
        assert not self.detector.is_mcp_server_running()
        assert self.detector.get_server_pid() is None
        assert self.detector.find_mcp_server() is None
        assert len(self.detector.detect_mcp_server_instances()) == 0
    
    def test_register_mcp_server(self):
        """Test MCP server registration."""
        test_pid = 12345
        
        self.detector.register_mcp_server(test_pid)
        
        pid_file = self.detector.coordination_dir / "mcp.pid"
        assert pid_file.exists()
        assert pid_file.read_text().strip() == str(test_pid)
    
    def test_create_and_remove_pid_file(self):
        """Test PID file creation and removal."""
        test_pid = 12345
        
        # Create PID file
        self.detector.create_pid_file(test_pid)
        pid_file = self.detector.coordination_dir / "mcp.pid"
        assert pid_file.exists()
        
        # Remove PID file
        self.detector.remove_pid_file()
        assert not pid_file.exists()
    
    @patch('psutil.Process')
    def test_validate_pid_active_running_process(self, mock_process_class):
        """Test PID validation for running process."""
        mock_process = Mock()
        mock_process.is_running.return_value = True
        mock_process_class.return_value = mock_process
        
        assert self.detector.validate_pid_active(12345)
        mock_process_class.assert_called_once_with(12345)
        mock_process.is_running.assert_called_once()
    
    @patch('psutil.Process')
    def test_validate_pid_active_no_such_process(self, mock_process_class):
        """Test PID validation for non-existent process."""
        mock_process_class.side_effect = psutil.NoSuchProcess(12345)
        
        assert not self.detector.validate_pid_active(12345)
    
    @patch('psutil.Process')
    def test_validate_pid_active_access_denied(self, mock_process_class):
        """Test PID validation with access denied."""
        mock_process_class.side_effect = psutil.AccessDenied(12345)
        
        assert not self.detector.validate_pid_active(12345)
    
    def test_find_mcp_server_no_pid_file(self):
        """Test finding MCP server when no PID file exists."""
        result = self.detector.find_mcp_server()
        assert result is None
    
    def test_find_mcp_server_empty_pid_file(self):
        """Test finding MCP server with empty PID file."""
        pid_file = self.detector.coordination_dir / "mcp.pid"
        pid_file.write_text("")
        
        result = self.detector.find_mcp_server()
        assert result is None
        assert not pid_file.exists()  # Should be cleaned up
    
    def test_find_mcp_server_invalid_pid(self):
        """Test finding MCP server with invalid PID."""
        pid_file = self.detector.coordination_dir / "mcp.pid"
        pid_file.write_text("not_a_number")
        
        result = self.detector.find_mcp_server()
        assert result is None
        assert not pid_file.exists()  # Should be cleaned up
    
    @patch('chunkhound.process_detection.ProcessDetector.validate_pid_active')
    def test_find_mcp_server_inactive_pid(self, mock_validate):
        """Test finding MCP server with inactive PID."""
        mock_validate.return_value = False
        
        pid_file = self.detector.coordination_dir / "mcp.pid"
        pid_file.write_text("12345")
        
        result = self.detector.find_mcp_server()
        assert result is None
        assert not pid_file.exists()  # Should be cleaned up
    
    @patch('chunkhound.process_detection.ProcessDetector._is_chunkhound_mcp')
    @patch('chunkhound.process_detection.ProcessDetector.validate_pid_active')
    @patch('psutil.Process')
    def test_find_mcp_server_not_chunkhound(self, mock_process_class, mock_validate, mock_is_chunkhound):
        """Test finding MCP server that's not ChunkHound."""
        mock_validate.return_value = True
        mock_is_chunkhound.return_value = False
        mock_process = Mock()
        mock_process_class.return_value = mock_process
        
        pid_file = self.detector.coordination_dir / "mcp.pid"
        pid_file.write_text("12345")
        
        result = self.detector.find_mcp_server()
        assert result is None
        assert not pid_file.exists()  # Should be cleaned up
    
    @patch('chunkhound.process_detection.ProcessDetector._is_chunkhound_mcp')
    @patch('chunkhound.process_detection.ProcessDetector.validate_pid_active')
    @patch('psutil.Process')
    def test_find_mcp_server_success(self, mock_process_class, mock_validate, mock_is_chunkhound):
        """Test successful MCP server detection."""
        mock_validate.return_value = True
        mock_is_chunkhound.return_value = True
        mock_process = Mock()
        mock_process_class.return_value = mock_process
        
        test_pid = 12345
        pid_file = self.detector.coordination_dir / "mcp.pid"
        pid_file.write_text(str(test_pid))
        
        result = self.detector.find_mcp_server()
        
        assert result is not None
        assert result["pid"] == test_pid
        assert result["process"] == mock_process
        assert result["pid_file"] == pid_file
    
    def test_is_chunkhound_mcp_valid_process(self):
        """Test ChunkHound MCP process validation."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.cmdline.return_value = [
            "python", "-m", "chunkhound", "mcp", str(self.test_db)
        ]
        
        result = self.detector._is_chunkhound_mcp(mock_process)
        assert result is True
    
    def test_is_chunkhound_mcp_different_command(self):
        """Test process validation with different command."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.cmdline.return_value = [
            "python", "-m", "some_other_app", "server"
        ]
        
        result = self.detector._is_chunkhound_mcp(mock_process)
        assert result is False
    
    def test_is_chunkhound_mcp_access_denied(self):
        """Test process validation with access denied."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.cmdline.side_effect = psutil.AccessDenied(12345)
        
        result = self.detector._is_chunkhound_mcp(mock_process)
        assert result is False
    
    def test_is_chunkhound_mcp_no_such_process(self):
        """Test process validation with no such process."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.cmdline.side_effect = psutil.NoSuchProcess(12345)
        
        result = self.detector._is_chunkhound_mcp(mock_process)
        assert result is False
    
    def test_cleanup_stale_pids_no_file(self):
        """Test stale PID cleanup when no file exists."""
        # Should not raise any exceptions
        self.detector.cleanup_stale_pids()
    
    @patch('chunkhound.process_detection.ProcessDetector.validate_pid_active')
    def test_cleanup_stale_pids_inactive(self, mock_validate):
        """Test cleanup of inactive PID."""
        mock_validate.return_value = False
        
        pid_file = self.detector.coordination_dir / "mcp.pid"
        pid_file.write_text("12345")
        
        self.detector.cleanup_stale_pids()
        
        assert not pid_file.exists()
    
    @patch('chunkhound.process_detection.ProcessDetector.validate_pid_active')
    def test_cleanup_stale_pids_active(self, mock_validate):
        """Test that active PIDs are not cleaned up."""
        mock_validate.return_value = True
        
        pid_file = self.detector.coordination_dir / "mcp.pid"
        pid_file.write_text("12345")
        
        self.detector.cleanup_stale_pids()
        
        assert pid_file.exists()
    
    def test_cleanup_coordination_files(self):
        """Test cleanup of all coordination files."""
        # Create some test files
        test_files = [
            self.detector.coordination_dir / "mcp.pid",
            self.detector.coordination_dir / "ready.flag",
            self.detector.coordination_dir / "done.flag"
        ]
        
        for file_path in test_files:
            file_path.write_text("test")
        
        self.detector.cleanup_coordination_files()
        
        for file_path in test_files:
            assert not file_path.exists()
    
    @patch('chunkhound.process_detection.ProcessDetector.find_mcp_server')
    def test_detect_mcp_server_instances_with_server(self, mock_find):
        """Test detection when server is running."""
        mock_process = Mock()
        mock_pid_file = Path("/tmp/test.pid")
        mock_find.return_value = {
            "pid": 12345,
            "process": mock_process,
            "pid_file": mock_pid_file
        }
        
        instances = self.detector.detect_mcp_server_instances()
        
        assert len(instances) == 1
        assert instances[0].pid == 12345
        assert instances[0].process == mock_process
        assert instances[0].pid_file == mock_pid_file
    
    @patch('chunkhound.process_detection.ProcessDetector.find_mcp_server')
    def test_detect_mcp_server_instances_no_server(self, mock_find):
        """Test detection when no server is running."""
        mock_find.return_value = None
        
        instances = self.detector.detect_mcp_server_instances()
        
        assert len(instances) == 0


class TestProcessDetectorIntegration:
    """Integration tests for ProcessDetector."""
    
    def test_full_lifecycle(self):
        """Test complete lifecycle of process detection."""
        temp_dir = Path(tempfile.mkdtemp())
        test_db = temp_dir / "integration_test.db"
        
        try:
            detector = ProcessDetector(test_db)
            
            # Initially no server
            assert not detector.is_mcp_server_running()
            
            # Register a fake server
            test_pid = os.getpid()  # Use current process PID
            detector.register_mcp_server(test_pid)
            
            # Should find the PID file (but validation will likely fail)
            pid_file = detector.coordination_dir / "mcp.pid"
            assert pid_file.exists()
            assert pid_file.read_text().strip() == str(test_pid)
            
            # Clean up
            detector.cleanup_coordination_files()
            assert not detector.coordination_dir.exists()
            
        finally:
            # Ensure cleanup
            if (temp_dir / "integration_test.db").exists():
                (temp_dir / "integration_test.db").unlink()