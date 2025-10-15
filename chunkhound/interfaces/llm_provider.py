"""LLM Provider Interface for ChunkHound deep research."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Response from LLM completion."""

    content: str
    tokens_used: int
    model: str
    finish_reason: str | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'anthropic')."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier."""
        ...

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_completion_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Generate a completion for the given prompt.

        Args:
            prompt: User prompt
            system: Optional system message
            max_completion_tokens: Maximum completion tokens to generate

        Returns:
            LLMResponse with content and metadata
        """
        ...

    @abstractmethod
    async def batch_complete(
        self,
        prompts: list[str],
        system: str | None = None,
        max_completion_tokens: int = 4096,
    ) -> list[LLMResponse]:
        """
        Generate completions for multiple prompts concurrently.

        Args:
            prompts: List of user prompts
            system: Optional system message (same for all)
            max_completion_tokens: Maximum completion tokens to generate per completion

        Returns:
            List of LLMResponse objects
        """
        ...

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check.

        Returns:
            Health status dictionary
        """
        ...

    @abstractmethod
    def get_usage_stats(self) -> dict[str, Any]:
        """
        Get usage statistics.

        Returns:
            Usage stats dictionary
        """
        ...
