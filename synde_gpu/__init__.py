"""
GPU task interface for SynDe LangGraph.

Provides task proxies to synde-minimal GPU tasks, an improved async manager,
distributed locking, and mock responses for testing.
"""

from synde_gpu.tasks import (
    call_esmfold,
    call_clean_ec,
    call_deepenzyme,
    call_temberture,
    call_flan_extractor,
    call_fpocket,
)

from synde_gpu.manager import (
    GpuTaskManager,
    TaskStatus,
    GpuTaskResult,
    execute_gpu_task,
)

from synde_gpu.mocks import (
    MockGpuResponses,
    get_mock_response,
    is_mock_mode,
)

__all__ = [
    # Task proxies
    "call_esmfold",
    "call_clean_ec",
    "call_deepenzyme",
    "call_temberture",
    "call_flan_extractor",
    "call_fpocket",
    # Manager
    "GpuTaskManager",
    "TaskStatus",
    "GpuTaskResult",
    "execute_gpu_task",
    # Mocks
    "MockGpuResponses",
    "get_mock_response",
    "is_mock_mode",
]
