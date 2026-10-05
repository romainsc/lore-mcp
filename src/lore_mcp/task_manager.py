"""Background task manager for long-running MCP operations. See docs/studies/grooming-E3.09.md."""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field

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
    cancel_event: threading.Event = field(default_factory=threading.Event)


_global_shutdown = threading.Event()


def check_cancelled():
    """Raise KeyboardInterrupt if shutdown requested or task cancelled."""
    if _global_shutdown.is_set():
        raise KeyboardInterrupt("Shutdown requested")
    info = getattr(threading.current_thread(), "_task_info", None)
    if info and info.cancel_event.is_set():
        raise KeyboardInterrupt("Task cancelled")


class ModelRegistry:
    """Track loaded models and manage resource slots (LOCAL_GPU, LOCAL_CPU, REMOTE)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._model_users: dict[str, int] = {}
        self._loaded: dict[str, str] = {}
        self._slot_events: dict[str, threading.Event] = {
            "local_gpu": threading.Event(),
            "local_cpu": threading.Event(),
        }
        for ev in self._slot_events.values():
            ev.set()

    def acquire(self, model_name: str, resource_type: str, llm_entry: dict | None = None) -> None:
        """Acquire a model for use. Waits if slot occupied by a different model."""
        with self._lock:
            if model_name in self._model_users and self._model_users[model_name] > 0:
                self._model_users[model_name] += 1
                return

        if resource_type in ("local_gpu", "local_cpu"):
            slot_event = self._slot_events[resource_type]
            model_to_stop = None
            while True:
                with self._lock:
                    current = self._loaded.get(resource_type)
                    if current is None or current == model_name:
                        self._loaded[resource_type] = model_name
                        self._model_users[model_name] = self._model_users.get(model_name, 0) + 1
                        slot_event.clear()
                        break
                    if self._model_users.get(current, 0) == 0:
                        self._loaded[resource_type] = model_name
                        self._model_users.pop(current, None)
                        self._model_users[model_name] = 1
                        model_to_stop = current
                        break
                    wait_model = current

                logger.warning("Waiting for %s slot: %s in use", resource_type, wait_model)
                slot_event.wait(timeout=2.0)
                continue

            if model_to_stop:
                self._stop_model(model_to_stop, llm_entry)
            self._start_model(model_name, llm_entry)
        else:
            with self._lock:
                self._model_users[model_name] = self._model_users.get(model_name, 0) + 1

    def release(self, model_name: str) -> None:
        """Release a model after use. Model stays loaded (lazy stop)."""
        with self._lock:
            if model_name in self._model_users:
                self._model_users[model_name] = max(0, self._model_users[model_name] - 1)
                if self._model_users[model_name] == 0:
                    for slot, loaded in self._loaded.items():
                        if loaded == model_name:
                            self._slot_events[slot].set()

    def _start_model(self, model_name: str, llm_entry: dict | None) -> None:
        """Start a model service if it has a start command."""
        if llm_entry and llm_entry.get("start"):
            from lore_mcp.preprocess.service import start_service
            start_service(llm_entry)

    def _stop_model(self, model_name: str, llm_entry: dict | None) -> None:
        """Stop a model service."""
        if llm_entry and llm_entry.get("stop"):
            from lore_mcp.preprocess.service import stop_service
            logger.info("Stopping %s to free slot", model_name)
            stop_service(llm_entry)

    def get_loaded(self) -> dict[str, str]:
        """Return currently loaded models per slot."""
        with self._lock:
            return dict(self._loaded)

    def get_users(self) -> dict[str, int]:
        """Return model usage counts."""
        with self._lock:
            return dict(self._model_users)


def report_progress(message: str) -> None:
    """Report progress from within a running task."""
    import threading
    info = getattr(threading.current_thread(), "_task_info", None)
    if info:
        info.progress = message


class TaskManager:
    """Manage background tasks with resource-aware scheduling."""

    def __init__(self):
        self._tasks: dict[str, TaskInfo] = {}
        self._lock = threading.Lock()
        self.models = ModelRegistry()

    def start(self, name: str, fn, args=(), kwargs=None, models=None) -> str:
        """Start a background task. Returns task_id.

        models: list of (model_name, resource_type, llm_entry) tuples
        the task needs. Resources are acquired before running.
        """
        task_id = uuid.uuid4().hex[:8]
        info = TaskInfo(id=task_id, name=name, started_at=time.time())
        model_list = models or []
        with self._lock:
            self._tasks[task_id] = info

        def _worker():
            import io
            import sys
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            acquired = []
            try:
                for model_name, resource_type, llm_entry in model_list:
                    info.status = "pending"
                    info.progress = f"Acquiring {model_name} ({resource_type})"
                    self.models.acquire(model_name, resource_type, llm_entry)
                    acquired.append(model_name)

                info.status = "running"
                info.progress = ""
                import threading
                threading.current_thread()._task_info = info
                result = fn(*args, **(kwargs or {}))
                info.status = "completed"
                info.result = str(result) if result else "done"
            except KeyboardInterrupt:
                info.status = "cancelled"
                info.error = "Task cancelled"
                logger.info("Task %s (%s) cancelled", task_id, name)
            except Exception as e:
                info.status = "failed"
                info.error = str(e)
                logger.warning("Task %s (%s) failed: %s", task_id, name, e)
            finally:
                info.completed_at = time.time()
                for m in acquired:
                    self.models.release(m)
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return task_id

    def status(self, task_id: str) -> TaskInfo | None:
        """Get task status by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending or running task. Returns True if cancellation initiated."""
        with self._lock:
            info = self._tasks.get(task_id)
        if not info:
            return False
        if info.status == "pending":
            info.status = "cancelled"
            info.completed_at = time.time()
            return True
        if info.status == "running":
            info.cancel_event.set()
            return True
        return False

    def list_tasks(self) -> list[TaskInfo]:
        """List all tasks."""
        with self._lock:
            return list(self._tasks.values())

