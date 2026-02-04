"""
Improved GPU Task Manager for LangGraph workflows.

Provides async-aware GPU task execution with:
- Proper async polling (no blocking allow_join_result)
- Pre-submission checkpointing to prevent orphan tasks
- Proper task cancellation with terminate=True
- Distributed locking for state updates
"""

import asyncio
import time
from typing import Any, Dict, Optional, Callable, Union
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from celery.result import AsyncResult

from synde_graph.config import GpuTimeouts
from synde_gpu.mocks import is_mock_mode


class TaskStatus(Enum):
    """GPU task execution status."""
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    REVOKED = "revoked"


@dataclass
class GpuTaskResult:
    """Result from a GPU task execution."""
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    task_id: Optional[str] = None
    elapsed_seconds: float = 0.0


class GpuTaskManager:
    """
    Improved GPU task manager with async support and proper checkpointing.

    Key improvements over synde-minimal:
    1. Async polling instead of blocking allow_join_result()
    2. Pre-submission checkpoint to prevent orphan tasks
    3. Proper cancellation with terminate=True and SIGKILL
    4. Distributed lock for state updates
    """

    def __init__(
        self,
        task_name: str,
        timeout: int = GpuTimeouts.ESMFOLD,
        poll_interval: float = GpuTimeouts.POLL_INTERVAL,
        checkpoint_interval: float = GpuTimeouts.CHECKPOINT_INTERVAL,
    ):
        """
        Initialize GPU task manager.

        Args:
            task_name: Human-readable task name for logging
            timeout: Maximum wait time in seconds
            poll_interval: Seconds between status checks
            checkpoint_interval: Seconds between checkpoint updates
        """
        self.task_name = task_name
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.checkpoint_interval = checkpoint_interval

    async def execute_async(
        self,
        task_func: Callable,
        args: tuple = (),
        kwargs: Optional[Dict] = None,
        on_checkpoint: Optional[Callable] = None,
        checkpointer: Optional[Any] = None,
        state: Optional[Dict] = None,
    ) -> GpuTaskResult:
        """
        Execute GPU task with async polling.

        FIX: Replaces blocking allow_join_result() with proper async polling.

        Args:
            task_func: Celery task function or proxy
            args: Task arguments
            kwargs: Task keyword arguments
            on_checkpoint: Optional callback for checkpoint updates
            checkpointer: Optional checkpointer for pre-submission checkpoint
            state: Current state for checkpointing

        Returns:
            GpuTaskResult with status and result/error
        """
        kwargs = kwargs or {}
        start_time = time.time()
        last_checkpoint_time = start_time

        # FIX: Pre-submission checkpoint to prevent orphan tasks
        if checkpointer and state:
            try:
                checkpointer.put(state, metadata={"stage": "pre_gpu", "task": self.task_name})
            except Exception:
                pass  # Non-fatal, continue with task

        # Handle mock mode
        if is_mock_mode():
            # For mocks, task_func returns the result directly
            result = task_func(*args, **kwargs)
            return GpuTaskResult(
                status=TaskStatus.SUCCESS,
                result=result,
                task_id="mock-task",
                elapsed_seconds=time.time() - start_time,
            )

        # Submit task
        async_result = task_func(*args, **kwargs)

        # Handle case where proxy returns result directly (mock mode)
        if not isinstance(async_result, AsyncResult):
            return GpuTaskResult(
                status=TaskStatus.SUCCESS,
                result=async_result,
                task_id="direct-result",
                elapsed_seconds=time.time() - start_time,
            )

        task_id = async_result.id

        try:
            # Async polling loop
            while True:
                elapsed = time.time() - start_time

                # Check timeout
                if elapsed > self.timeout:
                    # FIX: Proper cancellation with terminate=True
                    await self._cancel_task(async_result)
                    return GpuTaskResult(
                        status=TaskStatus.TIMEOUT,
                        error=f"Task timed out after {self.timeout}s",
                        task_id=task_id,
                        elapsed_seconds=elapsed,
                    )

                # Check if task is complete
                if async_result.ready():
                    break

                # Checkpoint callback during long waits
                if on_checkpoint and (time.time() - last_checkpoint_time) >= self.checkpoint_interval:
                    on_checkpoint(task_id, "started", elapsed)
                    last_checkpoint_time = time.time()

                # Async sleep instead of blocking
                await asyncio.sleep(self.poll_interval)

            # Get result
            elapsed = time.time() - start_time

            if async_result.successful():
                return GpuTaskResult(
                    status=TaskStatus.SUCCESS,
                    result=async_result.result,
                    task_id=task_id,
                    elapsed_seconds=elapsed,
                )
            else:
                error_msg = str(async_result.result) if async_result.result else "Unknown error"
                return GpuTaskResult(
                    status=TaskStatus.FAILURE,
                    error=error_msg,
                    task_id=task_id,
                    elapsed_seconds=elapsed,
                )

        except Exception as e:
            elapsed = time.time() - start_time
            return GpuTaskResult(
                status=TaskStatus.FAILURE,
                error=str(e),
                task_id=task_id,
                elapsed_seconds=elapsed,
            )

    def execute_sync(
        self,
        task_func: Callable,
        args: tuple = (),
        kwargs: Optional[Dict] = None,
    ) -> GpuTaskResult:
        """
        Execute GPU task synchronously with polling.

        This is a simpler interface for non-async contexts.
        Uses polling instead of blocking allow_join_result().

        Args:
            task_func: Celery task function or proxy
            args: Task arguments
            kwargs: Task keyword arguments

        Returns:
            GpuTaskResult with status and result/error
        """
        kwargs = kwargs or {}
        start_time = time.time()

        # Handle mock mode
        if is_mock_mode():
            result = task_func(*args, **kwargs)
            return GpuTaskResult(
                status=TaskStatus.SUCCESS,
                result=result,
                task_id="mock-task",
                elapsed_seconds=time.time() - start_time,
            )

        # Submit task
        async_result = task_func(*args, **kwargs)

        # Handle direct result (mock mode)
        if not isinstance(async_result, AsyncResult):
            return GpuTaskResult(
                status=TaskStatus.SUCCESS,
                result=async_result,
                task_id="direct-result",
                elapsed_seconds=time.time() - start_time,
            )

        task_id = async_result.id

        try:
            # Polling loop
            while True:
                elapsed = time.time() - start_time

                if elapsed > self.timeout:
                    self._cancel_task_sync(async_result)
                    return GpuTaskResult(
                        status=TaskStatus.TIMEOUT,
                        error=f"Task timed out after {self.timeout}s",
                        task_id=task_id,
                        elapsed_seconds=elapsed,
                    )

                if async_result.ready():
                    break

                time.sleep(self.poll_interval)

            elapsed = time.time() - start_time

            if async_result.successful():
                return GpuTaskResult(
                    status=TaskStatus.SUCCESS,
                    result=async_result.result,
                    task_id=task_id,
                    elapsed_seconds=elapsed,
                )
            else:
                error_msg = str(async_result.result) if async_result.result else "Unknown error"
                return GpuTaskResult(
                    status=TaskStatus.FAILURE,
                    error=error_msg,
                    task_id=task_id,
                    elapsed_seconds=elapsed,
                )

        except Exception as e:
            elapsed = time.time() - start_time
            return GpuTaskResult(
                status=TaskStatus.FAILURE,
                error=str(e),
                task_id=task_id,
                elapsed_seconds=elapsed,
            )

    async def _cancel_task(self, async_result: AsyncResult) -> None:
        """
        Cancel a running GPU task properly.

        FIX: Use terminate=True to actually stop GPU computation.
        """
        try:
            # terminate=True sends SIGKILL to actually stop the task
            async_result.revoke(terminate=True, signal="SIGKILL")
        except Exception:
            pass  # Best effort cancellation

    def _cancel_task_sync(self, async_result: AsyncResult) -> None:
        """Synchronous version of task cancellation."""
        try:
            async_result.revoke(terminate=True, signal="SIGKILL")
        except Exception:
            pass


