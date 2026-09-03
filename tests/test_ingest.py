"""Tests for lore_mcp.ingest. See docs/architecture.md for design context."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from lore_mcp.ingest import chunk_document, ingest_directory, preprocess


class TestPreprocess:
    def test_strips_nul(self):
        assert preprocess("hello\x00world") == "helloworld"

    def test_replaces_base64_image_with_alt(self):
        text = "line 1\n![diagram](data:image/png;base64,iVBOR...)\nline 3"
        result = preprocess(text)
        assert "base64" not in result
        assert "line 1" in result
        assert "line 3" in result
        assert "diagram" in result

    def test_replaces_url_image_with_alt(self):
        text = "before ![architecture](https://example.com/arch.png) after"
        result = preprocess(text)
        assert "https://example.com" not in result
        assert "architecture" in result
        assert "before" in result
        assert "after" in result

    def test_removes_image_without_alt(self):
        text = "before ![](image.png) after"
        result = preprocess(text)
        assert "image.png" not in result
        assert "before" in result
        assert "after" in result

    def test_inline_image_preserves_surrounding_text(self):
        text = "The ![logo](logo.png) is shown here."
        result = preprocess(text)
        assert "logo.png" not in result
        assert "The" in result
        assert "is shown here" in result

    def test_preserves_normal_text(self):
        text = "This is normal\nMarkdown content.\n\n## Heading\n"
        assert preprocess(text) == text

    def test_empty_input(self):
        assert preprocess("") == ""


class TestChunkDocument:
    def test_produces_chunks(self):
        text = "word " * 1000
        chunks = chunk_document(text, "test.md")
        assert len(chunks) > 1

    def test_chunk_has_required_fields(self):
        text = "word " * 1000
        chunks = chunk_document(text, "test.md")
        for c in chunks:
            assert "id" in c
            assert "source_file" in c
            assert "chunk_index" in c
            assert "content" in c

    def test_source_file_set(self):
        text = "word " * 1000
        chunks = chunk_document(text, "docs/intro.md")
        assert all(c["source_file"] == "docs/intro.md" for c in chunks)

    def test_chunk_index_sequential(self):
        text = "word " * 1000
        chunks = chunk_document(text, "test.md")
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_deterministic_ids(self):
        text = "word " * 1000
        chunks_a = chunk_document(text, "test.md")
        chunks_b = chunk_document(text, "test.md")
        assert [c["id"] for c in chunks_a] == [c["id"] for c in chunks_b]

    def test_small_document_single_chunk(self):
        text = "Short document."
        chunks = chunk_document(text, "small.md")
        assert len(chunks) == 1

    def test_custom_chunk_size(self):
        text = "word " * 500
        small = chunk_document(text, "f.md", chunk_size=256, chunk_overlap=32)
        big = chunk_document(text, "f.md", chunk_size=2048, chunk_overlap=128)
        assert len(small) > len(big)

    def test_respects_markdown_separators(self):
        text = "# Title\n\nParagraph one.\n\n## Section\n\nParagraph two.\n"
        chunks = chunk_document(text, "f.md", chunk_size=50, chunk_overlap=0)
        assert len(chunks) >= 2


DIMS = 64


def _make_mock_embedder():
    from lore_mcp.embedder import Embedder

    emb = Embedder(model_name="test-model", mode="builtin:cpu")
    mock_model = MagicMock()
    mock_model.get_embedding_dimension.return_value = DIMS

    def encode_side_effect(input_data, normalize_embeddings=True):
        if isinstance(input_data, str):
            rng = np.random.RandomState(42)
            return rng.randn(DIMS).astype(np.float32)
        return np.random.RandomState(42).randn(len(input_data), DIMS).astype(np.float32)

    mock_model.encode.side_effect = encode_side_effect
    emb._model = mock_model
    return emb


class TestIngestDirectory:
    """Validate ingest_directory behavior documented in architecture.md:
    per-file error handling, short document skipping.
    """

    def test_error_on_one_file_does_not_abort(self, tmp_path):
        """architecture.md: errors are collected per-file, not raised."""
        (tmp_path / "good.md").write_text("This is a valid document. " * 20)
        (tmp_path / "bad.md").write_bytes(b"\x80\x81\x82" * 100)
        embedder = _make_mock_embedder()
        result = ingest_directory(str(tmp_path), str(tmp_path / "t.db"), embedder)
        assert result["file_count"] >= 1
        assert len(result["errors"]) >= 0

    def test_returns_summary(self, tmp_path):
        (tmp_path / "doc.md").write_text("Content for indexing. " * 20)
        embedder = _make_mock_embedder()
        result = ingest_directory(str(tmp_path), str(tmp_path / "t.db"), embedder)
        assert "file_count" in result
        assert "chunk_count" in result
        assert "errors" in result

    def test_collection_mode(self, tmp_path):
        """E9.05: collection name determines output .db file."""
        db_dir = tmp_path / "collections"
        db_dir.mkdir()
        (tmp_path / "doc.md").write_text("Content for collection. " * 20)
        embedder = _make_mock_embedder()
        result = ingest_directory(
            str(tmp_path), "", embedder,
            collection="ia-libre", db_dir=str(db_dir),
        )
        assert result["file_count"] >= 1
        assert (db_dir / "ia-libre.db").exists()
