"""Tests for E6.05: collection metadata and manifests."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from conftest import DIMS, make_embedding
from lore_mcp.store import create_tables, insert_chunk, open_db


# --- MVP1: sources table + manifest ---


class TestSourcesTable:
    def test_create_sources_table(self):
        from lore_mcp.store import create_tables
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)
        tables = {r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "sources" in tables
        db.close()

    def test_insert_source(self):
        from lore_mcp.store import upsert_source
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)
        upsert_source(db, "intro.md", title="Intro", author="RC",
                       url="https://example.com", license="CC-BY-SA-4.0", level="libre")
        row = db.execute("SELECT * FROM sources WHERE source_file='intro.md'").fetchone()
        assert row is not None
        db.close()

    def test_get_source(self):
        from lore_mcp.store import upsert_source, get_source
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)
        upsert_source(db, "intro.md", title="Intro", author="RC")
        src = get_source(db, "intro.md")
        assert src["title"] == "Intro"
        assert src["author"] == "RC"
        db.close()

    def test_get_all_sources(self):
        from lore_mcp.store import upsert_source, get_all_sources
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)
        upsert_source(db, "a.md", title="A")
        upsert_source(db, "b.md", title="B")
        sources = get_all_sources(db)
        assert len(sources) == 2
        db.close()

    def test_backward_compat_without_sources(self):
        """Chunks without sources entry still work."""
        from lore_mcp.store import search
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)
        insert_chunk(db, "c1", "old.md", 0, "content", make_embedding(0.1))
        results = search(db, make_embedding(0.1), top_k=1)
        assert len(results) == 1
        db.close()


class TestManifest:
    def test_parse_manifest(self, tmp_path):
        from lore_mcp.manifest import parse_manifest
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text("""
collection: docs-libre
level: libre
sources:
  - path: intro.md
    title: Introduction
    author: RC
    license: CC-BY-SA-4.0
  - path: config.md
    title: Configuration
""")
        result = parse_manifest(str(manifest))
        assert result["collection"] == "docs-libre"
        assert result["level"] == "libre"
        assert len(result["sources"]) == 2
        assert result["sources"][0]["title"] == "Introduction"

    def test_parse_manifest_minimal(self, tmp_path):
        from lore_mcp.manifest import parse_manifest
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text("""
collection: test
sources:
  - path: doc.md
""")
        result = parse_manifest(str(manifest))
        assert result["collection"] == "test"
        assert result["sources"][0]["path"] == "doc.md"

    def test_ingest_with_manifest(self, tmp_path):
        from lore_mcp.manifest import parse_manifest
        from lore_mcp.ingest import ingest_with_manifest
        from lore_mcp.store import get_all_sources

        (tmp_path / "intro.md").write_text("Introduction content. " * 30)
        (tmp_path / "config.md").write_text("Configuration guide. " * 30)
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(f"""
collection: test-libre
level: libre
sources:
  - path: intro.md
    title: Introduction
    author: RC
  - path: config.md
    title: Config Guide
