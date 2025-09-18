"""Custom exceptions for terminal input."""

from typing import Any


class TerminalError(Exception):
    """Base exception for all terminal input errors.

    This is the root exception class that all other terminal exceptions
    inherit from. It provides common functionality for error handling,
    context tracking, and debugging.
    """

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        """Initialize terminal error.

        Args:
            message: Human-readable error description
            context: Optional dictionary with error context
            cause: Optional underlying exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.cause = cause

    def __str__(self) -> str:
        """Return formatted error message with context."""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (context: {context_str})"
        return self.message

    def add_context(self, key: str, value: Any) -> "TerminalError":
        """Add context information to the error."""
        self.context[key] = value
        return self


class TerminalSetupError(TerminalError):
    """Raised when terminal setup or initialization fails.

    This exception is used when the terminal cannot be configured
    for raw input mode, or when platform-specific setup fails.
    """

    def __init__(
        self,
        operation: str,
        platform: str | None = None,
        reason: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        """Initialize terminal setup error.

        Args:
            operation: Setup operation that failed (e.g., "enter_raw_mode", "disable_echo")
            platform: Platform where error occurred (e.g., "unix", "windows")
            reason: Description of what went wrong
            context: Optional additional context
        """
        parts = []
        if platform:
            parts.append(f"platform={platform}")
        if operation:
            parts.append(f"operation={operation}")

        prefix = (
            f"Terminal setup error ({', '.join(parts)})"
            if parts
            else "Terminal setup error"
        )
        message = f"{prefix}: {reason}" if reason else prefix

        super().__init__(message, context)
        self.operation = operation
        self.platform = platform
        self.reason = reason


class TerminalInputTimeout(TerminalError):
    """Raised when input operation times out.

    This exception is used when no input is received within the
    specified timeout period.
    """

    def __init__(
        self,
        timeout: float,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        """Initialize input timeout error.

        Args:
            timeout: Timeout value in seconds
            operation: Input operation that timed out (e.g., "read_key", "read_char")
            context: Optional additional context
        """
        if operation:
            message = f"Input timeout after {timeout}s during {operation}"
        else:
            message = f"Input timeout after {timeout}s"

        super().__init__(message, context)
        self.timeout = timeout
        self.operation = operation


class TerminalUnsupportedPlatform(TerminalError):
    """Raised when terminal operations are not supported on current platform.

    This exception is used when the current platform doesn't support
    the required terminal operations.
    """

    def __init__(
        self,
        platform: str,
        operation: str | None = None,
        supported_platforms: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ):
        """Initialize unsupported platform error.

        Args:
            platform: Current platform that's not supported
            operation: Operation that's not supported
            supported_platforms: List of supported platforms
            context: Optional additional context
        """
        message = f"Platform '{platform}' not supported"
        if operation:
            message += f" for operation '{operation}'"
        if supported_platforms:
            message += f" (supported: {', '.join(supported_platforms)})"

        super().__init__(message, context)
        self.platform = platform
        self.operation = operation
        self.supported_platforms = supported_platforms or []


class TerminalConfigurationError(TerminalError):
    """Raised when terminal configuration is invalid.

    This exception is used when terminal configuration parameters
    are invalid or incompatible.
    """

    def __init__(
        self,
        config_key: str | None = None,
        config_value: Any | None = None,
        reason: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        """Initialize configuration error.

        Args:
            config_key: Configuration key that caused the error
            config_value: Invalid configuration value
            reason: Description of what went wrong
            context: Optional additional context
        """
        if config_key:
            message = f"Terminal configuration error for '{config_key}': {reason}"
        else:
            message = (
                f"Terminal configuration error: {reason}"
                if reason
                else "Terminal configuration error"
            )

        super().__init__(message, context)
        self.config_key = config_key
        self.config_value = config_value
        self.reason = reason
