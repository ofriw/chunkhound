# BGE-IN-ICL Monitoring Setup Guide

## Overview

This guide provides comprehensive instructions for setting up monitoring and observability for BGE-IN-ICL deployments. It covers Prometheus metrics collection, Grafana dashboards, alerting rules, and health monitoring to ensure optimal performance and reliability.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Prometheus Setup](#prometheus-setup)
3. [Grafana Configuration](#grafana-configuration)
4. [Alert Manager Setup](#alert-manager-setup)
5. [Health Monitoring](#health-monitoring)
6. [Log Aggregation](#log-aggregation)
7. [Custom Metrics](#custom-metrics)
8. [Production Deployment](#production-deployment)

## Prerequisites

### Required Components

- **Prometheus**: Time-series database for metrics collection
- **Grafana**: Visualization and dashboarding platform
- **AlertManager**: Alert routing and management
- **Node Exporter**: System metrics collection (optional)
- **BGE-IN-ICL Server**: With metrics endpoint enabled

### Installation

#### Docker Compose Setup

```yaml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./rules:/etc/prometheus/rules
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
      - '--web.enable-admin-api'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards

  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
      - alertmanager_data:/alertmanager

  node-exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'

  bge-in-icl:
    image: baai/bge-in-icl:latest
    ports:
      - "8080:8080"
      - "8081:8081"  # Metrics endpoint
    environment:
      - METRICS_ENABLED=true
      - METRICS_PORT=8081

volumes:
  prometheus_data:
  grafana_data:
  alertmanager_data:
```

## Prometheus Setup

### Configuration File

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'bge-icl-cluster'
    environment: 'production'

rule_files:
  - "rules/*.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  # BGE-IN-ICL Server Metrics
  - job_name: 'bge-icl-server'
    static_configs:
      - targets: ['bge-in-icl:8081']
    scrape_interval: 10s
    metrics_path: /metrics
    params:
      format: ['prometheus']

  # ChunkHound Application Metrics
  - job_name: 'chunkhound'
    static_configs:
      - targets: ['chunkhound:8082']
    scrape_interval: 15s
    metrics_path: /metrics

  # System Metrics
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
    scrape_interval: 30s

  # Prometheus Self-Monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Custom BGE-IN-ICL Metrics
  - job_name: 'bge-icl-custom'
    static_configs:
      - targets: ['bge-icl-metrics:9091']
    scrape_interval: 5s
    honor_labels: true
```

### Alert Rules

Create `rules/bge-icl-alerts.yml`:

```yaml
groups:
  - name: bge-icl-performance
    rules:
      - alert: BGEICLHighLatency
        expr: histogram_quantile(0.95, rate(bge_icl_request_duration_seconds_bucket[5m])) > 10
        for: 2m
        labels:
          severity: warning
          service: bge-icl
        annotations:
          summary: "BGE-IN-ICL high latency detected"
          description: "95th percentile latency is {{ $value }}s for {{ $labels.provider }}"
          runbook_url: "https://docs.company.com/runbooks/bge-icl-latency"

      - alert: BGEICLLowThroughput
        expr: rate(bge_icl_embeddings_generated_total[5m]) < 10
        for: 5m
        labels:
          severity: warning
          service: bge-icl
        annotations:
          summary: "BGE-IN-ICL low throughput"
          description: "Throughput is {{ $value }} embeddings/sec, below threshold of 10"

      - alert: BGEICLHighErrorRate
        expr: rate(bge_icl_requests_total{status="error"}[5m]) / rate(bge_icl_requests_total[5m]) > 0.05
        for: 3m
        labels:
          severity: critical
          service: bge-icl
        annotations:
          summary: "BGE-IN-ICL high error rate"
          description: "Error rate is {{ $value | humanizePercentage }} for {{ $labels.provider }}"

      - alert: BGEICLLowCacheHitRate
        expr: bge_icl_cache_hit_rate < 0.6
        for: 10m
        labels:
          severity: warning
          service: bge-icl
        annotations:
          summary: "BGE-IN-ICL low cache hit rate"
          description: "Cache hit rate is {{ $value | humanizePercentage }}, consider tuning cache settings"

  - name: bge-icl-availability
    rules:
      - alert: BGEICLServiceDown
        expr: up{job="bge-icl-server"} == 0
        for: 1m
        labels:
          severity: critical
          service: bge-icl
        annotations:
          summary: "BGE-IN-ICL service is down"
          description: "BGE-IN-ICL service has been down for more than 1 minute"

      - alert: BGEICLHighMemoryUsage
        expr: (process_resident_memory_bytes{job="bge-icl-server"} / node_memory_MemTotal_bytes) > 0.9
        for: 5m
        labels:
          severity: warning
          service: bge-icl
        annotations:
          summary: "BGE-IN-ICL high memory usage"
          description: "Memory usage is {{ $value | humanizePercentage }}"

      - alert: BGEICLHighCPUUsage
        expr: rate(process_cpu_seconds_total{job="bge-icl-server"}[5m]) > 0.8
        for: 10m
        labels:
          severity: warning
          service: bge-icl
        annotations:
          summary: "BGE-IN-ICL high CPU usage"
          description: "CPU usage is {{ $value | humanizePercentage }}"

  - name: bge-icl-capacity
    rules:
      - alert: BGEICLAdaptiveBatchingStuck
        expr: bge_icl_current_batch_size == bge_icl_min_batch_size
        for: 30m
        labels:
          severity: warning
          service: bge-icl
        annotations:
          summary: "BGE-IN-ICL adaptive batching stuck at minimum"
          description: "Batch size has been at minimum ({{ $value }}) for 30 minutes"

      - alert: BGEICLQueueDepthHigh
        expr: bge_icl_queue_depth > 100
        for: 5m
        labels:
          severity: warning
          service: bge-icl
        annotations:
          summary: "BGE-IN-ICL queue depth is high"
          description: "Queue depth is {{ $value }}, consider scaling"
```

## Grafana Configuration

### Dashboard Provisioning

Create `grafana/provisioning/dashboards/dashboard.yml`:

```yaml
apiVersion: 1

providers:
  - name: 'BGE-ICL Dashboards'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

### Data Source Configuration

Create `grafana/provisioning/datasources/prometheus.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

### Main BGE-IN-ICL Dashboard

Create `grafana/dashboards/bge-icl-overview.json`:

```json
{
  "dashboard": {
    "id": null,
    "title": "BGE-IN-ICL Overview",
    "tags": ["bge-icl", "embeddings"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bge_icl_requests_total[5m])",
            "legendFormat": "{{provider}} - {{language}} - {{status}}"
          }
        ],
        "yAxes": [
          {
            "label": "Requests/sec",
            "min": 0
          }
        ],
        "xAxis": {
          "show": true
        },
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 0,
          "y": 0
        }
      },
      {
        "id": 2,
        "title": "Response Time Percentiles",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(bge_icl_request_duration_seconds_bucket[5m]))",
            "legendFormat": "99th percentile"
          },
          {
            "expr": "histogram_quantile(0.95, rate(bge_icl_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.90, rate(bge_icl_request_duration_seconds_bucket[5m]))",
            "legendFormat": "90th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(bge_icl_request_duration_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          }
        ],
        "yAxes": [
          {
            "label": "Response Time (seconds)",
            "min": 0
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 12,
          "y": 0
        }
      },
      {
        "id": 3,
        "title": "Throughput",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bge_icl_embeddings_generated_total[5m])",
            "legendFormat": "{{provider}} - {{language}}"
          }
        ],
        "yAxes": [
          {
            "label": "Embeddings/sec",
            "min": 0
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 0,
          "y": 8
        }
      },
      {
        "id": 4,
        "title": "Cache Hit Rate",
        "type": "singlestat",
        "targets": [
          {
            "expr": "bge_icl_cache_hit_rate",
            "legendFormat": "{{provider}}"
          }
        ],
        "format": "percentunit",
        "thresholds": "0.5,0.7,0.8",
        "colorBackground": true,
        "gridPos": {
          "h": 8,
          "w": 6,
          "x": 12,
          "y": 8
        }
      },
      {
        "id": 5,
        "title": "Active Connections",
        "type": "singlestat",
        "targets": [
          {
            "expr": "bge_icl_active_connections",
            "legendFormat": "{{provider}}"
          }
        ],
        "format": "short",
        "gridPos": {
          "h": 8,
          "w": 6,
          "x": 18,
          "y": 8
        }
      },
      {
        "id": 6,
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bge_icl_requests_total{status=\"error\"}[5m]) / rate(bge_icl_requests_total[5m])",
            "legendFormat": "Error Rate"
          }
        ],
        "yAxes": [
          {
            "label": "Error Rate",
            "min": 0,
            "max": 1
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 0,
          "y": 16
        }
      },
      {
        "id": 7,
        "title": "Adaptive Batch Size",
        "type": "graph",
        "targets": [
          {
            "expr": "bge_icl_current_batch_size",
            "legendFormat": "{{provider}}"
          }
        ],
        "yAxes": [
          {
            "label": "Batch Size",
            "min": 0
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 12,
          "y": 16
        }
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s"
  }
}
```

### Performance Dashboard

Create `grafana/dashboards/bge-icl-performance.json`:

```json
{
  "dashboard": {
    "id": null,
    "title": "BGE-IN-ICL Performance Analysis",
    "tags": ["bge-icl", "performance"],
    "panels": [
      {
        "id": 1,
        "title": "Response Time Heatmap",
        "type": "heatmap",
        "targets": [
          {
            "expr": "rate(bge_icl_request_duration_seconds_bucket[5m])",
            "format": "heatmap",
            "legendFormat": "{{le}}"
          }
        ],
        "xAxis": {
          "show": true
        },
        "yAxis": {
          "show": true,
          "label": "Response Time (seconds)"
        },
        "gridPos": {
          "h": 8,
          "w": 24,
          "x": 0,
          "y": 0
        }
      },
      {
        "id": 2,
        "title": "Batch Size Distribution",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(bge_icl_request_duration_seconds_bucket{batch_size_range=\"small\"}[5m]))",
            "legendFormat": "Small Batches (≤10)"
          },
          {
            "expr": "histogram_quantile(0.50, rate(bge_icl_request_duration_seconds_bucket{batch_size_range=\"medium\"}[5m]))",
            "legendFormat": "Medium Batches (11-50)"
          },
          {
            "expr": "histogram_quantile(0.50, rate(bge_icl_request_duration_seconds_bucket{batch_size_range=\"large\"}[5m]))",
            "legendFormat": "Large Batches (>50)"
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 0,
          "y": 8
        }
      },
      {
        "id": 3,
        "title": "Context Preparation Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(bge_icl_context_preparation_seconds_bucket[5m]))",
            "legendFormat": "95th percentile - {{language}}"
          },
          {
            "expr": "histogram_quantile(0.50, rate(bge_icl_context_preparation_seconds_bucket[5m]))",
            "legendFormat": "50th percentile - {{language}}"
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 12,
          "y": 8
        }
      }
    ]
  }
}
```

## Alert Manager Setup

### Configuration

Create `alertmanager.yml`:

```yaml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@company.com'
  slack_api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'

route:
  group_by: ['alertname', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
    - match:
        severity: warning
      receiver: 'warning-alerts'

receivers:
  - name: 'web.hook'
    webhook_configs:
      - url: 'http://127.0.0.1:5001/'

  - name: 'critical-alerts'
    slack_configs:
      - channel: '#critical-alerts'
        title: 'BGE-IN-ICL Critical Alert'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
        send_resolved: true
    email_configs:
      - to: 'oncall@company.com'
        subject: 'BGE-IN-ICL Critical Alert'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          {{ end }}

  - name: 'warning-alerts'
    slack_configs:
      - channel: '#monitoring'
        title: 'BGE-IN-ICL Warning'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'service']
```

## Health Monitoring

### Health Check Script

Create `scripts/health-monitor.py`:

```python
#!/usr/bin/env python3
"""
BGE-IN-ICL Health Monitoring Script
"""
import asyncio
import aiohttp
import time
import json
import logging
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class HealthCheck:
    name: str
    url: str
    timeout: int = 10
    expected_status: int = 200
    critical: bool = True

class HealthMonitor:
    def __init__(self, checks: List[HealthCheck], interval: int = 60):
        self.checks = checks
        self.interval = interval
        self.logger = logging.getLogger(__name__)
        
    async def check_health(self, check: HealthCheck) -> Dict:
        """Perform a single health check."""
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=check.timeout)) as session:
                async with session.get(check.url) as response:
                    response_time = time.time() - start_time
                    
                    is_healthy = response.status == check.expected_status
                    
                    # Try to parse JSON response for additional info
                    try:
                        data = await response.json()
                    except:
                        data = {}
                    
                    return {
                        'name': check.name,
                        'healthy': is_healthy,
                        'status_code': response.status,
                        'response_time': response_time,
                        'timestamp': time.time(),
                        'data': data,
                        'critical': check.critical
                    }
                    
        except asyncio.TimeoutError:
            return {
                'name': check.name,
                'healthy': False,
                'status_code': 0,
                'response_time': check.timeout,
                'timestamp': time.time(),
                'error': 'Timeout',
                'critical': check.critical
            }
        except Exception as e:
            return {
                'name': check.name,
                'healthy': False,
                'status_code': 0,
                'response_time': time.time() - start_time,
                'timestamp': time.time(),
                'error': str(e),
                'critical': check.critical
            }

    async def run_all_checks(self) -> List[Dict]:
        """Run all health checks concurrently."""
        tasks = [self.check_health(check) for check in self.checks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        clean_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Health check exception: {result}")
            else:
                clean_results.append(result)
        
        return clean_results

    async def monitor(self):
        """Continuous health monitoring."""
        self.logger.info(f"Starting health monitoring with {len(self.checks)} checks")
        
        while True:
            try:
                results = await self.run_all_checks()
                
                # Log results
                healthy_count = sum(1 for r in results if r['healthy'])
                total_count = len(results)
                
                self.logger.info(f"Health check results: {healthy_count}/{total_count} healthy")
                
                # Check for critical failures
                critical_failures = [r for r in results if not r['healthy'] and r['critical']]
                if critical_failures:
                    self.logger.error(f"Critical health check failures: {len(critical_failures)}")
                    for failure in critical_failures:
                        self.logger.error(f"  {failure['name']}: {failure.get('error', 'Unknown error')}")
                
                # Detailed logging
                for result in results:
                    status = "✅" if result['healthy'] else "❌"
                    self.logger.info(
                        f"{status} {result['name']}: "
                        f"{result['response_time']:.2f}s "
                        f"(status: {result['status_code']})"
                    )
                
                # Export metrics (for Prometheus scraping)
                self.export_metrics(results)
                
            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")
            
            await asyncio.sleep(self.interval)

    def export_metrics(self, results: List[Dict]):
        """Export health check metrics for Prometheus."""
        metrics = []
        
        for result in results:
            # Health status (1 = healthy, 0 = unhealthy)
            metrics.append(
                f'bge_icl_health_check{{name="{result["name"]}"}} {int(result["healthy"])}'
            )
            
            # Response time
            metrics.append(
                f'bge_icl_health_response_time{{name="{result["name"]}"}} {result["response_time"]}'
            )
            
            # Status code
            if result['status_code']:
                metrics.append(
                    f'bge_icl_health_status_code{{name="{result["name"]}"}} {result["status_code"]}'
                )
        
        # Write metrics to file for Prometheus node_exporter textfile collector
        with open('/var/lib/node_exporter/bge_icl_health.prom', 'w') as f:
            f.write('\n'.join(metrics) + '\n')

# Health check configurations
HEALTH_CHECKS = [
    HealthCheck(
        name="bge-icl-server",
        url="http://localhost:8080/health",
        critical=True
    ),
    HealthCheck(
        name="bge-icl-metrics",
        url="http://localhost:8081/metrics",
        critical=False
    ),
    HealthCheck(
        name="chunkhound-api",
        url="http://localhost:8082/health",
        critical=True
    ),
    HealthCheck(
        name="prometheus",
        url="http://localhost:9090/-/healthy",
        critical=False
    ),
    HealthCheck(
        name="grafana",
        url="http://localhost:3000/api/health",
        critical=False
    )
]

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    monitor = HealthMonitor(HEALTH_CHECKS, interval=30)
    await monitor.monitor()

if __name__ == "__main__":
    asyncio.run(main())
```

## Log Aggregation

### ELK Stack Integration

Create `docker-compose.logging.yml`:

```yaml
version: '3.8'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.15.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data

  logstash:
    image: docker.elastic.co/logstash/logstash:7.15.0
    ports:
      - "5044:5044"
    volumes:
      - ./logstash/pipeline:/usr/share/logstash/pipeline
      - ./logstash/config:/usr/share/logstash/config
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:7.15.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch

  filebeat:
    image: docker.elastic.co/beats/filebeat:7.15.0
    user: root
    volumes:
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      - logstash

volumes:
  elasticsearch_data:
```

### Logstash Configuration

Create `logstash/pipeline/bge-icl.conf`:

```ruby
input {
  beats {
    port => 5044
  }
}

filter {
  if [container][name] =~ /bge-icl/ {
    # Parse BGE-IN-ICL logs
    grok {
      match => { 
        "message" => "%{TIMESTAMP_ISO8601:timestamp} - %{LOGLEVEL:level} - %{DATA:logger} - %{GREEDYDATA:log_message}"
      }
    }
    
    # Extract performance metrics from logs
    if [log_message] =~ /Performance/ {
      grok {
        match => {
          "log_message" => "Performance: %{NUMBER:response_time:float}s, %{NUMBER:throughput:float} emb/s, cache_hit_rate: %{NUMBER:cache_hit_rate:float}"
        }
      }
    }
    
    # Extract error information
    if [level] == "ERROR" {
      grok {
        match => {
          "log_message" => "Error: %{GREEDYDATA:error_message}"
        }
      }
    }
  }
  
  # Add common fields
  mutate {
    add_field => { "service" => "bge-icl" }
    add_field => { "environment" => "production" }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "bge-icl-logs-%{+YYYY.MM.dd}"
  }
  
  # Output performance metrics to separate index
  if [response_time] {
    elasticsearch {
      hosts => ["elasticsearch:9200"]
      index => "bge-icl-performance-%{+YYYY.MM.dd}"
    }
  }
}
```

## Custom Metrics

### Application Metrics Exporter

Create `metrics/bge_icl_exporter.py`:

```python
#!/usr/bin/env python3
"""
Custom BGE-IN-ICL Metrics Exporter for Prometheus
"""
import asyncio
import time
from prometheus_client import start_http_server, Counter, Histogram, Gauge
from chunkhound.embeddings import create_bge_in_icl_provider

class BGEICLMetricsExporter:
    def __init__(self, bge_icl_url: str, port: int = 9091):
        self.bge_icl_url = bge_icl_url
        self.port = port
        
        # Initialize metrics
        self.setup_metrics()
        self.provider = None

    def setup_metrics(self):
        """Initialize Prometheus metrics."""
        # Custom application metrics
        self.context_quality_score = Histogram(
            'bge_icl_context_quality_score',
            'Quality score of ICL context selection',
            ['language']
        )
        
        self.model_inference_time = Histogram(
            'bge_icl_model_inference_seconds',
            'Time spent in model inference',
            ['model', 'batch_size_range']
        )
        
        self.cache_efficiency = Gauge(
            'bge_icl_cache_efficiency_ratio',
            'Cache efficiency ratio (hits/total)',
            ['provider']
        )
        
        self.embedding_dimensions = Gauge(
            'bge_icl_embedding_dimensions',
            'Number of dimensions in embeddings',
            ['model']
        )
        
        self.active_requests = Gauge(
            'bge_icl_active_requests_current',
            'Currently active requests',
            ['provider']
        )

    async def initialize(self):
        """Initialize the BGE-IN-ICL provider."""
        self.provider = create_bge_in_icl_provider(
            base_url=self.bge_icl_url,
            adaptive_batching=True
        )

    async def collect_metrics(self):
        """Collect custom metrics from BGE-IN-ICL provider."""
        if not self.provider:
            return
            
        try:
            # Get provider metrics
            metrics = self.provider.get_performance_metrics()
            
            # Update cache efficiency
            cache_hit_rate = metrics.get('cache_hit_rate', 0)
            self.cache_efficiency.labels(provider=self.provider.name).set(cache_hit_rate)
            
            # Update embedding dimensions
            self.embedding_dimensions.labels(model=self.provider.model).set(self.provider.dims)
            
            # Test request to measure inference time
            test_text = ["def test(): return 'metrics'"]
            start_time = time.time()
            embeddings = await self.provider.embed(test_text)
            inference_time = time.time() - start_time
            
            # Record inference time
            batch_range = 'small'  # Single text test
            self.model_inference_time.labels(
                model=self.provider.model,
                batch_size_range=batch_range
            ).observe(inference_time)
            
        except Exception as e:
            print(f"Error collecting metrics: {e}")

    async def run_exporter(self):
        """Run the metrics exporter."""
        # Start Prometheus HTTP server
        start_http_server(self.port)
        print(f"BGE-IN-ICL metrics exporter started on port {self.port}")
        
        await self.initialize()
        
        while True:
            await self.collect_metrics()
            await asyncio.sleep(30)  # Collect metrics every 30 seconds

async def main():
    exporter = BGEICLMetricsExporter("http://localhost:8080")
    await exporter.run_exporter()

if __name__ == "__main__":
    asyncio.run(main())
```

## Production Deployment

### Kubernetes Monitoring Stack

Create `k8s/monitoring-stack.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  labels:
    app: prometheus
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:latest
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: prometheus-config
          mountPath: /etc/prometheus
        - name: prometheus-storage
          mountPath: /prometheus
        args:
          - '--config.file=/etc/prometheus/prometheus.yml'
          - '--storage.tsdb.path=/prometheus'
          - '--storage.tsdb.retention.time=30d'
          - '--web.enable-lifecycle'
      volumes:
      - name: prometheus-config
        configMap:
          name: prometheus-config
      - name: prometheus-storage
        persistentVolumeClaim:
          claimName: prometheus-pvc

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    rule_files:
      - "/etc/prometheus/rules/*.yml"
    
    alerting:
      alertmanagers:
        - static_configs:
            - targets:
              - alertmanager:9093
    
    scrape_configs:
      - job_name: 'bge-icl-server'
        kubernetes_sd_configs:
        - role: pod
        relabel_configs:
        - source_labels: [__meta_kubernetes_pod_label_app]
          action: keep
          regex: bge-in-icl
        - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
          action: keep
          regex: true
        - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
          action: replace
          target_label: __address__
          regex: ([^:]+)(?::\d+)?;(\d+)
          replacement: $1:$2

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
      - name: grafana
        image: grafana/grafana:latest
        ports:
        - containerPort: 3000
        env:
        - name: GF_SECURITY_ADMIN_PASSWORD
          valueFrom:
            secretKeyRef:
              name: grafana-secret
              key: admin-password
        volumeMounts:
        - name: grafana-storage
          mountPath: /var/lib/grafana
        - name: grafana-config
          mountPath: /etc/grafana/provisioning
      volumes:
      - name: grafana-storage
        persistentVolumeClaim:
          claimName: grafana-pvc
      - name: grafana-config
        configMap:
          name: grafana-config

---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
spec:
  selector:
    app: prometheus
  ports:
  - port: 9090
    targetPort: 9090
  type: ClusterIP

---
apiVersion: v1
kind: Service
metadata:
  name: grafana
spec:
  selector:
    app: grafana
  ports:
  - port: 3000
    targetPort: 3000
  type: LoadBalancer
```

### Helm Chart for BGE-IN-ICL Monitoring

Create `helm/bge-icl-monitoring/values.yaml`:

```yaml
# BGE-IN-ICL Monitoring Helm Chart Values

prometheus:
  enabled: true
  retention: "30d"
  scrapeInterval: "15s"
  evaluationInterval: "15s"
  resources:
    requests:
      memory: "1Gi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "1"
  persistence:
    enabled: true
    size: "50Gi"

grafana:
  enabled: true
  adminPassword: "admin"
  resources:
    requests:
      memory: "256Mi"
      cpu: "250m"
    limits:
      memory: "512Mi"
      cpu: "500m"
  persistence:
    enabled: true
    size: "10Gi"
  
  dashboards:
    bge-icl-overview:
      enabled: true
    bge-icl-performance:
      enabled: true
    bge-icl-alerts:
      enabled: true

alertmanager:
  enabled: true
  resources:
    requests:
      memory: "128Mi"
      cpu: "100m"
    limits:
      memory: "256Mi"
      cpu: "200m"
  
  config:
    slack:
      webhook_url: ""
      channel: "#monitoring"
    email:
      smtp_host: "smtp.company.com"
      smtp_port: 587
      from: "alerts@company.com"
      to: "oncall@company.com"

bgeicl:
  metrics:
    enabled: true
    port: 8081
  health:
    enabled: true
    interval: 30
  customMetrics:
    enabled: true
    port: 9091

nodeExporter:
  enabled: true
  
kubeStateMetrics:
  enabled: true
```

### Production Configuration Template

Create `production/bge-icl-monitoring.yaml`:

```yaml
# Production BGE-IN-ICL Monitoring Configuration

global:
  cluster_name: "production"
  environment: "prod"
  namespace: "bge-icl"

monitoring:
  prometheus:
    retention: "90d"
    scrape_interval: "10s"
    external_labels:
      cluster: "prod-cluster"
      region: "us-west-2"
    
    storage:
      class: "fast-ssd"
      size: "200Gi"
    
    resources:
      requests:
        memory: "4Gi"
        cpu: "2"
      limits:
        memory: "8Gi"
        cpu: "4"
    
    high_availability:
      enabled: true
      replicas: 2
      
  grafana:
    high_availability:
      enabled: true
      replicas: 2
    
    resources:
      requests:
        memory: "1Gi"
        cpu: "500m"
      limits:
        memory: "2Gi"
        cpu: "1"
    
    auth:
      ldap_enabled: true
      oauth_enabled: true
    
    persistence:
      class: "standard"
      size: "20Gi"

  alertmanager:
    high_availability:
      enabled: true
      replicas: 3
    
    clustering:
      enabled: true
      peers:
        - alertmanager-0.alertmanager:9094
        - alertmanager-1.alertmanager:9094
        - alertmanager-2.alertmanager:9094

alerts:
  critical:
    - name: "BGEICLServiceDown"
      threshold: "1m"
      severity: "critical"
    - name: "BGEICLHighErrorRate"
      threshold: "5%"
      duration: "3m"
      severity: "critical"
    
  warning:
    - name: "BGEICLHighLatency"
      threshold: "10s"
      duration: "5m"
      severity: "warning"
    - name: "BGEICLLowCacheHitRate"
      threshold: "60%"
      duration: "10m"
      severity: "warning"

security:
  tls:
    enabled: true
    cert_manager: true
  
  rbac:
    enabled: true
    
  network_policies:
    enabled: true
    
  pod_security_policies:
    enabled: true
```

### Monitoring Deployment Script

Create `scripts/deploy-monitoring.sh`:

```bash
#!/bin/bash
# BGE-IN-ICL Monitoring Deployment Script

set -euo pipefail

NAMESPACE="${NAMESPACE:-bge-icl-monitoring}"
ENVIRONMENT="${ENVIRONMENT:-production}"
CONFIG_DIR="${CONFIG_DIR:-./config}"

echo "🚀 Deploying BGE-IN-ICL Monitoring Stack"
echo "Environment: $ENVIRONMENT"
echo "Namespace: $NAMESPACE"

# Create namespace
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# Label namespace
kubectl label namespace "$NAMESPACE" app=bge-icl-monitoring --overwrite

# Deploy Prometheus
echo "📊 Deploying Prometheus..."
kubectl apply -n "$NAMESPACE" -f "$CONFIG_DIR/prometheus/"

# Deploy Grafana
echo "📈 Deploying Grafana..."
kubectl apply -n "$NAMESPACE" -f "$CONFIG_DIR/grafana/"

# Deploy AlertManager
echo "🚨 Deploying AlertManager..."
kubectl apply -n "$NAMESPACE" -f "$CONFIG_DIR/alertmanager/"

# Deploy custom metrics exporters
echo "📋 Deploying custom metrics..."
kubectl apply -n "$NAMESPACE" -f "$CONFIG_DIR/metrics/"

# Wait for deployments
echo "⏳ Waiting for deployments to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/prometheus -n "$NAMESPACE"
kubectl wait --for=condition=available --timeout=300s deployment/grafana -n "$NAMESPACE"
kubectl wait --for=condition=available --timeout=300s deployment/alertmanager -n "$NAMESPACE"

# Verify deployments
echo "✅ Verifying deployments..."
kubectl get pods -n "$NAMESPACE"
kubectl get services -n "$NAMESPACE"

# Setup port forwarding for local access (optional)
if [ "${SETUP_PORT_FORWARD:-false}" = "true" ]; then
    echo "🔧 Setting up port forwarding..."
    kubectl port-forward -n "$NAMESPACE" svc/grafana 3000:3000 &
    kubectl port-forward -n "$NAMESPACE" svc/prometheus 9090:9090 &
    echo "Grafana: http://localhost:3000"
    echo "Prometheus: http://localhost:9090"
fi

echo "🎉 BGE-IN-ICL Monitoring Stack deployed successfully!"
echo ""
echo "Next steps:"
echo "1. Configure dashboards in Grafana"
echo "2. Set up alert notification channels"
echo "3. Import BGE-IN-ICL dashboards"
echo "4. Test alert rules"
```

### Backup and Recovery

Create `scripts/backup-monitoring.sh`:

```bash
#!/bin/bash
# BGE-IN-ICL Monitoring Backup Script

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups/$(date +%Y%m%d_%H%M%S)}"
NAMESPACE="${NAMESPACE:-bge-icl-monitoring}"

