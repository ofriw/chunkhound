"""Windows terminal input provider."""

from typing import Any

from ..exceptions import TerminalUnsupportedPlatform
from .base import BaseTerminalProvider


class WindowsTerminalProvider(BaseTerminalProvider):
    """Windows terminal input provider using msvcrt."""

    def __init__(self, config):
        """Initialize Windows terminal provider.

        Args:
            config: Terminal configuration
        """
        super().__init__(config)

        # Import Windows-specific modules
        try:
            import msvcrt

            self._msvcrt = msvcrt
        except ImportError:
            raise TerminalUnsupportedPlatform(
                platform="windows",
                operation="import_msvcrt",
                reason="msvcrt module not available",
            )

    def _get_platform_name(self) -> str:
        """Get the platform name for this provider."""
        return "windows"

    def _save_terminal_state(self) -> Any:
        """Save current terminal state for later restoration.

        Returns:
            None (Windows doesn't need to save/restore terminal state)
        """
        # Windows terminal state is managed differently
        return None

    def _restore_terminal_state(self, state: Any) -> None:
        """Restore terminal to saved state.

        Args:
            state: Ignored for Windows
        """
        # No restoration needed for Windows
        pass

    def _enter_raw_mode(self) -> None:
        """Put terminal into raw input mode.

        For Windows, this is handled automatically by msvcrt.
        """
        # msvcrt.getch() already provides unbuffered input
        pass

    def _configure_terminal(self) -> None:
        """Apply Windows-specific terminal configuration."""
        # Windows doesn't support the same terminal control sequences
        # Bracketed paste and cursor modes are handled differently

        if self.config.disable_bracketed_paste:
            # Windows terminals don't typically use bracketed paste mode
            # in the same way as Unix terminals
            pass

        if self.config.normalize_cursor_mode:
            # Windows handles cursor keys differently
            pass

    def _read_raw_char(self) -> str:
        """Read a single raw character from terminal.

        Returns:
            Single character, may be empty string if no input
        """
        try:
            if self._has_raw_input(0):  # Non-blocking check
                char_code = self._msvcrt.getch()

                # Handle special keys that return two bytes
                if char_code in (b"\x00", b"\xe0"):
                    # Special key - read the second byte
                    if self._has_raw_input(0.01):  # Small timeout for second byte
                        second_byte = self._msvcrt.getch()
                        return self._map_special_key(char_code, second_byte)
                    else:
                        # Only got first byte - return escape
                        return "\x1b"
                else:
                    # Regular character
                    return char_code.decode("utf-8", errors="replace")
            return ""
        except (OSError, UnicodeDecodeError):
            return ""

    def _has_raw_input(self, timeout: float | None = None) -> bool:
        """Check if raw input is available.

        Args:
            timeout: Timeout in seconds (ignored for Windows - always non-blocking)

        Returns:
            True if input is available
        """
        try:
            return self._msvcrt.kbhit()
        except OSError:
            return False

    def _map_special_key(self, first_byte: bytes, second_byte: bytes) -> str:
        """Map Windows special key codes to standard key names.

        Args:
            first_byte: First byte (0x00 or 0xe0)
            second_byte: Second byte (key code)

        Returns:
            Standard key name
        """
        # Windows virtual key codes to standard names
        key_map = {
            b"H": "UP",  # Up arrow
            b"P": "DOWN",  # Down arrow
            b"K": "LEFT",  # Left arrow
            b"M": "RIGHT",  # Right arrow
            b"G": "HOME",  # Home
            b"O": "END",  # End
            b"I": "PAGE_UP",  # Page Up
            b"Q": "PAGE_DOWN",  # Page Down
            b"R": "INSERT",  # Insert
            b"S": "DELETE",  # Delete
        }

        return key_map.get(second_byte, f"\\x{second_byte[0]:02x}")

    def cleanup(self) -> None:
        """Restore terminal to original state with Windows-specific cleanup."""
        # Windows doesn't need special cleanup
        super().cleanup()
