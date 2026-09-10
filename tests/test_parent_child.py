"""Tests for E6.08: parent-child chunking."""

import numpy as np
import pytest

from lore_mcp.ingest import chunk_document_parent_child
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


class TestChunkDocumentParentChild:
    def test_produces_parents_and_children(self):
        text = ("## Section A\n\n" + "Word " * 200 +
                "\n\n## Section B\n\n" + "Text " * 200)
        parents, children = chunk_document_parent_child(
            text, "test.md", parent_size=500, child_size=200, child_overlap=0
        )
        assert len(parents) >= 2
        assert len(children) >= len(parents)

    def test_children_reference_parents(self):
        text = "## A\n\n" + "Word " * 100 + "\n\n## B\n\n" + "Text " * 100
        parents, children = chunk_document_parent_child(
            text, "test.md", parent_size=300, child_size=100, child_overlap=0
        )
        for child in children:
            assert "parent_index" in child
            assert 0 <= child["parent_index"] < len(parents)

    def test_children_have_ids(self):
        text = "## A\n\n" + "Content " * 50
        _, children = chunk_document_parent_child(
            text, "test.md", parent_size=500, child_size=100, child_overlap=0
        )
        for child in children:
            assert "id" in child
            assert len(child["id"]) == 16

    def test_empty_text(self):
        parents, children = chunk_document_parent_child(
            "", "test.md", parent_size=500, child_size=200, child_overlap=0
        )
        assert parents == []
        assert children == []


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
