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


class TestStartBuild:
    """E3.09b: start_build MCP tool."""

    def test_returns_task_id(self, monkeypatch):
        from lore_mcp.server import start_build
        monkeypatch.setattr(
            "lore_mcp.build.run_build",
            lambda *a, **kw: {"collection": "test", "file_count": 0},
        )
        result = start_build(recipe="/fake/recipe.yaml", build_dir="/tmp/test-build")
        assert "started" in result.lower()
        assert "get_task_status" in result


class TestStartPreprocess:
    """E3.09c: start_preprocess MCP tool."""

    def test_returns_task_id(self, monkeypatch):
        from lore_mcp.server import start_preprocess
        monkeypatch.setattr(
            "lore_mcp.preprocess.preprocess_sources",
            lambda *a, **kw: [],
        )
        result = start_preprocess(recipe="/fake/recipe.yaml", build_dir="/tmp/test-prep")
        assert "started" in result.lower()
        assert "get_task_status" in result


class TestRemoveSource:
    """E3.09d: remove_source MCP tool."""

    def test_no_db(self, tmp_path):
        from lore_mcp.server import remove_source
        result = remove_source(source="doc.md", build_dir=str(tmp_path))
        assert "no .db" in result.lower()

    def test_source_not_found(self, tmp_path):
        from lore_mcp.server import remove_source
        from lore_mcp.store import open_db, create_tables
        db_path = tmp_path / "test.db"
        db = open_db(str(db_path))
        create_tables(db, "test-model", 768)
        db.close()
        result = remove_source(source="nonexistent.md", build_dir=str(tmp_path))
        assert "not found" in result.lower()


class TestInvalidateDb:
    """E3.16: db connection invalidated after add/remove."""

    def test_invalidate_resets_single_db(self):
        import lore_mcp.server as srv
        srv._single_db = "fake-connection"
        srv._invalidate_db()
        assert srv._single_db is None

    def test_remove_source_invalidates(self, tmp_path):
        """After remove_source, _single_db must be None."""
        import lore_mcp.server as srv
        from lore_mcp.store import open_db, create_tables, insert_chunks

        db_path = tmp_path / "test.db"
        db = open_db(str(db_path))
        create_tables(db, "test-model", 768)
        db.execute(
            "INSERT INTO sources (source_file, title) VALUES (?, ?)",
            ("doc.md", "Test"),
        )
        db.execute(
            "INSERT INTO chunks (id, source_file, chunk_index, content) "
            "VALUES (?, ?, ?, ?)",
            ("c1", "doc.md", 0, "content"),
        )
        db.commit()
        db.close()

        srv._single_db = "old-connection"
        result = srv.remove_source(source="doc.md", build_dir=str(tmp_path))
        assert "removed" in result.lower()
        assert srv._single_db is None