""")
        embedder = _make_mock_embedder()
        db_dir = tmp_path / "db"
        db_dir.mkdir()
        result = ingest_with_manifest(
            str(manifest), str(tmp_path), str(db_dir), embedder
        )
        assert result["file_count"] >= 2
        db = open_db(str(db_dir / "test-libre.db"))
        sources = get_all_sources(db)
        assert len(sources) >= 2
        titles = {s["title"] for s in sources}
        assert "Introduction" in titles
        db.close()


# --- MVP2: search_docs with biblio metadata ---


class TestSearchWithMetadata:
    def test_search_includes_source_metadata(self):
        from lore_mcp.store import upsert_source, search
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)
        upsert_source(db, "intro.md", title="Introduction", author="RC",
                       license="CC-BY-SA-4.0")
        insert_chunk(db, "c1", "intro.md", 0, "content about AI", make_embedding(0.1))
        results = search(db, make_embedding(0.1), top_k=1)
        assert results[0].get("title") == "Introduction"
        assert results[0].get("author") == "RC"
        db.close()

    def test_search_without_source_metadata(self):
        """Backward compat: no source entry, fields are None."""
        from lore_mcp.store import search
        db = open_db(":memory:")
        create_tables(db, "test", DIMS)
        insert_chunk(db, "c1", "old.md", 0, "content", make_embedding(0.1))
        results = search(db, make_embedding(0.1), top_k=1)
        assert results[0].get("title") is None
        db.close()

    def test_format_includes_metadata(self):
        from lore_mcp.server import format_search_results
        results = [{"content": "text", "source_file": "f.md", "score": 0.9,
                     "title": "My Doc", "author": "RC", "license": "MIT"}]
        output = format_search_results(results, "cpu")
        assert "My Doc" in output
        assert "RC" in output


# --- MVP3: output files (.json, .bib, .md) ---


class TestOutputFiles:
    def _populated_db(self, tmp_path):
        from lore_mcp.store import upsert_source
        db_path = tmp_path / "test-libre.db"
        db = open_db(str(db_path))
        create_tables(db, "test-model", DIMS, chunk_size=1024, chunk_overlap=128)
        upsert_source(db, "intro.md", title="Introduction", author="RC",
                       url="https://example.com", license="CC-BY-SA-4.0", level="libre")
        upsert_source(db, "config.md", title="Config", author="RC")
        insert_chunk(db, "c1", "intro.md", 0, "intro content", make_embedding(0.1))
        insert_chunk(db, "c2", "config.md", 0, "config content", make_embedding(0.2))
        db.close()
        return str(db_path)

    def test_generate_json(self, tmp_path):
        from lore_mcp.metadata import generate_collection_json
        db_path = self._populated_db(tmp_path)
        json_path = generate_collection_json(db_path)
        assert Path(json_path).exists()
        data = json.loads(Path(json_path).read_text())
        assert data["collection"] == "test-libre"
        assert data["model_name"] == "test-model"
        assert data["chunk_size"] == 1024
        assert data["stats"]["chunk_count"] == 2
        assert "sha256" in data

    def test_generate_bib(self, tmp_path):
        from lore_mcp.metadata import generate_collection_bib
        db_path = self._populated_db(tmp_path)
        bib_path = generate_collection_bib(db_path)
        assert Path(bib_path).exists()
        content = Path(bib_path).read_text()
        assert "@misc{" in content
        assert "Introduction" in content
        assert "RC" in content

    def test_generate_md(self, tmp_path):
        from lore_mcp.metadata import generate_collection_md
        db_path = self._populated_db(tmp_path)
        md_path = generate_collection_md(db_path)
        assert Path(md_path).exists()
        content = Path(md_path).read_text()
        assert "test-libre" in content
        assert "Introduction" in content


# --- MVP4: front matter extraction ---


class TestFrontMatterExtraction:
    def test_extract_yaml_front_matter(self):
        from lore_mcp.manifest import extract_source_metadata
        text = """---
title: My Document
author: John Doe
license: MIT
---

# Content here
"""
        meta = extract_source_metadata(text, "doc.md")
        assert meta["title"] == "My Document"
        assert meta["author"] == "John Doe"
        assert meta["license"] == "MIT"

    def test_extract_title_from_heading(self):
        from lore_mcp.manifest import extract_source_metadata
        text = "# My Great Title\n\nSome content here."
        meta = extract_source_metadata(text, "doc.md")
        assert meta["title"] == "My Great Title"

    def test_fallback_to_filename(self):
        from lore_mcp.manifest import extract_source_metadata
        text = "Just plain text without any structure."
        meta = extract_source_metadata(text, "my-doc.md")
        assert meta["title"] == "my-doc"

    def test_ingest_without_manifest_extracts_metadata(self, tmp_path):
        """When no manifest, extract metadata from front matter."""
        from lore_mcp.ingest import ingest_directory
        from lore_mcp.store import get_all_sources

        (tmp_path / "doc.md").write_text("""---
title: Test Document
author: Test Author
---

Content for indexing. """ + "More content. " * 30)

        embedder = _make_mock_embedder()
        db_path = str(tmp_path / "test.db")
        ingest_directory(str(tmp_path), db_path, embedder)
        db = open_db(db_path)
        sources = get_all_sources(db)
        assert len(sources) >= 1
        assert sources[0]["title"] == "Test Document"
        db.close()


# --- Helpers ---

def _make_mock_embedder():
    from lore_mcp.embedder import Embedder
    emb = Embedder(model_name="test-model", mode="cpu")
    mock_model = MagicMock()
    mock_model.get_embedding_dimension.return_value = DIMS
    def encode_side_effect(input_data, normalize_embeddings=True):
        if isinstance(input_data, str):
            return np.random.RandomState(42).randn(DIMS).astype(np.float32)
        return np.random.RandomState(42).randn(len(input_data), DIMS).astype(np.float32)
    mock_model.encode.side_effect = encode_side_effect
    emb._model = mock_model
    return emb
