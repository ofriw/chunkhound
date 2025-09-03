"""Cross-platform keyboard input handling using readchar library."""

import readchar


class KeyboardInput:
    """Cross-platform keyboard input handler using readchar library."""

    def __init__(self):
        """Initialize keyboard input handler."""
        pass

    def getkey(self, timeout: float | None = None) -> str:
        """
        Get a single keypress without waiting for Enter.

        Args:
            timeout: Optional timeout in seconds (not supported by readchar)

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
            # Note: readchar doesn't support timeout, but it's very fast
            key = readchar.readkey()

            # Map readchar constants to our expected values
            if key == readchar.key.UP:
                return "UP"
            elif key == readchar.key.DOWN:
                return "DOWN"
            elif key == readchar.key.LEFT:
                return "LEFT"
            elif key == readchar.key.RIGHT:
                return "RIGHT"
            elif key == readchar.key.ENTER:
                return "ENTER"
            elif key == readchar.key.ESC:
                return "ESC"
            elif key == readchar.key.BACKSPACE:
                return "BACKSPACE"

            # Handle other special keys if available
            if hasattr(readchar.key, 'DELETE') and key == readchar.key.DELETE:
                return "DELETE"
            elif hasattr(readchar.key, 'HOME') and key == readchar.key.HOME:
                return "HOME"
            elif hasattr(readchar.key, 'END') and key == readchar.key.END:
                return "END"
            elif hasattr(readchar.key, 'PAGE_UP') and key == readchar.key.PAGE_UP:
                return "PAGE_UP"
            elif hasattr(readchar.key, 'PAGE_DOWN') and key == readchar.key.PAGE_DOWN:
                return "PAGE_DOWN"
            elif hasattr(readchar.key, 'INSERT') and key == readchar.key.INSERT:
                return "INSERT"
            elif hasattr(readchar.key, 'CTRL_C') and key == readchar.key.CTRL_C:
                return "CTRL_C"
            elif hasattr(readchar.key, 'CTRL_D') and key == readchar.key.CTRL_D:
                return "CTRL_D"

            # Handle regular characters
            if len(key) == 1:
                if key == '\r' or key == '\n':
                    return "ENTER"
                elif key == '\x1b':
                    return "ESC"
                elif key == '\x7f' or key == '\x08':
                    return "BACKSPACE"
                elif key == '\x03':
                    return "CTRL_C"
                elif key == '\x04':
                    return "CTRL_D"
                else:
                    return key
            else:
                # Multi-character sequences - return as-is
                return key

        except KeyboardInterrupt:
            return "CTRL_C"
        except EOFError:
            return "CTRL_D"


# Global keyboard instance for convenience
keyboard = KeyboardInput()