"""Tests for configurable chunking. See docs/architecture.md."""

from lore_mcp.config import LoreConfig
from lore_mcp.store import create_tables, open_db


DIMS = 8


class TestDefaultChunkSize:
    def test_default_is_1024(self):
        from lore_mcp.ingest import DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP
        assert DEFAULT_CHUNK_SIZE == 1024
        assert DEFAULT_CHUNK_OVERLAP == 128


class TestMetaChunkParams:
    def test_stores_chunk_params(self):
        db = open_db(":memory:")
        create_tables(db, "test", DIMS, chunk_size=1024, chunk_overlap=128)
        meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
        assert meta["chunk_size"] == "1024"
        assert meta["chunk_overlap"] == "128"
        db.close()

    def test_stores_default_chunk_params(self):
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)
        meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
        assert "chunk_size" not in meta
        db.close()
