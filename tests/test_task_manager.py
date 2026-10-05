"""Tests for TaskManager and ModelRegistry. See E3.09a, E3.13."""

import time
import threading
import pytest

from lore_mcp.task_manager import TaskManager, TaskInfo, ModelRegistry


class TestTaskStart:

    def test_start_returns_id(self):
        tm = TaskManager()
        task_id = tm.start("test", lambda: "result")
        assert isinstance(task_id, str)
        assert len(task_id) == 8

    def test_status_tracks_completion(self):
        tm = TaskManager()
        task_id = tm.start("test", lambda: "hello")
        time.sleep(0.2)
        info = tm.status(task_id)
        assert info is not None
        assert info.status == "completed"
        assert info.result == "hello"
        assert info.completed_at > info.started_at

    def test_failed_task_captures_error(self):
        def failing():
            raise ValueError("boom")

        tm = TaskManager()
        task_id = tm.start("fail-test", failing)
        time.sleep(0.2)
        info = tm.status(task_id)
        assert info.status == "failed"
        assert "boom" in info.error

    def test_unknown_task_returns_none(self):
        tm = TaskManager()
        assert tm.status("nonexistent") is None


class TestTaskCancel:

    def test_cancel_nonexistent_returns_false(self):
        tm = TaskManager()
        assert not tm.cancel("nonexistent")


class TestListTasks:

    def test_list_empty(self):
        tm = TaskManager()
        assert tm.list_tasks() == []

    def test_list_shows_all(self):
        tm = TaskManager()
        tm.start("a", lambda: None)
        tm.start("b", lambda: None)
        time.sleep(0.2)
        tasks = tm.list_tasks()
        assert len(tasks) == 2
        names = {t.name for t in tasks}
        assert names == {"a", "b"}


class TestModelRegistry:

    def test_acquire_release_basic(self):
        reg = ModelRegistry()
        reg.acquire("model-a", "remote")
        assert reg.get_users()["model-a"] == 1
        reg.release("model-a")
        assert reg.get_users()["model-a"] == 0

    def test_same_model_concurrent(self):
        """Two tasks using the same model → both get it."""
        reg = ModelRegistry()
        reg.acquire("tei", "local_gpu")
        reg.acquire("tei", "local_gpu")
        assert reg.get_users()["tei"] == 2
        reg.release("tei")
        assert reg.get_users()["tei"] == 1
        reg.release("tei")
        assert reg.get_users()["tei"] == 0

    def test_different_gpu_models_serialized(self):
        """Two different LOCAL_GPU models → second waits for first to be released."""
        reg = ModelRegistry()
        reg.acquire("model-a", "local_gpu")
        assert reg.get_loaded().get("local_gpu") == "model-a"

        acquired = threading.Event()

        def acquire_b():
            reg.acquire("model-b", "local_gpu")
            acquired.set()

        t = threading.Thread(target=acquire_b, daemon=True)
        t.start()
        time.sleep(0.3)
        assert not acquired.is_set(), "model-b should be waiting"

        reg.release("model-a")
        acquired.wait(timeout=5)
        assert acquired.is_set(), "model-b should have acquired after release"
        assert reg.get_loaded().get("local_gpu") == "model-b"
        reg.release("model-b")

    def test_gpu_and_remote_parallel(self):
        """LOCAL_GPU + REMOTE → both run immediately."""
        reg = ModelRegistry()
        reg.acquire("tei", "local_gpu")
        reg.acquire("granite-8b", "remote")
        assert reg.get_users()["tei"] == 1
        assert reg.get_users()["granite-8b"] == 1
        reg.release("tei")
        reg.release("granite-8b")

    def test_gpu_and_cpu_parallel(self):
        """LOCAL_GPU + LOCAL_CPU → both run (different slots)."""
        reg = ModelRegistry()
        reg.acquire("tei", "local_gpu")
        reg.acquire("stt", "local_cpu")
        assert reg.get_users()["tei"] == 1
        assert reg.get_users()["stt"] == 1
        reg.release("tei")
        reg.release("stt")

    def test_lazy_stop(self):
        """Model stays loaded after release (lazy stop)."""
        reg = ModelRegistry()
        reg.acquire("tei", "local_gpu")
        reg.release("tei")
        assert reg.get_loaded().get("local_gpu") == "tei"
        assert reg.get_users()["tei"] == 0

    def test_idle_model_swapped_for_new(self):
        """An idle model (users=0) is swapped when a new model needs the slot."""
        reg = ModelRegistry()
        reg.acquire("model-a", "local_gpu")
        reg.release("model-a")
        assert reg.get_loaded()["local_gpu"] == "model-a"

        reg.acquire("model-b", "local_gpu")
        assert reg.get_loaded()["local_gpu"] == "model-b"
        assert reg.get_users()["model-b"] == 1
        reg.release("model-b")