class TestIngestSource:
    """E3.14: incremental ingest into existing .db."""

    def test_preserves_existing_sources(self, tmp_path):
        """add_source must not destroy existing sources."""
        from lore_mcp.store import open_db, create_tables
        from lore_mcp.ingest import ingest_source, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP

        db_path = tmp_path / "test.db"
        db = open_db(str(db_path))
        create_tables(db, "test-model", 768, chunk_size=1024, chunk_overlap=128)
        db.execute(
            "INSERT INTO sources (source_file, title) VALUES (?, ?)",
            ("existing.md", "Existing Doc"),
        )
        db.execute(
            "INSERT INTO source_hashes (source_file, content_hash, indexed_at) VALUES (?, ?, ?)",
            ("existing.md", "abc123", "2026-01-01"),
        )
        db.execute(
            "INSERT INTO chunks (id, source_file, chunk_index, content) "
            "VALUES (?, ?, ?, ?)",
            ("e1", "existing.md", 0, "existing content"),
        )
        db.commit()
        db.close()

        new_file = tmp_path / "new.md"
        new_file.write_text("## New Document\n\nThis is new content for testing incremental ingest.\n" * 5)

        class FakeEmbedder:
            model_name = "test-model"
            model_dim = 768
            api_batch_size = None
            def embed_batch(self, texts):
                return [[0.1] * 768 for _ in texts]

        result = ingest_source(str(db_path), new_file, FakeEmbedder())
        assert result["file_count"] == 1
        assert result["chunk_count"] > 0

        db = open_db(str(db_path))
        sources = db.execute("SELECT source_file FROM sources ORDER BY source_file").fetchall()
        source_names = [s[0] for s in sources]
        assert "existing.md" in source_names
        assert "new.md" in source_names
        db.close()

    def test_reads_chunk_params_from_db(self, tmp_path):
        """ingest_source must use chunk params from db meta, not defaults."""
        from lore_mcp.store import open_db, create_tables
        from lore_mcp.ingest import ingest_source

        db_path = tmp_path / "test.db"
        db = open_db(str(db_path))
        create_tables(db, "test-model", 768, chunk_size=2048, chunk_overlap=256)
        db.close()

        doc = tmp_path / "doc.md"
        doc.write_text("## Test\n\nContent for chunk param test.\n" * 10)

        class FakeEmbedder:
            model_name = "test-model"
            model_dim = 768
            api_batch_size = None
            def embed_batch(self, texts):
                return [[0.1] * 768 for _ in texts]

        result = ingest_source(str(db_path), doc, FakeEmbedder())
        assert result["chunk_count"] > 0

        db = open_db(str(db_path))
        meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
        assert meta["chunk_size"] == "2048"
        assert meta["chunk_overlap"] == "256"
        db.close()

    def test_rejects_model_mismatch(self, tmp_path):
        """ingest_source must reject if model doesn't match db."""
        from lore_mcp.store import open_db, create_tables
        from lore_mcp.ingest import ingest_source

        db_path = tmp_path / "test.db"
        db = open_db(str(db_path))
        create_tables(db, "model-A", 768)
        db.close()

        doc = tmp_path / "doc.md"
        doc.write_text("## Test\n\nContent.\n")

        class FakeEmbedder:
            model_name = "model-B"
            model_dim = 768
            api_batch_size = None
            def embed_batch(self, texts):
                return [[0.1] * 768 for _ in texts]

        with pytest.raises(ValueError, match="model"):
            ingest_source(str(db_path), doc, FakeEmbedder())

    def test_reindex_replaces_chunks(self, tmp_path):
        """ingest_source on existing source replaces old chunks."""
        from lore_mcp.store import open_db, create_tables
        from lore_mcp.ingest import ingest_source

        db_path = tmp_path / "test.db"
        db = open_db(str(db_path))
        create_tables(db, "test-model", 768)
        db.execute(
            "INSERT INTO sources (source_file) VALUES (?)", ("doc.md",)
        )
        db.execute(
            "INSERT INTO chunks (id, source_file, chunk_index, content) "
            "VALUES (?, ?, ?, ?)",
            ("old1", "doc.md", 0, "old content"),
        )
        db.commit()
        db.close()

        doc = tmp_path / "doc.md"
        doc.write_text("## Updated\n\nNew content replaces old content for testing.\n" * 5)

        class FakeEmbedder:
            model_name = "test-model"
            model_dim = 768
            api_batch_size = None
            def embed_batch(self, texts):
                return [[0.1] * 768 for _ in texts]

        result = ingest_source(str(db_path), doc, FakeEmbedder())
        assert result["chunk_count"] > 0

        db = open_db(str(db_path))
        old = db.execute("SELECT id FROM chunks WHERE id = 'old1'").fetchone()
        assert old is None
        new_count = db.execute("SELECT COUNT(*) FROM chunks WHERE source_file = 'doc.md'").fetchone()[0]
        assert new_count == result["chunk_count"]
        db.close()


class TestStartEval:
    """E3.09e: start_eval MCP tool."""

    def test_no_db(self, tmp_path):
        from lore_mcp.server import start_eval
        result = start_eval(build_dir=str(tmp_path))
        assert "no .db" in result.lower()


class TestStartOptimize:
    """E3.09e: start_optimize MCP tool."""

    def test_returns_task_id(self, monkeypatch):
        from lore_mcp.server import start_optimize
        monkeypatch.setattr(
            "lore_mcp.eval.run_optimize",
            lambda **kw: {"best": {"chunk_size": 1024, "chunk_overlap": 128, "top_k": 5, "avg_score": 0.5}},
        )
        result = start_optimize(recipe="/fake/recipe.yaml", build_dir="/tmp/test-opt")
        assert "started" in result.lower()


class TestStartEnrich:
    """E3.09f: start_enrich MCP tool."""

    def test_returns_task_id(self, monkeypatch):
        from lore_mcp.server import start_enrich
        monkeypatch.setattr(
            "lore_mcp.preprocess.preprocess_sources",
            lambda *a, **kw: [],
        )
        result = start_enrich(recipe="/fake/recipe.yaml", build_dir="/tmp/test-enrich")
        assert "started" in result.lower()
