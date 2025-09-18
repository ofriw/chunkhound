"""Unix/Linux terminal input provider."""

import os
import select
import signal
import sys

try:
    import termios

    HAS_TERMIOS = True
except ImportError:
    # termios is Unix-only, not available on Windows
    HAS_TERMIOS = False
from typing import Any

from ..core import TERMINAL_CONTROL_SEQUENCES
from ..exceptions import TerminalSetupError
from .base import BaseTerminalProvider


class UnixTerminalProvider(BaseTerminalProvider):
    """Unix/Linux terminal input provider using termios and select."""

    def __init__(self, config):
        """Initialize Unix terminal provider.

        Args:
            config: Terminal configuration

        Raises:
            ImportError: If termios module is not available (Windows)
        """
        if not HAS_TERMIOS:
            raise ImportError(
                "termios module not available - Unix terminal provider cannot be used on this platform"
            )

        super().__init__(config)
        self._stdin_fd = None  # Lazy initialization
        self._original_signal_handler = None

    def _get_stdin_fd(self):
        """Get stdin file descriptor with lazy initialization."""
        if self._stdin_fd is None:
            self._stdin_fd = sys.stdin.fileno()
        return self._stdin_fd

    def _get_platform_name(self) -> str:
        """Get the platform name for this provider."""
        return "unix"

    def _save_terminal_state(self) -> Any:
        """Save current terminal state for later restoration.

        Returns:
            Terminal attributes from termios.tcgetattr()
        """
        try:
            return termios.tcgetattr(self._get_stdin_fd())
        except (termios.error, OSError) as e:
            raise TerminalSetupError(
                operation="save_terminal_state",
                platform="unix",
                reason=f"Failed to get terminal attributes: {e}",
            ) from e

    def _restore_terminal_state(self, state: Any) -> None:
        """Restore terminal to saved state.

        Args:
            state: Terminal attributes from _save_terminal_state()
        """
        try:
            termios.tcsetattr(self._get_stdin_fd(), termios.TCSADRAIN, state)
        except (termios.error, OSError):
            # Best effort - don't raise exceptions during cleanup
            pass

    def _enter_raw_mode(self) -> None:
        """Put terminal into character-at-a-time mode while keeping output processing."""
        try:
            # Get current terminal attributes
            attrs = termios.tcgetattr(self._get_stdin_fd())

            # Disable canonical mode and echo (like setraw does)
            attrs[3] &= ~(termios.ICANON | termios.ECHO | termios.ISIG)
            # Disable input processing that interferes with raw input
            attrs[0] &= ~(termios.IXON | termios.IXOFF | termios.ICRNL)

            # CRITICAL: Keep OPOST enabled for output processing
            # This allows \n to work as newline (not just line feed)
            # Ensure ONLCR is set for \n -> \r\n translation
            attrs[1] |= termios.OPOST | termios.ONLCR

            # Set VMIN=1, VTIME=0 for immediate single-char input
            attrs[6][termios.VMIN] = 1
            attrs[6][termios.VTIME] = 0

            termios.tcsetattr(self._get_stdin_fd(), termios.TCSADRAIN, attrs)
        except (termios.error, OSError) as e:
            raise TerminalSetupError(
                operation="enter_raw_mode",
                platform="unix",
                reason=f"Failed to set raw mode: {e}",
            ) from e

    def _configure_terminal(self) -> None:
        """Apply Unix-specific terminal configuration."""
        try:
            # Send terminal control sequences to normalize behavior
            if self.config.disable_bracketed_paste:
                self._write_to_terminal(
                    TERMINAL_CONTROL_SEQUENCES["disable_bracketed_paste"]
                )

            if self.config.normalize_cursor_mode:
                self._write_to_terminal(
                    TERMINAL_CONTROL_SEQUENCES["normal_cursor_mode"]
                )

            # Set up signal handler for cleanup
            self._setup_signal_handler()

        except Exception as e:
            raise TerminalSetupError(
                operation="configure_terminal",
                platform="unix",
                reason=f"Failed to configure terminal: {e}",
            ) from e

    def _write_to_terminal(self, sequence: str) -> None:
        """Write control sequence to terminal.

        Args:
            sequence: Control sequence to write
        """
        try:
            os.write(sys.stdout.fileno(), sequence.encode())
            sys.stdout.flush()
        except OSError:
            # If we can't write control sequences, continue anyway
            pass

    def _setup_signal_handler(self) -> None:
        """Set up signal handler for cleanup."""

        def signal_handler(signum, frame):
            self.cleanup()
            # Restore original handler and re-raise
            if self._original_signal_handler:
                signal.signal(signal.SIGINT, self._original_signal_handler)
            raise KeyboardInterrupt()

        self._original_signal_handler = signal.signal(signal.SIGINT, signal_handler)

    def _read_raw_char(self) -> str:
        """Read a single raw character from terminal.

        Returns:
            Single character, may be empty string if no input
        """
        try:
            if self._has_raw_input(0):  # Non-blocking check
                char = os.read(self._get_stdin_fd(), 1)
                return char.decode("utf-8", errors="replace")
            return ""
        except (OSError, UnicodeDecodeError):
            return ""

    def _set_timeout_mode(self) -> None:
        """Set terminal to timeout mode for escape sequence detection."""
        try:
            attrs = termios.tcgetattr(self._get_stdin_fd())
            # Convert seconds to deciseconds (VTIME units)
            timeout_deciseconds = int(self.config.timeout_incomplete_sequence * 10)
            # Ensure minimum of 1 decisecond (100ms) and maximum of 25 (2.5s)
            timeout_deciseconds = max(1, min(25, timeout_deciseconds))
            attrs[6][termios.VTIME] = timeout_deciseconds
            attrs[6][termios.VMIN] = 0  # Return immediately after timeout
            termios.tcsetattr(self._get_stdin_fd(), termios.TCSANOW, attrs)
        except (termios.error, OSError):
            # If we can't set timeout mode, continue without it
            pass

    def _set_normal_mode(self) -> None:
        """Set terminal to normal mode for regular input."""
        try:
            attrs = termios.tcgetattr(self._get_stdin_fd())
            attrs[6][termios.VTIME] = 0  # No timeout
            attrs[6][termios.VMIN] = 1  # Wait for at least 1 byte
            termios.tcsetattr(self._get_stdin_fd(), termios.TCSANOW, attrs)
        except (termios.error, OSError):
            # If we can't set normal mode, continue without it
            pass

    def _read_key_with_escape_handling(self) -> str:
        """Read a key with proper escape sequence handling using VMIN/VTIME.

        This implements the standard Unix pattern for distinguishing
        between standalone Escape key and escape sequences.

        Returns:
            Raw key or escape sequence
        """
        try:
            # Read first byte with blocking mode (VMIN=1, VTIME=0)
            first_byte = os.read(self._get_stdin_fd(), 1)
            first_char = first_byte.decode("utf-8", errors="replace")

            if first_char == "\x1b":  # ESC character
                # Switch to timeout mode to check for continuation
                self._set_timeout_mode()
                try:
                    # Read continuation bytes (up to 10 for safety)
                    rest_bytes = os.read(self._get_stdin_fd(), 10)
                    if rest_bytes:
                        # We got continuation - it's an escape sequence
                        rest_chars = rest_bytes.decode("utf-8", errors="replace")
                        return first_char + rest_chars
                    else:
                        # Timeout - just the Escape key
                        return first_char
                finally:
                    # Always restore normal mode
                    self._set_normal_mode()
            else:
                # Regular character
                return first_char

        except (OSError, UnicodeDecodeError):
            return ""

    def _has_raw_input(self, timeout: float | None = None) -> bool:
        """Check if raw input is available.

        Args:
            timeout: Maximum time to wait, None for blocking

        Returns:
            True if input is available
        """
        try:
            stdin_fd = self._get_stdin_fd()
            if timeout is None:
                # Blocking check - wait indefinitely
                ready, _, _ = select.select([stdin_fd], [], [])
                return bool(ready)
            elif timeout == 0:
                # Non-blocking check
                ready, _, _ = select.select([stdin_fd], [], [], 0)
                return bool(ready)
            else:
                # Timeout check
                ready, _, _ = select.select([stdin_fd], [], [], timeout)
                return bool(ready)
        except OSError:
            return False

    def cleanup(self) -> None:
        """Restore terminal to original state with Unix-specific cleanup."""
        # Flush input buffer to prevent leftover characters from appearing in terminal
        if self._is_setup:
            try:
                # Flush input buffer (discard unread input)
                termios.tcflush(self._get_stdin_fd(), termios.TCIFLUSH)
            except (termios.error, OSError):
                # Best effort - continue with cleanup even if flush fails
                pass

        # Restore signal handler
        if self._original_signal_handler is not None:
            try:
                signal.signal(signal.SIGINT, self._original_signal_handler)
                self._original_signal_handler = None
            except (OSError, ValueError):
                pass

        # Send control sequences to restore terminal behavior
        if self._is_setup:
            try:
                if self.config.disable_bracketed_paste:
                    # Re-enable bracketed paste if it was originally on
                    # (This is debatable - we might want to leave it disabled)
                    pass

                if self.config.normalize_cursor_mode:
                    # Could restore to application cursor mode, but safer to leave in normal mode
                    pass

            except Exception:
                pass

        # Call parent cleanup to restore terminal attributes
        super().cleanup()


class UnixTerminalProviderLegacy(UnixTerminalProvider):
    """Legacy Unix provider that tries to work with older systems.

    This version uses more conservative approaches that may work better
    on older Ubuntu versions or systems with limited terminal capabilities.
    """

    def _configure_terminal(self) -> None:
        """Apply conservative Unix terminal configuration."""
        try:
            # Only send essential control sequences
            if self.config.disable_bracketed_paste:
                self._write_to_terminal(
                    TERMINAL_CONTROL_SEQUENCES["disable_bracketed_paste"]
                )

            # Don't normalize cursor mode on legacy systems
            # Set up signal handler
            self._setup_signal_handler()

        except Exception:
            # On legacy systems, continue even if configuration fails
            pass

    def _read_raw_char(self) -> str:
        """Read with more conservative approach for legacy systems."""
        try:
            # Use smaller read buffer for older systems
            if self._has_raw_input(0):
                char_bytes = os.read(self._get_stdin_fd(), 1)
                if char_bytes:
                    # Handle encoding more gracefully
                    try:
                        return char_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        # Fallback to latin-1 for non-UTF8 systems
                        return char_bytes.decode("latin-1", errors="replace")
            return ""
        except OSError:
            return ""
