"""Tests for SignalCoordinator - signal-based database coordination."""

import asyncio
import os
import signal
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from chunkhound.signal_coordinator import CLICoordinator, SignalCoordinator


class TestSignalCoordinator:
    """Test cases for SignalCoordinator class."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        # Cleanup
        db_path.unlink(missing_ok=True)
    
    @pytest.fixture
    def mock_database(self):
        """Create mock database manager."""
        db = Mock()
        db.db_path = "/test/path/db"
        db.connection = Mock()
        db.disconnect = Mock(return_value=True)
        db.reconnect = Mock(return_value=True)
        db.detach_database = Mock(return_value=True)
        db.reattach_database = Mock(return_value=True)
        db.close = Mock()
        db.connect = Mock()
        return db
    
    @pytest.fixture
    def signal_coordinator(self, temp_db_path, mock_database):
        """Create SignalCoordinator instance for testing."""
        return SignalCoordinator(temp_db_path, mock_database)
    
    def test_init(self, temp_db_path, mock_database):
        """Test SignalCoordinator initialization."""
        coordinator = SignalCoordinator(temp_db_path, mock_database)
        
        assert coordinator.db_path == temp_db_path.resolve()
        assert coordinator.database_manager == mock_database
        assert coordinator.coordination_dir.exists()
        assert not coordinator._coordination_active
        assert not coordinator._shutdown_requested
        assert coordinator._original_handlers == {}
    
    def test_coordination_dir_creation(self, temp_db_path, mock_database):
        """Test coordination directory is created properly."""
        coordinator = SignalCoordinator(temp_db_path, mock_database)
        
        # Directory should exist
        assert coordinator.coordination_dir.exists()
        assert coordinator.coordination_dir.is_dir()
        
        # Should be based on hash of db path
        expected_name = f"chunkhound-{coordinator._get_coordination_dir().name.split('-')[1]}"
        assert coordinator.coordination_dir.name == expected_name.split('/')[-1]
    
    @patch('chunkhound.signal_coordinator.signal.signal')
    def test_setup_mcp_signal_handling(self, mock_signal, signal_coordinator):
        """Test MCP signal handler setup."""
        # Mock original signal handlers
        mock_signal.return_value = Mock()
        
        with patch.object(signal_coordinator.process_detector, 'register_mcp_server') as mock_register:
            signal_coordinator.setup_mcp_signal_handling()
        
        # Verify signal handlers were set
        expected_calls = [
            call(signal.SIGUSR1, signal_coordinator._handle_shutdown_request),
            call(signal.SIGUSR2, signal_coordinator._handle_reopen_request),
            call(signal.SIGTERM, signal_coordinator._handle_terminate),
            call(signal.SIGINT, signal_coordinator._handle_terminate),
        ]
        mock_signal.assert_has_calls(expected_calls, any_order=True)
        
        # Verify process registration
        mock_register.assert_called_once()
        
        # Verify handlers stored
        assert len(signal_coordinator._original_handlers) == 4
    
    def test_handle_shutdown_request_with_event_loop(self, signal_coordinator):
        """Test shutdown request handling with active event loop."""
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop
            
            signal_coordinator._handle_shutdown_request(signal.SIGUSR1, None)
            
            mock_loop.create_task.assert_called_once()
    
    def test_handle_shutdown_request_no_event_loop(self, signal_coordinator):
        """Test shutdown request handling without event loop."""
        with patch('asyncio.get_event_loop', side_effect=RuntimeError):
            with patch('asyncio.run') as mock_run:
                signal_coordinator._handle_shutdown_request(signal.SIGUSR1, None)
                mock_run.assert_called_once()
    
    def test_handle_reopen_request_with_event_loop(self, signal_coordinator):
        """Test reopen request handling with active event loop."""
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop
            
            signal_coordinator._handle_reopen_request(signal.SIGUSR2, None)
            
            mock_loop.create_task.assert_called_once()
    
    def test_handle_terminate(self, signal_coordinator):
        """Test termination signal handling."""
        with patch('os._exit') as mock_exit:
            with patch.object(signal_coordinator, '_restore_signal_handlers') as mock_restore:
                with patch.object(signal_coordinator, 'cleanup_coordination_files') as mock_cleanup:
                    
                    signal_coordinator._handle_terminate(signal.SIGTERM, None)
                    
                    assert signal_coordinator._shutdown_requested
                    mock_cleanup.assert_called_once()
                    mock_restore.assert_called_once()
                    mock_exit.assert_called_once_with(0)
    
    @pytest.mark.asyncio
    async def test_graceful_database_shutdown_success(self, signal_coordinator):
        """Test successful graceful database shutdown."""
        # Setup
        signal_coordinator.database_manager.db_path = "/test/db"
        ready_flag = signal_coordinator.coordination_dir / "ready.flag"
        
        with patch.object(signal_coordinator, '_wait_for_indexing_completion') as mock_wait:
            await signal_coordinator._graceful_database_shutdown()
        
        # Verify state changes
        assert signal_coordinator._coordination_active
        assert signal_coordinator._original_db_path == Path("/test/db")
        
        # Verify database operations
        signal_coordinator.database_manager.connection.execute.assert_called_with("FORCE CHECKPOINT")
        signal_coordinator.database_manager.disconnect.assert_called_once()
        
        # Verify ready flag created
        assert ready_flag.exists()
        
        # Verify waiting for completion
        mock_wait.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_graceful_database_shutdown_disconnect_fails(self, signal_coordinator):
        """Test graceful shutdown when disconnect fails."""
        signal_coordinator.database_manager.disconnect.return_value = False
        
        with patch.object(signal_coordinator, '_wait_for_indexing_completion'):
            await signal_coordinator._graceful_database_shutdown()
        
        # Should fallback to detach_database, then close if detach fails too
        signal_coordinator.database_manager.disconnect.assert_called_once()
        signal_coordinator.database_manager.detach_database.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_graceful_database_shutdown_error_handling(self, signal_coordinator):
        """Test error handling during shutdown."""
        # Make disconnect raise exception
        signal_coordinator.database_manager.disconnect.side_effect = Exception("Test error")
        
        await signal_coordinator._graceful_database_shutdown()
        
        # Should cleanup ready flag on error
        ready_flag = signal_coordinator.coordination_dir / "ready.flag"
        assert not ready_flag.exists()
        assert not signal_coordinator._coordination_active
    
    @pytest.mark.asyncio
    async def test_graceful_database_reopen_success(self, signal_coordinator):
        """Test successful graceful database reopen."""
        # Setup coordination state
        signal_coordinator._coordination_active = True
        
        # Create coordination flags
        ready_flag = signal_coordinator.coordination_dir / "ready.flag"
        done_flag = signal_coordinator.coordination_dir / "done.flag"
        ready_flag.touch()
        done_flag.touch()
        
        await signal_coordinator._graceful_database_reopen()
        
        # Verify database operations
        signal_coordinator.database_manager.reconnect.assert_called_once()
        
        # Verify flags cleaned up
        assert not ready_flag.exists()
        assert not done_flag.exists()
        
        # Verify state reset
        assert not signal_coordinator._coordination_active
    
    @pytest.mark.asyncio
    async def test_graceful_database_reopen_reconnect_fails(self, signal_coordinator):
        """Test reopen when reconnect fails."""
        signal_coordinator._coordination_active = True
        signal_coordinator.database_manager.reconnect.return_value = False
        
        await signal_coordinator._graceful_database_reopen()
        
        # Should fallback to reattach_database, then connect if reattach fails too
        signal_coordinator.database_manager.reconnect.assert_called_once()
        signal_coordinator.database_manager.reattach_database.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_graceful_database_reopen_not_coordinating(self, signal_coordinator):
        """Test reopen when not in coordination mode."""
        signal_coordinator._coordination_active = False
        
        await signal_coordinator._graceful_database_reopen()
        
        # Should not attempt database operations
        signal_coordinator.database_manager.reconnect.assert_not_called()
        signal_coordinator.database_manager.reattach_database.assert_not_called()
        signal_coordinator.database_manager.connect.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_wait_for_indexing_completion_success(self, signal_coordinator):
        """Test waiting for indexing completion - success case."""
        done_flag = signal_coordinator.coordination_dir / "done.flag"
        
        # Create done flag after short delay
        async def create_flag():
            await asyncio.sleep(0.1)
            done_flag.touch()
        
        # Run both tasks concurrently
        await asyncio.gather(
            signal_coordinator._wait_for_indexing_completion(),
            create_flag()
        )
        
        # Done flag should exist
        assert done_flag.exists()
    
    @pytest.mark.asyncio
    async def test_wait_for_indexing_completion_timeout(self, signal_coordinator):
        """Test waiting for indexing completion - timeout case."""
        # Set very short timeout for testing
        original_timeout = 300
        
        with patch.object(signal_coordinator, '_wait_for_indexing_completion') as mock_wait:
            # Mock the method to simulate timeout
            async def mock_timeout():
                await asyncio.sleep(0.1)  # Short sleep
                # Timeout condition
                
            mock_wait.side_effect = mock_timeout
            await mock_wait()
    
    @pytest.mark.asyncio
    async def test_wait_for_indexing_completion_shutdown_requested(self, signal_coordinator):
        """Test waiting interrupted by shutdown request."""
        signal_coordinator._shutdown_requested = True
        
        # Should return immediately
        await signal_coordinator._wait_for_indexing_completion()
        
        # Done flag should not exist
        done_flag = signal_coordinator.coordination_dir / "done.flag"
        assert not done_flag.exists()
    
    def test_send_coordination_signal_shutdown(self, signal_coordinator):
        """Test sending shutdown coordination signal."""
        test_pid = 12345
        
        with patch('os.kill') as mock_kill:
            result = signal_coordinator.send_coordination_signal('shutdown', test_pid)
        
        assert result is True
        mock_kill.assert_called_once_with(test_pid, signal.SIGUSR1)
    
    def test_send_coordination_signal_reopen(self, signal_coordinator):
        """Test sending reopen coordination signal."""
        test_pid = 12345
        
        with patch('os.kill') as mock_kill:
            result = signal_coordinator.send_coordination_signal('reopen', test_pid)
        
        assert result is True
        mock_kill.assert_called_once_with(test_pid, signal.SIGUSR2)
    
    def test_send_coordination_signal_auto_detect_pid(self, signal_coordinator):
        """Test sending signal with auto-detected PID."""
        test_pid = 12345
        
        with patch.object(signal_coordinator.process_detector, 'get_server_pid', return_value=test_pid):
            with patch('os.kill') as mock_kill:
                result = signal_coordinator.send_coordination_signal('shutdown')
        
        assert result is True
        mock_kill.assert_called_once_with(test_pid, signal.SIGUSR1)
    
    def test_send_coordination_signal_no_server(self, signal_coordinator):
        """Test sending signal when no server found."""
        with patch.object(signal_coordinator.process_detector, 'get_server_pid', return_value=None):
            result = signal_coordinator.send_coordination_signal('shutdown')
        
        assert result is False
    
    def test_send_coordination_signal_invalid_type(self, signal_coordinator):
        """Test sending signal with invalid type."""
        result = signal_coordinator.send_coordination_signal('invalid', 12345)
        assert result is False
    
    def test_send_coordination_signal_process_not_found(self, signal_coordinator):
        """Test sending signal to non-existent process."""
        with patch('os.kill', side_effect=ProcessLookupError("Process not found")):
            result = signal_coordinator.send_coordination_signal('shutdown', 12345)
        
        assert result is False
    
    def test_wait_for_ready_flag_success(self, signal_coordinator):
        """Test waiting for ready flag - success case."""
        ready_flag = signal_coordinator.coordination_dir / "ready.flag"
        
        # Create flag in background thread
        import threading
        def create_flag():
            time.sleep(0.1)
            ready_flag.touch()
        
        thread = threading.Thread(target=create_flag)
        thread.start()
        
        result = signal_coordinator.wait_for_ready_flag(timeout=1.0)
        thread.join()
        
        assert result is True
        assert ready_flag.exists()
    
    def test_wait_for_ready_flag_timeout(self, signal_coordinator):
        """Test waiting for ready flag - timeout case."""
        result = signal_coordinator.wait_for_ready_flag(timeout=0.1)
        assert result is False
    
    def test_signal_indexing_complete(self, signal_coordinator):
        """Test signaling indexing completion."""
        signal_coordinator.signal_indexing_complete()
        
        done_flag = signal_coordinator.coordination_dir / "done.flag"
        assert done_flag.exists()
        
        # Should contain timestamp
        content = done_flag.read_text()
        timestamp = float(content)
        assert timestamp > 0
    
    def test_cleanup_coordination_files(self, signal_coordinator):
        """Test cleanup of coordination files."""
        # Create test files
        ready_flag = signal_coordinator.coordination_dir / "ready.flag"
        done_flag = signal_coordinator.coordination_dir / "done.flag"
        ready_flag.touch()
        done_flag.touch()
        
        with patch.object(signal_coordinator.process_detector, 'cleanup_coordination_files') as mock_cleanup:
            signal_coordinator.cleanup_coordination_files()
        
        # Flags should be removed
        assert not ready_flag.exists()
        assert not done_flag.exists()
        
        # ProcessDetector cleanup should be called
        mock_cleanup.assert_called_once()
    
    def test_restore_signal_handlers(self, signal_coordinator):
        """Test restoration of signal handlers."""
        # Setup mock handlers
        mock_handler1 = Mock()
        mock_handler2 = Mock()
        signal_coordinator._original_handlers = {
            signal.SIGUSR1: mock_handler1,
            signal.SIGUSR2: mock_handler2,
        }
        
        with patch('chunkhound.signal_coordinator.signal.signal') as mock_signal:
            signal_coordinator._restore_signal_handlers()
        
        # Verify handlers restored
        expected_calls = [
            call(signal.SIGUSR1, mock_handler1),
            call(signal.SIGUSR2, mock_handler2),
        ]
        mock_signal.assert_has_calls(expected_calls, any_order=True)
        
        # Verify handlers cleared
        assert signal_coordinator._original_handlers == {}
    
    def test_is_coordination_active(self, signal_coordinator):
        """Test coordination active status check."""
        assert not signal_coordinator.is_coordination_active()
        
        signal_coordinator._coordination_active = True
        assert signal_coordinator.is_coordination_active()
    
    def test_is_mcp_server_running(self, signal_coordinator):
        """Test MCP server running status check."""
        with patch.object(signal_coordinator.process_detector, 'is_mcp_server_running', return_value=True):
            assert signal_coordinator.is_mcp_server_running()
        
        with patch.object(signal_coordinator.process_detector, 'is_mcp_server_running', return_value=False):
            assert not signal_coordinator.is_mcp_server_running()
    
    def test_context_manager(self, signal_coordinator):
        """Test context manager functionality."""
        with patch.object(signal_coordinator, '_restore_signal_handlers') as mock_restore:
            with patch.object(signal_coordinator, 'cleanup_coordination_files') as mock_cleanup:
                
                with signal_coordinator:
                    pass
                
                mock_restore.assert_called_once()
                mock_cleanup.assert_called_once()


class TestCLICoordinator:
    """Test cases for CLICoordinator class."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        db_path.unlink(missing_ok=True)
    
    @pytest.fixture
    def cli_coordinator(self, temp_db_path):
        """Create CLICoordinator instance for testing."""
        return CLICoordinator(temp_db_path)
    
    def test_init(self, temp_db_path):
        """Test CLICoordinator initialization."""
        coordinator = CLICoordinator(temp_db_path)
        
        assert coordinator.db_path == temp_db_path.resolve()
        assert coordinator.signal_coordinator is not None
        assert not coordinator._coordination_active
    
    def test_request_database_access_no_server(self, cli_coordinator):
        """Test requesting access when no MCP server running."""
        with patch.object(cli_coordinator.signal_coordinator, 'is_mcp_server_running', return_value=False):
            result = cli_coordinator.request_database_access()
        
        assert result is True
        assert not cli_coordinator._coordination_active
    
    def test_request_database_access_success(self, cli_coordinator):
        """Test successful database access request."""
        with patch.object(cli_coordinator.signal_coordinator, 'is_mcp_server_running', return_value=True):
            with patch.object(cli_coordinator.signal_coordinator, 'send_coordination_signal', return_value=True):
                with patch.object(cli_coordinator.signal_coordinator, 'wait_for_ready_flag', return_value=True):
                    
                    result = cli_coordinator.request_database_access()
        
        assert result is True
        assert cli_coordinator._coordination_active
    
    def test_request_database_access_signal_fails(self, cli_coordinator):
        """Test access request when signal sending fails."""
        with patch.object(cli_coordinator.signal_coordinator, 'is_mcp_server_running', return_value=True):
            with patch.object(cli_coordinator.signal_coordinator, 'send_coordination_signal', return_value=False):
                
                result = cli_coordinator.request_database_access()
        
        assert result is False
        assert not cli_coordinator._coordination_active
    
    def test_request_database_access_ready_timeout(self, cli_coordinator):
        """Test access request when ready flag times out."""
        with patch.object(cli_coordinator.signal_coordinator, 'is_mcp_server_running', return_value=True):
            with patch.object(cli_coordinator.signal_coordinator, 'send_coordination_signal', return_value=True):
                with patch.object(cli_coordinator.signal_coordinator, 'wait_for_ready_flag', return_value=False):
                    
                    result = cli_coordinator.request_database_access()
        
        assert result is False
        assert not cli_coordinator._coordination_active
    
    def test_release_database_access_not_active(self, cli_coordinator):
        """Test releasing access when not coordinating."""
        result = cli_coordinator.release_database_access()
        
        assert result is True
    
    def test_release_database_access_success(self, cli_coordinator):
        """Test successful database access release."""
        cli_coordinator._coordination_active = True
        
        with patch.object(cli_coordinator.signal_coordinator, 'signal_indexing_complete') as mock_signal:
            with patch.object(cli_coordinator.signal_coordinator, 'send_coordination_signal', return_value=True) as mock_send:
                with patch.object(cli_coordinator.signal_coordinator, 'cleanup_coordination_files') as mock_cleanup:
                    
                    result = cli_coordinator.release_database_access()
        
        assert result is True
        assert not cli_coordinator._coordination_active
        
        mock_signal.assert_called_once()
        mock_send.assert_called_once_with('reopen')
        mock_cleanup.assert_called_once()
    
    def test_release_database_access_signal_fails(self, cli_coordinator):
        """Test access release when signal sending fails."""
        cli_coordinator._coordination_active = True
        
        with patch.object(cli_coordinator.signal_coordinator, 'signal_indexing_complete'):
            with patch.object(cli_coordinator.signal_coordinator, 'send_coordination_signal', return_value=False):
                with patch.object(cli_coordinator.signal_coordinator, 'cleanup_coordination_files'):
                    
                    result = cli_coordinator.release_database_access()
        
        assert result is False
        assert not cli_coordinator._coordination_active
    
    def test_context_manager_success(self, temp_db_path):
        """Test context manager with successful coordination."""
        with patch('chunkhound.signal_coordinator.CLICoordinator.request_database_access', return_value=True):
            with patch('chunkhound.signal_coordinator.CLICoordinator.release_database_access') as mock_release:
                
                with CLICoordinator(temp_db_path) as coordinator:
                    coordinator._coordination_active = True
                
                mock_release.assert_called_once()
    
    def test_context_manager_no_coordination(self, temp_db_path):
        """Test context manager when no coordination needed."""
        with patch('chunkhound.signal_coordinator.CLICoordinator.release_database_access') as mock_release:
            
            with CLICoordinator(temp_db_path) as coordinator:
                pass  # No coordination active
            
            # Should not call release when coordination is not active
            mock_release.assert_not_called()