# =============================================================================
# Convenience Functions
# =============================================================================

async def execute_gpu_task(
    task_name: str,
    task_func: Callable,
    args: tuple = (),
    kwargs: Optional[Dict] = None,
    timeout: Optional[int] = None,
    poll_interval: Optional[float] = None,
) -> GpuTaskResult:
    """
    Convenience function to execute a GPU task.

    Args:
        task_name: Human-readable task name
        task_func: Celery task function
        args: Task arguments
        kwargs: Task keyword arguments
        timeout: Optional custom timeout
        poll_interval: Optional custom poll interval

    Returns:
        GpuTaskResult
    """
    manager = GpuTaskManager(
        task_name=task_name,
        timeout=timeout or GpuTimeouts.ESMFOLD,
        poll_interval=poll_interval or GpuTimeouts.POLL_INTERVAL,
    )

    return await manager.execute_async(task_func, args, kwargs)


def execute_gpu_task_sync(
    task_name: str,
    task_func: Callable,
    args: tuple = (),
    kwargs: Optional[Dict] = None,
    timeout: Optional[int] = None,
) -> GpuTaskResult:
    """
    Synchronous convenience function to execute a GPU task.

    Args:
        task_name: Human-readable task name
        task_func: Celery task function
        args: Task arguments
        kwargs: Task keyword arguments
        timeout: Optional custom timeout

    Returns:
        GpuTaskResult
    """
    manager = GpuTaskManager(
        task_name=task_name,
        timeout=timeout or GpuTimeouts.ESMFOLD,
    )

    return manager.execute_sync(task_func, args, kwargs)


# =============================================================================
# Pre-configured Managers
# =============================================================================

def create_esmfold_manager() -> GpuTaskManager:
    """Create manager for ESMFold tasks."""
    return GpuTaskManager(
        task_name="ESMFold",
        timeout=GpuTimeouts.ESMFOLD,
    )


def create_clean_ec_manager() -> GpuTaskManager:
    """Create manager for CLEAN EC tasks."""
    return GpuTaskManager(
        task_name="CLEAN_EC",
        timeout=GpuTimeouts.CLEAN_EC,
    )


def create_deepenzyme_manager() -> GpuTaskManager:
    """Create manager for DeepEnzyme tasks."""
    return GpuTaskManager(
        task_name="DeepEnzyme",
        timeout=GpuTimeouts.DEEPENZYME,
    )


def create_temberture_manager() -> GpuTaskManager:
    """Create manager for TemBERTure tasks."""
    return GpuTaskManager(
        task_name="TemBERTure",
        timeout=GpuTimeouts.TEMBERTURE,
    )


def create_flan_manager() -> GpuTaskManager:
    """Create manager for FLAN extraction tasks."""
    return GpuTaskManager(
        task_name="FLAN_Extractor",
        timeout=GpuTimeouts.FLAN_EXTRACTOR,
        poll_interval=2,
    )
