#!/usr/bin/env python3
"""
Task Coordinator - Priority Queue System for MCP Server
Ensures search operations get priority over file processing operations.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

logger = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    """Task priority levels - lower numbers = higher priority."""

    HIGH = 1  # Search operations (regex, semantic)
    MEDIUM = 5  # Health checks, stats
    LOW = 10  # File updates, embeddings generation
    BACKGROUND = 20  # Periodic indexing, maintenance tasks


@dataclass
class Task:
    """Represents a task to be executed."""

    priority: TaskPriority
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    future: asyncio.Future | None = field(default=None)
    created_at: float = field(default_factory=time.time)

    def __lt__(self, other: "Task") -> bool:
        """Priority queue comparison - lower priority number = higher priority."""
        if self.priority != other.priority:
            return self.priority < other.priority
        # Secondary sort by creation time for same priority tasks
        return self.created_at < other.created_at


class TaskCoordinator:
    """
    Coordinates tasks with priority-based execution.
    Ensures user-facing operations (searches) get priority over background operations (file processing).
    """

    def __init__(self, max_queue_size: int = 1000):
        """
        Initialize task coordinator.

        Args:
            max_queue_size: Maximum number of tasks to queue before blocking
        """
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=max_queue_size
        )
        self._worker_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._running = False
        self._stats = {
            "tasks_queued": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "queue_size": 0,
        }

    async def start(self) -> None:
        """Start the task coordinator worker."""
        if self._running:
            return

        self._running = True
        self._shutdown_event.clear()
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("TaskCoordinator started")

    async def stop(self, timeout: float = 30.0) -> None:
        """
        Stop the task coordinator and drain remaining tasks.

        Args:
            timeout: Maximum time to wait for graceful shutdown
        """
        if not self._running:
            return

        logger.info("TaskCoordinator stopping...")
        self._running = False
        self._shutdown_event.set()

        # Wait for worker to finish current task and drain queue
        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "TaskCoordinator worker did not stop gracefully, cancelling"
                )
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass

        logger.info("TaskCoordinator stopped")

    async def queue_task(
        self,
        priority: TaskPriority,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Queue a task for execution with given priority.

        Args:
            priority: Task priority level
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Result of the function execution

        Raises:
            RuntimeError: If coordinator is not running
            asyncio.QueueFull: If queue is full
        """
        if not self._running:
            raise RuntimeError("TaskCoordinator is not running")

        future: asyncio.Future[Any] = asyncio.Future()
        task = Task(
            priority=priority, func=func, args=args, kwargs=kwargs, future=future
        )

        try:
            await self._queue.put(task)
            self._stats["tasks_queued"] += 1
            self._stats["queue_size"] = self._queue.qsize()

            # Wait for task completion
            return await future

        except asyncio.QueueFull:
            logger.error("Task queue is full, rejecting task")
            raise

    async def queue_task_nowait(
        self,
        priority: TaskPriority,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> asyncio.Future[Any]:
        """
        Queue a task without waiting for completion.

        Args:
            priority: Task priority level
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Future that will contain the result

        Raises:
            RuntimeError: If coordinator is not running
            asyncio.QueueFull: If queue is full
        """
        if not self._running:
            raise RuntimeError("TaskCoordinator is not running")

        future: asyncio.Future[Any] = asyncio.Future()
        task = Task(
            priority=priority, func=func, args=args, kwargs=kwargs, future=future
        )

        try:
            self._queue.put_nowait(task)
            self._stats["tasks_queued"] += 1
            self._stats["queue_size"] = self._queue.qsize()
            return future

        except asyncio.QueueFull:
            logger.error("Task queue is full, rejecting task")
            raise

    def get_stats(self) -> dict[str, Any]:
        """Get task coordinator statistics."""
        return {
            **self._stats,
            "queue_size": self._queue.qsize(),
            "is_running": self._running,
        }

    async def _worker_loop(self) -> None:
        """Main worker loop that processes tasks from the priority queue."""
        logger.info("TaskCoordinator worker started")

        while self._running or not self._queue.empty():
            try:
                # Use a short timeout to allow checking shutdown flag
                try:
                    task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Check if we should shutdown
                    if self._shutdown_event.is_set():
                        break
                    continue

                self._stats["queue_size"] = self._queue.qsize()

                # Execute the task
                try:
                    if asyncio.iscoroutinefunction(task.func):
                        result = await task.func(*task.args, **task.kwargs)
                    else:
                        result = task.func(*task.args, **task.kwargs)

                    task.future.set_result(result)
                    self._stats["tasks_completed"] += 1

                except Exception as e:
                    logger.error(f"Task execution failed: {e}", exc_info=True)
                    task.future.set_exception(e)
                    self._stats["tasks_failed"] += 1

                finally:
                    self._queue.task_done()

            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)

        logger.info("TaskCoordinator worker stopped")
