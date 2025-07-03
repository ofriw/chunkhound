"""Process detection module for ChunkHound - MCP server discovery and PID management."""

import hashlib
from pathlib import Path
from typing import Any

import psutil
from loguru import logger


class ProcessInfo:
    """Information about a detected process."""

    def __init__(self, pid: int, process: psutil.Process, pid_file: Path):
        self.pid = pid
        self.process = process
        self.pid_file = pid_file

    def __repr__(self) -> str:
        return f"ProcessInfo(pid={self.pid}, pid_file={self.pid_file})"


class ProcessDetector:
    """Detect and manage MCP server processes for database coordination."""

    def __init__(self, db_path: Path | str):
        """Initialize process detector.

        Args:
            db_path: Path to the database file for coordination
        """
        self.db_path = Path(db_path).resolve()  # Ensure absolute path
        self.coordination_dir = self._get_coordination_dir()
        self._ensure_coordination_dir()

    def _get_coordination_dir(self) -> Path:
        """Get coordination directory based on database path hash."""
        db_hash = hashlib.md5(str(self.db_path.absolute()).encode()).hexdigest()[:8]
        return Path(f"/tmp/chunkhound-{db_hash}")

    def _ensure_coordination_dir(self) -> None:
        """Ensure coordination directory exists."""
        try:
            self.coordination_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Coordination directory ready: {self.coordination_dir}")
        except OSError as e:
            logger.error(
                f"Failed to create coordination directory {self.coordination_dir}: {e}"
            )
            raise

    def detect_mcp_server_instances(self) -> list[ProcessInfo]:
        """Detect all running MCP server instances for this database.

        Returns:
            List of ProcessInfo objects for detected servers
        """
        instances = []
        server_info = self.find_mcp_server()
        if server_info:
            instances.append(
                ProcessInfo(
                    pid=server_info["pid"],
                    process=server_info["process"],
                    pid_file=server_info["pid_file"],
                )
            )
        return instances

    def is_mcp_server_running(self) -> bool:
        """Check if MCP server is currently running.

        Returns:
            True if server is running, False otherwise
        """
        return self.find_mcp_server() is not None

    def get_server_pid(self) -> int | None:
        """Get PID of running MCP server.

        Returns:
            PID if server is running, None otherwise
        """
        server_info = self.find_mcp_server()
        return server_info["pid"] if server_info else None

    def find_mcp_server(self) -> dict[str, Any] | None:
        """Find running MCP server for this database.

        Returns:
            Dictionary with server info or None if not found
        """
        pid_file = self.coordination_dir / "mcp.pid"

        if not pid_file.exists():
            logger.debug(f"No PID file found at {pid_file}")
            return None

        try:
            pid_content = pid_file.read_text().strip()
            if not pid_content:
                logger.warning(f"Empty PID file: {pid_file}")
                self._cleanup_pid_file(pid_file)
                return None

            pid = int(pid_content)
            logger.debug(f"Found PID {pid} in file {pid_file}")

            if not self.validate_pid_active(pid):
                logger.info(f"PID {pid} is not active, cleaning up stale file")
                self._cleanup_pid_file(pid_file)
                return None

            process = psutil.Process(pid)

            # Validate it's actually chunkhound mcp server
            if not self._is_chunkhound_mcp(process):
                logger.warning(f"PID {pid} is not a ChunkHound MCP server, cleaning up")
                self._cleanup_pid_file(pid_file)
                return None

            logger.debug(f"Validated MCP server: PID {pid}")
            return {"pid": pid, "process": process, "pid_file": pid_file}

        except (ValueError, psutil.NoSuchProcess, FileNotFoundError) as e:
            logger.debug(f"Error reading/validating PID file {pid_file}: {e}")
            self._cleanup_pid_file(pid_file)
            return None
        except Exception as e:
            logger.error(f"Unexpected error checking PID file {pid_file}: {e}")
            return None

    def validate_pid_active(self, pid: int) -> bool:
        """Validate that a PID represents an active process.

        Args:
            pid: Process ID to validate

        Returns:
            True if process is active, False otherwise
        """
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception as e:
            logger.debug(f"Error validating PID {pid}: {e}")
            return False

    def _is_chunkhound_mcp(self, process: psutil.Process) -> bool:
        """Verify process is chunkhound mcp server with correct database.

        Args:
            process: Process to validate

        Returns:
            True if it's a ChunkHound MCP server for this database
        """
        try:
            cmdline = process.cmdline()
            cmdline_str = " ".join(cmdline)

            # Check for chunkhound command
            is_chunkhound = "chunkhound" in cmdline_str

            # Check for mcp subcommand
            is_mcp = "mcp" in cmdline

            # Check for database path (handle both absolute and relative paths)
            has_db_path = (
                str(self.db_path) in cmdline_str
                or str(self.db_path.name) in cmdline_str
            )

            result = is_chunkhound and is_mcp and has_db_path

            logger.debug(
                f"Process validation for PID {process.pid}: "
                f"chunkhound={is_chunkhound}, mcp={is_mcp}, db_path={has_db_path}"
            )

            return result

        except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
            logger.debug(f"Cannot access process {process.pid}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Error validating process {process.pid}: {e}")
            return False

    def register_mcp_server(self, pid: int) -> None:
        """Register MCP server PID for coordination.

        Args:
            pid: Process ID to register
        """
        try:
            pid_file = self.coordination_dir / "mcp.pid"
            pid_file.write_text(str(pid))
            logger.info(f"Registered MCP server PID {pid} in {pid_file}")
        except OSError as e:
            logger.error(f"Failed to register PID {pid}: {e}")
            raise

    def create_pid_file(self, pid: int) -> None:
        """Create PID file for process tracking.

        Args:
            pid: Process ID to store
        """
        self.register_mcp_server(pid)

    def remove_pid_file(self) -> None:
        """Remove PID file."""
        pid_file = self.coordination_dir / "mcp.pid"
        self._cleanup_pid_file(pid_file)

    def _cleanup_pid_file(self, pid_file: Path) -> None:
        """Clean up a PID file safely.

        Args:
            pid_file: Path to PID file to remove
        """
        try:
            if pid_file.exists():
                pid_file.unlink()
                logger.debug(f"Cleaned up PID file: {pid_file}")
        except FileNotFoundError:
            # Already removed, this is fine
            pass
        except OSError as e:
            logger.warning(f"Failed to clean up PID file {pid_file}: {e}")

    def cleanup_stale_pids(self) -> None:
        """Clean up stale PID files."""
        pid_file = self.coordination_dir / "mcp.pid"
        if pid_file.exists():
            try:
                pid_content = pid_file.read_text().strip()
                if pid_content:
                    pid = int(pid_content)
                    if not self.validate_pid_active(pid):
                        logger.info(f"Cleaning up stale PID {pid}")
                        self._cleanup_pid_file(pid_file)
                else:
                    logger.info("Cleaning up empty PID file")
                    self._cleanup_pid_file(pid_file)
            except (ValueError, FileNotFoundError) as e:
                logger.debug(f"Error during stale PID cleanup: {e}")
                self._cleanup_pid_file(pid_file)

    def cleanup_coordination_files(self) -> None:
        """Clean up all coordination files."""
        try:
            if not self.coordination_dir.exists():
                return

            for file_path in self.coordination_dir.glob("*"):
                try:
                    if file_path.is_file():
                        file_path.unlink()
                        logger.debug(f"Cleaned up coordination file: {file_path}")
                except FileNotFoundError:
                    # Already removed
                    pass
                except OSError as e:
                    logger.warning(f"Failed to clean up {file_path}: {e}")

            # Try to remove the directory if it's empty
            try:
                self.coordination_dir.rmdir()
                logger.debug(f"Removed coordination directory: {self.coordination_dir}")
            except OSError:
                # Directory not empty or other issue, leave it
                pass

        except Exception as e:
            logger.error(f"Error during coordination files cleanup: {e}")
