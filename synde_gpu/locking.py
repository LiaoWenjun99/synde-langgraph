"""
Distributed locking for GPU task state management.

FIX: Prevents race conditions on state["active_gpu_tasks"] updates
when multiple tasks complete concurrently.
"""

import time
from typing import Optional, Any
from contextlib import contextmanager

import redis

from synde_graph.config import REDIS_HOST, REDIS_PORT, LockSettings


class DistributedLock:
    """
    Redis-based distributed lock for safe state updates.

    FIX: Prevents race condition where multiple GPU tasks completing
    simultaneously could corrupt state["active_gpu_tasks"].
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        prefix: str = "synde:lock",
    ):
        """
        Initialize distributed lock.

        Args:
            redis_client: Optional Redis client (creates one if not provided)
            prefix: Key prefix for lock keys
        """
        self.redis = redis_client or redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
        )
        self.prefix = prefix

    def acquire(
        self,
        lock_name: str,
        timeout: int = LockSettings.DEFAULT_TIMEOUT,
        blocking: bool = True,
        retry_interval: float = LockSettings.RETRY_INTERVAL,
        max_retries: int = LockSettings.MAX_RETRIES,
    ) -> Optional[Any]:
        """
        Acquire a distributed lock.

        Args:
            lock_name: Name of the lock (e.g., job_id)
            timeout: Lock timeout in seconds (auto-release)
            blocking: Whether to wait for lock
            retry_interval: Seconds between retry attempts
            max_retries: Maximum retry attempts if blocking

        Returns:
            Lock object if acquired, None if not
        """
        lock_key = f"{self.prefix}:{lock_name}"
        lock = self.redis.lock(lock_key, timeout=timeout)

        if blocking:
            retries = 0
            while retries < max_retries:
                if lock.acquire(blocking=False):
                    return lock
                time.sleep(retry_interval)
                retries += 1
            return None
        else:
            if lock.acquire(blocking=False):
                return lock
            return None

    def release(self, lock: Any) -> bool:
        """
        Release a distributed lock.

        Args:
            lock: Lock object from acquire()

        Returns:
            True if released successfully
        """
        try:
            lock.release()
            return True
        except Exception:
            return False

    @contextmanager
    def locked(
        self,
        lock_name: str,
        timeout: int = LockSettings.DEFAULT_TIMEOUT,
    ):
        """
        Context manager for acquiring and releasing a lock.

        Usage:
            with lock.locked("job-123"):
                # Critical section
                update_state()

        Args:
            lock_name: Name of the lock
            timeout: Lock timeout in seconds
        """
        lock = self.acquire(lock_name, timeout=timeout)
        if lock is None:
            raise LockAcquisitionError(f"Failed to acquire lock: {lock_name}")

        try:
            yield lock
        finally:
            self.release(lock)

    def is_locked(self, lock_name: str) -> bool:
        """Check if a lock is currently held."""
        lock_key = f"{self.prefix}:{lock_name}"
        return self.redis.exists(lock_key) > 0


class LockAcquisitionError(Exception):
    """Raised when lock acquisition fails."""
    pass


class StateUpdateLock:
    """
    Specialized lock for state updates during GPU task completion.

    Ensures atomic updates to state when GPU tasks complete.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.lock = DistributedLock(redis_client, prefix="synde:state_lock")

    @contextmanager
    def for_job(self, job_id: str, timeout: int = 30):
        """
        Acquire lock for updating a specific job's state.

        Args:
            job_id: The workflow job ID
            timeout: Lock timeout
        """
        with self.lock.locked(job_id, timeout=timeout):
            yield


class GpuTaskLock:
    """
    Lock for GPU task operations.

    Prevents multiple tasks from running simultaneously on the same GPU
    (useful for single-GPU setups).
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.lock = DistributedLock(redis_client, prefix="synde:gpu")

    @contextmanager
    def for_task(self, task_name: str, timeout: int = 1800):
        """
        Acquire lock for a GPU task.

        Args:
            task_name: Name of the GPU task
            timeout: Lock timeout (should be >= task timeout)
        """
        with self.lock.locked(task_name, timeout=timeout):
            yield

    def is_gpu_busy(self) -> bool:
        """Check if any GPU task is currently running."""
        return self.lock.is_locked("esmfold") or \
               self.lock.is_locked("clean_ec") or \
               self.lock.is_locked("deepenzyme") or \
               self.lock.is_locked("temberture")


# =============================================================================
# Global instances for convenience
# =============================================================================

_state_lock: Optional[StateUpdateLock] = None
_gpu_lock: Optional[GpuTaskLock] = None


def get_state_lock() -> StateUpdateLock:
    """Get global state update lock instance."""
    global _state_lock
    if _state_lock is None:
        _state_lock = StateUpdateLock()
    return _state_lock


def get_gpu_lock() -> GpuTaskLock:
    """Get global GPU task lock instance."""
    global _gpu_lock
    if _gpu_lock is None:
        _gpu_lock = GpuTaskLock()
    return _gpu_lock