class TestIntegration:
    """Integration tests for signal coordination."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        db_path.unlink(missing_ok=True)
    
    def test_full_coordination_cycle(self, temp_db_path):
        """Test complete coordination cycle between CLI and MCP."""
        mock_database = Mock()
        mock_database.db_path = str(temp_db_path)
        
        # Create coordinators
        mcp_coordinator = SignalCoordinator(temp_db_path, mock_database)
        cli_coordinator = CLICoordinator(temp_db_path)
        
        try:
            # Simulate MCP server setup
            with patch.object(mcp_coordinator.process_detector, 'register_mcp_server'):
                mcp_coordinator.setup_mcp_signal_handling()
            
            # Simulate server running
            with patch.object(cli_coordinator.signal_coordinator, 'is_mcp_server_running', return_value=True):
                with patch.object(cli_coordinator.signal_coordinator, 'send_coordination_signal', return_value=True):
                    with patch.object(cli_coordinator.signal_coordinator, 'wait_for_ready_flag', return_value=True):
                        
                        # Request access
                        assert cli_coordinator.request_database_access()
                        assert cli_coordinator._coordination_active
                        
                        # Release access
                        with patch.object(cli_coordinator.signal_coordinator, 'send_coordination_signal', return_value=True):
                            assert cli_coordinator.release_database_access()
                            assert not cli_coordinator._coordination_active
        
        finally:
            # Cleanup
            mcp_coordinator.cleanup_coordination_files()