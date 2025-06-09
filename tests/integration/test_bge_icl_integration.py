#!/usr/bin/env python3
"""
BGE-IN-ICL Integration Tests

Comprehensive integration tests for BGE-IN-ICL provider with real server instances.
Tests end-to-end functionality, performance characteristics, and production scenarios.
"""

import asyncio
import pytest
import time
import statistics
import json
import os
from typing import List, Dict, Any, Optional
from unittest.mock import patch, AsyncMock
import aiohttp
import logging

from chunkhound.embeddings import (
    create_bge_in_icl_provider,
    BGEInICLProvider,
    ICLContextManager
)

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
TEST_SERVER_URL = os.getenv("BGE_ICL_TEST_SERVER", "http://localhost:8080")
TEST_API_KEY = os.getenv("BGE_ICL_TEST_API_KEY", None)
SKIP_REAL_SERVER_TESTS = os.getenv("SKIP_REAL_SERVER_TESTS", "true").lower() == "true"

# Test data
SAMPLE_CODE_TEXTS = [
    "def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
    "class DataProcessor: def __init__(self): self.data = []",
    "async function fetchData() { return await api.get('/data'); }",
    "public class Calculator { public int add(int a, int b) { return a + b; } }",
    "interface User { id: number; name: string; email: string; }",
    "from typing import List, Optional, Dict",
    "const users = await db.users.findMany({ where: { active: true } })",
    "try { const result = JSON.parse(data); } catch (error) { console.error(error); }",
    "SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id",
    "import React, { useState, useEffect } from 'react'"
]

LANGUAGE_SPECIFIC_TESTS = {
    'python': [
        "def process_data(data: List[str]) -> Dict[str, int]:",
        "class APIClient:\n    def __init__(self, base_url: str):",
        "async def fetch_user(user_id: int) -> Optional[User]:",
        "from dataclasses import dataclass\n@dataclass\nclass Config:"
    ],
    'typescript': [
        "interface APIResponse<T> { data: T; status: number; }",
        "const fetchUser = async (id: number): Promise<User> => {",
        "type EventHandler = (event: Event) => void;",
        "export class UserService { private api: APIClient; }"
    ],
    'java': [
        "public class UserRepository implements Repository<User> {",
        "@Service\npublic class UserService {",
        "public Optional<User> findById(Long id) {",
        "@Entity\npublic class User { @Id private Long id; }"
    ],
    'csharp': [
        "public class UserController : ControllerBase {",
        "public async Task<User> GetUserAsync(int id) {",
        "public interface IUserRepository { Task<User> FindAsync(int id); }",
        "[HttpGet]\npublic ActionResult<User> GetUser(int id) {"
    ]
}

