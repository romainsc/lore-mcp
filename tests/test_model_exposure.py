"""Tests for model info exposure in collections.

A third-party .db must be usable without prior knowledge of
which embedding model was used to create it.
"""

from conftest import DIMS, make_embedding
from lore_mcp.store import create_tables, insert_chunk, open_db


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
