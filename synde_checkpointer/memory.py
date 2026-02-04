"""
In-memory checkpointer for testing.
"""

from typing import Any, Dict, Optional, Iterator
from datetime import datetime, timezone
from dataclasses import dataclass, field
import copy


@dataclass
class CheckpointEntry:
    """A single checkpoint entry."""
    thread_id: str
    checkpoint_ns: str
    checkpoint_id: str
    checkpoint: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryCheckpointer:
    """
    Simple in-memory checkpointer for testing.

    Stores checkpoints in a dictionary, useful for unit tests
    and quick prototyping without persistence requirements.
    """

    def __init__(self):
        """Initialize empty checkpoint storage."""
        self._checkpoints: Dict[str, CheckpointEntry] = {}
        self._counter = 0

    def _make_key(self, thread_id: str, checkpoint_ns: str = "") -> str:
        """Create a storage key from thread_id and namespace."""
        return f"{thread_id}:{checkpoint_ns}"

    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store a checkpoint.

        Args:
            config: Configuration with thread_id
            checkpoint: State to checkpoint
            metadata: Optional metadata

        Returns:
            Checkpoint ID
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")

        self._counter += 1
        checkpoint_id = f"checkpoint-{self._counter}"

        key = self._make_key(thread_id, checkpoint_ns)

        entry = CheckpointEntry(
            thread_id=thread_id,
            checkpoint_ns=checkpoint_ns,
            checkpoint_id=checkpoint_id,
            checkpoint=copy.deepcopy(checkpoint),
            metadata=metadata or {},
        )

        self._checkpoints[key] = entry

        return checkpoint_id

    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointEntry]:
        """
        Get a checkpoint entry.

        Args:
            config: Configuration with thread_id

        Returns:
            CheckpointEntry or None
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")

        key = self._make_key(thread_id, checkpoint_ns)
        return self._checkpoints.get(key)

    def get(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get checkpoint state.

        Args:
            config: Configuration with thread_id

        Returns:
            Checkpoint state or None
        """
        entry = self.get_tuple(config)
        if entry:
            return copy.deepcopy(entry.checkpoint)
        return None

    def list(
        self,
        config: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointEntry]:
        """
        List checkpoints.

        Args:
            config: Optional filter by thread_id
            limit: Maximum entries to return

        Yields:
            CheckpointEntry objects
        """
        entries = list(self._checkpoints.values())

        if config:
            thread_id = config.get("configurable", {}).get("thread_id")
            if thread_id:
                entries = [e for e in entries if e.thread_id == thread_id]

        # Sort by creation time (newest first)
        entries.sort(key=lambda e: e.created_at, reverse=True)

        if limit:
            entries = entries[:limit]

        yield from entries

    def delete(self, config: Dict[str, Any]) -> bool:
        """
        Delete a checkpoint.

        Args:
            config: Configuration with thread_id

        Returns:
            True if deleted, False if not found
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")

        key = self._make_key(thread_id, checkpoint_ns)

        if key in self._checkpoints:
            del self._checkpoints[key]
            return True
        return False

    def clear(self):
        """Clear all checkpoints."""
        self._checkpoints.clear()
        self._counter = 0

    def __len__(self) -> int:
        """Return number of stored checkpoints."""
        return len(self._checkpoints)
