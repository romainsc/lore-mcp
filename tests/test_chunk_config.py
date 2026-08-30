"""Tests for E6.04: configurable chunking. See docs/architecture.md."""

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from lore_mcp.store import create_tables, open_db


DIMS = 8


class TestDefaultChunkSize:
    def test_default_is_1024(self):
        """E6.04: changed from 2048 to 1024 per AutoRAG E1.08."""
        from lore_mcp.ingest import DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP
        assert DEFAULT_CHUNK_SIZE == 1024
        assert DEFAULT_CHUNK_OVERLAP == 128


class TestGetChunkConfig:
    def test_defaults(self):
        from lore_mcp.ingest import get_chunk_config
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LORE_CHUNK_SIZE", None)
            os.environ.pop("LORE_CHUNK_OVERLAP", None)
            size, overlap = get_chunk_config()
            assert size == 1024
            assert overlap == 128

    def test_env_override(self):
        from lore_mcp.ingest import get_chunk_config
        with patch.dict(os.environ, {"LORE_CHUNK_SIZE": "512", "LORE_CHUNK_OVERLAP": "64"}):
            size, overlap = get_chunk_config()
            assert size == 512
            assert overlap == 64

    def test_partial_override(self):
        from lore_mcp.ingest import get_chunk_config
        with patch.dict(os.environ, {"LORE_CHUNK_SIZE": "2048"}, clear=False):
            os.environ.pop("LORE_CHUNK_OVERLAP", None)
            size, overlap = get_chunk_config()
            assert size == 2048
            assert overlap == 128


class TestMetaChunkParams:
    def test_stores_chunk_params(self):
        """Meta table records chunk_size and chunk_overlap at ingestion."""
        from lore_mcp.store import create_tables
        db = open_db(":memory:")
        create_tables(db, "test", DIMS, chunk_size=1024, chunk_overlap=128)
        meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
        assert meta["chunk_size"] == "1024"
        assert meta["chunk_overlap"] == "128"
        db.close()

    def test_stores_default_chunk_params(self):
        """Without explicit params, no chunk meta stored (backward compat)."""
        from lore_mcp.store import create_tables
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)
        meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
        assert "chunk_size" not in meta
        db.close()


class TestDiscoverCollectionsChunkInfo:
    def test_includes_chunk_params(self, tmp_path):
        """discover_collections returns chunk_size/overlap per collection."""
        from lore_mcp.store import insert_chunk
        from lore_mcp.collections import discover_collections
        from conftest import make_embedding

        db_path = tmp_path / "docs-libre.db"
        db = open_db(str(db_path))
        create_tables(db, "test", DIMS, chunk_size=1024, chunk_overlap=128)
        insert_chunk(db, "c1", "f.md", 0, "text", make_embedding(0.1))
        db.close()

        colls = discover_collections(str(tmp_path))
        assert len(colls) == 1
        assert colls[0]["chunk_size"] == 1024
        assert colls[0]["chunk_overlap"] == 128

    def test_missing_chunk_params(self, tmp_path):
        """Old .db files without chunk meta return None."""
        from lore_mcp.store import insert_chunk
        from lore_mcp.collections import discover_collections
        from conftest import make_embedding

        db_path = tmp_path / "old-libre.db"
        db = open_db(str(db_path))
        create_tables(db, "test", DIMS)
        insert_chunk(db, "c1", "f.md", 0, "text", make_embedding(0.1))
        db.close()

        colls = discover_collections(str(tmp_path))
        assert colls[0]["chunk_size"] is None