echo "💾 Creating monitoring backup..."
mkdir -p "$BACKUP_DIR"

# Backup Prometheus data
echo "📊 Backing up Prometheus data..."
kubectl exec -n "$NAMESPACE" prometheus-0 -- tar czf - /prometheus > "$BACKUP_DIR/prometheus-data.tar.gz"

# Backup Grafana data
echo "📈 Backing up Grafana data..."
kubectl exec -n "$NAMESPACE" grafana-0 -- tar czf - /var/lib/grafana > "$BACKUP_DIR/grafana-data.tar.gz"

# Backup configurations
echo "⚙️ Backing up configurations..."
kubectl get configmaps -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/configmaps.yaml"
kubectl get secrets -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/secrets.yaml"

# Backup dashboard definitions
echo "📋 Backing up dashboards..."
kubectl exec -n "$NAMESPACE" grafana-0 -- curl -s -H "Authorization: Bearer $GRAFANA_API_KEY" \
  http://localhost:3000/api/search?type=dash-db | jq '.[].uid' | \
  xargs -I {} kubectl exec -n "$NAMESPACE" grafana-0 -- curl -s -H "Authorization: Bearer $GRAFANA_API_KEY" \
  "http://localhost:3000/api/dashboards/uid/{}" > "$BACKUP_DIR/dashboards.json"

echo "✅ Backup completed: $BACKUP_DIR"
```

This comprehensive monitoring setup provides:

1. **Complete observability** for BGE-IN-ICL deployments
2. **Production-ready** configurations with HA support
3. **Automated deployment** scripts and tools
4. **Custom metrics** specific to BGE-IN-ICL performance
5. **Alert management** with multiple notification channels
6. **Health monitoring** with detailed checks
7. **Log aggregation** using ELK stack
8. **Backup and recovery** procedures

The monitoring stack is designed to scale with your BGE-IN-ICL deployment and provide comprehensive insights into performance, reliability, and operational health.
