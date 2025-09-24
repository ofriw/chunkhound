"""Base provider with common terminal input logic."""

import sys
from abc import ABC, abstractmethod

from ..core import TerminalConfig, TerminalInputProvider
from ..exceptions import TerminalSetupError
from ..filters import SimpleEscapeFilter


class BaseTerminalProvider(ABC):
    """Base class for platform-specific terminal input providers.

    This class provides common functionality shared across platforms,
    including filtering, timeout handling, and state management.
    """

    def __init__(self, config: TerminalConfig):
        """Initialize base provider.

        Args:
            config: Terminal configuration
        """
        self.config = config
        self.filter = SimpleEscapeFilter(config)
        self._is_setup = False
        self._original_state = None

    def setup(self) -> None:
        """Initialize terminal for raw input mode."""
        if self._is_setup:
            return

        try:
            self._original_state = self._save_terminal_state()
            self._enter_raw_mode()
            self._configure_terminal()
            self._is_setup = True
        except Exception as e:
            raise TerminalSetupError(
                operation="setup", platform=self._get_platform_name(), reason=str(e)
            ) from e

    def cleanup(self) -> None:
        """Restore terminal to original state."""
        if not self._is_setup:
            return

        try:
            if self._original_state is not None:
                self._restore_terminal_state(self._original_state)
            self._is_setup = False
            self._original_state = None
        except Exception:
            # Best effort cleanup - don't raise exceptions
            pass

    def read_key(self, timeout: float | None = None) -> str:
        """Read a key input with timeout, returning normalized key name.

        Args:
            timeout: Timeout in seconds, or None for no timeout

        Returns:
            Normalized key name

        Raises:
            TerminalInputTimeout: If timeout occurs
            TerminalSetupError: If terminal is not set up
        """
        if not self._is_setup:
            raise TerminalSetupError(
                operation="read_key",
                platform=self._get_platform_name(),
                reason="Terminal not initialized - call setup() first",
            )

        # Use the Unix provider's proper escape handling if available
        if hasattr(self, "_read_key_with_escape_handling"):
            raw_input = self._read_key_with_escape_handling()
        else:
            # Fallback to simple read for other providers
            raw_input = self._read_raw_char()

        if raw_input:
            # Process through simple filter
            return self.filter.filter_input(raw_input)

        # If no input, return empty string (shouldn't happen in normal operation)
        return ""

    def read_char(self) -> str:
        """Read a single character from terminal without processing.

        Returns:
            Raw character
        """
        if not self._is_setup:
            raise TerminalSetupError(
                operation="read_char",
                platform=self._get_platform_name(),
                reason="Terminal not initialized - call setup() first",
            )

        return self._read_raw_char()

    def has_input(self, timeout: float | None = None) -> bool:
        """Check if input is available without blocking.

        Args:
            timeout: Maximum time to wait for input

        Returns:
            True if input is available
        """
        if not self._is_setup:
            return False

        return self._has_raw_input(timeout)

    def __enter__(self):
        """Context manager entry."""
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()

    # Abstract methods that must be implemented by platform-specific providers

    @abstractmethod
    def _get_platform_name(self) -> str:
        """Get the platform name for this provider.

        Returns:
            Platform name (e.g., "unix", "windows")
        """
        pass

    @abstractmethod
    def _save_terminal_state(self):
        """Save current terminal state for later restoration.

        Returns:
            Opaque state object
        """
        pass

    @abstractmethod
    def _restore_terminal_state(self, state) -> None:
        """Restore terminal to saved state.

        Args:
            state: State object from _save_terminal_state()
        """
        pass

    @abstractmethod
    def _enter_raw_mode(self) -> None:
        """Put terminal into raw input mode."""
        pass

    @abstractmethod
    def _configure_terminal(self) -> None:
        """Apply platform-specific terminal configuration."""
        pass

    @abstractmethod
    def _read_raw_char(self) -> str:
        """Read a single raw character from terminal.

        Returns:
            Single character, may be empty string if no input
        """
        pass

    @abstractmethod
    def _has_raw_input(self, timeout: float | None = None) -> bool:
        """Check if raw input is available.

        Args:
            timeout: Maximum time to wait

        Returns:
            True if input is available
        """
        pass


def create_provider(config: TerminalConfig | None = None) -> TerminalInputProvider:
    """Create appropriate terminal provider for current platform.

    Args:
        config: Terminal configuration, uses defaults if None

    Returns:
        Platform-specific terminal provider

    Raises:
        TerminalUnsupportedPlatform: If platform is not supported
    """
    if config is None:
        config = TerminalConfig()

    platform = sys.platform.lower()

    if platform.startswith("win"):
        from .windows import WindowsTerminalProvider

        return WindowsTerminalProvider(config)
    elif platform in ("linux", "darwin") or platform.startswith("freebsd"):
        from .unix import UnixTerminalProvider

        return UnixTerminalProvider(config)
    else:
        from ..exceptions import TerminalUnsupportedPlatform

        raise TerminalUnsupportedPlatform(
            platform=platform,
            operation="create_provider",
            supported_platforms=["windows", "linux", "darwin", "freebsd"],
        )
