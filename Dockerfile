# ChunkHound Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY pyproject.toml README.md ./
COPY chunkhound/ ./chunkhound/

# Install ChunkHound
RUN pip install --no-cache-dir .

# Create cache directory
RUN mkdir -p /root/.cache/chunkhound

# Expose API port
EXPOSE 7474

# Set default command
CMD ["chunkhound", "server", "--host", "0.0.0.0", "--port", "7474"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7474/health || exit 1

# Labels
LABEL maintainer="ChunkHound Team"
LABEL description="Local-first semantic code search with vector and regex capabilities"
LABEL version="0.1.0"