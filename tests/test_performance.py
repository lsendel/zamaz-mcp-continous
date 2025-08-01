"""
Performance tests for Claude Remote Client.

This module contains performance benchmarks, load tests, and scalability tests
to ensure the application performs well under various conditions.
"""

import pytest
import asyncio
import time
import statistics
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch
import psutil
import gc

from claude_remote_client.session_manager.enhanced_session_manager import EnhancedSessionManager
from claude_remote_client.performance import LRUCache, ConnectionPool, RateLimiter, BatchProcessor
from claude_remote_client.models import ClaudeSession, SessionStatus, QueuedTask, TaskStatus
from claude_remote_client.task_queue.queue_manager import QueueManager


@pytest.mark.performance
class TestCachePerformance:
    """Test cache performance and efficiency."""
    
    @pytest.mark.asyncio
    async def test_lru_cache_performance(self):
        """Test LRU cache performance with various operations."""
        cache = LRUCache[str](max_size=1000)
        
        # Test write performance
        start_time = time.time()
        for i in range(1000):
            await cache.set(f"key_{i}", f"value_{i}")
        write_time = time.time() - start_time
        
        # Test read performance
        start_time = time.time()
        for i in range(1000):
            await cache.get(f"key_{i}")
        read_time = time.time() - start_time
        
        # Test mixed operations
        start_time = time.time()
        for i in range(500):
            await cache.get(f"key_{i}")
            await cache.set(f"new_key_{i}", f"new_value_{i}")
        mixed_time = time.time() - start_time
        
        # Performance assertions
        assert write_time < 1.0, f"Write operations too slow: {write_time:.3f}s"
        assert read_time < 0.5, f"Read operations too slow: {read_time:.3f}s"
        assert mixed_time < 1.0, f"Mixed operations too slow: {mixed_time:.3f}s"
        
        # Verify cache stats
        stats = await cache.get_stats()
        assert stats['hit_rate'] > 0.8  # Should have high hit rate
        assert stats['size'] <= 1000    # Should not exceed max size
    
    @pytest.mark.asyncio
    async def test_cache_memory_efficiency(self):
        """Test cache memory usage and efficiency."""
        cache = LRUCache[Dict[str, Any]](max_size=100)
        
        # Measure initial memory
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss
        
        # Add large objects to cache
        large_objects = []
        for i in range(100):
            obj = {
                'id': i,
                'data': 'x' * 1000,  # 1KB of data
                'metadata': {'created': time.time(), 'size': 1000}
            }
            large_objects.append(obj)
            await cache.set(f"large_{i}", obj)
        
        # Measure memory after caching
        gc.collect()
        cached_memory = psutil.Process().memory_info().rss
        memory_increase = cached_memory - initial_memory
        
        # Add more objects to trigger eviction
        for i in range(100, 200):
            obj = {
                'id': i,
                'data': 'x' * 1000,
                'metadata': {'created': time.time(), 'size': 1000}
            }
            await cache.set(f"large_{i}", obj)
        
        # Measure memory after eviction
        gc.collect()
        final_memory = psutil.Process().memory_info().rss
        
        # Memory should not grow significantly after eviction
        memory_growth = final_memory - cached_memory
        assert memory_growth < memory_increase * 0.5, "Cache not properly evicting old entries"
        
        # Verify cache size is maintained
        stats = await cache.get_stats()
        assert stats['size'] == 100
        assert stats['evictions'] == 100


