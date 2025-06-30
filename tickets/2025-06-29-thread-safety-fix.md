# Thread Safety Fix for FileWatcher

## Problem
The `ChunkHoundEventHandler` was attempting to use `asyncio.Queue` from within watchdog's observer thread, which violates asyncio's thread safety requirements. This could lead to race conditions, corrupted state, and unpredictable behavior.

## Solution
Implemented a proper thread-safe bridge between the watchdog thread and asyncio:

1. **Thread-Safe Queue**: Replaced `asyncio.Queue` with `queue.Queue` in `ChunkHoundEventHandler` for thread-safe communication
2. **Bridge Coroutine**: Added `_queue_bridge()` method to transfer events from the thread-safe queue to the asyncio queue
3. **Async Methods**: Converted `start()` and `stop()` methods to async to properly manage the bridge task
4. **Removed Unused Code**: Removed the unused `ThreadPoolExecutor` import and field

## Key Changes

### ChunkHoundEventHandler
- Changed constructor parameter from `asyncio.Queue` to `queue.Queue`
- Updated exception handling from `asyncio.QueueFull` to `queue.Full`

### FileWatcher
- Added `thread_safe_queue` for watchdog handler
- Added `bridge_task` to manage the queue bridge coroutine
- Implemented `_queue_bridge()` to safely transfer events between queues
- Made `start()` and `stop()` methods async
- Properly manages bridge task lifecycle

### FileWatcherManager
- Updated to use async `start()` and `stop()` methods

## Benefits
- Eliminates thread safety violations
- Maintains all existing functionality
- Proper cleanup of resources
- No risk of race conditions between threads