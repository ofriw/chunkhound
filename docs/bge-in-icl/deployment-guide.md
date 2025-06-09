# BGE-IN-ICL Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying BGE-IN-ICL (Background Generation Enhanced with In-Context Learning) embedding servers and integrating them with ChunkHound for enhanced code understanding.

BGE-IN-ICL provides advanced semantic embeddings with in-context learning capabilities, offering superior code comprehension compared to traditional embedding models.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [BGE-IN-ICL Server Setup](#bge-in-icl-server-setup)
3. [ChunkHound Configuration](#chunkhound-configuration)
4. [Production Deployment](#production-deployment)
5. [Monitoring and Health Checks](#monitoring-and-health-checks)
6. [Performance Optimization](#performance-optimization)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Python**: 3.8 or higher
- **Memory**: Minimum 8GB RAM (16GB+ recommended for production)
- **Storage**: 10GB+ free space for model weights
- **Network**: Stable internet connection for model downloads

### Software Dependencies

```bash
# Core dependencies
pip install torch transformers
pip install fastapi uvicorn
pip install numpy sentence-transformers
```

### ChunkHound Installation

Ensure ChunkHound is installed with BGE-IN-ICL support:

```bash
pip install chunkhound[bge-in-icl]
# OR
git clone https://github.com/your-org/chunkhound.git
cd chunkhound
pip install -e .
```

## BGE-IN-ICL Server Setup

### Option 1: Using Docker (Recommended)

#### 1. Create Docker Configuration

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  bge-in-icl:
    image: baai/bge-in-icl:latest
    ports:
      - "8080:8080"
    environment:
      - MODEL_NAME=BAAI/bge-in-icl
      - PORT=8080
      - WORKERS=1
      - MAX_BATCH_SIZE=100
      - ENABLE_ICL=true
    volumes:
      - ./models:/app/models
    deploy:
      resources:
        limits:
          memory: 16G
        reservations:
          memory: 8G
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
```

#### 2. Start the Server

```bash
# Start BGE-IN-ICL server
docker-compose up -d bge-in-icl

# Verify server is running
curl http://localhost:8080/health
```

### Option 2: Manual Installation

#### 1. Install BGE-IN-ICL Dependencies

```bash
# Create virtual environment
python -m venv bge-icl-env
source bge-icl-env/bin/activate  # On Windows: bge-icl-env\Scripts\activate

# Install BGE-IN-ICL
pip install torch transformers sentence-transformers
pip install fastapi uvicorn
```

#### 2. Create Server Script

Create `bge_icl_server.py`:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModel
import torch
import uvicorn
from typing import List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BGE-IN-ICL Embedding Server")

class EmbeddingRequest(BaseModel):
    input: List[str]
    model: str = "BAAI/bge-in-icl"
    language: Optional[str] = "auto"
    enable_icl: bool = True

class EmbeddingResponse(BaseModel):
    data: List[dict]
    model: str
    usage: dict

class BGEInICLModel:
    def __init__(self, model_name: str = "BAAI/bge-in-icl"):
        logger.info(f"Loading BGE-IN-ICL model: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True)
        self.model.eval()
        logger.info("BGE-IN-ICL model loaded successfully")
    
    def embed(self, texts: List[str], language: str = "auto", enable_icl: bool = True) -> List[List[float]]:
        """Generate embeddings with optional in-context learning."""
        try:
            # Tokenize input texts
            inputs = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=512)
            
            # Generate embeddings
            with torch.no_grad():
                outputs = self.model(**inputs)
                embeddings = outputs.last_hidden_state.mean(dim=1)  # Mean pooling
                
            # Normalize embeddings
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            
            return embeddings.tolist()
        
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")

# Initialize model
model = BGEInICLModel()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": "BAAI/bge-in-icl"}

@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    try:
        embeddings = model.embed(
            texts=request.input,
            language=request.language,
            enable_icl=request.enable_icl
        )
        
        data = [
            {
                "object": "embedding",
                "embedding": emb,
                "index": i
            }
            for i, emb in enumerate(embeddings)
        ]
        
        return EmbeddingResponse(
            data=data,
            model=request.model,
            usage={
                "prompt_tokens": sum(len(text.split()) for text in request.input),
                "total_tokens": sum(len(text.split()) for text in request.input)
            }
        )
    
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

#### 3. Start the Server

```bash
python bge_icl_server.py
```

### Option 3: Using Hugging Face Text Embeddings Inference (TEI)

```bash
# Pull and run TEI with BGE-IN-ICL
docker run --gpus all -p 8080:80 \
  -v $PWD/data:/data \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-in-icl \
  --max-batch-tokens 16384 \
  --port 80
```

## ChunkHound Configuration

### 1. Add BGE-IN-ICL Server

#### Using CLI (Recommended)

```bash
# Add BGE-IN-ICL server with basic configuration
chunkhound config add \
  --name "bge-icl-local" \
  --type "bge-in-icl" \
  --base-url "http://localhost:8080" \
  --model "BAAI/bge-in-icl" \
  --language "auto" \
  --enable-icl \
  --batch-size 32 \
  --timeout 120 \
  --default

# Add BGE-IN-ICL server with language-specific optimization
chunkhound config add \
  --name "bge-icl-python" \
  --type "bge-in-icl" \
  --base-url "http://localhost:8080" \
  --model "BAAI/bge-in-icl" \
  --language "python" \
  --enable-icl \
  --batch-size 16 \
  --timeout 120

# Add BGE-IN-ICL server with ICL disabled (faster processing)
chunkhound config add \
  --name "bge-icl-fast" \
  --type "bge-in-icl" \
  --base-url "http://localhost:8080" \
  --model "BAAI/bge-in-icl" \
  --disable-icl \
  --batch-size 64 \
  --timeout 60
```

#### Using YAML Configuration

Create `chunkhound-config.yaml`:

```yaml
servers:
  bge-icl-local:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 32
    timeout: 120
    health_check_interval: 300
    metadata:
      language: auto
      enable_icl: true
    
  bge-icl-python:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    batch_size: 16
    timeout: 120
    metadata:
      language: python
      enable_icl: true
    
  bge-icl-production:
    type: bge-in-icl
    base_url: http://bge-icl-prod:8080
    model: BAAI/bge-in-icl
    api_key: ${BGE_ICL_API_KEY}
    batch_size: 50
    timeout: 180
    health_check_interval: 60
    metadata:
      language: auto
      enable_icl: true

default_server: bge-icl-local
```

Load configuration:

```bash
chunkhound config load chunkhound-config.yaml
```

### 2. Verify Configuration

```bash
# List configured servers
chunkhound config list

# Test server health
chunkhound config health bge-icl-local

# Test embeddings
chunkhound config test bge-icl-local
```

### 3. Use BGE-IN-ICL for Indexing

```bash
# Index with BGE-IN-ICL provider
chunkhound run /path/to/code --provider bge-in-icl

# Index with specific language optimization
chunkhound run /path/to/python/code --provider bge-icl-python

# Index with fast processing (no ICL)
chunkhound run /path/to/code --provider bge-icl-fast
```

## Production Deployment

### 1. Environment Configuration

Create `.env` file:

```bash
# BGE-IN-ICL Configuration
BGE_ICL_BASE_URL=https://bge-icl.your-domain.com
BGE_ICL_API_KEY=your-api-key-here
BGE_ICL_MODEL=BAAI/bge-in-icl
BGE_ICL_BATCH_SIZE=50
BGE_ICL_TIMEOUT=180
BGE_ICL_LANGUAGE=auto
BGE_ICL_ENABLE_ICL=true

# Performance Optimization
BGE_ICL_ADAPTIVE_BATCHING=true
BGE_ICL_MIN_BATCH_SIZE=10
BGE_ICL_MAX_BATCH_SIZE=100
BGE_ICL_CONTEXT_CACHE_SIZE=200
BGE_ICL_SIMILARITY_THRESHOLD=0.8

# Monitoring
BGE_ICL_HEALTH_CHECK_INTERVAL=60
BGE_ICL_LOG_LEVEL=INFO
```

### 2. Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'
services:
  bge-in-icl:
    image: baai/bge-in-icl:latest
    ports:
      - "8080:8080"
    environment:
      - MODEL_NAME=${BGE_ICL_MODEL}
      - PORT=8080
      - WORKERS=4
      - MAX_BATCH_SIZE=${BGE_ICL_MAX_BATCH_SIZE}
      - ENABLE_ICL=${BGE_ICL_ENABLE_ICL}
      - LOG_LEVEL=${BGE_ICL_LOG_LEVEL}
    volumes:
      - models_cache:/app/models
      - logs:/app/logs
    deploy:
      resources:
        limits:
          memory: 32G
          cpus: '8'
        reservations:
          memory: 16G
          cpus: '4'
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s
    networks:
      - bge-icl-network

  chunkhound:
    image: your-org/chunkhound:latest
    depends_on:
      - bge-in-icl
    environment:
      - BGE_ICL_BASE_URL=http://bge-in-icl:8080
      - BGE_ICL_BATCH_SIZE=${BGE_ICL_BATCH_SIZE}
      - BGE_ICL_TIMEOUT=${BGE_ICL_TIMEOUT}
    volumes:
      - code_repos:/app/repos
      - chunkhound_data:/app/data
    networks:
      - bge-icl-network

volumes:
  models_cache:
  logs:
  code_repos:
  chunkhound_data:

networks:
  bge-icl-network:
    driver: bridge
```

### 3. Kubernetes Deployment

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bge-in-icl
  labels:
    app: bge-in-icl
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bge-in-icl
  template:
    metadata:
      labels:
        app: bge-in-icl
    spec:
      containers:
      - name: bge-in-icl
        image: baai/bge-in-icl:latest
        ports:
        - containerPort: 8080
        env:
        - name: MODEL_NAME
          value: "BAAI/bge-in-icl"
        - name: WORKERS
          value: "2"
        - name: MAX_BATCH_SIZE
          value: "100"
        resources:
          requests:
            memory: "8Gi"
            cpu: "2"
          limits:
            memory: "16Gi"
            cpu: "4"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 120
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        volumeMounts:
        - name: models-cache
          mountPath: /app/models
      volumes:
      - name: models-cache
        persistentVolumeClaim:
          claimName: bge-icl-models-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: bge-in-icl-service
spec:
  selector:
    app: bge-in-icl
  ports:
  - protocol: TCP
    port: 8080
    targetPort: 8080
  type: ClusterIP

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: bge-icl-models-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
```

## Monitoring and Health Checks

### 1. Health Check Endpoints

BGE-IN-ICL servers expose health check endpoints:

```bash
# Basic health check
curl http://localhost:8080/health

# Detailed status (if supported)
curl http://localhost:8080/v1/models
```

### 2. ChunkHound Health Monitoring

```bash
# Check server health through ChunkHound
chunkhound config health --all

# Continuous monitoring
chunkhound config health --watch --interval 30
```

### 3. Performance Monitoring

Create monitoring script `monitor_bge_icl.py`:

```python
#!/usr/bin/env python3
import asyncio
import time
from chunkhound.embeddings import create_bge_in_icl_provider

async def monitor_performance():
    provider = create_bge_in_icl_provider(
        base_url="http://localhost:8080",
        adaptive_batching=True
    )
    
    # Test texts
    test_texts = [
        "def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
        "class DataProcessor: def __init__(self): self.data = []",
        "async function fetchData() { return await api.get('/data'); }"
    ]
    
    while True:
        start_time = time.time()
        try:
            # Generate embeddings
            embeddings = await provider.embed(test_texts)
            
            # Get performance metrics
            metrics = provider.get_performance_metrics()
            
            elapsed = time.time() - start_time
            
            print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Response time: {elapsed:.2f}s")
            print(f"Embeddings generated: {len(embeddings)}")
            print(f"Cache hit rate: {metrics.get('cache_hit_rate', 0):.1%}")
            print(f"Current batch size: {metrics.get('current_batch_size', 'N/A')}")
            print(f"Average response time: {metrics.get('avg_response_time', 0):.2f}s")
            print("-" * 50)
            
        except Exception as e:
            print(f"Error: {e}")
        
        await asyncio.sleep(60)  # Monitor every minute

if __name__ == "__main__":
    asyncio.run(monitor_performance())
```

## Performance Optimization

### 1. Batch Size Optimization

```python
# Configuration for different workloads
workload_configs = {
    "interactive": {
        "batch_size": 8,
        "adaptive_batching": True,
        "min_batch_size": 1,
        "max_batch_size": 16
    },
    "bulk_processing": {
        "batch_size": 64,
        "adaptive_batching": True,
        "min_batch_size": 32,
        "max_batch_size": 128
    },
    "real_time": {
        "batch_size": 4,
        "adaptive_batching": False,
        "timeout": 30
    }
}
```

### 2. Language-Specific Optimization

```bash
# Add language-specific servers for better performance
chunkhound config add --name "bge-icl-python" --type "bge-in-icl" --base-url "http://localhost:8080" --language "python" --batch-size 16
chunkhound config add --name "bge-icl-typescript" --type "bge-in-icl" --base-url "http://localhost:8080" --language "typescript" --batch-size 24
chunkhound config add --name "bge-icl-java" --type "bge-in-icl" --base-url "http://localhost:8080" --language "java" --batch-size 20
```

### 3. Caching Configuration

```yaml
# Optimal caching settings
servers:
  bge-icl-optimized:
    type: bge-in-icl
    base_url: http://localhost:8080
    model: BAAI/bge-in-icl
    metadata:
      context_cache_size: 200
      similarity_threshold: 0.8
      adaptive_batching: true
      min_batch_size: 10
      max_batch_size: 100
```

## Troubleshooting

### Common Issues

#### 1. Server Connection Issues

**Problem**: `Connection refused` or `Timeout errors`

**Solutions**:
```bash
# Check server status
curl -v http://localhost:8080/health

# Check Docker container logs
docker logs bge-in-icl

# Verify port accessibility
netstat -tulpn | grep 8080

# Test with increased timeout
chunkhound config add --name test --type bge-in-icl --base-url http://localhost:8080 --timeout 300
```

#### 2. Memory Issues

**Problem**: `Out of memory` errors or slow performance

**Solutions**:
- Reduce batch size: `--batch-size 16`
- Disable ICL for faster processing: `--disable-icl`
- Increase Docker memory limits
- Use GPU acceleration if available

#### 3. Model Loading Issues

**Problem**: `Model not found` or `Loading errors`

**Solutions**:
```bash
# Pre-download model
python -c "from transformers import AutoModel; AutoModel.from_pretrained('BAAI/bge-in-icl')"

# Check disk space
df -h

# Verify model files
ls -la ~/.cache/huggingface/transformers/
```

#### 4. Performance Issues

**Problem**: Slow embedding generation

**Solutions**:
- Enable adaptive batching
- Optimize language settings
- Check server resources
- Monitor cache hit rates

### Debug Mode

Enable debug logging:

```bash
export CHUNKHOUND_LOG_LEVEL=DEBUG
export BGE_ICL_LOG_LEVEL=DEBUG
chunkhound run /path/to/code --provider bge-in-icl
```

### Performance Profiling

```python
import time
import asyncio
from chunkhound.embeddings import create_bge_in_icl_provider

async def profile_provider():
    provider = create_bge_in_icl_provider(base_url="http://localhost:8080")
    
    test_sizes = [1, 5, 10, 25, 50, 100]
    test_text = "def example_function(): return 'hello world'"
    
    for size in test_sizes:
        texts = [test_text] * size
        
        start_time = time.time()
        embeddings = await provider.embed(texts)
        elapsed = time.time() - start_time
        
        print(f"Batch size {size}: {elapsed:.2f}s ({size/elapsed:.1f} texts/sec)")

asyncio.run(profile_provider())
```

## Next Steps

1. **Configure Monitoring**: Set up Prometheus/Grafana dashboards
2. **Performance Testing**: Run benchmarks with your specific workload
3. **Production Deployment**: Deploy to your production environment
4. **Integration Testing**: Validate with real codebases
5. **Optimization**: Fine-tune configuration based on usage patterns

For advanced configuration and monitoring setup, see:
- [BGE-IN-ICL Configuration Reference](./configuration-reference.md)
- [Performance Tuning Guide](./performance-tuning.md)
- [Monitoring Setup](./monitoring-setup.md)