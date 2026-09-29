"""Background task manager for long-running MCP operations. See docs/studies/grooming-E3.09.md."""

import logging
import threading
import time
import uuid
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TaskInfo:
    """Status of a background task."""

    id: str
    name: str
    status: str = "pending"
    progress: str = ""
    result: str = ""
    error: str = ""
    started_at: float = 0
    completed_at: float = 0


class TaskManager:
    """Manage background tasks with semaphore-limited concurrency."""

    def __init__(self, max_concurrent: int = 1):
        self._tasks: dict[str, TaskInfo] = {}
        self._lock = threading.Lock()
        self._sem = threading.Semaphore(max_concurrent)

    def start(self, name: str, fn, args=(), kwargs=None) -> str:
        """Start a background task. Returns task_id."""
        task_id = uuid.uuid4().hex[:8]
        info = TaskInfo(id=task_id, name=name, started_at=time.time())
        with self._lock:
            self._tasks[task_id] = info

        def _worker():
            acquired = self._sem.acquire(timeout=0)
            if not acquired:
                info.status = "pending"
                info.progress = "Waiting for another task to finish"
                self._sem.acquire()
            info.status = "running"
            try:
                result = fn(*args, **(kwargs or {}))
                info.status = "completed"
                info.result = str(result) if result else "done"
            except Exception as e:
                info.status = "failed"
                info.error = str(e)
                logger.warning("Task %s (%s) failed: %s", task_id, name, e)
            finally:
                info.completed_at = time.time()
                self._sem.release()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return task_id

    def status(self, task_id: str) -> TaskInfo | None:
        """Get task status by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending task. Returns True if cancelled."""
        with self._lock:
            info = self._tasks.get(task_id)
        if info and info.status == "pending":
            info.status = "cancelled"
            info.completed_at = time.time()
            return True
        return False

    def list_tasks(self) -> list[TaskInfo]:
        """List all tasks."""
        with self._lock:
            return list(self._tasks.values())

    def update_progress(self, task_id: str, progress: str) -> None:
        """Update progress message for a running task."""
        with self._lock:
            info = self._tasks.get(task_id)
        if info and info.status == "running":
            info.progress = progress
