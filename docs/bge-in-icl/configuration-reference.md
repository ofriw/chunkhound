# BGE-IN-ICL Configuration Reference

## Overview

This document provides comprehensive reference for all BGE-IN-ICL configuration options available in ChunkHound. BGE-IN-ICL supports advanced configuration for optimal performance across different deployment scenarios.

## Table of Contents

1. [Basic Configuration](#basic-configuration)
2. [Advanced Settings](#advanced-settings)
3. [Performance Optimization](#performance-optimization)
4. [Environment Variables](#environment-variables)
5. [YAML Configuration](#yaml-configuration)
6. [CLI Options](#cli-options)
7. [Provider Parameters](#provider-parameters)
8. [Best Practices](#best-practices)

## Basic Configuration

### Minimal Configuration

```yaml
servers:
  bge-icl-basic:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
```

### Essential Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | string | - | Must be `bge-in-icl` |
| `base_url` | string | - | BGE-IN-ICL server URL |
| `model` | string | `bge-in-icl` | Model identifier |

## Advanced Settings

### Complete Configuration

```yaml
servers:
  bge-icl-advanced:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    api_key: ${BGE_ICL_API_KEY}
    batch_size: 50
    timeout: 120
    health_check_interval: 300
    metadata:
      # In-Context Learning
      language: auto
      enable_icl: true
      context_cache_size: 100
      similarity_threshold: 0.8
      
      # Adaptive Batching
      adaptive_batching: true
      min_batch_size: 10
      max_batch_size: 100
      
      # Performance Monitoring
      enable_metrics: true
      metrics_window_size: 10
```

### Parameter Reference

#### Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | string | - | Server type, must be `bge-in-icl` |
| `base_url` | string | - | Base URL of BGE-IN-ICL server |
| `model` | string | `bge-in-icl` | Model name for the provider |
| `api_key` | string | null | Optional API key for authentication |
| `batch_size` | integer | 50 | Initial batch size for embeddings |
| `timeout` | integer | 120 | Request timeout in seconds |
| `health_check_interval` | integer | 300 | Health check interval in seconds |

#### In-Context Learning Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `language` | string | `auto` | Programming language for context |
| `enable_icl` | boolean | true | Enable in-context learning features |
| `context_cache_size` | integer | 100 | Size of context cache |
| `similarity_threshold` | float | 0.8 | Minimum similarity for context reuse |

#### Adaptive Batching Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `adaptive_batching` | boolean | true | Enable adaptive batch sizing |
| `min_batch_size` | integer | 10 | Minimum batch size limit |
| `max_batch_size` | integer | 100 | Maximum batch size limit |

#### Performance Monitoring Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_metrics` | boolean | true | Enable performance metrics collection |
| `metrics_window_size` | integer | 10 | Size of performance tracking window |

## Performance Optimization

### Workload-Specific Configurations

#### Interactive Development

```yaml
servers:
  bge-icl-interactive:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 8
    timeout: 60
    metadata:
      adaptive_batching: true
      min_batch_size: 1
      max_batch_size: 16
      language: auto
      enable_icl: true
```

#### Bulk Processing

```yaml
servers:
  bge-icl-bulk:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 64
    timeout: 300
    metadata:
      adaptive_batching: true
      min_batch_size: 32
      max_batch_size: 128
      context_cache_size: 200
      enable_icl: true
```

#### Real-Time Processing

```yaml
servers:
  bge-icl-realtime:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 4
    timeout: 30
    metadata:
      adaptive_batching: false
      enable_icl: false  # Faster without ICL
      language: auto
```

### Language-Specific Optimization

#### Python Optimization

```yaml
servers:
  bge-icl-python:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 16
    metadata:
      language: python
      enable_icl: true
      context_cache_size: 150
      similarity_threshold: 0.85
```

#### TypeScript/JavaScript Optimization

```yaml
servers:
  bge-icl-typescript:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 24
    metadata:
      language: typescript
      enable_icl: true
      context_cache_size: 120
      similarity_threshold: 0.8
```

#### Multi-Language Support

```yaml
servers:
  bge-icl-auto:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 32
    metadata:
      language: auto
      enable_icl: true
      context_cache_size: 200
      similarity_threshold: 0.75
```

## Environment Variables

### Core Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BGE_ICL_BASE_URL` | BGE-IN-ICL server base URL | - |
| `BGE_ICL_API_KEY` | API key for authentication | - |
| `BGE_ICL_MODEL` | Model name | `bge-in-icl` |
| `BGE_ICL_BATCH_SIZE` | Default batch size | 50 |
| `BGE_ICL_TIMEOUT` | Request timeout in seconds | 120 |

### Advanced Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BGE_ICL_LANGUAGE` | Default language setting | `auto` |
| `BGE_ICL_ENABLE_ICL` | Enable ICL by default | `true` |
| `BGE_ICL_CACHE_SIZE` | Context cache size | 100 |
| `BGE_ICL_SIMILARITY_THRESHOLD` | Similarity threshold | 0.8 |
| `BGE_ICL_ADAPTIVE_BATCHING` | Enable adaptive batching | `true` |
| `BGE_ICL_MIN_BATCH_SIZE` | Minimum batch size | 10 |
| `BGE_ICL_MAX_BATCH_SIZE` | Maximum batch size | 100 |

### Environment Configuration Example

```bash
# Production environment variables
export BGE_ICL_BASE_URL="https://bge-icl.company.com"
export BGE_ICL_API_KEY="your-api-key-here"
export BGE_ICL_MODEL="BAAI/bge-in-icl"
export BGE_ICL_BATCH_SIZE="50"
export BGE_ICL_TIMEOUT="180"
export BGE_ICL_LANGUAGE="auto"
export BGE_ICL_ENABLE_ICL="true"
export BGE_ICL_ADAPTIVE_BATCHING="true"
export BGE_ICL_CACHE_SIZE="200"
```

## YAML Configuration

### Complete YAML Example

```yaml
# chunkhound-bge-icl.yaml
version: "1.0"

servers:
  # Production BGE-IN-ICL server
  bge-icl-prod:
    type: bge-in-icl
    base_url: https://bge-icl.company.com
    model: BAAI/bge-in-icl
    api_key: ${BGE_ICL_API_KEY}
    batch_size: 50
    timeout: 180
    health_check_interval: 60
    metadata:
      language: auto
      enable_icl: true
      context_cache_size: 200
      similarity_threshold: 0.8
      adaptive_batching: true
      min_batch_size: 10
      max_batch_size: 100
      enable_metrics: true
      metrics_window_size: 20

  # Development server
  bge-icl-dev:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 16
    timeout: 120
    metadata:
      language: auto
      enable_icl: true
      adaptive_batching: true
      min_batch_size: 4
      max_batch_size: 32

  # Language-specific servers
  bge-icl-python:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 20
    metadata:
      language: python
      enable_icl: true
      context_cache_size: 150

  bge-icl-typescript:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 24
    metadata:
      language: typescript
      enable_icl: true
      context_cache_size: 120

  # Fast processing (no ICL)
  bge-icl-fast:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 64
    timeout: 60
    metadata:
      enable_icl: false
      adaptive_batching: true
      min_batch_size: 32
      max_batch_size: 128

default_server: bge-icl-prod

# Global settings
settings:
  log_level: INFO
  health_check_on_startup: true
  retry_failed_requests: true
  retry_count: 3
  retry_delay: 5
```

### YAML Validation

ChunkHound validates YAML configuration on load:

```bash
# Validate configuration
chunkhound config validate chunkhound-bge-icl.yaml

# Load with validation
chunkhound config load chunkhound-bge-icl.yaml --validate
```

## CLI Options

### Adding BGE-IN-ICL Servers via CLI

#### Basic Addition

```bash
chunkhound config add \
  --name "bge-icl-server" \
  --type "bge-in-icl" \
  --base-url "http://localhost:8080"
```

#### Complete Configuration

```bash
chunkhound config add \
  --name "bge-icl-complete" \
  --type "bge-in-icl" \
  --base-url "http://localhost:8080" \
  --model "BAAI/bge-in-icl" \
  --api-key "your-api-key" \
  --batch-size 50 \
  --timeout 120 \
  --language "auto" \
  --enable-icl \
  --default
```

#### Language-Specific Configuration

```bash
# Python-optimized server
chunkhound config add \
  --name "bge-icl-python" \
  --type "bge-in-icl" \
  --base-url "http://localhost:8080" \
  --language "python" \
  --enable-icl \
  --batch-size 16

# TypeScript-optimized server
chunkhound config add \
  --name "bge-icl-ts" \
  --type "bge-in-icl" \
  --base-url "http://localhost:8080" \
  --language "typescript" \
  --enable-icl \
  --batch-size 24

# Fast processing without ICL
chunkhound config add \
  --name "bge-icl-fast" \
  --type "bge-in-icl" \
  --base-url "http://localhost:8080" \
  --disable-icl \
  --batch-size 64
```

### CLI Parameter Reference

| CLI Option | Type | Description |
|------------|------|-------------|
| `--name` | string | Server name (required) |
| `--type` | string | Must be `bge-in-icl` |
| `--base-url` | string | Server base URL (required) |
| `--model` | string | Model name |
| `--api-key` | string | API key for authentication |
| `--batch-size` | integer | Batch size for embeddings |
| `--timeout` | integer | Request timeout in seconds |
| `--language` | string | Programming language |
| `--enable-icl` | flag | Enable in-context learning |
| `--disable-icl` | flag | Disable in-context learning |
| `--default` | flag | Set as default server |

## Provider Parameters

### BGEInICLProvider Constructor

```python
from chunkhound.embeddings import BGEInICLProvider

provider = BGEInICLProvider(
    base_url="http://localhost:8080",
    model="BAAI/bge-in-icl",
    api_key=None,
    batch_size=50,
    timeout=120,
    language="auto",
    enable_icl=True,
    context_cache_size=100,
    adaptive_batching=True,
    min_batch_size=10,
    max_batch_size=100,
    similarity_threshold=0.8
)
```

### Provider Factory Function

```python
from chunkhound.embeddings import create_bge_in_icl_provider

# Basic provider
provider = create_bge_in_icl_provider(
    base_url="http://localhost:8080"
)

# Advanced configuration
provider = create_bge_in_icl_provider(
    base_url="http://localhost:8080",
    model="BAAI/bge-in-icl",
    language="python",
    enable_icl=True,
    adaptive_batching=True,
    context_cache_size=150,
    min_batch_size=8,
    max_batch_size=64
)
```

### Parameter Validation

The provider validates parameters on initialization:

- `base_url`: Must be valid URL
- `batch_size`: Must be positive integer
- `timeout`: Must be positive integer
- `language`: Must be supported language or "auto"
- `cache_size`: Must be positive integer
- `similarity_threshold`: Must be between 0.0 and 1.0

## Best Practices

### Performance Configuration

1. **Start with defaults** and adjust based on performance monitoring
2. **Enable adaptive batching** for varying workloads
3. **Use language-specific settings** for better context optimization
4. **Monitor cache hit rates** and adjust cache size accordingly
5. **Set appropriate timeouts** based on server capacity

### Language Settings

```yaml
# Recommended language settings
languages:
  python:
    batch_size: 16-24
    cache_size: 150
    similarity_threshold: 0.85
    
  typescript:
    batch_size: 20-28
    cache_size: 120
    similarity_threshold: 0.8
    
  java:
    batch_size: 18-26
    cache_size: 130
    similarity_threshold: 0.82
    
  csharp:
    batch_size: 20-28
    cache_size: 125
    similarity_threshold: 0.8
    
  auto:
    batch_size: 24-32
    cache_size: 200
    similarity_threshold: 0.75
```

### Resource Management

1. **Memory**: Allocate sufficient memory for model and cache
2. **CPU**: Use multiple workers for concurrent processing
3. **Network**: Configure appropriate timeouts for network conditions
4. **Storage**: Ensure adequate space for model weights and cache

### Security Configuration

```yaml
servers:
  bge-icl-secure:
    type: bge-in-icl
    base_url: https://secure-bge-icl.company.com
    model: BAAI/bge-in-icl
    api_key: ${BGE_ICL_API_KEY}  # Use environment variable
    timeout: 120
    # Additional security settings
    verify_ssl: true
    client_cert: /path/to/client.crt
    client_key: /path/to/client.key
```

### Monitoring Configuration

```yaml
servers:
  bge-icl-monitored:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    health_check_interval: 60
    metadata:
      enable_metrics: true
      metrics_window_size: 20
      log_performance: true
      alert_on_errors: true
```

### Development vs Production

#### Development Configuration

```yaml
servers:
  bge-icl-dev:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 8
    timeout: 60
    metadata:
      enable_icl: true
      adaptive_batching: true
      min_batch_size: 1
      max_batch_size: 16
```

#### Production Configuration

```yaml
servers:
  bge-icl-prod:
    type: bge-in-icl
    base_url: https://bge-icl.company.com
    model: BAAI/bge-in-icl
    api_key: ${BGE_ICL_API_KEY}
    batch_size: 50
    timeout: 180
    health_check_interval: 60
    metadata:
      enable_icl: true
      adaptive_batching: true
      min_batch_size: 20
      max_batch_size: 100
      context_cache_size: 200
      enable_metrics: true
```

## Configuration Migration

### From Basic to Advanced

```bash
# Start with basic configuration
chunkhound config add --name basic --type bge-in-icl --base-url http://localhost:8080

# Upgrade to advanced
chunkhound config update basic \
  --language python \
  --enable-icl \
  --batch-size 24

# Export for YAML
chunkhound config export basic > bge-icl-config.yaml
```

### Configuration Templates

ChunkHound provides configuration templates:

```bash
# Generate template
chunkhound config template bge-in-icl > bge-icl-template.yaml

# Use template
chunkhound config load bge-icl-template.yaml
```

This configuration reference provides comprehensive coverage of all BGE-IN-ICL options available in ChunkHound. For deployment instructions, see the [Deployment Guide](./deployment-guide.md).