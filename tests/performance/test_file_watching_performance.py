"""
Performance tests for MCP file watching functionality.

Tests scalability and performance characteristics:
- High-frequency file changes
- Large file processing
- Memory usage monitoring
- Task queue performance under load
- Concurrent operations throughput
"""

import asyncio
import pytest
import tempfile
import time
import psutil
import os
from pathlib import Path
from typing import List, Dict

from tests.fixtures.mcp_testing import temp_project_with_monitoring, file_operations
from tests.utils.file_watching_helpers import (
    FileOperationGenerator,
    execute_file_operations,
    generate_unique_content,
    wait_for_file_processing,
)


class TestHighFrequencyChanges:
    """Test performance under high-frequency file changes."""

    @pytest.mark.asyncio
    async def test_rapid_file_modifications_performance(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test performance with rapid file modifications."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server for performance test")

        try:
            await asyncio.sleep(3)

            # Create initial file
            test_file = file_operations.create_file(
                "rapid_perf.py", generate_unique_content("initial")
            )

            # Wait for initial indexing
            await asyncio.sleep(2)

            # Perform rapid modifications
            start_time = time.time()
            modification_count = 20

            for i in range(modification_count):
                content = generate_unique_content(f"rapid_{i}")
                file_operations.modify_file(test_file, content)
                await asyncio.sleep(0.1)  # 10 changes per second

            # Wait for processing to complete
            await asyncio.sleep(10)

            end_time = time.time()
            total_time = end_time - start_time

            # Performance assertion - should handle 20 changes in reasonable time
            assert total_time < 60, f"Rapid modifications took too long: {total_time}s"

            # Server should still be running
            assert fixture.process.poll() is None, "Server should handle rapid changes"

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_bulk_file_creation_performance(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test performance with bulk file creation."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server for performance test")

        try:
            await asyncio.sleep(3)

            # Create many files rapidly
            file_count = 30
            start_time = time.time()

            created_files = []
            for i in range(file_count):
                content = generate_unique_content(f"bulk_{i}")
                created_file = file_operations.create_file(f"bulk_{i}.py", content)
                created_files.append(created_file)
                await asyncio.sleep(0.05)  # 20 files per second

            # Wait for processing
            await asyncio.sleep(15)

            end_time = time.time()
            total_time = end_time - start_time

            # Performance check
            files_per_second = file_count / total_time
            assert files_per_second > 1, (
                f"File creation rate too slow: {files_per_second} files/sec"
            )

            # Server should be responsive
            assert fixture.process.poll() is None, (
                "Server should handle bulk file creation"
            )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_concurrent_file_operations_throughput(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test throughput of concurrent file operations."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server for performance test")

        try:
            await asyncio.sleep(3)

            # Create concurrent operations
            operation_count = 15
            start_time = time.time()

            async def create_and_modify_file(index):
                """Create and modify a file."""
                # Create file
                content = generate_unique_content(f"concurrent_{index}")
                file_path = file_operations.create_file(
                    f"concurrent_{index}.py", content
                )

                await asyncio.sleep(0.2)

                # Modify file
                modified_content = generate_unique_content(f"modified_{index}")
                file_operations.modify_file(file_path, modified_content)

                return file_path

            # Run concurrent operations
            tasks = [create_and_modify_file(i) for i in range(operation_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Wait for processing
            await asyncio.sleep(10)

            end_time = time.time()
            total_time = end_time - start_time

            # Check for exceptions
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0, (
                f"Concurrent operations had {len(exceptions)} exceptions"
            )

            # Performance check
            ops_per_second = (operation_count * 2) / total_time  # 2 ops per task
            assert ops_per_second > 2, (
                f"Concurrent throughput too low: {ops_per_second} ops/sec"
            )

            assert fixture.process.poll() is None, (
                "Server should handle concurrent operations"
            )

        finally:
            await fixture.stop_mcp_server()


class TestLargeFilePerformance:
    """Test performance with large files."""

    @pytest.mark.asyncio
    async def test_large_file_processing_time(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test processing time for large files."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server for performance test")

        try:
            await asyncio.sleep(3)

            # Create large file content
            large_content = "# Large file\n"
            for i in range(1000):
                large_content += f"""
def function_{i}():
    '''Function number {i}'''
    return "result_{i}"
    
class Class_{i}:
    '''Class number {i}'''
    def method_{i}(self):
        return "method_{i}_result"
"""

            # Measure processing time
            start_time = time.time()

            large_file = file_operations.create_file(
                "large_performance.py", large_content
            )

            # Wait for processing with extended timeout
            processed = await wait_for_file_processing(
                large_file, "function_0", fixture.db_path, timeout=30.0
            )

            end_time = time.time()
            processing_time = end_time - start_time

            # Performance assertions
            assert processed, "Large file should be processed successfully"
            assert processing_time < 60, (
                f"Large file processing took too long: {processing_time}s"
            )

            # File size performance metric
            file_size_kb = len(large_content) / 1024
            kb_per_second = file_size_kb / processing_time

            assert kb_per_second > 1, f"Processing rate too slow: {kb_per_second} KB/s"

            assert fixture.process.poll() is None, "Server should handle large files"

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_multiple_large_files_memory_usage(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test memory usage with multiple large files."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server for performance test")

        try:
            await asyncio.sleep(3)

            # Get initial memory usage
            process = psutil.Process(fixture.process.pid)
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Create multiple large files
            large_files = []
            for i in range(5):
                # Create moderately large content
                content = f"# Large file {i}\n" + "print('line')\n" * 2000
                large_file = file_operations.create_file(f"large_{i}.py", content)
                large_files.append(large_file)

                await asyncio.sleep(1)  # Stagger creation

            # Wait for processing
            await asyncio.sleep(15)

            # Check memory usage
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            # Memory usage should be reasonable
            assert memory_increase < 500, (
                f"Memory usage increased too much: {memory_increase} MB"
            )

            assert fixture.process.poll() is None, (
                "Server should handle multiple large files"
            )

        finally:
            await fixture.stop_mcp_server()


class TestTaskQueuePerformance:
    """Test task queue performance under load."""

    @pytest.mark.asyncio
    async def test_task_queue_under_load(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test task queue performance under heavy load."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server for performance test")

        try:
            await asyncio.sleep(3)

            # Generate mixed operations to stress task queue
            operations = []

            # Create operations
            for i in range(20):
                operations.extend(
                    [
                        {
                            "type": "create",
                            "file_path": fixture.project_dir / f"queue_test_{i}.py",
                            "content": generate_unique_content(f"queue_{i}"),
                            "delay_after": 0.05,
                        },
                        {
                            "type": "modify",
                            "file_path": fixture.project_dir / f"queue_test_{i}.py",
                            "content": generate_unique_content(f"modified_queue_{i}"),
                            "delay_after": 0.05,
                        },
                    ]
                )

            # Execute operations rapidly
            start_time = time.time()
            await execute_file_operations(operations)

            # Wait for task queue to process everything
            await asyncio.sleep(20)

            end_time = time.time()
            total_time = end_time - start_time

            # Performance metrics
            total_operations = len(operations)
            ops_per_second = total_operations / total_time

            assert ops_per_second > 5, f"Task queue too slow: {ops_per_second} ops/sec"
            assert fixture.process.poll() is None, (
                "Server should handle task queue load"
            )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_queue_backpressure_handling(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test handling of queue backpressure."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server for performance test")

        try:
            await asyncio.sleep(3)

            # Create operations faster than they can be processed
            rapid_operations = []
            for i in range(50):
                rapid_operations.append(
                    {
                        "type": "create",
                        "file_path": fixture.project_dir / f"backpressure_{i}.py",
                        "content": generate_unique_content(f"backpressure_{i}"),
                        "delay_after": 0.01,  # Very rapid
                    }
                )

            # Execute very rapidly
            start_time = time.time()
            await execute_file_operations(rapid_operations)

            # Give time for queue to drain
            await asyncio.sleep(25)

            end_time = time.time()
            total_time = end_time - start_time

            # System should handle backpressure gracefully
            assert fixture.process.poll() is None, (
                "Server should handle queue backpressure"
            )

            # Should eventually process all operations
            processed_files = list(fixture.project_dir.glob("backpressure_*.py"))
            assert len(processed_files) == 50, (
                "All files should be created despite backpressure"
            )

        finally:
            await fixture.stop_mcp_server()


class TestResourceUtilization:
    """Test resource utilization patterns."""

    @pytest.mark.asyncio
    async def test_cpu_utilization_under_load(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test CPU utilization under file processing load."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server for performance test")

        try:
            await asyncio.sleep(3)

            # Monitor CPU usage
            process = psutil.Process(fixture.process.pid)
            cpu_samples = []

            # Create files while monitoring CPU
            async def monitor_cpu():
                for _ in range(20):  # 10 second monitoring
                    cpu_percent = process.cpu_percent()
                    cpu_samples.append(cpu_percent)
                    await asyncio.sleep(0.5)

            async def create_load():
                for i in range(30):
                    content = generate_unique_content(f"cpu_test_{i}")
                    file_operations.create_file(f"cpu_test_{i}.py", content)
                    await asyncio.sleep(0.2)

            # Run monitoring and load concurrently
            await asyncio.gather(monitor_cpu(), create_load())

            # Wait for processing to complete
            await asyncio.sleep(10)

            # Analyze CPU usage
            if cpu_samples:
                avg_cpu = sum(cpu_samples) / len(cpu_samples)
                max_cpu = max(cpu_samples)

                # CPU usage should be reasonable (not pegging CPU)
                assert max_cpu < 90, f"CPU usage too high: {max_cpu}%"
                assert avg_cpu < 50, f"Average CPU usage too high: {avg_cpu}%"

            assert fixture.process.poll() is None, (
                "Server should maintain reasonable CPU usage"
            )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_memory_stability_over_time(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test memory stability over extended operation."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server for performance test")

        try:
            await asyncio.sleep(3)

            process = psutil.Process(fixture.process.pid)
            memory_samples = []

            # Create sustained load and monitor memory
            for cycle in range(5):
                # Get memory before cycle
                memory_before = process.memory_info().rss / 1024 / 1024  # MB
                memory_samples.append(memory_before)

                # Create files in this cycle
                for i in range(10):
                    content = generate_unique_content(f"cycle_{cycle}_{i}")
                    file_operations.create_file(f"cycle_{cycle}_{i}.py", content)
                    await asyncio.sleep(0.1)

                # Wait for processing
                await asyncio.sleep(3)

                # Clean up some files to test memory release
                for i in range(5):
                    file_path = fixture.project_dir / f"cycle_{cycle}_{i}.py"
                    file_operations.delete_file(file_path)

                await asyncio.sleep(2)

            # Final memory check
            final_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Memory should be stable (not continuously growing)
            if len(memory_samples) > 2:
                memory_growth = final_memory - memory_samples[0]
                assert memory_growth < 200, (
                    f"Memory growth too high: {memory_growth} MB"
                )

            assert fixture.process.poll() is None, (
                "Server should maintain memory stability"
            )

        finally:
            await fixture.stop_mcp_server()
