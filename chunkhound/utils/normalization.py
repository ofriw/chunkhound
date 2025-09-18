"""Content normalization utilities for consistent processing across ChunkHound."""


def normalize_content(content: str) -> str:
    """Normalize content for consistent processing and comparison.

    This function ensures consistent normalization across all components that
    process or compare content, preventing hash mismatches that could cause
    unnecessary embedding regeneration.

    Normalization steps:
    1. Convert all line endings (CRLF, LF) to Unix format (\n)
    2. Strip leading and trailing whitespace

    Args:
        content: Raw content string to normalize

    Returns:
        Normalized content string
    """
    # Normalize line endings: Windows CRLF (\r\n) and Mac CR (\r) to Unix LF (\n)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")

    # Strip leading and trailing whitespace for consistent comparison
    normalized = normalized.strip()

    return normalized
