"""Cross-platform keyboard input handling.

This module provides reliable keyboard input handling across platforms,
with proper support for bracketed paste mode filtering and arrow keys.

Now uses our custom terminal module instead of readchar to fix
cross-platform compatibility issues.
"""

from .terminal import Keys, TerminalError, TerminalInput, TerminalInputTimeout


class KeyboardInput:
    """Cross-platform keyboard input handler.

    Provides the same API as the original readchar-based implementation
    but uses our custom terminal module for better cross-platform support.
    """

    def __init__(self):
        """Initialize keyboard input handler."""
        self._terminal = TerminalInput()
        self._setup_done = False

    def getkey(self, timeout: float | None = None) -> str:
        """
        Get a single keypress without waiting for Enter.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            String representing the key pressed:
            - "UP", "DOWN", "LEFT", "RIGHT" for arrow keys
            - "ENTER" for Enter key
            - "ESC" for Escape key
            - "BACKSPACE" for Backspace
            - Single character for regular keys
            - "CTRL_C", "CTRL_D" for control characters
        """
        try:
            # Ensure terminal is set up
            if not self._setup_done:
                self._terminal.setup()
                self._setup_done = True

            # Get key from terminal
            key = self._terminal.getkey(timeout)

            # Map our terminal module keys to expected format
            if key == Keys.UP:
                return "UP"
            elif key == Keys.DOWN:
                return "DOWN"
            elif key == Keys.LEFT:
                return "LEFT"
            elif key == Keys.RIGHT:
                return "RIGHT"
            elif key == Keys.HOME:
                return "HOME"
            elif key == Keys.END:
                return "END"
            elif key == Keys.PAGE_UP:
                return "PAGE_UP"
            elif key == Keys.PAGE_DOWN:
                return "PAGE_DOWN"
            elif key == Keys.INSERT:
                return "INSERT"
            elif key == Keys.DELETE:
                return "DELETE"
            elif key == Keys.F1:
                return "F1"
            elif key == Keys.F2:
                return "F2"
            elif key == Keys.F3:
                return "F3"
            elif key == Keys.F4:
                return "F4"
            elif key == Keys.F5:
                return "F5"
            elif key == Keys.F6:
                return "F6"
            elif key == Keys.F7:
                return "F7"
            elif key == Keys.F8:
                return "F8"
            elif key == Keys.F9:
                return "F9"
            elif key == Keys.F10:
                return "F10"
            elif key == Keys.F11:
                return "F11"
            elif key == Keys.F12:
                return "F12"

            # Handle single characters and control sequences
            if len(key) == 1:
                if key == "\r" or key == "\n":
                    return "ENTER"
                elif key == "\x1b":
                    return "ESC"
                elif key == "\x7f" or key == "\x08":
                    return "BACKSPACE"
                elif key == "\x03":
                    return "CTRL_C"
                elif key == "\x04":
                    return "CTRL_D"
                elif key == "\t":
                    return "TAB"
                else:
                    return key
            else:
                # Multi-character sequences or unrecognized keys - return as-is
                return key

        except TerminalInputTimeout:
            # Convert timeout to the same format as readchar would
            raise TimeoutError("Input timeout")
        except KeyboardInterrupt:
            return "CTRL_C"
        except EOFError:
            return "CTRL_D"
        except TerminalError:
            # For terminal errors, try to return something reasonable
            # rather than crashing the setup wizard
            self.cleanup()
            return "ESC"
        except Exception as e:
            # Any other error - clean up but be selective about returning ESC
            self.cleanup()
            # Only return ESC for specific error types that warrant cancellation
            if isinstance(e, (OSError, IOError, UnicodeDecodeError)):
                return "ESC"
            else:
                # For other exceptions, re-raise to avoid masking bugs
                raise

    def cleanup(self) -> None:
        """Clean up terminal state.

        This should be called when the application exits to restore
        normal terminal behavior.
        """
        if self._setup_done:
            self._terminal.cleanup()
            self._setup_done = False

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.cleanup()
        except Exception:
            # Don't raise exceptions in destructor
            pass


# Global keyboard instance for convenience (lazy initialization)
_keyboard_instance = None


def _get_keyboard():
    """Get or create the global keyboard instance."""
    global _keyboard_instance
    if _keyboard_instance is None:
        _keyboard_instance = KeyboardInput()
    return _keyboard_instance


# Create a proxy object that behaves like KeyboardInput
class _KeyboardProxy:
    """Proxy object for lazy keyboard initialization."""

    def getkey(self, timeout: float | None = None) -> str:
        """Get key from lazy-initialized keyboard instance."""
        return _get_keyboard().getkey(timeout)

    def cleanup(self) -> None:
        """Clean up lazy-initialized keyboard instance."""
        if _keyboard_instance is not None:
            _keyboard_instance.cleanup()


# Global keyboard instance that won't cause import errors
keyboard = _KeyboardProxy()
