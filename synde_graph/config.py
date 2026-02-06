"""
Configuration settings for SynDe LangGraph workflow.

Centralizes timeouts, paths, and other settings that can be overridden
via environment variables.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# =============================================================================
# Redis Configuration
# =============================================================================

REDIS_HOST = os.getenv("REDIS_HOST", "172.31.19.34")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"

# LangGraph checkpoint database (separate from synde-minimal)
LANGGRAPH_CHECKPOINT_DB = int(os.getenv("LANGGRAPH_CHECKPOINT_DB", "3"))


# =============================================================================
# Celery Configuration
# =============================================================================

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", f"{REDIS_URL}/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", f"{REDIS_URL}/1")


# =============================================================================
# GPU Task Timeouts (in seconds)
# =============================================================================

class GpuTimeouts:
    """Timeout settings for GPU tasks."""

    ESMFOLD = int(os.getenv("TIMEOUT_ESMFOLD", "180"))  # 30 minutes
    ALPHAFOLD = int(os.getenv("TIMEOUT_ALPHAFOLD", "3600"))  # 60 minutes
    CLEAN_EC = int(os.getenv("TIMEOUT_CLEAN_EC", "180"))  # 30 minutes
    DEEPENZYME = int(os.getenv("TIMEOUT_DEEPENZYME", "180"))  # 30 minutes
    TEMBERTURE = int(os.getenv("TIMEOUT_TEMBERTURE", "180"))  # 30 minutes
    FLAN_EXTRACTOR = int(os.getenv("TIMEOUT_FLAN", "180"))  # 3 minutes
    FPOCKET = int(os.getenv("TIMEOUT_FPOCKET", "180"))  # 3 minutes

    # Polling intervals
    POLL_INTERVAL = int(os.getenv("GPU_POLL_INTERVAL", "5"))  # seconds
    CHECKPOINT_INTERVAL = int(os.getenv("CHECKPOINT_INTERVAL", "30"))  # seconds


# =============================================================================
# Output Directories
# =============================================================================

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "synde_outputs"))

class OutputPaths:
    """Output directory paths."""

    ROOT = OUTPUT_DIR
    ESMFOLD = OUTPUT_DIR / "ESMFold"
    ALPHAFOLD = OUTPUT_DIR / "AlphaFold3"
    FPOCKET_WT = OUTPUT_DIR / "fpocket_results" / "wild_type"
    FPOCKET_MUT = OUTPUT_DIR / "fpocket_results" / "mutants"
    FOLDX = OUTPUT_DIR / "foldx"
    ZYMCTRL = OUTPUT_DIR / "ZymCTRL"
    DIFFDOCK = OUTPUT_DIR / "diffdock_output"

    @classmethod
    def ensure_all(cls) -> None:
        """Create all output directories."""
        for attr in dir(cls):
            if not attr.startswith("_") and attr.isupper():
                path = getattr(cls, attr)
                if isinstance(path, Path):
                    path.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Sequence Limits
# =============================================================================

class SequenceLimits:
    """Sequence length limits for different predictors."""

    ESMFOLD_MAX = 400  # ESMFold limit
    MIN_SEQUENCE = 10  # Minimum valid sequence
    MAX_SEQUENCE = 2000  # Maximum supported sequence


# =============================================================================
# Mock Mode
# =============================================================================

MOCK_GPU = os.getenv("MOCK_GPU", "false").lower() in ("true", "1", "yes")


# =============================================================================
# LLM Configuration
# =============================================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "claude-3-5-sonnet-20241022")


# =============================================================================
# Distributed Lock Settings
# =============================================================================

class LockSettings:
    """Settings for distributed locks."""

    DEFAULT_TIMEOUT = int(os.getenv("LOCK_TIMEOUT", "30"))  # seconds
    RETRY_INTERVAL = float(os.getenv("LOCK_RETRY_INTERVAL", "0.5"))  # seconds
    MAX_RETRIES = int(os.getenv("LOCK_MAX_RETRIES", "10"))


def get_redis_url(db: Optional[int] = None) -> str:
    """Get Redis URL with optional database number."""
    if db is not None:
        return f"{REDIS_URL}/{db}"
    return REDIS_URL
