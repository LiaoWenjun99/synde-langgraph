"""
Live Logger for real-time workflow status reporting.

Provides real-time status updates during workflow execution via Redis pub/sub.
"""

import os
import time
import json
import redis
import contextvars
from typing import Optional, List, Tuple

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", os.getenv("CELERY_REDIS_HOST", "172.31.19.34"))
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Use db=2 for logs (same as synde-minimal)
_redis_client = None


def get_redis():
    """Get Redis client (lazy initialization)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=2,
            decode_responses=True
        )
    return _redis_client


# Context variable to track current job/workflow ID
_current_job_id = contextvars.ContextVar("current_job_id", default=None)


def set_current_job_id(job_id: Optional[str]):
    """Set the current job ID for the context."""
    _current_job_id.set(job_id)


def get_current_job_id() -> Optional[str]:
    """Get the current job ID from context."""
    return _current_job_id.get()


def _key(job_id: str) -> str:
    """Generate Redis key for job logs."""
    return f"agentlog:{job_id}"


def report(*args):
    """
    Report a status message for the current workflow.

    Supports:
        report(job_id, msg)  - explicit job_id
        report(msg)          - uses contextvar current_job_id

    Args:
        *args: Either (job_id, msg) or (msg,)
    """
    if len(args) == 2:
        job_id, msg = args
    elif len(args) == 1:
        msg = args[0]
        job_id = _current_job_id.get()
    else:
        raise TypeError("report() expects report(job_id, msg) or report(msg)")

    if not job_id:
        # No job_id available: skip silently
        return

    try:
        r = get_redis()
        entry = {"ts": time.time(), "msg": str(msg)}
        r.rpush(_key(str(job_id)), json.dumps(entry))
        r.expire(_key(str(job_id)), 60 * 60)  # Expire after 1 hour
    except Exception:
        # Don't let logging failures break the workflow
        pass


def get_logs(job_id: str, since: int = 0) -> Tuple[List[dict], int]:
    """
    Get logs for a job since a given index.

    Args:
        job_id: The job/workflow ID
        since: Index to start from (for incremental fetching)

    Returns:
        Tuple of (list of log entries, new index)
    """
    try:
        r = get_redis()
        raw = r.lrange(_key(job_id), since, -1)
        logs = [json.loads(x) for x in raw]
        return logs, since + len(logs)
    except Exception:
        return [], since


def clear_logs(job_id: str):
    """Clear logs for a job."""
    try:
        r = get_redis()
        r.delete(_key(job_id))
    except Exception:
        pass


# Convenience functions for common status messages
def report_node_start(node_name: str, details: str = ""):
    """Report that a node has started."""
    msg = f"🔄 Starting: {node_name}"
    if details:
        msg += f" - {details}"
    report(msg)


def report_node_complete(node_name: str, details: str = ""):
    """Report that a node has completed."""
    msg = f"✅ Completed: {node_name}"
    if details:
        msg += f" - {details}"
    report(msg)


def report_node_error(node_name: str, error: str):
    """Report that a node encountered an error."""
    report(f"❌ Error in {node_name}: {error}")


def report_gpu_task(task_name: str, status: str):
    """Report GPU task status."""
    report(f"🖥️ GPU Task [{task_name}]: {status}")


def report_info(msg: str):
    """Report an informational message."""
    report(f"ℹ️ {msg}")


def report_warning(msg: str):
    """Report a warning message."""
    report(f"⚠️ {msg}")
