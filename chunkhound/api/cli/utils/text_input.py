"""Text input state management for interactive CLI components."""

from rich.text import Text


class TextInputState:
    """Manages text input state including cursor position and editing operations."""

    def __init__(self, initial_text: str = ""):
        """Initialize text input state.

        Args:
            initial_text: Initial text content
        """
        self.text = initial_text
        self.cursor_pos = len(initial_text)
        self.validation_error: str | None = None

    def move_cursor(self, direction: str) -> None:
        """Move cursor based on direction.

        Args:
            direction: One of "LEFT", "RIGHT", "HOME", "END"
        """
        if direction == "LEFT":
            self.cursor_pos = max(0, self.cursor_pos - 1)
        elif direction == "RIGHT":
            self.cursor_pos = min(len(self.text), self.cursor_pos + 1)
        elif direction == "HOME":
            self.cursor_pos = 0
        elif direction == "END":
            self.cursor_pos = len(self.text)

    def insert_char(self, char: str) -> None:
        """Insert character at current cursor position.

        Args:
            char: Character to insert
        """
        self.text = self.text[: self.cursor_pos] + char + self.text[self.cursor_pos :]
        self.cursor_pos += 1
        self.validation_error = None  # Clear validation error when text changes

    def delete_char(self, direction: str) -> None:
        """Delete character at or before cursor.

        Args:
            direction: "BACKSPACE" or "DELETE"
        """
        if direction == "BACKSPACE" and self.cursor_pos > 0:
            self.text = self.text[: self.cursor_pos - 1] + self.text[self.cursor_pos :]
            self.cursor_pos -= 1
            self.validation_error = None
        elif direction == "DELETE" and self.cursor_pos < len(self.text):
            self.text = self.text[: self.cursor_pos] + self.text[self.cursor_pos + 1 :]
            self.validation_error = None

    def get_display_text(self, password: bool = False) -> Text:
        """Generate Rich Text object with cursor highlighting.

        Args:
            password: Whether to mask text with asterisks

        Returns:
            Rich Text object with cursor and content
        """
        display_text = Text()

        # Handle password masking
        if password and self.text:
            masked_text = "*" * len(self.text)
        else:
            masked_text = self.text

        # Cursor positioning logic
        if not self.text:
            # Empty text - show cursor block
            display_text.append(" ", style="reverse")
        elif self.cursor_pos == 0:
            # Cursor at beginning
            display_text.append(masked_text[0], style="reverse")
            if len(masked_text) > 1:
                display_text.append(masked_text[1:])
        elif self.cursor_pos >= len(self.text):
            # Cursor at or past end
            display_text.append(masked_text)
            display_text.append(" ", style="reverse")
        else:
            # Cursor in middle
            display_text.append(masked_text[: self.cursor_pos])
            display_text.append(masked_text[self.cursor_pos], style="reverse")
            if self.cursor_pos + 1 < len(masked_text):
                display_text.append(masked_text[self.cursor_pos + 1 :])

        return display_text


def create_text_input_display(
    question: str, state: TextInputState, password: bool = False
) -> Text:
    """Create complete text input display with question, input, and hints.

    Args:
        question: The question/prompt text
        state: Text input state
        password: Whether to mask input

    Returns:
        Complete Rich Text display
    """
    display = Text()

    # Add question
    display.append(f"\n{question}\n", style="bold")

    # Add input text with cursor
    display.append(state.get_display_text(password))

    # Add navigation hints
    display.append("\n", style="")
    display.append(
        "(Arrow keys to navigate, Enter to confirm, ESC to cancel)", style="dim"
    )

    # Add validation error if present
    if state.validation_error:
        display.append("\n", style="")
        display.append(f"❌ {state.validation_error}", style="red bold")

    return display
