"""Tests for parent-child storage (backward compat for existing .db files)."""

import numpy as np
import pytest

from lore_mcp.store import (
    create_tables,
    insert_chunks,
    insert_parent_chunk,
    open_db,
    search,
    _has_parent_chunks,
    _expand_parent,
)
from sqlite_vec import serialize_float32


DIMS = 8


def _fake_emb(val: float) -> list[float]:
    return [val] * DIMS


class TestParentChunkStorage:
    def test_insert_and_retrieve_parent(self):
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)
        pid = insert_parent_chunk(db, "test.md", "Parent content here")
        assert pid > 0
        row = db.execute(
            "SELECT content FROM parent_chunks WHERE id = ?", (pid,)
        ).fetchone()
        assert row[0] == "Parent content here"
        db.close()

    def test_has_parent_chunks(self):
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)
        assert not _has_parent_chunks(db)
        insert_parent_chunk(db, "test.md", "Content")
        assert _has_parent_chunks(db)
        db.close()


class TestParentExpansion:
    def test_expand_replaces_child_with_parent(self):
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)

        pid = insert_parent_chunk(db, "doc.md", "Full parent content with all details")

        chunks = [{
            "id": "child1",
            "source_file": "doc.md",
            "chunk_index": 0,
            "content": "Child subset",
            "parent_id": pid,
        }]
        embs = [_fake_emb(0.5)]
        insert_chunks(db, chunks, embs)

        results = [{"content": "Child subset", "source_file": "doc.md", "score": 0.9}]
        expanded = _expand_parent(db, results)

        assert len(expanded) == 1
        assert "Full parent content" in expanded[0]["content"]
        db.close()

    def test_no_parent_keeps_original(self):
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)

        chunks = [{
            "id": "nop1",
            "source_file": "doc.md",
            "chunk_index": 0,
            "content": "No parent chunk",
        }]
        embs = [_fake_emb(0.5)]
        insert_chunks(db, chunks, embs)

        results = [{"content": "No parent chunk", "source_file": "doc.md", "score": 0.8}]
        expanded = _expand_parent(db, results)

        assert expanded[0]["content"] == "No parent chunk"
        db.close()

    def test_deduplicates_same_parent(self):
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)

        pid = insert_parent_chunk(db, "doc.md", "Shared parent")

        for i, text in enumerate(["Child A", "Child B"]):
            chunks = [{
                "id": f"dup{i}",
                "source_file": "doc.md",
                "chunk_index": i,
                "content": text,
                "parent_id": pid,
            }]
            insert_chunks(db, chunks, [_fake_emb(0.5 + i * 0.1)])

        results = [
            {"content": "Child A", "source_file": "doc.md", "score": 0.9},
            {"content": "Child B", "source_file": "doc.md", "score": 0.8},
        ]
        expanded = _expand_parent(db, results)

        assert len(expanded) == 1
        assert expanded[0]["content"] == "Shared parent"
        db.close()
