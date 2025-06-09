#!/usr/bin/env python3
"""
BGE-IN-ICL Performance Benchmarking Script

Comprehensive performance benchmarking tool for BGE-IN-ICL deployments.
Measures throughput, latency, cache efficiency, and adaptive batching performance.
"""

import asyncio
import time
import statistics
import json
import csv
import argparse
import sys
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

# Import BGE-IN-ICL components
try:
    from chunkhound.embeddings import create_bge_in_icl_provider, BGEInICLProvider
except ImportError:
    print("Error: chunkhound package not found. Please install chunkhound first.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class BenchmarkConfig:
    """Configuration for benchmark tests."""
    server_url: str
    api_key: Optional[str] = None
    batch_sizes: List[int] = None
    languages: List[str] = None
    runs_per_test: int = 5
    warmup_runs: int = 2
    timeout: int = 300
    enable_icl: bool = True
    adaptive_batching: bool = True
    context_cache_size: int = 100
    output_format: str = 'json'  # json, csv, both
    output_file: Optional[str] = None
    verbose: bool = False

    def __post_init__(self):
        if self.batch_sizes is None:
            self.batch_sizes = [1, 5, 10, 25, 50, 100]
        if self.languages is None:
            self.languages = ['auto', 'python', 'typescript', 'java', 'csharp']

@dataclass
class BenchmarkResult:
    """Results from a single benchmark test."""
    test_name: str
    language: str
    batch_size: int
    enable_icl: bool
    adaptive_batching: bool
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    std_response_time: float
    throughput: float  # embeddings per second
    cache_hit_rate: float
    current_batch_size: int
    successful_runs: int
    failed_runs: int
    timestamp: float

class BGEICLBenchmark:
    """BGE-IN-ICL performance benchmark suite."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.results: List[BenchmarkResult] = []
        self.test_data = self._generate_test_data()

    def _generate_test_data(self) -> Dict[str, List[str]]:
        """Generate test data for different programming languages."""
        return {
            'auto': [
                "def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
                "class DataProcessor: def __init__(self): self.data = []",
                "async function fetchData() { return await api.get('/data'); }",
                "public class Calculator { public int add(int a, int b) { return a + b; } }",
                "interface User { id: number; name: string; email: string; }",
                "from typing import List, Optional, Dict",
                "const users = await db.users.findMany({ where: { active: true } })",
                "try { const result = JSON.parse(data); } catch (error) { console.error(error); }",
                "SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id",
                "import React, { useState, useEffect } from 'react'",
                "public async Task<User> GetUserAsync(int id) { return await _repo.FindAsync(id); }",
                "class ApiService { constructor(private http: HttpClient) {} }",
                "def process_data(data: List[str]) -> Dict[str, Any]: return {'count': len(data)}",
                "const handleSubmit = async (event: FormEvent) => { event.preventDefault(); }",
                "public interface IUserRepository { Task<User> FindByIdAsync(int id); }",
                "@Component\npublic class UserController { @Autowired private UserService service; }",
                "type EventHandler<T> = (event: T) => void;",
                "async def fetch_user_data(user_id: int) -> Optional[UserData]: pass",
                "public class UserService : IUserService { private readonly IRepository _repo; }",
                "const useUserData = (userId: number) => { const [user, setUser] = useState(null); }"
            ],
            'python': [
                "def process_data(data: List[str]) -> Dict[str, int]:",
                "class APIClient:\n    def __init__(self, base_url: str):",
                "async def fetch_user(user_id: int) -> Optional[User]:",
                "from dataclasses import dataclass\n@dataclass\nclass Config:",
                "@pytest.fixture\ndef client():\n    return TestClient(app)",
                "def calculate_metrics(values: List[float]) -> Tuple[float, float]:",
                "class DatabaseManager:\n    async def connect(self) -> None:",
                "import asyncio\nfrom typing import AsyncGenerator",
                "def validate_email(email: str) -> bool:\n    return '@' in email",
                "with open('data.json', 'r') as f:\n    data = json.load(f)",
                "logger = logging.getLogger(__name__)",
                "async with aiohttp.ClientSession() as session:",
                "class UserRepository:\n    def __init__(self, db: Database):",
                "def fibonacci(n: int) -> int:\n    if n <= 1: return n",
                "from pydantic import BaseModel, Field",
                "async def process_batch(items: List[Item]) -> List[Result]:",
                "def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:",
                "class EventProcessor:\n    def handle_event(self, event: Event):",
                "import pandas as pd\ndf = pd.read_csv('data.csv')",
                "async def stream_data() -> AsyncGenerator[bytes, None]:"
            ],
            'typescript': [
                "interface APIResponse<T> { data: T; status: number; }",
                "const fetchUser = async (id: number): Promise<User> => {",
                "type EventHandler = (event: Event) => void;",
                "export class UserService { private api: APIClient; }",
                "const useEffect = (callback: () => void, deps: any[]) => {",
                "interface DatabaseConfig { host: string; port: number; }",
                "const processData = <T>(items: T[]): ProcessedData<T> => {",
                "export async function validateSchema(data: unknown): Promise<boolean> {",
                "const createLogger = (name: string): Logger => {",
                "type AsyncFunction<T> = (...args: any[]) => Promise<T>;",
                "interface Repository<T> { findById(id: string): Promise<T | null>; }",
                "const withRetry = async <T>(fn: () => Promise<T>, retries: number): Promise<T> => {",
                "export class EventEmitter<T extends Record<string, any>> {",
                "const isValidEmail = (email: string): boolean => /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email);",
                "interface PaginatedResponse<T> { items: T[]; total: number; page: number; }",
                "const createAsyncThunk = <T, U>(typePrefix: string, payloadCreator: (arg: T) => Promise<U>) => {",
                "export type DeepPartial<T> = { [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P]; };",
                "const debounce = <T extends (...args: any[]) => any>(func: T, delay: number): T => {",
                "interface GraphQLResponse<T> { data?: T; errors?: GraphQLError[]; }",
                "const mapAsync = async <T, U>(items: T[], mapper: (item: T) => Promise<U>): Promise<U[]> => {"
            ],
            'java': [
                "public class UserRepository implements Repository<User> {",
                "@Service\npublic class UserService {",
                "public Optional<User> findById(Long id) {",
                "@Entity\npublic class User { @Id private Long id; }",
                "@RestController\npublic class UserController {",
                "public CompletableFuture<List<User>> findUsersAsync() {",
                "@Configuration\npublic class DatabaseConfig {",
                "public class ValidationException extends RuntimeException {",
                "@Component\npublic class EventProcessor {",
                "public interface UserRepository extends JpaRepository<User, Long> {",
                "@Transactional\npublic void updateUser(User user) {",
                "public class AsyncTaskExecutor implements TaskExecutor {",
                "@Cacheable(\"users\")\npublic User getUserById(Long id) {",
                "public Stream<User> findActiveUsers() {",
                "@EventListener\npublic void handleUserCreated(UserCreatedEvent event) {",
                "public class UserMapper { public static UserDto toDto(User user) {",
                "@Value(\"${app.database.url}\")\nprivate String databaseUrl;",
                "public class RetryableOperation<T> {",
                "@Scheduled(fixedRate = 30000)\npublic void cleanupExpiredSessions() {",
                "public class GenericResponse<T> { private T data; private String message; }"
            ],
            'csharp': [
                "public class UserController : ControllerBase {",
                "public async Task<User> GetUserAsync(int id) {",
                "public interface IUserRepository { Task<User> FindAsync(int id); }",
                "[HttpGet]\npublic ActionResult<User> GetUser(int id) {",
                "public class UserService : IUserService {",
                "public async Task<IEnumerable<User>> GetUsersAsync() {",
                "[ApiController, Route(\"[controller]\")]\npublic class UsersController {",
                "public class DatabaseContext : DbContext {",
                "public class ConfigurationService : IConfigurationService {",
                "[Authorize]\npublic async Task<IActionResult> CreateUser([FromBody] CreateUserRequest request) {",
                "public class EventHandler : IEventHandler<UserCreatedEvent> {",
                "public async Task<Result<T>> ExecuteAsync<T>(Func<Task<T>> operation) {",
                "public class CacheService : ICacheService {",
                "public class ValidationAttribute : Attribute {",
                "[ServiceContract]\npublic interface IUserService {",
                "public class GenericRepository<T> : IRepository<T> where T : class {",
                "public async Task<PagedResult<T>> GetPagedAsync<T>(int page, int size) {",
                "public class BackgroundTaskService : BackgroundService {",
                "[JsonPropertyName(\"user_id\")]\npublic int UserId { get; set; }",
                "public class DependencyInjectionExtensions {"
            ]
        }

    async def create_provider(self, language: str = 'auto', batch_size: int = 50) -> BGEInICLProvider:
        """Create a BGE-IN-ICL provider with specified configuration."""
        return create_bge_in_icl_provider(
            base_url=self.config.server_url,
            api_key=self.config.api_key,
            language=language,
            enable_icl=self.config.enable_icl,
            adaptive_batching=self.config.adaptive_batching,
            batch_size=batch_size,
            timeout=self.config.timeout,
            context_cache_size=self.config.context_cache_size
        )

    async def run_single_test(
        self, 
        provider: BGEInICLProvider, 
        texts: List[str], 
        test_name: str
    ) -> Tuple[float, Dict[str, Any]]:
        """Run a single benchmark test and return timing and metrics."""
        start_time = time.time()
        
        try:
            embeddings = await provider.embed(texts)
            elapsed = time.time() - start_time
            
            # Verify results
            if len(embeddings) != len(texts):
                raise ValueError(f"Expected {len(texts)} embeddings, got {len(embeddings)}")
            
            # Get performance metrics
            metrics = provider.get_performance_metrics()
            
            return elapsed, metrics
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Test {test_name} failed: {e}")
            raise

    async def benchmark_batch_size(self, language: str, batch_size: int) -> BenchmarkResult:
        """Benchmark a specific batch size for a language."""
        test_name = f"batch_size_{batch_size}"
        logger.info(f"Benchmarking {language} with batch size {batch_size}")
        
        provider = await self.create_provider(language=language, batch_size=batch_size)
        
        # Get test texts
        available_texts = self.test_data.get(language, self.test_data['auto'])
        
        # Create batch by repeating texts if necessary
        if batch_size <= len(available_texts):
            texts = available_texts[:batch_size]
        else:
            # Repeat texts to reach desired batch size
            texts = []
            while len(texts) < batch_size:
                texts.extend(available_texts)
            texts = texts[:batch_size]
        
        # Add some variation to avoid cache hits
        texts = [f"// Batch {batch_size} - {i}\n{text}" for i, text in enumerate(texts)]
        
        # Warmup runs
        for i in range(self.config.warmup_runs):
            try:
                await self.run_single_test(provider, texts[:min(5, len(texts))], f"warmup_{i}")
            except Exception as e:
                logger.warning(f"Warmup run {i} failed: {e}")
        
        # Actual benchmark runs
        times = []
        metrics_list = []
        failed_runs = 0
        
        for run in range(self.config.runs_per_test):
            try:
                elapsed, metrics = await self.run_single_test(provider, texts, f"{test_name}_run_{run}")
                times.append(elapsed)
                metrics_list.append(metrics)
                
                if self.config.verbose:
                    throughput = len(texts) / elapsed
                    cache_hit_rate = metrics.get('cache_hit_rate', 0)
                    logger.info(f"  Run {run + 1}: {elapsed:.2f}s, {throughput:.1f} emb/s, cache: {cache_hit_rate:.1%}")
                
            except Exception as e:
                logger.error(f"Run {run} failed: {e}")
                failed_runs += 1
        
        if not times:
            raise ValueError(f"All runs failed for batch size {batch_size}")
        
        # Calculate statistics
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        std_time = statistics.stdev(times) if len(times) > 1 else 0
        throughput = batch_size / avg_time
        
        # Average metrics across successful runs
        avg_cache_hit_rate = statistics.mean([m.get('cache_hit_rate', 0) for m in metrics_list])
        avg_current_batch_size = statistics.mean([m.get('current_batch_size', batch_size) for m in metrics_list])
        
        return BenchmarkResult(
            test_name=test_name,
            language=language,
            batch_size=batch_size,
            enable_icl=self.config.enable_icl,
            adaptive_batching=self.config.adaptive_batching,
            avg_response_time=avg_time,
            min_response_time=min_time,
            max_response_time=max_time,
            std_response_time=std_time,
            throughput=throughput,
            cache_hit_rate=avg_cache_hit_rate,
            current_batch_size=int(avg_current_batch_size),
            successful_runs=len(times),
            failed_runs=failed_runs,
            timestamp=time.time()
        )

    async def benchmark_language(self, language: str) -> List[BenchmarkResult]:
        """Benchmark all batch sizes for a specific language."""
        logger.info(f"Benchmarking language: {language}")
        results = []
        
        for batch_size in self.config.batch_sizes:
            try:
                result = await self.benchmark_batch_size(language, batch_size)
                results.append(result)
                logger.info(f"  Batch {batch_size}: {result.throughput:.1f} emb/s")
            except Exception as e:
                logger.error(f"  Batch {batch_size} failed: {e}")
        
        return results

    async def run_all_benchmarks(self) -> List[BenchmarkResult]:
        """Run comprehensive benchmarks for all configurations."""
        logger.info("Starting BGE-IN-ICL performance benchmarks")
        logger.info(f"Server: {self.config.server_url}")
        logger.info(f"Languages: {self.config.languages}")
        logger.info(f"Batch sizes: {self.config.batch_sizes}")
        logger.info(f"Runs per test: {self.config.runs_per_test}")
        
        all_results = []
        
        for language in self.config.languages:
            try:
                results = await self.benchmark_language(language)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Language {language} benchmarks failed: {e}")
        
        self.results = all_results
        return all_results

    def analyze_results(self) -> Dict[str, Any]:
        """Analyze benchmark results and generate insights."""
        if not self.results:
            return {}
        
        analysis = {
            'summary': {
                'total_tests': len(self.results),
                'languages_tested': len(set(r.language for r in self.results)),
                'batch_sizes_tested': len(set(r.batch_size for r in self.results)),
                'total_successful_runs': sum(r.successful_runs for r in self.results),
                'total_failed_runs': sum(r.failed_runs for r in self.results)
            },
            'performance': {
                'best_throughput': max(r.throughput for r in self.results),
                'worst_throughput': min(r.throughput for r in self.results),
                'avg_throughput': statistics.mean([r.throughput for r in self.results]),
                'best_latency': min(r.avg_response_time for r in self.results),
                'worst_latency': max(r.avg_response_time for r in self.results),
                'avg_latency': statistics.mean([r.avg_response_time for r in self.results])
            },
            'cache_performance': {
                'avg_cache_hit_rate': statistics.mean([r.cache_hit_rate for r in self.results]),
                'best_cache_hit_rate': max(r.cache_hit_rate for r in self.results),
                'worst_cache_hit_rate': min(r.cache_hit_rate for r in self.results)
            }
        }
        
        # Find optimal configurations
        best_throughput_result = max(self.results, key=lambda r: r.throughput)
        best_latency_result = min(self.results, key=lambda r: r.avg_response_time)
        
        analysis['recommendations'] = {
            'best_throughput_config': {
                'language': best_throughput_result.language,
                'batch_size': best_throughput_result.batch_size,
                'throughput': best_throughput_result.throughput,
                'latency': best_throughput_result.avg_response_time
            },
            'best_latency_config': {
                'language': best_latency_result.language,
                'batch_size': best_latency_result.batch_size,
                'throughput': best_latency_result.throughput,
                'latency': best_latency_result.avg_response_time
            }
        }
        
        # Language-specific analysis
        analysis['by_language'] = {}
        for language in set(r.language for r in self.results):
            lang_results = [r for r in self.results if r.language == language]
            analysis['by_language'][language] = {
                'best_throughput': max(r.throughput for r in lang_results),
                'best_latency': min(r.avg_response_time for r in lang_results),
                'optimal_batch_size': max(lang_results, key=lambda r: r.throughput).batch_size,
                'avg_cache_hit_rate': statistics.mean([r.cache_hit_rate for r in lang_results])
            }
        
        return analysis

    def save_results(self, filename: Optional[str] = None) -> str:
        """Save benchmark results to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bge_icl_benchmark_{timestamp}"
        
        # Remove extension if provided
        base_filename = filename.replace('.json', '').replace('.csv', '')
        
        saved_files = []
        
        # Save JSON format
        if self.config.output_format in ['json', 'both']:
            json_file = f"{base_filename}.json"
            data = {
                'config': asdict(self.config),
                'results': [asdict(r) for r in self.results],
                'analysis': self.analyze_results(),
                'timestamp': time.time(),
                'benchmark_info': {
                    'total_duration': sum(r.avg_response_time * r.successful_runs for r in self.results),
                    'total_embeddings': sum(r.batch_size * r.successful_runs for r in self.results)
                }
            }
            
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=2)
            saved_files.append(json_file)
        
        # Save CSV format
        if self.config.output_format in ['csv', 'both']:
            csv_file = f"{base_filename}.csv"
            
            with open(csv_file, 'w', newline='') as f:
                if self.results:
                    writer = csv.DictWriter(f, fieldnames=asdict(self.results[0]).keys())
                    writer.writeheader()
                    for result in self.results:
                        writer.writerow(asdict(result))
            saved_files.append(csv_file)
        
        return saved_files

    def print_summary(self):
        """Print a summary of benchmark results."""
        if not self.results:
            print("No benchmark results available.")
            return
        
        analysis = self.analyze_results()
        
        print("\n" + "="*80)
        print("BGE-IN-ICL PERFORMANCE BENCHMARK RESULTS")
        print("="*80)
        
        # Summary statistics
        summary = analysis['summary']
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Languages: {summary['languages_tested']}")
        print(f"Batch Sizes: {summary['batch_sizes_tested']}")
        print(f"Successful Runs: {summary['total_successful_runs']}")
        print(f"Failed Runs: {summary['total_failed_runs']}")
        
        # Performance overview
        perf = analysis['performance']
        print(f"\nPerformance Overview:")
        print(f"  Best Throughput: {perf['best_throughput']:.1f} embeddings/sec")
        print(f"  Average Throughput: {perf['avg_throughput']:.1f} embeddings/sec")
        print(f"  Best Latency: {perf['best_latency']:.3f} seconds")
        print(f"  Average Latency: {perf['avg_latency']:.3f} seconds")
        
        # Cache performance
        cache = analysis['cache_performance']
        print(f"\nCache Performance:")
        print(f"  Average Hit Rate: {cache['avg_cache_hit_rate']:.1%}")
        print(f"  Best Hit Rate: {cache['best_cache_hit_rate']:.1%}")
        
        # Recommendations
        recommendations = analysis['recommendations']
        print(f"\nRecommendations:")
        best_throughput = recommendations['best_throughput_config']
        print(f"  For Maximum Throughput: {best_throughput['language']} with batch size {best_throughput['batch_size']} ({best_throughput['throughput']:.1f} emb/s)")
        
        best_latency = recommendations['best_latency_config']
        print(f"  For Minimum Latency: {best_latency['language']} with batch size {best_latency['batch_size']} ({best_latency['latency']:.3f}s)")
        
        # Language breakdown
        print(f"\nLanguage Performance:")
        for language, lang_data in analysis['by_language'].items():
            print(f"  {language:.<20} Best: {lang_data['best_throughput']:.1f} emb/s (batch {lang_data['optimal_batch_size']})")


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(description="BGE-IN-ICL Performance Benchmark Tool")
    
    parser.add_argument(
        "server_url",
        help="BGE-IN-ICL server URL (e.g., http://localhost:8080)"
    )
    
    parser.add_argument(
        "--api-key",
        help="API key for authentication"
    )
    
    parser.add_argument(
        "--batch-sizes",
        nargs="+",
        type=int,
        default=[1, 5, 10, 25, 50, 100],
        help="Batch sizes to test (default: 1 5 10 25 50 100)"
    )
    
    parser.add_argument(
        "--languages",
        nargs="+",
        default=['auto', 'python', 'typescript', 'java', 'csharp'],
        help="Languages to test (default: auto python typescript java csharp)"
    )
    
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of runs per test (default: 5)"
    )
    
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=2,
        help="Number of warmup runs (default: 2)"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Request timeout in seconds (default: 300)"
    )
    
    parser.add_argument(
        "--disable-icl",
        action="store_true",
        help="Disable in-context learning"
    )
    
    parser.add_argument(
        "--disable-adaptive-batching",
        action="store_true",
        help="Disable adaptive batching"
    )
    
    parser.add_argument(
        "--cache-size",
        type=int,
        default=100,
        help="Context cache size (default: 100)"
    )
    
    parser.add_argument(
        "--output-format",
        choices=['json', 'csv', 'both'],
        default='json',
        help="Output format (default: json)"
    )
    
    parser.add_argument(
        "--output-file",
        help="Output file name (without extension)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    return parser


async def main():
    """Main entry point for the benchmark tool."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Create benchmark configuration
    config = BenchmarkConfig(
        server_url=args.server_url,
        api_key=args.api_key,
        batch_sizes=args.batch_sizes,
        languages=args.languages,
        runs_per_test=args.runs,
        warmup_runs=args.warmup_runs,
        timeout=args.timeout,
        enable_icl=not args.disable_icl,
        adaptive_batching=not args.disable_adaptive_batching,
        context_cache_size=args.cache_size,
        output_format=args.output_format,
        output_file=args.output_file,
        verbose=args.verbose
    )
    
    # Set logging level based on verbosity
    if config.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run benchmark
    benchmark = BGEICLBenchmark(config)
    
    try:
        # Run benchmarks
        start_time = time.time()
        results = await benchmark.run_all_benchmarks()
        total_time = time.time() - start_time
        
        if not results:
            print("No benchmark results generated.")
            return 1
        
        # Print summary
        benchmark.print_summary()
        
        print(f"\nBenchmark completed in {total_time:.1f} seconds")
        
        # Save results
        saved_files = benchmark.save_results(config.output_file)
        print(f"\nResults saved to: {', '.join(saved_files)}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user.")
        return 1
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)