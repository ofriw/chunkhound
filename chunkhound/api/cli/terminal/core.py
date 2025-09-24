"""Core types and protocols for terminal input."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class TerminalConfig(BaseModel):
    """Configuration for terminal input behavior."""

    disable_bracketed_paste: bool = True
    normalize_cursor_mode: bool = True
    timeout_incomplete_sequence: float = 0.5  # Timeout in seconds for escape sequences
    arrow_key_mode: str = "auto"  # auto, normal, application
    enable_mouse: bool = False
    buffer_size: int = 64


class TerminalInputProvider(Protocol):
    """Protocol for platform-specific terminal input providers."""

    def setup(self) -> None:
        """Initialize terminal for raw input mode."""
        ...

    def cleanup(self) -> None:
        """Restore terminal to original state."""
        ...

    def read_char(self) -> str:
        """Read a single character from terminal without processing."""
        ...

    def read_key(self, timeout: float | None = None) -> str:
        """Read a key input with timeout, returning normalized key name."""
        ...

    def has_input(self) -> bool:
        """Check if input is available without blocking."""
        ...


# Standard key name constants
class Keys:
    """Standard key name constants."""

    # Arrow keys
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    # Navigation keys
    HOME = "HOME"
    END = "END"
    PAGE_UP = "PAGE_UP"
    PAGE_DOWN = "PAGE_DOWN"
    INSERT = "INSERT"
    DELETE = "DELETE"

    # Control keys
    ENTER = "\r"
    TAB = "\t"
    BACKSPACE = "\x08"
    ESCAPE = "\x1b"
    SPACE = " "

    # Function keys
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"
    F7 = "F7"
    F8 = "F8"
    F9 = "F9"
    F10 = "F10"
    F11 = "F11"
    F12 = "F12"

    # Ctrl combinations (keeping common ones)
    CTRL_C = "\x03"
    CTRL_D = "\x04"
    CTRL_Z = "\x1a"


# Escape sequence mappings for different terminal modes
NORMAL_CURSOR_SEQUENCES = {
    "\x1b[A": Keys.UP,
    "\x1b[B": Keys.DOWN,
    "\x1b[C": Keys.RIGHT,
    "\x1b[D": Keys.LEFT,
    "\x1b[H": Keys.HOME,
    "\x1b[F": Keys.END,
    "\x1b[5~": Keys.PAGE_UP,
    "\x1b[6~": Keys.PAGE_DOWN,
    "\x1b[2~": Keys.INSERT,
    "\x1b[3~": Keys.DELETE,
}

APPLICATION_CURSOR_SEQUENCES = {
    "\x1bOA": Keys.UP,
    "\x1bOB": Keys.DOWN,
    "\x1bOC": Keys.RIGHT,
    "\x1bOD": Keys.LEFT,
    "\x1bOH": Keys.HOME,
    "\x1bOF": Keys.END,
}

# Function key sequences
FUNCTION_KEY_SEQUENCES = {
    "\x1bOP": Keys.F1,
    "\x1bOQ": Keys.F2,
    "\x1bOR": Keys.F3,
    "\x1bOS": Keys.F4,
    "\x1b[15~": Keys.F5,
    "\x1b[17~": Keys.F6,
    "\x1b[18~": Keys.F7,
    "\x1b[19~": Keys.F8,
    "\x1b[20~": Keys.F9,
    "\x1b[21~": Keys.F10,
    "\x1b[23~": Keys.F11,
    "\x1b[24~": Keys.F12,
}

# Combined mapping of all standard escape sequences
ALL_ESCAPE_SEQUENCES = {
    **NORMAL_CURSOR_SEQUENCES,
    **APPLICATION_CURSOR_SEQUENCES,
    **FUNCTION_KEY_SEQUENCES,
}

# Bracketed paste mode sequences
BRACKETED_PASTE_START = "\x1b[200~"
BRACKETED_PASTE_END = "\x1b[201~"

# Terminal control sequences
TERMINAL_CONTROL_SEQUENCES = {
    "disable_bracketed_paste": "\x1b[?2004l",
    "enable_bracketed_paste": "\x1b[?2004h",
    "normal_cursor_mode": "\x1b[?1l",
    "application_cursor_mode": "\x1b[?1h",
}
