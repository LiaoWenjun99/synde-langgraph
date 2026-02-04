"""
SQLite checkpointer for CLI and local testing.
"""

import json
import sqlite3
from typing import Any, Dict, Optional, Iterator
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CheckpointEntry:
    """A single checkpoint entry."""
    thread_id: str
    checkpoint_ns: str
    checkpoint_id: str
    checkpoint: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: datetime


class SqliteCheckpointer:
    """
    SQLite-based checkpointer for CLI and local testing.

    Persists checkpoints to a local SQLite database, useful for
    CLI workflows and development without Redis.
    """

    def __init__(self, db_path: str = "checkpoints.db"):
        """
        Initialize SQLite checkpointer.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT DEFAULT '',
                    checkpoint_id TEXT NOT NULL,
                    checkpoint_data TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(thread_id, checkpoint_ns)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_thread_id
                ON checkpoints(thread_id)
            """)
            conn.commit()

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
        checkpoint_id = f"cp-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO checkpoints
                (thread_id, checkpoint_ns, checkpoint_id, checkpoint_data, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                json.dumps(checkpoint),
                json.dumps(metadata or {}),
                datetime.now(timezone.utc).isoformat(),
            ))
            conn.commit()

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

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT thread_id, checkpoint_ns, checkpoint_id, checkpoint_data, metadata, created_at
                FROM checkpoints
                WHERE thread_id = ? AND checkpoint_ns = ?
            """, (thread_id, checkpoint_ns))

            row = cursor.fetchone()

        if row:
            return CheckpointEntry(
                thread_id=row[0],
                checkpoint_ns=row[1],
                checkpoint_id=row[2],
                checkpoint=json.loads(row[3]),
                metadata=json.loads(row[4]),
                created_at=datetime.fromisoformat(row[5]),
            )

        return None

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
            return entry.checkpoint
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
        query = "SELECT thread_id, checkpoint_ns, checkpoint_id, checkpoint_data, metadata, created_at FROM checkpoints"
        params = []

        if config:
            thread_id = config.get("configurable", {}).get("thread_id")
            if thread_id:
                query += " WHERE thread_id = ?"
                params.append(thread_id)

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)

            for row in cursor:
                yield CheckpointEntry(
                    thread_id=row[0],
                    checkpoint_ns=row[1],
                    checkpoint_id=row[2],
                    checkpoint=json.loads(row[3]),
                    metadata=json.loads(row[4]),
                    created_at=datetime.fromisoformat(row[5]),
                )

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

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM checkpoints
                WHERE thread_id = ? AND checkpoint_ns = ?
            """, (thread_id, checkpoint_ns))
            conn.commit()

            return cursor.rowcount > 0

    def clear(self):
        """Clear all checkpoints."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM checkpoints")
            conn.commit()
