"""Tests for E3.09 MVP1: MCP tools for lint and state management."""

import json
import pytest


class TestLintTool:
    """lint_source MCP tool."""

    def test_returns_verdict(self, tmp_path):
        from lore_mcp.server import lint_source

        doc = tmp_path / "doc.md"
        doc.write_text("## Title\n\nGood content here with enough text.\n")

        result = lint_source(str(doc))
        assert "verdict" in result.lower() or "good" in result.lower() or "density" in result.lower()

    def test_missing_file(self, tmp_path):
        from lore_mcp.server import lint_source

        result = lint_source(str(tmp_path / "nonexistent.md"))
        assert "not found" in result.lower() or "error" in result.lower()


class TestListStateTool:
    """list_pipeline_state MCP tool."""

    def test_returns_format(self):
        from lore_mcp.server import list_pipeline_state

        result = list_pipeline_state()
        assert isinstance(result, str)

    def test_with_state(self, monkeypatch, tmp_path):
        from lore_mcp import checkpoint
        from lore_mcp.checkpoint import Checkpoint
        import yaml

        monkeypatch.setattr(checkpoint, "_state_dir", lambda: tmp_path)
        manifest = tmp_path / "m.yaml"
        manifest.write_text(yaml.dump({"collection": "test-mcp-tool", "sources": []}))
        cp = Checkpoint(str(manifest))
        cp.mark_phase_done("phase1")

        from lore_mcp.server import list_pipeline_state
        result = list_pipeline_state()
        assert "phase" in result.lower() or "state" in result.lower()


class TestPurgeStateTool:
    """purge_pipeline_state MCP tool."""

    def test_purge_nonexistent(self, monkeypatch, tmp_path):
        from lore_mcp import checkpoint
        monkeypatch.setattr(checkpoint, "_state_dir", lambda: tmp_path)
        from lore_mcp.server import purge_pipeline_state

        result = purge_pipeline_state(hash="nonexistent123456")
        assert "not found" in result.lower()

    def test_purge_all(self, monkeypatch, tmp_path):
        from lore_mcp import checkpoint
        monkeypatch.setattr(checkpoint, "_state_dir", lambda: tmp_path)
        from lore_mcp.server import purge_pipeline_state

        result = purge_pipeline_state(purge_all=True)
        assert "purged" in result.lower() or "0" in result

    def test_does_not_touch_real_state_dir(self, monkeypatch, tmp_path):
        """E12.76: purge tests must use isolated state dir."""
        import os
        from lore_mcp import checkpoint

        real_state = checkpoint._state_dir()
        sentinel = real_state / "_test_sentinel"
        sentinel.mkdir(parents=True, exist_ok=True)
        try:
            monkeypatch.setattr(checkpoint, "_state_dir", lambda: tmp_path)
            from lore_mcp.server import purge_pipeline_state
            purge_pipeline_state(purge_all=True)
            assert sentinel.exists(), "purge_all destroyed real state dir"
        finally:
            if sentinel.exists():
                sentinel.rmdir()


class TestServiceStatus:
    """E3.11: get_service_status MCP tool."""

    def test_returns_string(self):
        from lore_mcp.server import get_service_status

        result = get_service_status()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_shows_embedder(self):
        from lore_mcp.server import get_service_status

        result = get_service_status()
        assert "Embedder" in result

    def test_shows_no_services_when_empty(self):
        from lore_mcp.server import get_service_status
        from lore_mcp.preprocess.service import _running_services

        old = list(_running_services)
        _running_services.clear()
        try:
            result = get_service_status()
            assert "No services" in result
        finally:
            _running_services.extend(old)


class TestTaskTools:
    """E3.09a: task management MCP tools."""

    def test_get_task_status_not_found(self):
        from lore_mcp.server import get_task_status
        result = get_task_status(task_id="nonexistent")
        assert "not found" in result.lower()

    def test_get_task_status_completed(self):
        import time
        from lore_mcp.server import get_task_status, _task_manager
        task_id = _task_manager.start("test-tool", lambda: "ok")
        time.sleep(0.2)
        result = get_task_status(task_id=task_id)
        assert "completed" in result.lower()
        assert "ok" in result

    def test_cancel_task_not_found(self):
        from lore_mcp.server import cancel_task
        result = cancel_task(task_id="nonexistent")
        assert "cannot" in result.lower() or "not found" in result.lower()

    def test_list_tasks_empty(self):
        from lore_mcp.server import list_tasks, _task_manager
        _task_manager._tasks.clear()
        result = list_tasks()
        assert "no tasks" in result.lower()

    def test_list_tasks_shows_task(self):
        import time
        from lore_mcp.server import list_tasks, _task_manager
        _task_manager._tasks.clear()
        _task_manager.start("list-test", lambda: None)
        time.sleep(0.2)
        result = list_tasks()
        assert "list-test" in result
