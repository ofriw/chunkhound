"""Utilities for OpenAI API endpoint detection."""


def is_official_openai_endpoint(base_url: str | None) -> bool:
    """
    Determine if a base URL points to the official OpenAI API.

    Args:
        base_url: The base URL to check, or None for default OpenAI endpoint

    Returns:
        True if this is an official OpenAI endpoint requiring API key authentication
    """
    if not base_url:
        # No base_url means default OpenAI endpoint
        return True

    # Check if URL starts with official OpenAI domain
    return base_url.startswith("https://api.openai.com") and (
        base_url == "https://api.openai.com"
        or base_url.startswith("https://api.openai.com/")
    )
