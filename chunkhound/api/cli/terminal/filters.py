"""Simple escape sequence filtering for terminal input."""

from .core import (
    ALL_ESCAPE_SEQUENCES,
    BRACKETED_PASTE_END,
    BRACKETED_PASTE_START,
    TerminalConfig,
)


class SimpleEscapeFilter:
    """Simple, reliable escape sequence filter without complex state management."""

    def __init__(self, config: TerminalConfig):
        """Initialize simple escape sequence filter.

        Args:
            config: Terminal configuration options
        """
        self.config = config

    def filter_input(self, raw_input: str) -> str:
        """Filter raw input and return processed result.

        Args:
            raw_input: Raw input string from terminal

        Returns:
            Filtered input string
        """
        # Handle bracketed paste sequences if configured
        if self.config.disable_bracketed_paste and raw_input:
            raw_input = self._handle_bracketed_paste(raw_input)

        # Handle escape sequences - direct mapping
        if raw_input in ALL_ESCAPE_SEQUENCES:
            return ALL_ESCAPE_SEQUENCES[raw_input]

        # Return as-is
        return raw_input

    def _handle_bracketed_paste(self, text: str) -> str:
        """Handle bracketed paste mode sequences.

        Args:
            text: Input text that may contain bracketed paste sequences

        Returns:
            Text with bracketed paste sequences removed
        """
        if not text.startswith(BRACKETED_PASTE_START):
            return text

        # Find the end marker
        end_pos = text.find(BRACKETED_PASTE_END)
        if end_pos == -1:
            # No end marker found - return content after start marker
            return text[len(BRACKETED_PASTE_START) :]

        # Extract content between markers
        start_len = len(BRACKETED_PASTE_START)
        return text[start_len:end_pos]


# Keep original name for compatibility
EscapeSequenceFilter = SimpleEscapeFilter
