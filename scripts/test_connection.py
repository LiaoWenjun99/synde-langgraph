#!/usr/bin/env python3
"""
Test connections to Redis and Celery infrastructure.

This script verifies that the synde-langgraph environment can
connect to the shared Redis/Celery infrastructure.

Usage:
    python scripts/test_connection.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_redis_connection():
    """Test Redis connection."""
    print("Testing Redis connection...")

    try:
        import redis
        from synde_graph.config import REDIS_HOST, REDIS_PORT

        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, socket_timeout=5)
        result = client.ping()

        if result:
            print(f"  [OK] Redis connected at {REDIS_HOST}:{REDIS_PORT}")
            return True
        else:
            print(f"  [FAIL] Redis ping failed")
            return False

    except Exception as e:
        print(f"  [FAIL] Redis connection error: {e}")
        return False


def test_celery_broker():
    """Test Celery broker connection."""
    print("Testing Celery broker...")

    try:
        from synde_gpu.tasks import celery_app

        # Try to inspect workers
        inspector = celery_app.control.inspect(timeout=5)
        active = inspector.active()

        if active is not None:
            workers = list(active.keys())
            print(f"  [OK] Celery broker connected, workers: {workers if workers else 'none active'}")
            return True
        else:
            print(f"  [WARN] Celery broker connected but no workers responding")
            return True

    except Exception as e:
        print(f"  [FAIL] Celery broker error: {e}")
        return False


def test_gpu_queue():
    """Test GPU queue availability."""
    print("Testing GPU queue...")

    try:
        from synde_gpu.tasks import celery_app

        inspector = celery_app.control.inspect(timeout=5)
        queues = inspector.active_queues()

        if queues:
            gpu_workers = []
            for worker, queue_list in queues.items():
                for q in queue_list:
                    if q.get("name") == "gpu":
                        gpu_workers.append(worker)

            if gpu_workers:
                print(f"  [OK] GPU queue available on: {gpu_workers}")
                return True
            else:
                print(f"  [WARN] No workers on GPU queue")
                return False
        else:
            print(f"  [WARN] No queue information available")
            return False

    except Exception as e:
        print(f"  [FAIL] GPU queue check error: {e}")
        return False


def test_mock_mode():
    """Test mock mode functionality."""
    print("Testing mock mode...")

    try:
        os.environ["MOCK_GPU"] = "true"

        from synde_gpu.mocks import is_mock_mode, get_mock_response

        if not is_mock_mode():
            print(f"  [FAIL] Mock mode not enabled")
            return False

        # Test mock responses
        esmfold_result = get_mock_response("esmfold", "test", "MKTVRQ")
        if esmfold_result.get("status") == "success":
            print(f"  [OK] Mock ESMFold response working")
        else:
            print(f"  [FAIL] Mock ESMFold failed")
            return False

        clean_result = get_mock_response("clean_ec", "MKTVRQ")
        if clean_result.get("status") == "success":
            print(f"  [OK] Mock CLEAN EC response working")
        else:
            print(f"  [FAIL] Mock CLEAN EC failed")
            return False

        return True

    except Exception as e:
        print(f"  [FAIL] Mock mode error: {e}")
        return False

    finally:
        os.environ["MOCK_GPU"] = "false"


def test_workflow_mock():
    """Test workflow execution with mocks."""
    print("Testing workflow with mocks...")

    try:
        os.environ["MOCK_GPU"] = "true"

        from synde_graph.graph import run_workflow

        result = run_workflow(
            user_query="Predict EC number for P00720",
            job_id="test-connection",
        )

        if result and result.get("response"):
            print(f"  [OK] Workflow execution successful")
            print(f"      Nodes visited: {len(result.get('node_history', []))}")
            return True
        else:
            print(f"  [FAIL] Workflow returned no response")
            return False

    except Exception as e:
        print(f"  [FAIL] Workflow error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        os.environ["MOCK_GPU"] = "false"


def main():
    """Run all connection tests."""
    print("\n" + "=" * 50)
    print("SynDe LangGraph Connection Test")
    print("=" * 50 + "\n")

    results = {}

    results["Redis"] = test_redis_connection()
    print()

    results["Celery Broker"] = test_celery_broker()
    print()

    results["GPU Queue"] = test_gpu_queue()
    print()

    results["Mock Mode"] = test_mock_mode()
    print()

    results["Workflow (Mock)"] = test_workflow_mock()
    print()

    # Summary
    print("=" * 50)
    print("Summary")
    print("=" * 50)

    all_passed = True
    for test, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {test}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