@pytest.mark.performance
class TestSessionManagerPerformance:
    """Test session manager performance under load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self, test_config, mock_subprocess):
        """Test concurrent session creation performance."""
        session_manager = EnhancedSessionManager(test_config)
        await session_manager.start()
        
        try:
            # Create many sessions concurrently
            start_time = time.time()
            
            tasks = []
            for i in range(50):
                task = asyncio.create_task(
                    session_manager.create_session(f"project_{i % 5}")
                )
                tasks.append(task)
            
            sessions = await asyncio.gather(*tasks, return_exceptions=True)
            creation_time = time.time() - start_time
            
            # Count successful sessions
            successful_sessions = [s for s in sessions if isinstance(s, ClaudeSession)]
            
            # Performance assertions
            assert creation_time < 10.0, f"Session creation too slow: {creation_time:.3f}s"
            assert len(successful_sessions) >= 40, "Too many session creation failures"
            
            # Test concurrent message sending
            start_time = time.time()
            
            message_tasks = []
            for session in successful_sessions[:20]:  # Use first 20 sessions
                task = asyncio.create_task(
                    session_manager.send_message(session.session_id, f"Test message for {session.project_name}")
                )
                message_tasks.append(task)
            
            responses = await asyncio.gather(*message_tasks, return_exceptions=True)
            messaging_time = time.time() - start_time
            
            successful_responses = [r for r in responses if not isinstance(r, Exception)]
            
            assert messaging_time < 15.0, f"Concurrent messaging too slow: {messaging_time:.3f}s"
            assert len(successful_responses) >= 15, "Too many messaging failures"
            
        finally:
            await session_manager.stop()
    
    @pytest.mark.asyncio
    async def test_session_cache_performance(self, test_config, mock_subprocess):
        """Test session caching performance benefits."""
        session_manager = EnhancedSessionManager(test_config)
        await session_manager.start()
        
        try:
            # Create test sessions
            sessions = []
            for i in range(10):
                session = await session_manager.create_session(f"project_{i}")
                sessions.append(session)
            
            # Test cache hit performance
            cache_hit_times = []
            for _ in range(100):
                start_time = time.time()
                for session in sessions:
                    await session_manager.get_session(session.session_id)
                cache_hit_times.append(time.time() - start_time)
            
            # Test cache miss performance (clear cache first)
            await session_manager.session_cache.clear()
            
            cache_miss_times = []
            for _ in range(10):  # Fewer iterations for cache misses
                start_time = time.time()
                for session in sessions:
                    await session_manager.get_session(session.session_id)
                cache_miss_times.append(time.time() - start_time)
            
            # Cache hits should be significantly faster
            avg_hit_time = statistics.mean(cache_hit_times)
            avg_miss_time = statistics.mean(cache_miss_times)
            
            assert avg_hit_time < avg_miss_time * 0.5, "Cache not providing performance benefit"
            assert avg_hit_time < 0.1, f"Cache hits too slow: {avg_hit_time:.3f}s"
            
        finally:
            await session_manager.stop()
    
    @pytest.mark.asyncio
    async def test_memory_optimization_performance(self, test_config, mock_subprocess):
        """Test memory optimization performance."""
        session_manager = EnhancedSessionManager(test_config)
        await session_manager.start()
        
        try:
            # Create sessions with large conversation histories
            sessions = []
            for i in range(10):
                session = await session_manager.create_session(f"project_{i}")
                
                # Add large conversation history
                for j in range(200):
                    session.conversation_history.append({
                        'role': 'user' if j % 2 == 0 else 'assistant',
                        'content': f"Message {j} with some content " * 10,
                        'timestamp': time.time()
                    })
                
                sessions.append(session)
            
            # Measure memory before optimization
            gc.collect()
            initial_memory = psutil.Process().memory_info().rss
            
            # Run memory optimization
            start_time = time.time()
            optimization_stats = await session_manager.optimize_memory_usage()
            optimization_time = time.time() - start_time
            
            # Measure memory after optimization
            gc.collect()
            final_memory = psutil.Process().memory_info().rss
            
            # Verify optimization results
            assert optimization_time < 5.0, f"Memory optimization too slow: {optimization_time:.3f}s"
            assert optimization_stats['sessions_optimized'] > 0, "No sessions were optimized"
            assert optimization_stats['memory_usage']['saved_bytes'] > 0, "No memory was saved"
            
            # Memory should be reduced
            memory_reduction = initial_memory - final_memory
            assert memory_reduction > 0, "Memory usage did not decrease"
            
        finally:
            await session_manager.stop()


@pytest.mark.performance
class TestRateLimiterPerformance:
    """Test rate limiter performance and accuracy."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_accuracy(self):
        """Test rate limiter accuracy under load."""
        rate_limiter = RateLimiter(rate=10.0, burst=20)  # 10 requests per second
        
        # Test burst handling
        start_time = time.time()
        burst_results = []
        
        for _ in range(20):  # Should all succeed immediately
            result = await rate_limiter.acquire()
            burst_results.append(result)
        
        burst_time = time.time() - start_time
        
        assert all(burst_results), "Burst requests should all succeed"
        assert burst_time < 0.1, f"Burst handling too slow: {burst_time:.3f}s"
        
        # Test rate limiting
        start_time = time.time()
        rate_limited_results = []
        
        for _ in range(10):  # Should be rate limited
            result = await rate_limiter.acquire()
            rate_limited_results.append(result)
        
        rate_limited_time = time.time() - start_time
        
        # Should have some failures due to rate limiting
        success_count = sum(rate_limited_results)
        assert success_count < 10, "Rate limiter not working properly"
        
        # Test wait_for_tokens performance
        start_time = time.time()
        await rate_limiter.wait_for_tokens(5)
        wait_time = time.time() - start_time
        
        # Should wait approximately 0.5 seconds for 5 tokens at 10/sec rate
        assert 0.4 < wait_time < 0.7, f"Wait time inaccurate: {wait_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_concurrent_rate_limiting(self):
        """Test rate limiter with concurrent requests."""
        rate_limiter = RateLimiter(rate=5.0, burst=10)
        
        async def make_request():
            return await rate_limiter.acquire()
        
        # Make many concurrent requests
        start_time = time.time()
        tasks = [asyncio.create_task(make_request()) for _ in range(50)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        success_count = sum(results)
        
        # Should have limited success due to rate limiting
        assert success_count <= 15, f"Too many requests succeeded: {success_count}"
        assert total_time < 1.0, f"Concurrent rate limiting too slow: {total_time:.3f}s"


@pytest.mark.performance
class TestBatchProcessorPerformance:
    """Test batch processor performance and efficiency."""
    
    @pytest.mark.asyncio
    async def test_batch_processing_throughput(self):
        """Test batch processor throughput."""
        processed_batches = []
        
        async def process_batch(items):
            processed_batches.append(len(items))
            await asyncio.sleep(0.01)  # Simulate processing time
        
        processor = BatchProcessor(
            process_batch=process_batch,
            batch_size=10,
            max_wait_time=0.1
        )
        
        await processor.start()
        
        try:
            # Add items rapidly
            start_time = time.time()
            
            for i in range(100):
                await processor.add_item(f"item_{i}")
            
            # Wait for processing to complete
            await asyncio.sleep(2.0)
            
            processing_time = time.time() - start_time
            
            # Verify batching efficiency
            total_processed = sum(processed_batches)
            assert total_processed == 100, f"Not all items processed: {total_processed}"
            assert len(processed_batches) <= 15, f"Too many small batches: {len(processed_batches)}"
            assert processing_time < 3.0, f"Batch processing too slow: {processing_time:.3f}s"
            
            # Most batches should be full size
            full_batches = [b for b in processed_batches if b == 10]
            assert len(full_batches) >= 8, "Not enough full-size batches"
            
        finally:
            await processor.stop()


@pytest.mark.performance
class TestQueueManagerPerformance:
    """Test task queue manager performance under load."""
    
    @pytest.mark.asyncio
    async def test_high_volume_task_processing(self, test_config):
        """Test queue manager with high volume of tasks."""
        queue_manager = QueueManager(test_config)
        
        # Mock Claude execution
        processed_tasks = []
        
        async def mock_claude_execution(task):
            processed_tasks.append(task.task_id)
            await asyncio.sleep(0.01)  # Simulate processing time
            return f"Response for {task.task_id}"
        
        queue_manager.claude_execution_callback = mock_claude_execution
        
        await queue_manager.start()
        
        try:
            # Add many tasks rapidly
            start_time = time.time()
            task_ids = []
            
            for i in range(200):
                task_id = await queue_manager.add_task(
                    queue_name="performance_test",
                    task_type="test_task",
                    prompt=f"Test task {i}",
                    project_name=f"project_{i % 5}"
                )
                task_ids.append(task_id)
            
            addition_time = time.time() - start_time
            
            # Wait for processing
            await asyncio.sleep(10.0)
            
            total_time = time.time() - start_time
            
            # Verify performance
            assert addition_time < 5.0, f"Task addition too slow: {addition_time:.3f}s"
            assert len(processed_tasks) > 50, f"Too few tasks processed: {len(processed_tasks)}"
            assert total_time < 15.0, f"Overall processing too slow: {total_time:.3f}s"
            
            # Check task completion rate
            completion_rate = len(processed_tasks) / len(task_ids)
            assert completion_rate > 0.25, f"Low completion rate: {completion_rate:.2f}"
            
        finally:
            await queue_manager.stop()
    
    @pytest.mark.asyncio
    async def test_queue_persistence_performance(self, test_config):
        """Test queue persistence performance."""
        queue_manager = QueueManager(test_config)
        await queue_manager.start()
        
        try:
            # Add many tasks
            start_time = time.time()
            
            for i in range(100):
                await queue_manager.add_task(
                    queue_name="persistence_test",
                    task_type="test_task",
                    prompt=f"Persistence test task {i}",
                    project_name="test_project"
                )
            
            addition_time = time.time() - start_time
            
            # Force persistence
            start_time = time.time()
            await queue_manager._save_queues()
            persistence_time = time.time() - start_time
            
            # Stop and restart to test loading
            await queue_manager.stop()
            
            start_time = time.time()
            new_queue_manager = QueueManager(test_config)
            await new_queue_manager.start()
            loading_time = time.time() - start_time
            
            # Verify loaded tasks
            tasks = await new_queue_manager.list_tasks("persistence_test")
            
            # Performance assertions
            assert addition_time < 2.0, f"Task addition too slow: {addition_time:.3f}s"
            assert persistence_time < 1.0, f"Persistence too slow: {persistence_time:.3f}s"
            assert loading_time < 2.0, f"Loading too slow: {loading_time:.3f}s"
            assert len(tasks) == 100, f"Not all tasks loaded: {len(tasks)}"
            
            await new_queue_manager.stop()
            
        finally:
            if queue_manager.is_running:
                await queue_manager.stop()


@pytest.mark.performance
@pytest.mark.slow
class TestScalabilityLimits:
    """Test system scalability limits."""
    
    @pytest.mark.asyncio
    async def test_maximum_concurrent_sessions(self, test_config, mock_subprocess):
        """Test maximum number of concurrent sessions."""
        # Increase limits for this test
        test_config.max_sessions = 100
        
        session_manager = EnhancedSessionManager(test_config)
        await session_manager.start()
        
        try:
            # Create sessions until we hit limits
            sessions = []
            creation_times = []
            
            for i in range(100):
                start_time = time.time()
                try:
                    session = await session_manager.create_session(f"project_{i % 10}")
                    sessions.append(session)
                    creation_times.append(time.time() - start_time)
                except Exception as e:
                    print(f"Failed to create session {i}: {e}")
                    break
            
            # Analyze performance degradation
            if len(creation_times) > 50:
                early_times = creation_times[:25]
                late_times = creation_times[-25:]
                
                avg_early = statistics.mean(early_times)
                avg_late = statistics.mean(late_times)
                
                # Performance should not degrade too much
                degradation_ratio = avg_late / avg_early
                assert degradation_ratio < 3.0, f"Performance degraded too much: {degradation_ratio:.2f}x"
            
            print(f"Successfully created {len(sessions)} concurrent sessions")
            assert len(sessions) >= 50, "Could not create minimum expected sessions"
            
        finally:
            await session_manager.stop()
    
    @pytest.mark.asyncio
    async def test_memory_usage_scaling(self, test_config, mock_subprocess):
        """Test memory usage scaling with load."""
        session_manager = EnhancedSessionManager(test_config)
        await session_manager.start()
        
        try:
            memory_measurements = []
            
            # Measure memory at different session counts
            for session_count in [10, 25, 50]:
                # Create sessions
                sessions = []
                for i in range(session_count):
                    session = await session_manager.create_session(f"project_{i % 5}")
                    sessions.append(session)
                
                # Add conversation history
                for session in sessions:
                    for j in range(50):
                        session.conversation_history.append({
                            'role': 'user' if j % 2 == 0 else 'assistant',
                            'content': f"Message {j} content",
                            'timestamp': time.time()
                        })
                
                # Measure memory
                gc.collect()
                memory_usage = psutil.Process().memory_info().rss
                memory_measurements.append((session_count, memory_usage))
                
                # Clean up sessions
                for session in sessions:
                    await session_manager.stop_session(session.session_id)
            
            # Analyze memory scaling
            if len(memory_measurements) >= 2:
                # Calculate memory per session
                memory_per_session = []
                for i in range(1, len(memory_measurements)):
                    prev_count, prev_memory = memory_measurements[i-1]
                    curr_count, curr_memory = memory_measurements[i]
                    
                    memory_diff = curr_memory - prev_memory
                    session_diff = curr_count - prev_count
                    
                    if session_diff > 0:
                        memory_per_session.append(memory_diff / session_diff)
                
                if memory_per_session:
                    avg_memory_per_session = statistics.mean(memory_per_session)
                    print(f"Average memory per session: {avg_memory_per_session / (1024*1024):.2f} MB")
                    
                    # Memory per session should be reasonable
                    assert avg_memory_per_session < 50 * 1024 * 1024, "Memory usage per session too high"
            
        finally:
            await session_manager.stop()


# Utility functions for performance testing

def measure_async_function_performance(func, *args, iterations=10, **kwargs):
    """Measure performance of an async function."""
    async def run_test():
        times = []
        for _ in range(iterations):
            start_time = time.time()
            await func(*args, **kwargs)
            times.append(time.time() - start_time)
        
        return {
            'avg_time': statistics.mean(times),
            'min_time': min(times),
            'max_time': max(times),
            'std_dev': statistics.stdev(times) if len(times) > 1 else 0,
            'iterations': iterations
        }
    
    return asyncio.run(run_test())


def assert_performance_within_bounds(actual_time: float, expected_max: float, operation: str):
    """Assert that performance is within expected bounds."""
    assert actual_time <= expected_max, (
        f"{operation} performance exceeded bounds: "
        f"{actual_time:.3f}s > {expected_max:.3f}s"
    )
