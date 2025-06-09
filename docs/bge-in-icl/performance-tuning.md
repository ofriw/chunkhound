# BGE-IN-ICL Performance Tuning Guide

## Overview

This guide provides comprehensive performance tuning strategies for BGE-IN-ICL (Background Generation Enhanced with In-Context Learning) deployments. It covers optimization techniques, benchmarking methodologies, and troubleshooting performance issues.

## Table of Contents

1. [Performance Fundamentals](#performance-fundamentals)
2. [Benchmarking and Measurement](#benchmarking-and-measurement)
3. [Optimization Strategies](#optimization-strategies)
4. [Hardware Configuration](#hardware-configuration)
5. [Software Optimization](#software-optimization)
6. [Network Optimization](#network-optimization)
7. [Monitoring and Alerting](#monitoring-and-alerting)
8. [Troubleshooting](#troubleshooting)

## Performance Fundamentals

### Key Performance Metrics

#### Throughput Metrics
- **Embeddings per second**: Total embedding generation rate
- **Texts per second**: Rate of text processing
- **Batch throughput**: Efficiency of batch processing
- **Request rate**: Number of API requests processed per second

#### Latency Metrics
- **Response time**: End-to-end request processing time
- **Context preparation time**: Time spent on ICL context generation
- **Model inference time**: Time for actual embedding generation
- **Queue wait time**: Time requests spend waiting for processing

#### Resource Utilization
- **CPU usage**: Processor utilization during embedding generation
- **Memory usage**: RAM consumption for models and caching
- **GPU utilization**: Graphics processor usage (if applicable)
- **Network bandwidth**: Data transfer rates

#### Quality Metrics
- **Cache hit rate**: Percentage of context cache hits
- **Context similarity scores**: Quality of ICL example selection
- **Embedding quality**: Semantic accuracy of generated embeddings

### Performance Targets

#### Interactive Workloads
```yaml
targets:
  response_time: < 2 seconds
  throughput: 10-50 embeddings/second
  cache_hit_rate: > 70%
  resource_usage: < 60% CPU
```

#### Batch Processing
```yaml
targets:
  response_time: < 30 seconds
  throughput: 100-500 embeddings/second
  cache_hit_rate: > 80%
  resource_usage: < 90% CPU
```

#### Real-time Processing
```yaml
targets:
  response_time: < 1 second
  throughput: 5-20 embeddings/second
  cache_hit_rate: > 60%
  resource_usage: < 50% CPU
```

## Benchmarking and Measurement

### Comprehensive Benchmarking Script

```python
#!/usr/bin/env python3
"""
BGE-IN-ICL Performance Benchmarking Tool
"""
import asyncio
import time
import statistics
import json
from typing import List, Dict, Any
from chunkhound.embeddings import create_bge_in_icl_provider

class BGEICLBenchmark:
    def __init__(self, base_url: str, configurations: List[Dict[str, Any]]):
        self.base_url = base_url
        self.configurations = configurations
        self.results = []

    async def benchmark_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Benchmark a specific configuration."""
        print(f"Benchmarking configuration: {config['name']}")
        
        provider = create_bge_in_icl_provider(
            base_url=self.base_url,
            **config['params']
        )
        
        # Test datasets
        test_cases = [
            self._generate_test_texts(size) 
            for size in [1, 5, 10, 25, 50, 100]
        ]
        
        results = {
            'configuration': config,
            'test_results': [],
            'performance_metrics': {}
        }
        
        for i, texts in enumerate(test_cases):
            batch_size = len(texts)
            print(f"  Testing batch size: {batch_size}")
            
            # Warm-up run
            await provider.embed(texts[:min(5, len(texts))])
            
            # Actual benchmark
            times = []
            for run in range(5):  # 5 runs per batch size
                start_time = time.time()
                embeddings = await provider.embed(texts)
                elapsed = time.time() - start_time
                times.append(elapsed)
                
                # Verify embeddings
                assert len(embeddings) == len(texts)
                assert all(len(emb) > 0 for emb in embeddings)
            
            # Calculate statistics
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            std_dev = statistics.stdev(times) if len(times) > 1 else 0
            throughput = batch_size / avg_time
            
            test_result = {
                'batch_size': batch_size,
                'avg_time': avg_time,
                'min_time': min_time,
                'max_time': max_time,
                'std_dev': std_dev,
                'throughput': throughput,
                'times': times
            }
            
            results['test_results'].append(test_result)
            print(f"    Avg: {avg_time:.2f}s, Throughput: {throughput:.1f} emb/s")
        
        # Get performance metrics
        if hasattr(provider, 'get_performance_metrics'):
            results['performance_metrics'] = provider.get_performance_metrics()
        
        return results

    def _generate_test_texts(self, size: int) -> List[str]:
        """Generate test texts for benchmarking."""
        code_examples = [
            "def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
            "class DataProcessor: def __init__(self): self.data = []",
            "async function fetchData() { return await api.get('/data'); }",
            "public class Calculator { public int add(int a, int b) { return a + b; } }",
            "interface User { id: number; name: string; email: string; }",
            "from typing import List, Optional, Dict",
            "const users = await db.users.findMany({ where: { active: true } })",
            "try { const result = JSON.parse(data); } catch (error) { console.error(error); }",
            "SELECT u.name, COUNT(o.id) as order_count FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.id",
            "import React, { useState, useEffect } from 'react'"
        ]
        
        # Repeat and vary to reach desired size
        texts = []
        for i in range(size):
            base_text = code_examples[i % len(code_examples)]
            # Add variation to avoid cache hits
            varied_text = f"// Example {i}\n{base_text}"
            texts.append(varied_text)
        
        return texts

    async def run_benchmarks(self) -> Dict[str, Any]:
        """Run all benchmark configurations."""
        print("Starting BGE-IN-ICL performance benchmarks...")
        
        for config in self.configurations:
            result = await self.benchmark_configuration(config)
            self.results.append(result)
        
        # Generate summary
        summary = self._generate_summary()
        
        return {
            'benchmark_results': self.results,
            'summary': summary,
            'timestamp': time.time()
        }

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate benchmark summary."""
        summary = {
            'configurations_tested': len(self.configurations),
            'best_throughput': {'config': None, 'throughput': 0},
            'best_latency': {'config': None, 'latency': float('inf')},
            'recommended_config': None
        }
        
        for result in self.results:
            config_name = result['configuration']['name']
            
            # Find best throughput result
            max_throughput = max(
                tr['throughput'] for tr in result['test_results']
            )
            if max_throughput > summary['best_throughput']['throughput']:
                summary['best_throughput'] = {
                    'config': config_name,
                    'throughput': max_throughput
                }
            
            # Find best latency result
            min_latency = min(
                tr['avg_time'] for tr in result['test_results']
            )
            if min_latency < summary['best_latency']['latency']:
                summary['best_latency'] = {
                    'config': config_name,
                    'latency': min_latency
                }
        
        return summary

    def save_results(self, filename: str):
        """Save benchmark results to file."""
        with open(filename, 'w') as f:
            json.dump({
                'benchmark_results': self.results,
                'summary': self._generate_summary(),
                'timestamp': time.time()
            }, f, indent=2)

# Example benchmark configurations
BENCHMARK_CONFIGS = [
    {
        'name': 'default',
        'params': {
            'batch_size': 50,
            'enable_icl': True,
            'adaptive_batching': True
        }
    },
    {
        'name': 'high_throughput',
        'params': {
            'batch_size': 100,
            'enable_icl': True,
            'adaptive_batching': True,
            'min_batch_size': 50,
            'max_batch_size': 150
        }
    },
    {
        'name': 'low_latency',
        'params': {
            'batch_size': 16,
            'enable_icl': True,
            'adaptive_batching': True,
            'min_batch_size': 4,
            'max_batch_size': 32
        }
    },
    {
        'name': 'no_icl',
        'params': {
            'batch_size': 64,
            'enable_icl': False,
            'adaptive_batching': True
        }
    }
]

async def main():
    benchmark = BGEICLBenchmark(
        base_url="http://localhost:8080",
        configurations=BENCHMARK_CONFIGS
    )
    
    results = await benchmark.run_benchmarks()
    benchmark.save_results('bge_icl_benchmark_results.json')
    
    print("\nBenchmark Summary:")
    print(f"Best throughput: {results['summary']['best_throughput']}")
    print(f"Best latency: {results['summary']['best_latency']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Performance Monitoring Script

```python
#!/usr/bin/env python3
"""
Real-time BGE-IN-ICL Performance Monitor
"""
import asyncio
import time
import psutil
import requests
from dataclasses import dataclass
from typing import Dict, List
from chunkhound.embeddings import create_bge_in_icl_provider

@dataclass
class PerformanceSnapshot:
    timestamp: float
    response_time: float
    throughput: float
    cache_hit_rate: float
    cpu_usage: float
    memory_usage: float
    batch_size: int
    queue_depth: int

class PerformanceMonitor:
    def __init__(self, base_url: str, monitor_interval: int = 30):
        self.base_url = base_url
        self.monitor_interval = monitor_interval
        self.provider = None
        self.snapshots: List[PerformanceSnapshot] = []

    async def initialize(self):
        """Initialize the performance monitor."""
        self.provider = create_bge_in_icl_provider(
            base_url=self.base_url,
            adaptive_batching=True
        )

    async def take_snapshot(self) -> PerformanceSnapshot:
        """Take a performance snapshot."""
        # Test embedding request
        test_texts = [
            "def test_function(): return 'hello world'",
            "class TestClass: pass",
            "async function test() { return 'test'; }"
        ]
        
        start_time = time.time()
        embeddings = await self.provider.embed(test_texts)
        response_time = time.time() - start_time
        
        # Get provider metrics
        metrics = self.provider.get_performance_metrics()
        
        # Get system metrics
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        
        # Try to get server metrics
        queue_depth = 0
        try:
            response = requests.get(f"{self.base_url}/metrics", timeout=5)
            if response.status_code == 200:
                server_metrics = response.json()
                queue_depth = server_metrics.get('queue_depth', 0)
        except:
            pass
        
        return PerformanceSnapshot(
            timestamp=time.time(),
            response_time=response_time,
            throughput=len(test_texts) / response_time,
            cache_hit_rate=metrics.get('cache_hit_rate', 0),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            batch_size=metrics.get('current_batch_size', 0),
            queue_depth=queue_depth
        )

    async def monitor(self, duration: int = 3600):
        """Monitor performance for specified duration."""
        print(f"Starting performance monitoring for {duration} seconds...")
        print("Timestamp | Response Time | Throughput | Cache Hit | CPU% | Mem% | Batch Size")
        print("-" * 80)
        
        start_time = time.time()
        while time.time() - start_time < duration:
            try:
                snapshot = await self.take_snapshot()
                self.snapshots.append(snapshot)
                
                print(f"{time.strftime('%H:%M:%S')} | "
                      f"{snapshot.response_time:.2f}s | "
                      f"{snapshot.throughput:.1f} emb/s | "
                      f"{snapshot.cache_hit_rate:.1%} | "
                      f"{snapshot.cpu_usage:.1f}% | "
                      f"{snapshot.memory_usage:.1f}% | "
                      f"{snapshot.batch_size}")
                
                # Check for alerts
                self._check_alerts(snapshot)
                
            except Exception as e:
                print(f"Error taking snapshot: {e}")
            
            await asyncio.sleep(self.monitor_interval)

    def _check_alerts(self, snapshot: PerformanceSnapshot):
        """Check for performance alerts."""
        alerts = []
        
        if snapshot.response_time > 10:
            alerts.append(f"HIGH LATENCY: {snapshot.response_time:.2f}s")
        
        if snapshot.cpu_usage > 90:
            alerts.append(f"HIGH CPU: {snapshot.cpu_usage:.1f}%")
        
        if snapshot.memory_usage > 95:
            alerts.append(f"HIGH MEMORY: {snapshot.memory_usage:.1f}%")
        
        if snapshot.cache_hit_rate < 0.3:
            alerts.append(f"LOW CACHE HIT RATE: {snapshot.cache_hit_rate:.1%}")
        
        if alerts:
            print(f"⚠️  ALERTS: {', '.join(alerts)}")

    def generate_report(self) -> Dict:
        """Generate performance report."""
        if not self.snapshots:
            return {}
        
        response_times = [s.response_time for s in self.snapshots]
        throughputs = [s.throughput for s in self.snapshots]
        cache_rates = [s.cache_hit_rate for s in self.snapshots]
        cpu_usage = [s.cpu_usage for s in self.snapshots]
        
        return {
            'monitoring_duration': len(self.snapshots) * self.monitor_interval,
            'total_snapshots': len(self.snapshots),
            'response_time': {
                'avg': sum(response_times) / len(response_times),
                'min': min(response_times),
                'max': max(response_times),
                'p95': sorted(response_times)[int(0.95 * len(response_times))]
            },
            'throughput': {
                'avg': sum(throughputs) / len(throughputs),
                'min': min(throughputs),
                'max': max(throughputs)
            },
            'cache_hit_rate': {
                'avg': sum(cache_rates) / len(cache_rates),
                'min': min(cache_rates),
                'max': max(cache_rates)
            },
            'cpu_usage': {
                'avg': sum(cpu_usage) / len(cpu_usage),
                'max': max(cpu_usage)
            }
        }

async def main():
    monitor = PerformanceMonitor("http://localhost:8080")
    await monitor.initialize()
    
    # Monitor for 30 minutes
    await monitor.monitor(duration=1800)
    
    # Generate report
    report = monitor.generate_report()
    print("\nPerformance Report:")
    print(f"Average response time: {report['response_time']['avg']:.2f}s")
    print(f"Average throughput: {report['throughput']['avg']:.1f} emb/s")
    print(f"Average cache hit rate: {report['cache_hit_rate']['avg']:.1%}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Optimization Strategies

### 1. Batch Size Optimization

#### Adaptive Batching Configuration

```yaml
# Workload-specific batch configurations
configurations:
  interactive:
    initial_batch_size: 8
    adaptive_batching: true
    min_batch_size: 1
    max_batch_size: 16
    scale_up_threshold: 0.7  # Scale up if recent perf is 70% better
    scale_down_threshold: 1.5  # Scale down if recent perf is 50% worse
    
  bulk_processing:
    initial_batch_size: 64
    adaptive_batching: true
    min_batch_size: 32
    max_batch_size: 128
    scale_up_threshold: 0.8
    scale_down_threshold: 1.3
    
  real_time:
    initial_batch_size: 4
    adaptive_batching: false  # Fixed for predictable latency
    min_batch_size: 4
    max_batch_size: 4
```

#### Custom Batch Size Logic

```python
async def optimize_batch_size(provider, test_texts):
    """Find optimal batch size for current workload."""
    batch_sizes = [4, 8, 16, 32, 64, 128]
    results = {}
    
    for batch_size in batch_sizes:
        # Update provider batch size
        provider._batch_size = batch_size
        
        # Test with multiple runs
        times = []
        for _ in range(5):
            start = time.time()
            await provider.embed(test_texts[:batch_size])
            times.append(time.time() - start)
        
        avg_time = sum(times) / len(times)
        throughput = batch_size / avg_time
        
        results[batch_size] = {
            'avg_time': avg_time,
            'throughput': throughput,
            'efficiency': throughput / batch_size  # Embeddings per second per text
        }
    
    # Find optimal batch size (highest efficiency)
    optimal = max(results.keys(), key=lambda k: results[k]['efficiency'])
    return optimal, results
```

### 2. Cache Optimization

#### Context Cache Tuning

```python
class OptimizedICLContextManager:
    def __init__(self, 
                 cache_size: int = 200,
                 similarity_threshold: float = 0.8,
                 eviction_strategy: str = 'lru_similarity'):
        self.cache_size = cache_size
        self.similarity_threshold = similarity_threshold
        self.eviction_strategy = eviction_strategy
        
        # Advanced caching strategies
        self._cache = {}
        self._access_times = {}
        self._similarity_scores = {}
        self._usage_counts = {}

    def _evict_with_similarity(self):
        """Smart eviction based on similarity and usage."""
        if self.eviction_strategy == 'lru_similarity':
            # Combine LRU with similarity scores
            candidates = []
            for key in self._cache:
                score = (
                    self._similarity_scores.get(key, 0) * 0.6 +
                    (time.time() - self._access_times.get(key, 0)) * 0.4
                )
                candidates.append((key, score))
            
            # Evict lowest scoring items
            candidates.sort(key=lambda x: x[1])
            for key, _ in candidates[:len(candidates) // 4]:
                self._remove_from_cache(key)
```

#### Cache Performance Analysis

```python
def analyze_cache_performance(provider, test_duration=3600):
    """Analyze cache performance over time."""
    metrics_history = []
    start_time = time.time()
    
    while time.time() - start_time < test_duration:
        metrics = provider.get_performance_metrics()
        metrics_history.append({
            'timestamp': time.time(),
            'cache_hit_rate': metrics.get('cache_hit_rate', 0),
            'cache_size': metrics.get('cache_size', 0),
            'cache_utilization': metrics.get('cache_utilization', 0)
        })
        
        time.sleep(60)  # Sample every minute
    
    # Analysis
    hit_rates = [m['cache_hit_rate'] for m in metrics_history]
    avg_hit_rate = sum(hit_rates) / len(hit_rates)
    
    print(f"Average cache hit rate: {avg_hit_rate:.1%}")
    print(f"Hit rate stability: {statistics.stdev(hit_rates):.3f}")
    
    # Recommendations
    if avg_hit_rate < 0.7:
        print("Recommendation: Increase cache size or adjust similarity threshold")
    elif avg_hit_rate > 0.95:
        print("Recommendation: Consider reducing cache size to free memory")
```

### 3. Language-Specific Optimization

#### Language Detection Optimization

```python
def optimize_language_detection():
    """Optimize language detection for better context selection."""
    
    language_patterns = {
        'python': {
            'keywords': ['def ', 'class ', 'import ', 'from ', '__init__'],
            'extensions': ['.py'],
            'context_examples': 3,
            'similarity_threshold': 0.85
        },
        'typescript': {
            'keywords': ['interface ', 'type ', 'const ', 'function ', 'async '],
            'extensions': ['.ts', '.tsx'],
            'context_examples': 2,
            'similarity_threshold': 0.8
        },
        'java': {
            'keywords': ['public class', 'private ', 'protected ', 'package '],
            'extensions': ['.java'],
            'context_examples': 2,
            'similarity_threshold': 0.82
        }
    }
    
    return language_patterns
```

#### Per-Language Configuration

```yaml
# Language-specific optimization profiles
language_profiles:
  python:
    batch_size: 20
    context_cache_size: 150
    similarity_threshold: 0.85
    context_examples: 3
    
  typescript:
    batch_size: 24
    context_cache_size: 120
    similarity_threshold: 0.8
    context_examples: 2
    
  java:
    batch_size: 22
    context_cache_size: 130
    similarity_threshold: 0.82
    context_examples: 2
    
  csharp:
    batch_size: 24
    context_cache_size: 125
    similarity_threshold: 0.8
    context_examples: 2
```

## Hardware Configuration

### CPU Optimization

#### Multi-threading Configuration

```yaml
# Server configuration for optimal CPU usage
server_config:
  workers: 4  # Number of worker processes
  threads_per_worker: 2  # Threads per worker
  max_concurrent_requests: 16  # Total concurrent requests
  
  # CPU affinity (Linux)
  cpu_affinity:
    worker_0: [0, 1]
    worker_1: [2, 3]
    worker_2: [4, 5]
    worker_3: [6, 7]
```

#### Process Optimization

```python
import multiprocessing
import concurrent.futures

class OptimizedBGEProvider:
    def __init__(self, base_url, num_workers=None):
        self.base_url = base_url
        self.num_workers = num_workers or multiprocessing.cpu_count()
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.num_workers
        )

    async def embed_parallel(self, text_batches):
        """Process multiple batches in parallel."""
        tasks = []
        for batch in text_batches:
            task = self.executor.submit(self._embed_batch, batch)
            tasks.append(task)
        
        results = []
        for task in concurrent.futures.as_completed(tasks):
            result = await asyncio.wrap_future(task)
            results.append(result)
        
        return results
```

### Memory Optimization

#### Memory Pool Management

```python
class MemoryOptimizedProvider:
    def __init__(self, base_url, memory_pool_size=1024*1024*512):  # 512MB
        self.base_url = base_url
        self.memory_pool = bytearray(memory_pool_size)
        self.pool_offset = 0
        
    def allocate_embedding_buffer(self, size):
        """Allocate buffer from memory pool."""
        if self.pool_offset + size > len(self.memory_pool):
            self.pool_offset = 0  # Reset pool
        
        buffer = memoryview(self.memory_pool[self.pool_offset:self.pool_offset + size])
        self.pool_offset += size
        return buffer
```

#### Memory Monitoring

```python
import psutil
import gc

def monitor_memory_usage():
    """Monitor memory usage and trigger optimization."""
    process = psutil.Process()
    
    while True:
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
        
        print(f"Memory usage: {memory_info.rss / 1024 / 1024:.1f} MB ({memory_percent:.1f}%)")
        
        # Trigger garbage collection if memory usage is high
        if memory_percent > 80:
            print("High memory usage detected, triggering garbage collection")
            gc.collect()
        
        time.sleep(30)
```

### GPU Optimization

#### GPU Configuration for BGE-IN-ICL

```python
import torch

def configure_gpu_optimization():
    """Configure GPU settings for optimal performance."""
    
    if torch.cuda.is_available():
        # Enable optimizations
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.enabled = True
        
        # Memory management
        torch.cuda.empty_cache()
        
        # Set memory fraction
        torch.cuda.set_per_process_memory_fraction(0.8)
        
        print(f"GPU configured: {torch.cuda.get_device_name()}")
        print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    return torch.cuda.is_available()
```

## Software Optimization

### Connection Pool Optimization

```python
import aiohttp
import asyncio

class OptimizedHTTPClient:
    def __init__(self, base_url, max_connections=100, keepalive_timeout=30):
        self.base_url = base_url
        
        connector = aiohttp.TCPConnector(
            limit=max_connections,
            limit_per_host=max_connections,
            keepalive_timeout=keepalive_timeout,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=120, connect=10)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'Connection': 'keep-alive'}
        )

    async def embed_optimized(self, texts):
        """Optimized embedding request with connection pooling."""
        payload = {
            'input': texts,
            'model': 'BAAI/bge-in-icl'
        }
        
        async with self.session.post(
            f"{self.base_url}/v1/embeddings",
            json=payload
        ) as response:
            data = await response.json()
            return [item['embedding'] for item in data['data']]
```

### Async Optimization

```python
import asyncio
from asyncio import Semaphore

class AsyncOptimizedProvider:
    def __init__(self, base_url, max_concurrent=20):
        self.base_url = base_url
        self.semaphore = Semaphore(max_concurrent)
        
    async def embed_with_concurrency_limit(self, text_batches):
        """Process with concurrency limits."""
        async def process_batch(batch):
            async with self.semaphore:
                return await self._embed_single_batch(batch)
        
        tasks = [process_batch(batch) for batch in text_batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        successful_results = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Batch failed: {result}")
            else:
                successful_results.append(result)
        
        return successful_results
```

## Network Optimization

### Connection Configuration

```yaml
# Network optimization settings
network_config:
  connection_pool:
    max_connections: 100
    max_connections_per_host: 50
    keepalive_timeout: 30
    connect_timeout: 10
    read_timeout: 120
    
  retry_config:
    max_retries: 3
    retry_delay: 1
    backoff_factor: 2
    retry_on_status: [500, 502, 503, 504]
    
  compression:
    enable_gzip: true
    compression_level: 6
```

### Load Balancing

```python
import random
from typing import List

class LoadBalancedProvider:
    def __init__(self, server_urls: List[str], weights: List[float] = None):
        self.servers = server_urls
        self.weights = weights or [1.0] * len(server_urls)
        self.providers = [
            create_bge_in_icl_provider(url) for url in server_urls
        ]
        
    async def embed_load_balanced(self, texts):
        """Distribute load across multiple servers."""
        # Weighted random selection
        server_idx = random.choices(
            range(len(self.servers)),
            weights=self.weights
        )[0]
        
        try:
            return await self.providers[server_idx].embed(texts)
        except Exception as e:
            # Fallback to other servers
            for i, provider in enumerate(self.providers):
                if i != server_idx:
                    try:
                        return await provider.embed(texts)
                    except:
                        continue
            raise e

    async def health_check_servers(self):
        """Check health of all servers and adjust weights."""
        for i, provider in enumerate(self.providers):
            try:
                # Simple health check
                await provider.embed(["test"])
                self.weights[i] = max(self.weights[i], 0.1)  # Restore weight
            except:
                self.weights[i] = 0.01  # Reduce weight for unhealthy server
```

## Monitoring and Alerting

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import time

class BGEICLMetrics:
    def __init__(self, registry=None):
        self.registry = registry or CollectorRegistry()
        
        # Counters
        self.requests_total = Counter(
            'bge_icl_requests_total',
            'Total number of embedding requests',
            ['provider', 'language', 'status'],
            registry=self.registry
        )
        
        self.embeddings_generated = Counter(
            'bge_icl_embeddings_generated_total',
            'Total number of embeddings generated',
            ['provider', 'language'],
            registry=self.registry
        )
        
        # Histograms
        self.request_duration = Histogram(
            'bge_icl_request_duration_seconds',
            'Time spent processing embedding requests',
            ['provider', 'batch_size_range'],
            registry=self.registry
        )
        
        self.context_preparation_duration = Histogram(
            'bge_icl_context_preparation_seconds',
            'Time spent preparing ICL context',
            ['language'],
            registry=self.registry
        )
        
        # Gauges
        self.cache_hit_rate = Gauge(
            'bge_icl_cache_hit_rate',
            'Current cache hit rate',
            ['provider'],
            registry=self.registry
        )
        
        self.current_batch_size = Gauge(
            'bge_icl_current_batch_size',
            'Current adaptive batch size',
            ['provider'],
            registry=self.registry
        )
        
        self.active_connections = Gauge(
            'bge_icl_active_connections',
            'Number of active connections',
            ['provider'],
            registry=self.registry
        )

    def record_request(self, provider, language, batch_size, duration, status='success'):
        """Record metrics for a request."""
        # Determine batch size range
        if batch_size <= 10:
            batch_range = 'small'
        elif batch_size <= 50:
            batch_range = 'medium'
        else:
            batch_range = 'large'
            
        self.requests_total.labels(
            provider=provider,
            language=language,
            status=status
        ).inc()
        
        self.embeddings_generated.labels(
            provider=provider,
            language=language
        ).inc(batch_size)
        
        self.request_duration.labels(
            provider=provider,
            batch_size_range=batch_range
        ).observe(duration)

# Integration with BGE-IN-ICL Provider
class MonitoredBGEProvider(BGEInICLProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = BGEICLMetrics()
        
    async def embed(self, texts):
        start_time = time.time()
        language = self._detect_language(texts[0] if texts else "")
        
        try:
            result = await super().embed(texts)
            duration = time.time() - start_time
            
            # Record successful request
            self.metrics.record_request(
                provider=self.name,
                language=language,
                batch_size=len(texts),
                duration=duration,
                status='success'
            )
            
            # Update gauges
            metrics = self.get_performance_metrics()
            self.metrics.cache_hit_rate.labels(provider=self.name).set(
                metrics.get('cache_hit_rate', 0)
            )
            self.metrics.current_batch_size.labels(provider=self.name).set(
                metrics.get('current_batch_size', 0)
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_request(
                provider=self.name,
                language=language,
                batch_size=len(texts),
                duration=duration,
                status='error'
            )
            raise
```

### Grafana Dashboard Configuration

```json
{
  "dashboard": {
    "title": "BGE-IN-ICL Performance Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bge_icl_requests_total[5m])",
            "legendFormat": "{{provider}} - {{language}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(bge_icl_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(bge_icl_request_duration_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "type": "singlestat",
        "targets": [
          {
            "expr": "bge_icl_cache_hit_rate",
            "legendFormat": "{{provider}}"
          }
        ],
        "thresholds": [
          {"color": "red", "value": 0.5},
          {"color": "yellow", "value": 0.7},
          {"color": "green", "value": 0.8}
        ]
      },
      {
        "title": "Throughput",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bge_icl_embeddings_generated_total[5m])",
            "legendFormat": "{{provider}} - {{language}}"
          }
        ]
      },
      {
        "title": "Adaptive Batch Size",
        "type": "graph",
        "targets": [
          {
            "expr": "bge_icl_current_batch_size",
            "legendFormat": "{{provider}}"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bge_icl_requests_total{status=\"error\"}[5m]) / rate(bge_icl_requests_total[5m])",
            "legendFormat": "Error Rate"
          }
        ]
      }
    ]
  }
}
```

### Alert Rules

```yaml
# prometheus-alerts.yml
groups:
  - name: bge-icl-alerts
    rules:
      - alert: BGEICLHighLatency
        expr: histogram_quantile(0.95, rate(bge_icl_request_duration_seconds_bucket[5m])) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "BGE-IN-ICL high latency detected"
          description: "95th percentile latency is {{ $value }}s"
          
      - alert: BGEICLLowCacheHitRate
        expr: bge_icl_cache_hit_rate < 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "BGE-IN-ICL low cache hit rate"
          description: "Cache hit rate is {{ $value | humanizePercentage }}"
          
      - alert: BGEICLHighErrorRate
        expr: rate(bge_icl_requests_total{status="error"}[5m]) / rate(bge_icl_requests_total[5m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "BGE-IN-ICL high error rate"
          description: "Error rate is {{ $value | humanizePercentage }}"
          
      - alert: BGEICLServiceDown
        expr: up{job="bge-icl"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "BGE-IN-ICL service is down"
          description: "BGE-IN-ICL service has been down for more than 1 minute"
```

## Troubleshooting

### Common Performance Issues

#### 1. High Latency
**Symptoms**: Response times > 10 seconds, timeout errors
**Diagnosis**:
```python
async def diagnose_latency_issues(provider):
    """Diagnose latency problems."""
    test_texts = ["def test(): pass"] * 10
    
    # Test different batch sizes
    for batch_size in [1, 5, 10, 25]:
        texts = test_texts[:batch_size]
        
        start_time = time.time()
        try:
            await provider.embed(texts)
            elapsed = time.time() - start_time
            print(f"Batch size {batch_size}: {elapsed:.2f}s ({batch_size/elapsed:.1f} emb/s)")
        except Exception as e:
            print(f"Batch size {batch_size}: ERROR - {e}")
    
    # Check server health
    try:
        response = requests.get(f"{provider._base_url}/health", timeout=5)
        print(f"Server health: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Server health check failed: {e}")
```

**Solutions**:
- Reduce batch size
- Enable adaptive batching
- Check server resources (CPU, memory, GPU)
- Optimize network configuration
- Disable ICL for faster processing

#### 2. Low Throughput
**Symptoms**: < 10 embeddings/second, poor scalability
**Diagnosis**:
```python
def diagnose_throughput_issues():
    """Analyze throughput bottlenecks."""
    
    # Test concurrent requests
    async def test_concurrency():
        providers = [
            create_bge_in_icl_provider("http://localhost:8080")
            for _ in range(5)
        ]
        
        test_texts = ["def example(): return 'test'"] * 20
        
        # Sequential processing
        start_time = time.time()
        for provider in providers:
            await provider.embed(test_texts)
        sequential_time = time.time() - start_time
        
        # Concurrent processing
        start_time = time.time()
        tasks = [provider.embed(test_texts) for provider in providers]
        await asyncio.gather(*tasks)
        concurrent_time = time.time() - start_time
        
        print(f"Sequential: {sequential_time:.2f}s")
        print(f"Concurrent: {concurrent_time:.2f}s")
        print(f"Speedup: {sequential_time/concurrent_time:.2f}x")
    
    asyncio.run(test_concurrency())
```

**Solutions**:
- Increase batch size
- Enable concurrent processing
- Scale horizontally with multiple servers
- Optimize server configuration
- Use load balancing

#### 3. Memory Issues
**Symptoms**: Out of memory errors, memory leaks
**Diagnosis**:
```python
import psutil
import gc

def diagnose_memory_issues(provider):
    """Monitor memory usage during embedding generation."""
    process = psutil.Process()
    
    initial_memory = process.memory_info().rss / 1024 / 1024
    print(f"Initial memory: {initial_memory:.1f} MB")
    
    # Test with increasing batch sizes
    test_text = "def test_function(): return 'hello world'"
    
    for batch_size in [10, 50, 100, 200, 500]:
        texts = [test_text] * batch_size
        
        memory_before = process.memory_info().rss / 1024 / 1024
        
        try:
            embeddings = await provider.embed(texts)
            memory_after = process.memory_info().rss / 1024 / 1024
            memory_delta = memory_after - memory_before
            
            print(f"Batch {batch_size}: {memory_delta:+.1f} MB (total: {memory_after:.1f} MB)")
            
            # Check for memory leaks
            if memory_delta > batch_size * 0.1:  # More than 0.1 MB per embedding
                print(f"  ⚠️  Potential memory leak detected")
            
        except Exception as e:
            print(f"Batch {batch_size}: ERROR - {e}")
        
        # Force garbage collection
        gc.collect()
```

**Solutions**:
- Reduce batch size
- Implement memory pooling
- Regular garbage collection
- Monitor cache size
- Use streaming for large datasets

#### 4. Cache Performance Issues
**Symptoms**: Low cache hit rates, poor context quality
**Diagnosis**:
```python
def diagnose_cache_issues(provider):
    """Analyze cache performance and context quality."""
    
    # Test cache behavior
    test_texts = [
        "def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
        "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)",
        "def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",  # Repeat
    ]
    
    for i, text in enumerate(test_texts):
        start_time = time.time()
        await provider.embed([text])
        elapsed = time.time() - start_time
        
        metrics = provider.get_performance_metrics()
        hit_rate = metrics.get('cache_hit_rate', 0)
        
        print(f"Request {i+1}: {elapsed:.3f}s, hit rate: {hit_rate:.1%}")
```

**Solutions**:
- Increase cache size
- Adjust similarity threshold
- Optimize context selection algorithm
- Monitor cache eviction patterns
- Use language-specific optimization

### Performance Optimization Checklist

#### Server Configuration
- [ ] Adequate CPU cores (4+ recommended)
- [ ] Sufficient RAM (16GB+ for production)
- [ ] GPU availability (if supported)
- [ ] Fast storage (SSD preferred)
- [ ] Stable network connection

#### BGE-IN-ICL Configuration
- [ ] Optimal batch size for workload
- [ ] Adaptive batching enabled
- [ ] Appropriate timeout settings
- [ ] Language-specific optimization
- [ ] Cache size tuned for memory

#### Network Optimization
- [ ] Connection pooling configured
- [ ] Keep-alive connections enabled
- [ ] Compression enabled (if supported)
- [ ] Load balancing (multiple servers)
- [ ] Retry logic implemented

#### Monitoring Setup
- [ ] Prometheus metrics collection
- [ ] Grafana dashboards configured
- [ ] Alert rules defined
- [ ] Performance logging enabled
- [ ] Health checks operational

### Advanced Optimization Techniques

#### 1. Predictive Batching
```python
class PredictiveBatchingProvider:
    def __init__(self, base_url):
        self.base_url = base_url
        self.request_queue = []
        self.batch_predictor = BatchSizePredictor()
        
    async def embed_with_prediction(self, texts):
        """Use ML to predict optimal batch size."""
        predicted_batch_size = self.batch_predictor.predict(
            text_count=len(texts),
            text_lengths=[len(t) for t in texts],
            current_load=self._get_current_load()
        )
        
        # Adjust provider batch size
        self._batch_size = predicted_batch_size
        return await self.embed(texts)
```

#### 2. Smart Request Routing
```python
class SmartRoutingProvider:
    def __init__(self, server_configs):
        self.servers = [
            create_bge_in_icl_provider(**config)
            for config in server_configs
        ]
        self.performance_tracker = PerformanceTracker()
        
    async def embed_with_routing(self, texts):
        """Route requests to optimal server."""
        # Choose server based on current performance
        server_scores = []
        for server in self.servers:
            metrics = server.get_performance_metrics()
            score = self._calculate_server_score(metrics, len(texts))
            server_scores.append(score)
        
        best_server_idx = max(range(len(server_scores)), key=lambda i: server_scores[i])
        return await self.servers[best_server_idx].embed(texts)
```

#### 3. Dynamic Configuration Adjustment
```python
class AdaptiveProvider:
    def __init__(self, base_url):
        self.base_url = base_url
        self.config_optimizer = ConfigurationOptimizer()
        
    async def embed_adaptive(self, texts):
        """Automatically adjust configuration based on performance."""
        current_config = self._get_current_config()
        performance_history = self._get_performance_history()
        
        # Optimize configuration
        new_config = self.config_optimizer.optimize(
            current_config,
            performance_history,
            target_metrics={'latency': 2.0, 'throughput': 50}
        )
        
        # Apply new configuration
        self._apply_config(new_config)
        
        return await self.embed(texts)
```

## Conclusion

Optimizing BGE-IN-ICL performance requires a comprehensive approach covering:

1. **Baseline Measurement**: Establish performance baselines with comprehensive benchmarking
2. **Configuration Tuning**: Optimize batch sizes, caching, and language-specific settings
3. **Resource Optimization**: Ensure adequate hardware and efficient resource utilization
4. **Network Optimization**: Configure connection pooling, load balancing, and retry logic
5. **Continuous Monitoring**: Implement monitoring, alerting, and performance tracking
6. **Iterative Improvement**: Continuously analyze and optimize based on real-world usage

The key to successful optimization is:
- Start with baseline measurements
- Make incremental changes
- Monitor the impact of each change
- Adapt configuration to your specific workload
- Maintain comprehensive monitoring

For additional support and advanced optimization techniques, consult the [BGE-IN-ICL API Reference](./api-reference.md) and [Troubleshooting Guide](./troubleshooting.md).