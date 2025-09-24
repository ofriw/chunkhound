"""Cross-platform terminal input library.

This package provides reliable keyboard input handling across platforms,
with proper support for bracketed paste mode filtering and arrow keys.

Designed to be standalone and extractable as a separate library.
"""

from .core import Keys, TerminalConfig
from .exceptions import (
    TerminalConfigurationError,
    TerminalError,
    TerminalInputTimeout,
    TerminalSetupError,
    TerminalUnsupportedPlatform,
)
from .providers.base import create_provider


class TerminalInput:
    """Main terminal input class providing cross-platform keyboard input.

    This class provides a simple, readchar-compatible API while handling
    all the complexities of cross-platform terminal input, including:
    - Bracketed paste mode filtering
    - Arrow key normalization
    - Proper terminal setup and cleanup
    - Timeout handling

    Usage:
        # Simple usage
        terminal = TerminalInput()
        key = terminal.getkey()

        # With configuration
        config = TerminalConfig(disable_bracketed_paste=False)
        terminal = TerminalInput(config)

        # As context manager (recommended)
        with TerminalInput() as terminal:
            key = terminal.getkey()
    """

    def __init__(self, config: TerminalConfig | None = None):
        """Initialize terminal input handler.

        Args:
            config: Terminal configuration, uses defaults if None
        """
        self.config = config or TerminalConfig()
        self._provider = create_provider(self.config)
        self._is_setup = False

    def setup(self) -> None:
        """Initialize terminal for input capture.

        This must be called before using getkey() or getchar().
        Use as context manager to ensure proper cleanup.

        Raises:
            TerminalSetupError: If terminal setup fails
        """
        if not self._is_setup:
            self._provider.setup()
            self._is_setup = True

    def cleanup(self) -> None:
        """Restore terminal to original state.

        Should be called when done with terminal input to restore
        normal terminal behavior.
        """
        if self._is_setup:
            self._provider.cleanup()
            self._is_setup = False

    def getkey(self, timeout: float | None = None) -> str:
        """Read a key input, returning normalized key name.

        This is the main method for getting keyboard input. It handles:
        - Arrow keys (returns "UP", "DOWN", "LEFT", "RIGHT")
        - Function keys (returns "F1", "F2", etc.)
        - Control keys (returns normalized names)
        - Regular characters (returns the character)
        - Bracketed paste filtering (returns pasted content without control chars)

        Args:
            timeout: Maximum time to wait for input in seconds.
                    None for no timeout (blocks indefinitely).

        Returns:
            Key name or character. For special keys, returns standard names
            like "UP", "DOWN", "ENTER", etc. For regular characters, returns
            the character itself.

        Raises:
            TerminalInputTimeout: If timeout occurs before input is available
            TerminalSetupError: If terminal is not set up

        Examples:
            key = terminal.getkey()        # Block until key pressed
            key = terminal.getkey(1.0)     # Wait up to 1 second

            if key == "UP":
                handle_up_arrow()
            elif key == "\r":  # Enter key
                handle_enter()
            elif key.isalpha():
                handle_letter(key)
        """
        if not self._is_setup:
            self.setup()

        return self._provider.read_key(timeout)

    def getchar(self) -> str:
        """Read a single raw character without processing.

        This method bypasses all filtering and processing, returning
        the raw character from the terminal. Use getkey() instead
        unless you need unprocessed input.

        Returns:
            Raw character from terminal

        Raises:
            TerminalSetupError: If terminal is not set up
        """
        if not self._is_setup:
            self.setup()

        return self._provider.read_char()

    def has_input(self, timeout: float | None = None) -> bool:
        """Check if input is available without blocking.

        Args:
            timeout: Maximum time to wait for input in seconds.
                    None blocks indefinitely, 0 returns immediately.

        Returns:
            True if input is available
        """
        if not self._is_setup:
            return False

        return self._provider.has_input(timeout)

    def __enter__(self):
        """Context manager entry - sets up terminal."""
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleans up terminal."""
        self.cleanup()

    def __del__(self):
        """Destructor - ensure cleanup."""
        try:
            self.cleanup()
        except Exception:
            # Don't raise exceptions in destructor
            pass


# Create a global instance for convenience (like readchar)
_global_terminal = None


def getkey(timeout: float | None = None) -> str:
    """Global function to read a key (readchar compatibility).

    This provides a drop-in replacement for readchar.readkey().
    Creates a global TerminalInput instance on first use.

    Args:
        timeout: Maximum time to wait for input in seconds

    Returns:
        Key name or character

    Raises:
        TerminalInputTimeout: If timeout occurs
        TerminalSetupError: If terminal setup fails
    """
    global _global_terminal
    if _global_terminal is None:
        _global_terminal = TerminalInput()

    return _global_terminal.getkey(timeout)


def getchar() -> str:
    """Global function to read a character (readchar compatibility).

    This provides a drop-in replacement for readchar.readchar().

    Returns:
        Raw character from terminal
    """
    global _global_terminal
    if _global_terminal is None:
        _global_terminal = TerminalInput()

    return _global_terminal.getchar()


# Export main public API
__all__ = [
    # Main classes
    "TerminalInput",
    "TerminalConfig",
    "Keys",
    # Exceptions
    "TerminalError",
    "TerminalSetupError",
    "TerminalInputTimeout",
    "TerminalUnsupportedPlatform",
    "TerminalConfigurationError",
    # Global functions (readchar compatibility)
    "getkey",
    "getchar",
]
