"""Tests for E3.09a: TaskManager background task framework."""

import time
import threading
import pytest

from lore_mcp.task_manager import TaskManager, TaskInfo


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

    def test_cancel_pending(self):
        blocker = threading.Event()
        tm = TaskManager(max_concurrent=1)
        # First task blocks the semaphore
        tm.start("blocker", lambda: blocker.wait(timeout=5))
        time.sleep(0.1)
        # Second task should be pending
        task_id = tm.start("pending", lambda: "result")
        time.sleep(0.1)
        info = tm.status(task_id)
        assert info.status == "pending"
        assert tm.cancel(task_id)
        info = tm.status(task_id)
        assert info.status == "cancelled"
        blocker.set()

    def test_cancel_running_returns_false(self):
        blocker = threading.Event()
        tm = TaskManager()
        task_id = tm.start("running", lambda: blocker.wait(timeout=5))
        time.sleep(0.1)
        assert not tm.cancel(task_id)
        blocker.set()

    def test_cancel_nonexistent_returns_false(self):
        tm = TaskManager()
        assert not tm.cancel("nonexistent")


class TestSemaphore:

    def test_semaphore_limits_concurrent(self):
        results = []
        lock = threading.Lock()

        def tracked_task(idx):
            with lock:
                results.append(("start", idx))
            time.sleep(0.2)
            with lock:
                results.append(("end", idx))

        tm = TaskManager(max_concurrent=1)
        tm.start("t1", tracked_task, args=(1,))
        tm.start("t2", tracked_task, args=(2,))
        time.sleep(0.8)

        starts = [r for r in results if r[0] == "start"]
        ends = [r for r in results if r[0] == "end"]
        assert len(starts) == 2
        assert len(ends) == 2
        # t1 must end before t2 starts (serial execution)
        t1_end_idx = results.index(("end", 1))
        t2_start_idx = results.index(("start", 2))
        assert t1_end_idx < t2_start_idx


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


class TestUpdateProgress:

    def test_update_progress(self):
        blocker = threading.Event()
        tm = TaskManager()
        task_id = tm.start("progress-test", lambda: blocker.wait(timeout=5))
        time.sleep(0.1)
        tm.update_progress(task_id, "Phase 2: captioning 25/49")
        info = tm.status(task_id)
        assert info.progress == "Phase 2: captioning 25/49"
        blocker.set()
