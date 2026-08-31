"""Tests for model info exposure in collections and list_collections.

A third-party .db must be usable without prior knowledge of
which embedding model was used to create it.
"""

import os
from unittest.mock import patch

import pytest

from conftest import DIMS, make_embedding
from lore_mcp.store import create_tables, insert_chunk, open_db


class TestDiscoverCollectionsModel:
    def test_includes_model_name(self, tmp_path):
        from lore_mcp.collections import discover_collections

        db = open_db(str(tmp_path / "docs-libre.db"))
        create_tables(db, "BAAI/bge-m3", DIMS, chunk_size=1024, chunk_overlap=128)
        insert_chunk(db, "c1", "f.md", 0, "text", make_embedding(0.1))
        db.close()

        colls = discover_collections(str(tmp_path))
        assert colls[0]["model_name"] == "BAAI/bge-m3"
        assert colls[0]["model_dim"] == DIMS

    def test_different_models_per_collection(self, tmp_path):
        from lore_mcp.collections import discover_collections

        for name, model, dim in [
            ("en-libre", "BAAI/bge-m3", 1024),
            ("fr-libre", "sentence-transformers/all-MiniLM-L6-v2", 384),
        ]:
            db = open_db(str(tmp_path / f"{name}.db"))
            create_tables(db, model, dim)
            insert_chunk(db, f"{name}-c1", "f.md", 0, "text", [0.1] * dim)
            db.close()

        colls = discover_collections(str(tmp_path))
        by_name = {c["name"]: c for c in colls}
        assert by_name["en-libre"]["model_name"] == "BAAI/bge-m3"
        assert by_name["fr-libre"]["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert by_name["fr-libre"]["model_dim"] == 384


class TestListCollectionsShowsModel:
    def test_format_includes_model(self):
        from lore_mcp.server import format_collections

        colls = [{
            "name": "docs-libre", "level": "libre",
            "chunk_count": 10, "file_count": 3,
            "chunk_size": 1024, "chunk_overlap": 128,
            "model_name": "BAAI/bge-m3", "model_dim": 1024,
        }]
        output = format_collections(colls)
        assert "bge-m3" in output
        assert "1024d" in output or "1024" in output


class TestAutoModelFromDb:
    def test_search_single_collection_uses_stored_model(self, tmp_path):
        """When querying a third-party .db, lore-mcp should know the model."""
        db_path = str(tmp_path / "third-party.db")
        db = open_db(db_path)
        create_tables(db, "BAAI/bge-m3", DIMS)
        insert_chunk(db, "c1", "f.md", 0, "text", make_embedding(0.1))
        meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
        db.close()

        assert meta["model_name"] == "BAAI/bge-m3"
        assert meta["model_dim"] == str(DIMS)
