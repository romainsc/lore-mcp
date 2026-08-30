"""Tests for lore_mcp.server. See docs/architecture.md for design context."""

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from lore_mcp.server import (
    _get_embedder,
    format_collections,
    format_search_results,
    format_sources,
    list_collections,
    list_indexed_sources,
    search_docs,
)
from lore_mcp.store import create_tables, insert_chunk, open_db

import lore_mcp.server as server_module


DIMS = 64


def _fake_embedding(text):
    seed = hash(text) % (2**31)
    rng = np.random.RandomState(seed)
    vec = rng.randn(DIMS).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def _make_mock_embedder():
    from lore_mcp.embedder import Embedder

    emb = Embedder(model_name="test-model", mode="cpu")
    mock_model = MagicMock()
    mock_model.get_embedding_dimension.return_value = DIMS

    def encode_side_effect(input_data, normalize_embeddings=True):
        if isinstance(input_data, str):
            return np.array(_fake_embedding(input_data), dtype=np.float32)
        return np.array(
            [_fake_embedding(t) for t in input_data], dtype=np.float32
        )

    mock_model.encode.side_effect = encode_side_effect
    emb._model = mock_model
    return emb


@pytest.fixture
def single_db(tmp_path):
    """Create a single populated database."""
    db_path = str(tmp_path / "test.db")
    db = open_db(db_path)
    create_tables(db, "test-model", DIMS)
    for i, text in enumerate(["Semantic search.", "Configuration guide.", "Advanced usage."]):
        insert_chunk(db, f"c{i}", f"doc{i}.md", 0, text, _fake_embedding(text))
    db.close()
    return db_path


@pytest.fixture
def multi_db(tmp_path):
    """Create a directory with multiple collections."""
    db_dir = tmp_path / "collections"
    db_dir.mkdir()
    for name, texts in [
        ("docs-libre", ["Free docs about Linux.", "Open tools guide."]),
        ("ai-gris", ["Blog on transformers.", "Fine-tuning tutorial."]),
    ]:
        db = open_db(str(db_dir / f"{name}.db"))
        create_tables(db, "test-model", DIMS)
        for i, text in enumerate(texts):
            insert_chunk(db, f"{name}-{i}", f"doc{i}.md", i, text, _fake_embedding(text))
        db.close()
    return str(db_dir)


class TestFormatSearchResults:
    def test_formats_results(self):
        results = [
            {"content": "hello world", "source_file": "a.md", "score": 0.95},
            {"content": "foo bar", "source_file": "b.md", "score": 0.80},
        ]
        output = format_search_results(results, "cpu")
        assert "a.md" in output
        assert "0.95" in output
        assert "2 result" in output

    def test_empty_results(self):
        output = format_search_results([], "cpu")
        assert "0 result" in output.lower()

    def test_includes_collection_name(self):
        results = [{"content": "x", "source_file": "f.md", "score": 0.9, "collection": "docs-libre"}]
        output = format_search_results(results, "cpu")
        assert "docs-libre" in output


class TestFormatSources:
    def test_formats_sources(self):
        sources = [
            {"source_file": "a.md", "count": 10},
            {"source_file": "b.md", "count": 5},
        ]
        output = format_sources(sources)
        assert "a.md" in output
        assert "15 chunks" in output or "15 chunk" in output

    def test_empty_sources(self):
        output = format_sources([])
        assert "0" in output


class TestFormatCollections:
    def test_formats_collections(self):
        colls = [
            {"name": "docs-libre", "level": "libre", "chunk_count": 10, "file_count": 3},
            {"name": "ai-gris", "level": "gris", "chunk_count": 5, "file_count": 2},
        ]
        output = format_collections(colls)
        assert "2 collection" in output
        assert "docs-libre" in output
        assert "[libre]" in output

    def test_empty(self):
        output = format_collections([])
        assert "no collection" in output.lower() or "No collection" in output


class TestSingleCollectionMode:
    def test_search_docs(self, single_db):
        server_module._embedder = _make_mock_embedder()
        try:
            with patch.dict(os.environ, {"LORE_DB_PATH": single_db}, clear=False):
                with patch.dict(os.environ, {}, clear=False):
                    if "LORE_DB_DIR" in os.environ:
                        del os.environ["LORE_DB_DIR"]
                    output = search_docs("search", top_k=2)
                    assert "result" in output.lower()
        finally:
            server_module._embedder = None

    def test_list_sources(self, single_db):
        server_module._embedder = _make_mock_embedder()
        try:
            with patch.dict(os.environ, {"LORE_DB_PATH": single_db}, clear=False):
                if "LORE_DB_DIR" in os.environ:
                    del os.environ["LORE_DB_DIR"]
                output = list_indexed_sources()
                assert "3 chunks" in output
        finally:
            server_module._embedder = None

    def test_list_collections_single_mode(self):
        if "LORE_DB_DIR" in os.environ:
            del os.environ["LORE_DB_DIR"]
        output = list_collections()
        assert "Single-collection" in output


class TestMultiCollectionMode:
    def test_search_across_all(self, multi_db):
        server_module._embedder = _make_mock_embedder()
        try:
            with patch.dict(os.environ, {"LORE_DB_DIR": multi_db}, clear=False):
                output = search_docs("search", top_k=3)
                assert "result" in output.lower()
        finally:
            server_module._embedder = None

    def test_search_single_collection(self, multi_db):
        server_module._embedder = _make_mock_embedder()
        try:
            with patch.dict(os.environ, {"LORE_DB_DIR": multi_db}, clear=False):
                output = search_docs("search", top_k=2, collection="docs-libre")
                assert "docs-libre" in output
        finally:
            server_module._embedder = None

    def test_list_collections(self, multi_db):
        with patch.dict(os.environ, {"LORE_DB_DIR": multi_db}, clear=False):
            output = list_collections()
            assert "2 collection" in output
            assert "docs-libre" in output
            assert "ai-gris" in output

    def test_list_sources_across(self, multi_db):
        server_module._embedder = _make_mock_embedder()
        try:
            with patch.dict(os.environ, {"LORE_DB_DIR": multi_db}, clear=False):
                output = list_indexed_sources()
                assert "4 chunks" in output
        finally:
            server_module._embedder = None


class TestLazyLoading:
    def test_get_embedder_loads_from_env(self):
        server_module._embedder = None
        with patch.dict(os.environ, {"LORE_MODEL": "test-model", "LORE_EMBED_MODE": "cpu"}):
            emb = _get_embedder()
            assert emb.model_name == "test-model"
        server_module._embedder = None
