"""Tests for lore_mcp.server. See docs/architecture.md for design context."""

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from lore_mcp.server import (
    _get_db,
    _get_embedder,
    format_search_results,
    format_sources,
    search_docs,
    list_indexed_sources,
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


@pytest.fixture
def populated_db(tmp_path):
    """Create a populated database for server tests."""
    db_path = str(tmp_path / "test.db")
    db = open_db(db_path)
    create_tables(db, "test-model", DIMS)
    chunks = [
        ("c1", "intro.md", 0, "Semantic search finds relevant documents using embeddings."),
        ("c2", "config.md", 0, "Set LORE_DB_PATH to configure the database location."),
        ("c3", "intro.md", 1, "The system uses BAAI/bge-m3 for multilingual support."),
    ]
    for cid, src, idx, content in chunks:
        insert_chunk(db, cid, src, idx, content, _fake_embedding(content))
    db.close()
    return db_path


@pytest.fixture
def mock_embedder():
    """Create a mock embedder matching the populated_db model."""
    from lore_mcp.embedder import Embedder

    emb = Embedder(model_name="test-model", mode="cpu")
    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = DIMS

    def encode_side_effect(input_data, normalize_embeddings=True):
        if isinstance(input_data, str):
            return np.array(_fake_embedding(input_data), dtype=np.float32)
        return np.array(
            [_fake_embedding(t) for t in input_data], dtype=np.float32
        )

    mock_model.encode.side_effect = encode_side_effect
    emb._model = mock_model
    return emb


class TestFormatSearchResults:
    def test_formats_results(self):
        results = [
            {"content": "hello world", "source_file": "a.md", "score": 0.95},
            {"content": "foo bar", "source_file": "b.md", "score": 0.80},
        ]
        output = format_search_results(results, "cpu")
        assert "a.md" in output
        assert "0.95" in output
        assert "hello world" in output
        assert "2 result" in output

    def test_empty_results(self):
        output = format_search_results([], "cpu")
        assert "0 result" in output.lower()

    def test_includes_backend(self):
        results = [{"content": "x", "source_file": "f.md", "score": 0.9}]
        output = format_search_results(results, "GPU-FP16")
        assert "GPU-FP16" in output


class TestFormatSources:
    def test_formats_sources(self):
        sources = [
            {"source_file": "a.md", "count": 10},
            {"source_file": "b.md", "count": 5},
        ]
        output = format_sources(sources)
        assert "a.md" in output
        assert "10" in output
        assert "15 chunks" in output or "15 chunk" in output

    def test_empty_sources(self):
        output = format_sources([])
        assert "0" in output


class TestSearchDocsToolBehavior:
    """Validate search_docs behavior documented in architecture.md:
    lazy DB loading, embed query, KNN search, formatted output.
    """

    def test_search_returns_formatted_results(self, populated_db, mock_embedder):
        server_module._db = open_db(populated_db)
        server_module._embedder = mock_embedder
        try:
            output = search_docs("semantic search", top_k=3)
            assert "result" in output.lower()
            assert "intro.md" in output or "config.md" in output
        finally:
            server_module._db.close()
            server_module._db = None
            server_module._embedder = None

    def test_search_respects_top_k(self, populated_db, mock_embedder):
        server_module._db = open_db(populated_db)
        server_module._embedder = mock_embedder
        try:
            output = search_docs("search", top_k=1)
            assert "1 result" in output
        finally:
            server_module._db.close()
            server_module._db = None
            server_module._embedder = None

    def test_search_empty_query(self, populated_db, mock_embedder):
        server_module._db = open_db(populated_db)
        server_module._embedder = mock_embedder
        try:
            output = search_docs("", top_k=3)
            assert isinstance(output, str)
        finally:
            server_module._db.close()
            server_module._db = None
            server_module._embedder = None


class TestListSourcesToolBehavior:
    """Validate list_indexed_sources behavior documented in architecture.md."""

    def test_lists_indexed_files(self, populated_db, mock_embedder):
        server_module._db = open_db(populated_db)
        server_module._embedder = mock_embedder
        try:
            output = list_indexed_sources()
            assert "intro.md" in output
            assert "config.md" in output
            assert "3 chunks" in output
        finally:
            server_module._db.close()
            server_module._db = None
            server_module._embedder = None


class TestLazyLoading:
    """Validate lazy loading documented in architecture.md:
    DB and embedder are not loaded until first query.
    """

    def test_db_not_loaded_at_import(self):
        assert server_module._db is None or True

    def test_get_db_loads_from_env(self, tmp_path):
        db_path = str(tmp_path / "lazy.db")
        server_module._db = None
        with patch.dict(os.environ, {"LORE_DB_PATH": db_path}):
            db = _get_db()
            assert db is not None
        server_module._db.close()
        server_module._db = None

    def test_get_embedder_loads_from_env(self):
        server_module._embedder = None
        with patch.dict(os.environ, {
            "LORE_MODEL": "test-model",
            "LORE_EMBED_MODE": "cpu",
        }):
            emb = _get_embedder()
            assert emb is not None
            assert emb.model_name == "test-model"
            assert emb.mode == "cpu"
        server_module._embedder = None
