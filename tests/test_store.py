"""Tests for lore_mcp.store. See docs/architecture.md for design context."""

import pytest
from conftest import DIMS, make_embedding

from lore_mcp.store import (
    create_tables,
    insert_chunk,
    insert_chunks,
    list_sources,
    search,
    validate_model,
)


MODEL = "test-model"


class TestCreateTables:
    def test_creates_all_tables(self, db):
        create_tables(db, MODEL, DIMS)
        tables = {
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
            ).fetchall()
        }
        assert "chunks" in tables
        assert "meta" in tables

    def test_populates_meta(self, db):
        create_tables(db, MODEL, DIMS)
        meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
        assert meta["model_name"] == MODEL
        assert meta["model_dim"] == str(DIMS)
        assert "created_at" in meta

    def test_idempotent(self, db):
        create_tables(db, MODEL, DIMS)
        create_tables(db, MODEL, DIMS)

    def test_rejects_invalid_dim(self, db):
        with pytest.raises(ValueError):
            create_tables(db, MODEL, 0)

    def test_rejects_negative_dim(self, db):
        with pytest.raises(ValueError):
            create_tables(db, MODEL, -1)


class TestValidateModel:
    def test_matching_model_passes(self, db):
        create_tables(db, MODEL, DIMS)
        validate_model(db, MODEL, DIMS)

    def test_mismatched_name_raises(self, db):
        create_tables(db, MODEL, DIMS)
        with pytest.raises(ValueError, match="model"):
            validate_model(db, "wrong-model", DIMS)

    def test_mismatched_dim_raises(self, db):
        create_tables(db, MODEL, DIMS)
        with pytest.raises(ValueError, match="dimension"):
            validate_model(db, MODEL, 512)


class TestInsertChunk:
    def test_insert_and_retrieve(self, db):
        create_tables(db, MODEL, DIMS)
        emb = make_embedding(0.1)
        insert_chunk(db, "c1", "file.md", 0, "hello world", emb)
        row = db.execute(
            "SELECT id, source_file, chunk_index, content FROM chunks"
        ).fetchone()
        assert row == ("c1", "file.md", 0, "hello world")

    def test_duplicate_id_ignored(self, db):
        create_tables(db, MODEL, DIMS)
        emb = make_embedding(0.1)
        insert_chunk(db, "c1", "file.md", 0, "first", emb)
        insert_chunk(db, "c1", "file.md", 0, "second", emb)
        count = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
        assert count == 1


class TestInsertChunks:
    def test_batch_insert(self, db):
        create_tables(db, MODEL, DIMS)
        chunks = [
            {"id": f"c{i}", "source_file": "f.md", "chunk_index": i, "content": f"text {i}"}
            for i in range(5)
        ]
        embeddings = [make_embedding(0.1 * i) for i in range(5)]
        insert_chunks(db, chunks, embeddings)
        count = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
        assert count == 5


class TestSearch:
    def _populate(self, db):
        create_tables(db, MODEL, DIMS)
        data = [
            ("c1", "a.md", 0, "alpha content", make_embedding(0.1)),
            ("c2", "a.md", 1, "beta content", make_embedding(0.5)),
            ("c3", "b.md", 0, "gamma content", make_embedding(0.9)),
        ]
        for cid, src, idx, content, emb in data:
            insert_chunk(db, cid, src, idx, content, emb)

    def test_returns_results(self, db):
        self._populate(db)
        results = search(db, make_embedding(0.1), top_k=3)
        assert len(results) == 3
        assert all("content" in r for r in results)
        assert all("source_file" in r for r in results)
        assert all("score" in r for r in results)

    def test_ranked_by_similarity(self, db):
        self._populate(db)
        results = search(db, make_embedding(0.1), top_k=3)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_most_similar_first(self, db):
        self._populate(db)
        results = search(db, make_embedding(0.1), top_k=1)
        assert results[0]["content"] == "alpha content"

    def test_respects_top_k(self, db):
        self._populate(db)
        results = search(db, make_embedding(0.1), top_k=2)
        assert len(results) == 2

    def test_empty_db(self, db):
        create_tables(db, MODEL, DIMS)
        results = search(db, make_embedding(0.1), top_k=5)
        assert results == []


class TestListSources:
    def test_returns_sources_with_counts(self, db):
        create_tables(db, MODEL, DIMS)
        for i in range(3):
            insert_chunk(db, f"a{i}", "a.md", i, f"text {i}", make_embedding(0.1 * i))
        insert_chunk(db, "b0", "b.md", 0, "other", make_embedding(0.5))
        sources = list_sources(db)
        by_file = {s["source_file"]: s["count"] for s in sources}
        assert by_file == {"a.md": 3, "b.md": 1}

    def test_empty_db(self, db):
        create_tables(db, MODEL, DIMS)
        assert list_sources(db) == []
