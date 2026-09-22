"""Tests for lore_mcp.ingest. See docs/architecture.md for design context."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from lore_mcp.ingest import chunk_document, ingest_directory, ingest_with_manifest


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


def _make_manifest(path, sources, collection="test", level="libre"):
    import yaml
    path.write_text(yaml.dump({
        "collection": collection, "level": level,
        "sources": sources,
    }))


class TestDeclarativeSync:
    """E6.01: manifest is source of truth, DB is its reflection."""

    def test_skip_unchanged(self, tmp_path):
        """Second ingest skips unchanged files."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("Content for doc A. " * 20)
        manifest = tmp_path / "manifest.yaml"
        _make_manifest(manifest, [{"orig": "a.md", "path": "a.md"}])
        db_dir = tmp_path / "db"
        db_dir.mkdir()
        emb = _make_mock_embedder()

        r1 = ingest_with_manifest(str(manifest), str(docs), str(db_dir), emb)
        assert r1["file_count"] == 1

        r2 = ingest_with_manifest(str(manifest), str(docs), str(db_dir), emb)
        assert r2["skipped"] == 1
        assert r2["file_count"] == 0

    def test_update_changed(self, tmp_path):
        """Modified file re-ingested."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("Original content. " * 20)
        manifest = tmp_path / "manifest.yaml"
        _make_manifest(manifest, [{"orig": "a.md", "path": "a.md"}])
        db_dir = tmp_path / "db"
        db_dir.mkdir()
        emb = _make_mock_embedder()

        ingest_with_manifest(str(manifest), str(docs), str(db_dir), emb)
        (docs / "a.md").write_text("Updated content with changes. " * 20)
        r2 = ingest_with_manifest(str(manifest), str(docs), str(db_dir), emb)

        assert r2["updated"] == 1
        assert r2["file_count"] == 1

    def test_purge_absent(self, tmp_path):
        """Source removed from manifest gets purged from DB."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("Content A. " * 20)
        (docs / "b.md").write_text("Content B. " * 20)
        manifest = tmp_path / "manifest.yaml"
        _make_manifest(manifest, [
            {"orig": "a.md", "path": "a.md"},
            {"orig": "b.md", "path": "b.md"},
        ])
        db_dir = tmp_path / "db"
        db_dir.mkdir()
        emb = _make_mock_embedder()

        ingest_with_manifest(str(manifest), str(docs), str(db_dir), emb)

        _make_manifest(manifest, [{"orig": "a.md", "path": "a.md"}])
        r2 = ingest_with_manifest(str(manifest), str(docs), str(db_dir), emb)

        assert r2["purged"] == 1
        assert r2["skipped"] == 1

    def test_add_new(self, tmp_path):
        """New file added to manifest gets ingested."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("Content A. " * 20)
        manifest = tmp_path / "manifest.yaml"
        _make_manifest(manifest, [{"orig": "a.md", "path": "a.md"}])
        db_dir = tmp_path / "db"
        db_dir.mkdir()
        emb = _make_mock_embedder()

        ingest_with_manifest(str(manifest), str(docs), str(db_dir), emb)

        (docs / "b.md").write_text("Content B. " * 20)
        _make_manifest(manifest, [
            {"orig": "a.md", "path": "a.md"},
            {"orig": "b.md", "path": "b.md"},
        ])
        r2 = ingest_with_manifest(str(manifest), str(docs), str(db_dir), emb)

        assert r2["skipped"] == 1
        assert r2["file_count"] == 1
