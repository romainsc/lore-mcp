"""Tests for lore_mcp.collections. See docs/architecture.md."""

import numpy as np
import pytest
from unittest.mock import MagicMock

from conftest import DIMS, make_embedding

from lore_mcp.store import create_tables, insert_chunk, open_db


@pytest.fixture
def collections_dir(tmp_path):
    """Create a directory with multiple collection .db files."""
    for name, texts in [
        ("docs-libre", ["Free documentation about Linux.", "Open source tools guide."]),
        ("docs-nda", ["Confidential product roadmap.", "Internal architecture review."]),
        ("ai-gris", ["Blog post about transformers.", "Tutorial on fine-tuning."]),
    ]:
        db_path = tmp_path / f"{name}.db"
        db = open_db(str(db_path))
        create_tables(db, "test-model", DIMS)
        for i, text in enumerate(texts):
            insert_chunk(db, f"{name}-{i}", f"{name}/doc{i}.md", i, text, make_embedding(0.1 * (i + 1)))
        db.close()
    return tmp_path


class TestDiscoverCollections:
    def test_finds_all_db_files(self, collections_dir):
        from lore_mcp.collections import discover_collections

        colls = discover_collections(str(collections_dir))
        names = [c["name"] for c in colls]
        assert "docs-libre" in names
        assert "docs-nda" in names
        assert "ai-gris" in names

    def test_returns_chunk_counts(self, collections_dir):
        from lore_mcp.collections import discover_collections

        colls = discover_collections(str(collections_dir))
        for c in colls:
            assert "chunk_count" in c
            assert c["chunk_count"] == 2

    def test_returns_file_counts(self, collections_dir):
        from lore_mcp.collections import discover_collections

        colls = discover_collections(str(collections_dir))
        for c in colls:
            assert "file_count" in c
            assert c["file_count"] == 2

    def test_empty_directory(self, tmp_path):
        from lore_mcp.collections import discover_collections

        assert discover_collections(str(tmp_path)) == []

    def test_extracts_theme_and_level(self, collections_dir):
        from lore_mcp.collections import discover_collections

        colls = discover_collections(str(collections_dir))
        by_name = {c["name"]: c for c in colls}
        assert by_name["docs-libre"]["theme"] == "docs"
        assert by_name["docs-libre"]["level"] == "libre"
        assert by_name["docs-nda"]["level"] == "nda"
        assert by_name["ai-gris"]["level"] == "gris"


class TestSearchCollection:
    def test_search_single_collection(self, collections_dir):
        from lore_mcp.collections import search_collection

        results = search_collection(
            str(collections_dir), "docs-libre", make_embedding(0.1), top_k=2
        )
        assert len(results) == 2
        assert all(r["collection"] == "docs-libre" for r in results)

    def test_unknown_collection_raises(self, collections_dir):
        from lore_mcp.collections import search_collection

        with pytest.raises(FileNotFoundError):
            search_collection(
                str(collections_dir), "nonexistent", make_embedding(0.1), top_k=2
            )


class TestSearchAcrossCollections:
    def test_merges_results_by_score(self, collections_dir):
        from lore_mcp.collections import search_across

        results = search_across(
            str(collections_dir), make_embedding(0.1), top_k=5
        )
        assert len(results) > 0
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_results_include_collection_name(self, collections_dir):
        from lore_mcp.collections import search_across

        results = search_across(
            str(collections_dir), make_embedding(0.1), top_k=6
        )
        collections_found = {r["collection"] for r in results}
        assert len(collections_found) > 1

    def test_respects_top_k(self, collections_dir):
        from lore_mcp.collections import search_across

        results = search_across(
            str(collections_dir), make_embedding(0.1), top_k=3
        )
        assert len(results) <= 3


class TestCollectionPath:
    def test_collection_db_path(self, collections_dir):
        from lore_mcp.collections import collection_db_path

        path = collection_db_path(str(collections_dir), "docs-libre")
        assert path.endswith("docs-libre.db")

    def test_build_collection_name(self):
        from lore_mcp.collections import build_collection_name

        assert build_collection_name("ia", "libre") == "ia-libre"
        assert build_collection_name("docs", "nda") == "docs-nda"