class TestTaskManagerWithModels:

    def test_task_with_models(self):
        """Task acquires and releases models."""
        tm = TaskManager()
        task_id = tm.start(
            "build", lambda: "done",
            models=[("tei", "local_gpu", None)],
        )
        time.sleep(0.3)
        info = tm.status(task_id)
        assert info.status == "completed"
        assert tm.models.get_users().get("tei", 0) == 0

    def test_two_tasks_same_model_parallel(self):
        """Two tasks needing the same model run concurrently."""
        results = []
        lock = threading.Lock()

        def task(idx):
            with lock:
                results.append(("start", idx))
            time.sleep(0.2)
            with lock:
                results.append(("end", idx))

        tm = TaskManager()
        tm.start("t1", task, args=(1,), models=[("tei", "local_gpu", None)])
        tm.start("t2", task, args=(2,), models=[("tei", "local_gpu", None)])
        time.sleep(0.8)

        starts = [r for r in results if r[0] == "start"]
        assert len(starts) == 2
        # Both should start before either ends (parallel)
        t1_start = results.index(("start", 1))
        t2_start = results.index(("start", 2))
        t1_end = results.index(("end", 1))
        assert t2_start < t1_end, "Both tasks should run concurrently"

    def test_two_tasks_different_gpu_serialized(self):
        """Two tasks needing different GPU models → second waits."""
        order = []
        lock = threading.Lock()

        def task(name):
            with lock:
                order.append(("start", name))
            time.sleep(0.3)
            with lock:
                order.append(("end", name))

        tm = TaskManager()
        tm.start("t1", task, args=("a",), models=[("model-a", "local_gpu", None)])
        time.sleep(0.05)
        tm.start("t2", task, args=("b",), models=[("model-b", "local_gpu", None)])
        time.sleep(1.0)

        assert len(order) == 4
        a_end = order.index(("end", "a"))
        b_start = order.index(("start", "b"))
        assert a_end < b_start, "model-b task must wait for model-a task"


class TestStdoutIsolation:
    """E12.113: task threads must not write to real stdout."""

    def test_print_in_task_does_not_reach_stdout(self, capsys):
        import time

        def noisy_task():
            print("THIS SHOULD NOT APPEAR ON STDOUT")
            return "done"

        tm = TaskManager()
        task_id = tm.start("noisy", noisy_task)
        time.sleep(0.5)

        captured = capsys.readouterr()
        assert "THIS SHOULD NOT APPEAR" not in captured.out, (
            f"Task stdout leaked to real stdout: {captured.out!r}"
        )


class TestCancelRunningTask:
    """E12.111: cancel_task must stop running tasks."""

    def test_cancel_running_task(self):
        from lore_mcp.task_manager import check_cancelled

        blocker = threading.Event()

        def cancellable_task():
            for _ in range(100):
                check_cancelled()
                blocker.wait(timeout=0.05)

        tm = TaskManager()
        task_id = tm.start("cancel-test", cancellable_task)
        time.sleep(0.1)

        info = tm.status(task_id)
        assert info.status == "running"

        result = tm.cancel(task_id)
        assert result is True

        time.sleep(0.5)
        info = tm.status(task_id)
        assert info.status == "cancelled", f"Expected cancelled, got {info.status}"

    def test_cancel_pending_still_works(self):
        blocker = threading.Event()
        tm = TaskManager()
        task_id = tm.start("pending-cancel", lambda: blocker.wait(timeout=5),
                           models=[("fake-model", "local_gpu", None)])
        time.sleep(0.05)
        result = tm.cancel(task_id)
        assert result is True
