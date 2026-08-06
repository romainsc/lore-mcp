"""Integration tests: end-to-end ingestion and search.

These tests use real sqlite-vec but mock the embedding model
to avoid downloading bge-m3 (~2 GB) in CI. The mock produces
deterministic vectors that exercise the full pipeline.

See docs/architecture.md for the system design.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from lore_mcp.embedder import Embedder
from lore_mcp.ingest import ingest_directory
from lore_mcp.server import format_search_results, format_sources
from lore_mcp.store import list_sources, open_db, search, validate_model


DIMS = 64


def _fake_embedding(text: str) -> list[float]:
    """Deterministic embedding based on text hash."""
    seed = hash(text) % (2**31)
    rng = np.random.RandomState(seed)
    vec = rng.randn(DIMS).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def _make_mock_embedder() -> Embedder:
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


@pytest.fixture
def corpus(tmp_path):
    """Create a small test corpus."""
    (tmp_path / "intro.md").write_text(
        "# Introduction\n\n"
        "This project provides semantic search over local documents. "
        "It uses vector embeddings to find relevant content.\n\n"
        "## Features\n\n"
        "The main features are indexing and searching.\n"
    )
    (tmp_path / "config.md").write_text(
        "# Configuration\n\n"
        "Set LORE_DB_PATH to change the database location. "
        "Set LORE_MODEL to use a different embedding model.\n\n"
        "## Environment Variables\n\n"
        "All configuration uses environment variables.\n"
    )
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "advanced.md").write_text(
        "# Advanced Usage\n\n"
        "You can use hybrid search combining vector and keyword matching. "
        "This improves retrieval quality for technical queries.\n"
    )
    (tmp_path / "tiny.md").write_text("Too short.")
    (tmp_path / "binary.md").write_text(
        "# Images\n\n"
        "Here is an image:\n"
        "![logo](data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...)\n\n"
        "The image above shows the logo. " * 20 + "\n"
    )
    return tmp_path


class TestEndToEndIngestion:
    def test_ingest_and_search(self, corpus, tmp_path):
        db_path = str(tmp_path / "test.db")
        embedder = _make_mock_embedder()

        result = ingest_directory(str(corpus), db_path, embedder)

        assert result["file_count"] >= 3
        assert result["chunk_count"] > 0
        assert result["errors"] == []

        db = open_db(db_path)
        validate_model(db, "test-model", DIMS)

        query_emb = _fake_embedding("semantic search documents")
        results = search(db, query_emb, top_k=3)

        assert len(results) > 0
        assert all("score" in r for r in results)
        assert all(r["content"] for r in results)
        assert all(r["source_file"] for r in results)
        db.close()

    def test_skips_short_documents(self, corpus, tmp_path):
        db_path = str(tmp_path / "test.db")
        embedder = _make_mock_embedder()
        result = ingest_directory(str(corpus), db_path, embedder)
        db = open_db(db_path)
        sources = list_sources(db)
        source_names = [s["source_file"] for s in sources]
        assert "tiny.md" not in source_names
        db.close()

    def test_strips_base64(self, corpus, tmp_path):
        db_path = str(tmp_path / "test.db")
        embedder = _make_mock_embedder()
        ingest_directory(str(corpus), db_path, embedder)
        db = open_db(db_path)
        rows = db.execute(
            "SELECT content FROM chunks WHERE source_file = 'binary.md'"
        ).fetchall()
        for row in rows:
            assert "base64," not in row[0]
        db.close()

    def test_recursive_directory_traversal(self, corpus, tmp_path):
        db_path = str(tmp_path / "test.db")
        embedder = _make_mock_embedder()
        ingest_directory(str(corpus), db_path, embedder)
        db = open_db(db_path)
        sources = list_sources(db)
        source_names = [s["source_file"] for s in sources]
        assert any("subdir" in s for s in source_names)
        db.close()


class TestEndToEndSearch:
    @pytest.fixture(autouse=True)
    def setup_db(self, corpus, tmp_path):
        self.db_path = str(tmp_path / "test.db")
        self.embedder = _make_mock_embedder()
        ingest_directory(str(corpus), self.db_path, self.embedder)
        self.db = open_db(self.db_path)
        yield
        self.db.close()

    def test_search_returns_ranked_results(self):
        query_emb = _fake_embedding("configuration environment variables")
        results = search(self.db, query_emb, top_k=5)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_top_k_limits_results(self):
        query_emb = _fake_embedding("search")
        results = search(self.db, query_emb, top_k=2)
        assert len(results) <= 2

    def test_list_sources_matches_ingested(self):
        sources = list_sources(self.db)
        assert len(sources) >= 3
        total = sum(s["count"] for s in sources)
        assert total > 0

    def test_format_search_results_integration(self):
        query_emb = _fake_embedding("features")
        results = search(self.db, query_emb, top_k=3)
        output = format_search_results(results, "mock-cpu")
        assert "result" in output.lower()
        assert "mock-cpu" in output

    def test_format_sources_integration(self):
        sources = list_sources(self.db)
        output = format_sources(sources)
        assert "chunks" in output
        assert "file" in output


class TestModelValidation:
    def test_rejects_mismatched_model(self, corpus, tmp_path):
        db_path = str(tmp_path / "test.db")
        embedder = _make_mock_embedder()
        ingest_directory(str(corpus), db_path, embedder)
        db = open_db(db_path)
        with pytest.raises(ValueError, match="model"):
            validate_model(db, "different-model", DIMS)
        db.close()

    def test_rejects_mismatched_dimension(self, corpus, tmp_path):
        db_path = str(tmp_path / "test.db")
        embedder = _make_mock_embedder()
        ingest_directory(str(corpus), db_path, embedder)
        db = open_db(db_path)
        with pytest.raises(ValueError, match="dimension"):
            validate_model(db, "test-model", 1024)
        db.close()