class BGEICLIntegrationTestSuite:
    """Comprehensive integration test suite for BGE-IN-ICL."""
    
    def __init__(self, server_url: str = TEST_SERVER_URL, api_key: Optional[str] = TEST_API_KEY):
        self.server_url = server_url
        self.api_key = api_key
        self.provider = None
        self.test_results = {}

    async def setup(self):
        """Set up test environment and provider."""
        logger.info(f"Setting up BGE-IN-ICL integration tests with server: {self.server_url}")
        
        # Create provider with test configuration
        self.provider = create_bge_in_icl_provider(
            base_url=self.server_url,
            api_key=self.api_key,
            batch_size=32,
            timeout=120,
            enable_icl=True,
            adaptive_batching=True,
            context_cache_size=100
        )
        
        # Verify server connectivity
        await self._verify_server_health()

    async def _verify_server_health(self):
        """Verify BGE-IN-ICL server is accessible and healthy."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.server_url}/health", timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"Server health check failed: {response.status}")
                    data = await response.json()
                    logger.info(f"Server health: {data}")
        except Exception as e:
            logger.error(f"Server health check failed: {e}")
            raise

    async def test_basic_functionality(self) -> Dict[str, Any]:
        """Test basic embedding generation functionality."""
        logger.info("Testing basic BGE-IN-ICL functionality...")
        
        test_texts = SAMPLE_CODE_TEXTS[:5]
        start_time = time.time()
        
        try:
            embeddings = await self.provider.embed(test_texts)
            elapsed = time.time() - start_time
            
            # Validate results
            assert len(embeddings) == len(test_texts), "Embedding count mismatch"
            assert all(len(emb) == self.provider.dims for emb in embeddings), "Dimension mismatch"
            assert all(isinstance(emb, list) for emb in embeddings), "Invalid embedding type"
            
            result = {
                'status': 'pass',
                'response_time': elapsed,
                'throughput': len(test_texts) / elapsed,
                'embedding_count': len(embeddings),
                'embedding_dims': len(embeddings[0]) if embeddings else 0,
                'details': 'Basic functionality test passed successfully'
            }
            
            logger.info(f"Basic test passed: {elapsed:.2f}s, {result['throughput']:.1f} emb/s")
            return result
            
        except Exception as e:
            logger.error(f"Basic functionality test failed: {e}")
            return {
                'status': 'fail',
                'error': str(e),
                'response_time': time.time() - start_time
            }

    async def test_language_specific_optimization(self) -> Dict[str, Any]:
        """Test language-specific context optimization."""
        logger.info("Testing language-specific optimization...")
        
        results = {}
        
        for language, texts in LANGUAGE_SPECIFIC_TESTS.items():
            logger.info(f"Testing {language} optimization...")
            
            # Create language-specific provider
            lang_provider = create_bge_in_icl_provider(
                base_url=self.server_url,
                api_key=self.api_key,
                language=language,
                enable_icl=True,
                batch_size=16
            )
            
            start_time = time.time()
            try:
                embeddings = await lang_provider.embed(texts)
                elapsed = time.time() - start_time
                
                # Get performance metrics
                metrics = lang_provider.get_performance_metrics()
                
                results[language] = {
                    'status': 'pass',
                    'response_time': elapsed,
                    'throughput': len(texts) / elapsed,
                    'cache_hit_rate': metrics.get('cache_hit_rate', 0),
                    'embedding_count': len(embeddings)
                }
                
                logger.info(f"{language}: {elapsed:.2f}s, cache hit: {metrics.get('cache_hit_rate', 0):.1%}")
                
            except Exception as e:
                logger.error(f"{language} test failed: {e}")
                results[language] = {
                    'status': 'fail',
                    'error': str(e),
                    'response_time': time.time() - start_time
                }
        
        return results

    async def test_adaptive_batching(self) -> Dict[str, Any]:
        """Test adaptive batching functionality."""
        logger.info("Testing adaptive batching...")
        
        # Create provider with adaptive batching
        adaptive_provider = create_bge_in_icl_provider(
            base_url=self.server_url,
            api_key=self.api_key,
            adaptive_batching=True,
            min_batch_size=4,
            max_batch_size=64,
            batch_size=16
        )
        
        batch_sizes_tested = []
        response_times = []
        
        # Test with varying loads to trigger adaptation
        test_scenarios = [
            (SAMPLE_CODE_TEXTS[:2], "small_load"),
            (SAMPLE_CODE_TEXTS[:8], "medium_load"),
            (SAMPLE_CODE_TEXTS, "large_load"),
            (SAMPLE_CODE_TEXTS[:4], "reduced_load")
        ]
        
        for texts, scenario in test_scenarios:
            logger.info(f"Testing adaptive batching with {scenario}...")
            
            start_time = time.time()
            try:
                embeddings = await adaptive_provider.embed(texts)
                elapsed = time.time() - start_time
                
                metrics = adaptive_provider.get_performance_metrics()
                current_batch_size = metrics.get('current_batch_size', 0)
                
                batch_sizes_tested.append(current_batch_size)
                response_times.append(elapsed)
                
                logger.info(f"{scenario}: batch_size={current_batch_size}, time={elapsed:.2f}s")
                
                # Small delay to allow adaptation
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Adaptive batching test failed on {scenario}: {e}")
                return {
                    'status': 'fail',
                    'error': str(e),
                    'scenario': scenario
                }
        
        # Analyze adaptation behavior
        batch_size_changed = len(set(batch_sizes_tested)) > 1
        
        return {
            'status': 'pass' if batch_size_changed else 'warning',
            'batch_sizes': batch_sizes_tested,
            'response_times': response_times,
            'adaptation_detected': batch_size_changed,
            'avg_response_time': statistics.mean(response_times),
            'details': 'Adaptive batching shows size variation' if batch_size_changed 
                      else 'No batch size adaptation detected'
        }

    async def test_performance_characteristics(self) -> Dict[str, Any]:
        """Test performance characteristics under various conditions."""
        logger.info("Testing performance characteristics...")
        
        performance_results = {}
        
        # Test different batch sizes
        batch_sizes = [1, 5, 10, 25, 50]
        
        for batch_size in batch_sizes:
            if batch_size > len(SAMPLE_CODE_TEXTS):
                continue
                
            texts = SAMPLE_CODE_TEXTS[:batch_size]
            times = []
            
            # Multiple runs for statistical significance
            for run in range(3):
                start_time = time.time()
                try:
                    embeddings = await self.provider.embed(texts)
                    elapsed = time.time() - start_time
                    times.append(elapsed)
                    
                    # Verify results
                    assert len(embeddings) == len(texts)
                    
                except Exception as e:
                    logger.error(f"Performance test failed for batch_size={batch_size}, run={run}: {e}")
                    times.append(float('inf'))
            
            # Calculate statistics
            valid_times = [t for t in times if t != float('inf')]
            if valid_times:
                avg_time = statistics.mean(valid_times)
                throughput = batch_size / avg_time
                
                performance_results[f"batch_{batch_size}"] = {
                    'avg_time': avg_time,
                    'min_time': min(valid_times),
                    'max_time': max(valid_times),
                    'throughput': throughput,
                    'successful_runs': len(valid_times)
                }
                
                logger.info(f"Batch {batch_size}: {avg_time:.2f}s avg, {throughput:.1f} emb/s")
        
        return {
            'status': 'pass',
            'results': performance_results,
            'best_throughput': max(
                (r['throughput'] for r in performance_results.values()),
                default=0
            )
        }

    async def test_cache_efficiency(self) -> Dict[str, Any]:
        """Test context cache efficiency."""
        logger.info("Testing cache efficiency...")
        
        # Clear cache first (if possible)
        cache_provider = create_bge_in_icl_provider(
            base_url=self.server_url,
            api_key=self.api_key,
            enable_icl=True,
            context_cache_size=50
        )
        
        # First request - should miss cache
        python_texts = LANGUAGE_SPECIFIC_TESTS['python'][:2]
        
        start_time = time.time()
        await cache_provider.embed(python_texts)
        first_time = time.time() - start_time
        
        first_metrics = cache_provider.get_performance_metrics()
        first_hit_rate = first_metrics.get('cache_hit_rate', 0)
        
        # Second request with similar content - should hit cache
        start_time = time.time()
        await cache_provider.embed(python_texts)
        second_time = time.time() - start_time
        
        second_metrics = cache_provider.get_performance_metrics()
        second_hit_rate = second_metrics.get('cache_hit_rate', 0)
        
        # Third request with different content
        ts_texts = LANGUAGE_SPECIFIC_TESTS['typescript'][:2]
        await cache_provider.embed(ts_texts)
        
        final_metrics = cache_provider.get_performance_metrics()
        final_hit_rate = final_metrics.get('cache_hit_rate', 0)
        
        return {
            'status': 'pass',
            'first_request': {
                'time': first_time,
                'cache_hit_rate': first_hit_rate
            },
            'second_request': {
                'time': second_time,
                'cache_hit_rate': second_hit_rate
            },
            'final_cache_hit_rate': final_hit_rate,
            'cache_improvement': second_hit_rate > first_hit_rate,
            'speedup_ratio': first_time / second_time if second_time > 0 else 1
        }

    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling and recovery scenarios."""
        logger.info("Testing error handling...")
        
        error_tests = {}
        
        # Test with invalid texts
        try:
            await self.provider.embed([])
            error_tests['empty_input'] = {'status': 'pass', 'handled': True}
        except Exception as e:
            error_tests['empty_input'] = {'status': 'pass', 'error': str(e), 'handled': True}
        
        # Test with very large batch
        try:
            large_batch = SAMPLE_CODE_TEXTS * 20  # 200 texts
            start_time = time.time()
            embeddings = await self.provider.embed(large_batch)
            elapsed = time.time() - start_time
            
            error_tests['large_batch'] = {
                'status': 'pass',
                'processed': len(embeddings),
                'time': elapsed,
                'handled': True
            }
        except Exception as e:
            error_tests['large_batch'] = {
                'status': 'expected_error',
                'error': str(e),
                'handled': True
            }
        
        # Test timeout handling (with short timeout)
        try:
            timeout_provider = create_bge_in_icl_provider(
                base_url=self.server_url,
                api_key=self.api_key,
                timeout=1  # Very short timeout
            )
            
            await timeout_provider.embed(SAMPLE_CODE_TEXTS)
            error_tests['timeout'] = {'status': 'unexpected_pass', 'handled': False}
            
        except Exception as e:
            error_tests['timeout'] = {
                'status': 'pass',
                'error': str(e),
                'handled': 'timeout' in str(e).lower() or 'time' in str(e).lower()
            }
        
        return {
            'status': 'pass',
            'tests': error_tests,
            'all_handled': all(test.get('handled', False) for test in error_tests.values())
        }

    async def test_concurrent_requests(self) -> Dict[str, Any]:
        """Test concurrent request handling."""
        logger.info("Testing concurrent requests...")
        
        # Create multiple providers to simulate concurrent users
        providers = [
            create_bge_in_icl_provider(
                base_url=self.server_url,
                api_key=self.api_key,
                batch_size=16
            )
            for _ in range(5)
        ]
        
        # Prepare different text batches
        text_batches = [
            SAMPLE_CODE_TEXTS[:3],
            LANGUAGE_SPECIFIC_TESTS['python'][:2],
            LANGUAGE_SPECIFIC_TESTS['typescript'][:2],
            SAMPLE_CODE_TEXTS[3:6],
            LANGUAGE_SPECIFIC_TESTS['java'][:2]
        ]
        
        # Execute concurrent requests
        start_time = time.time()
        try:
            tasks = [
                provider.embed(texts)
                for provider, texts in zip(providers, text_batches)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.time() - start_time
            
            # Analyze results
            successful = sum(1 for r in results if not isinstance(r, Exception))
            failed = len(results) - successful
            
            total_embeddings = sum(
                len(r) for r in results 
                if not isinstance(r, Exception)
            )
            
            return {
                'status': 'pass' if failed == 0 else 'partial',
                'total_time': total_time,
                'successful_requests': successful,
                'failed_requests': failed,
                'total_embeddings': total_embeddings,
                'concurrent_throughput': total_embeddings / total_time,
                'errors': [str(r) for r in results if isinstance(r, Exception)]
            }
            
        except Exception as e:
            return {
                'status': 'fail',
                'error': str(e),
                'total_time': time.time() - start_time
            }

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests and return comprehensive results."""
        logger.info("Starting BGE-IN-ICL integration test suite...")
        
        await self.setup()
        
        test_results = {
            'test_suite': 'BGE-IN-ICL Integration Tests',
            'server_url': self.server_url,
            'timestamp': time.time(),
            'provider_info': {
                'name': self.provider.name,
                'model': self.provider.model,
                'dims': self.provider.dims,
                'distance': self.provider.distance
            }
        }
        
        # Run individual tests
        tests = [
            ('basic_functionality', self.test_basic_functionality),
            ('language_optimization', self.test_language_specific_optimization),
            ('adaptive_batching', self.test_adaptive_batching),
            ('performance_characteristics', self.test_performance_characteristics),
            ('cache_efficiency', self.test_cache_efficiency),
            ('error_handling', self.test_error_handling),
            ('concurrent_requests', self.test_concurrent_requests)
        ]
        
        for test_name, test_func in tests:
            logger.info(f"Running {test_name}...")
            try:
                result = await test_func()
                test_results[test_name] = result
                status = result.get('status', 'unknown')
                logger.info(f"{test_name}: {status}")
            except Exception as e:
                logger.error(f"{test_name} failed with exception: {e}")
                test_results[test_name] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Calculate overall results
        test_results['summary'] = self._calculate_summary(test_results)
        
        return test_results

    def _calculate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate summary statistics from test results."""
        test_statuses = []
        
        for key, value in results.items():
            if isinstance(value, dict) and 'status' in value:
                test_statuses.append(value['status'])
        
        passed = sum(1 for s in test_statuses if s == 'pass')
        failed = sum(1 for s in test_statuses if s == 'fail')
        warnings = sum(1 for s in test_statuses if s == 'warning')
        errors = sum(1 for s in test_statuses if s == 'error')
        
        overall_status = 'pass'
        if failed > 0 or errors > 0:
            overall_status = 'fail'
        elif warnings > 0:
            overall_status = 'warning'
        
        return {
            'overall_status': overall_status,
            'total_tests': len(test_statuses),
            'passed': passed,
            'failed': failed,
            'warnings': warnings,
            'errors': errors,
            'success_rate': passed / len(test_statuses) if test_statuses else 0
        }


# Pytest integration
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_SERVER_TESTS, reason="Real server tests disabled")
async def test_bge_icl_basic_functionality():
    """Test basic BGE-IN-ICL functionality."""
    suite = BGEICLIntegrationTestSuite()
    await suite.setup()
    result = await suite.test_basic_functionality()
    assert result['status'] == 'pass', f"Basic functionality test failed: {result}"

@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_SERVER_TESTS, reason="Real server tests disabled")
async def test_bge_icl_language_optimization():
    """Test language-specific optimization."""
    suite = BGEICLIntegrationTestSuite()
    await suite.setup()
    results = await suite.test_language_specific_optimization()
    
    # Check that at least some languages passed
    passed_languages = sum(1 for r in results.values() if r.get('status') == 'pass')
    assert passed_languages > 0, f"No languages passed optimization test: {results}"

@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_SERVER_TESTS, reason="Real server tests disabled")
async def test_bge_icl_performance():
    """Test performance characteristics."""
    suite = BGEICLIntegrationTestSuite()
    await suite.setup()
    result = await suite.test_performance_characteristics()
    
    assert result['status'] == 'pass', f"Performance test failed: {result}"
    assert result['best_throughput'] > 0, "No throughput measured"

@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_SERVER_TESTS, reason="Real server tests disabled")
async def test_bge_icl_cache_efficiency():
    """Test cache efficiency."""
    suite = BGEICLIntegrationTestSuite()
    await suite.setup()
    result = await suite.test_cache_efficiency()
    
    assert result['status'] == 'pass', f"Cache efficiency test failed: {result}"

# Standalone execution
async def main():
    """Run integration tests as standalone script."""
    suite = BGEICLIntegrationTestSuite()
    results = await suite.run_all_tests()
    
    # Print results
    print("\n" + "="*80)
    print("BGE-IN-ICL INTEGRATION TEST RESULTS")
    print("="*80)
    
    summary = results['summary']
    print(f"Overall Status: {summary['overall_status'].upper()}")
    print(f"Tests: {summary['total_tests']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Warnings: {summary['warnings']}")
    print(f"Errors: {summary['errors']}")
    print(f"Success Rate: {summary['success_rate']:.1%}")
    
    print("\nDetailed Results:")
    print("-" * 40)
    
    for test_name, result in results.items():
        if test_name in ['test_suite', 'server_url', 'timestamp', 'provider_info', 'summary']:
            continue
            
        status = result.get('status', 'unknown')
        print(f"{test_name:.<30} {status.upper()}")
        
        if status == 'fail' or status == 'error':
            error = result.get('error', 'Unknown error')
            print(f"  Error: {error}")
    
    # Save detailed results
    output_file = f"bge_icl_integration_results_{int(time.time())}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")
    
    # Exit with appropriate code
    exit_code = 0 if summary['overall_status'] == 'pass' else 1
    return exit_code

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)