"""Tests for E10.04: optimize with manifest. See docs/architecture.md."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from conftest import DIMS, make_embedding


def _make_mock_embedder():
    from lore_mcp.embedder import Embedder
    emb = Embedder(model_name="test-model", mode="builtin:cpu")
    mock_model = MagicMock()
    mock_model.get_embedding_dimension.return_value = DIMS
    def encode_side_effect(input_data, normalize_embeddings=True):
        if isinstance(input_data, str):
            seed = hash(input_data) % (2**31)
            rng = np.random.RandomState(seed)
            vec = rng.randn(DIMS).astype(np.float32)
            return vec / np.linalg.norm(vec)
        vecs = []
        for t in input_data:
            seed = hash(t) % (2**31)
            rng = np.random.RandomState(seed)
            vec = rng.randn(DIMS).astype(np.float32)
            vecs.append(vec / np.linalg.norm(vec))
        return np.array(vecs, dtype=np.float32)
    mock_model.encode.side_effect = encode_side_effect
    emb._model = mock_model
    return emb


class TestOptimizeWithManifest:
    def test_optimize_uses_manifest(self, tmp_path):
        """E10.04: optimize --manifest preserves biblio metadata."""
        from lore_mcp.eval import run_optimize

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "intro.md").write_text("Introduction to the system. " * 30)
        (docs_dir / "config.md").write_text("Configuration of parameters. " * 30)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
collection: test-optimize
level: libre
sources:
  - path: intro.md
    title: Introduction
    author: RC
    license: CC-BY-SA-4.0
  - path: config.md
    title: Configuration
    author: RC
""")

        db_dir = tmp_path / "opt-dbs"
        db_dir.mkdir()
        embedder = _make_mock_embedder()

        results = run_optimize(
            manifest_path=str(manifest_path),
            docs_dir=str(docs_dir),
            db_dir=str(db_dir),
            embedder=embedder,
            chunk_sizes=[512, 1024],
            chunk_overlaps=[64],
            top_ks=[3],
            num_questions=2,
        )

        assert "best" in results
        assert "all" in results
        assert len(results["all"]) == 2  # 2 chunk_sizes × 1 overlap × 1 top_k

        # Verify biblio metadata preserved in optimized dbs
        from lore_mcp.store import open_db, get_all_sources
        for f in db_dir.glob("*.db"):
            db = open_db(str(f))
            sources = get_all_sources(db)
            if sources:
                titles = {s["title"] for s in sources if s["title"]}
                assert "Introduction" in titles or "Configuration" in titles
            db.close()

    def test_optimize_without_manifest(self, tmp_path):
        """Backward compat: optimize with source-dir still works."""
        from lore_mcp.eval import run_optimize

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "doc.md").write_text("Document content for testing. " * 30)

        db_dir = tmp_path / "opt-dbs"
        db_dir.mkdir()
        embedder = _make_mock_embedder()

        results = run_optimize(
            source_dir=str(docs_dir),
            db_dir=str(db_dir),
            embedder=embedder,
            chunk_sizes=[1024],
            chunk_overlaps=[128],
            top_ks=[3],
            num_questions=2,
        )

        assert "best" in results
        assert len(results["all"]) == 1


class TestOptimizeDbNaming:
    """E10.06: no .db naming collision between optimization iterations."""

    def test_deterministic_db_names(self, tmp_path):
        """Each config gets a unique .db named opt-<size>-<overlap>.db."""
        from lore_mcp.eval import run_optimize

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "doc.md").write_text("Document content for testing. " * 30)

        db_dir = tmp_path / "opt-dbs"
        db_dir.mkdir()
        embedder = _make_mock_embedder()

        run_optimize(
            source_dir=str(docs_dir),
            db_dir=str(db_dir),
            embedder=embedder,
            chunk_sizes=[512, 1024],
            chunk_overlaps=[64, 128],
            top_ks=[3],
            num_questions=2,
        )

        db_files = sorted(f.name for f in db_dir.glob("opt-*.db"))
        assert "opt-512-64.db" in db_files
        assert "opt-512-128.db" in db_files
        assert "opt-1024-64.db" in db_files
        assert "opt-1024-128.db" in db_files

    def test_manifest_no_collision(self, tmp_path):
        """E10.06: manifest optimize uses opt-<size>-<overlap>.db, not collection name."""
        from lore_mcp.eval import run_optimize

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "doc.md").write_text("Document content. " * 30)

        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("""
collection: my-collection
level: libre
sources:
  - path: doc.md
    title: Test Doc
""")

        db_dir = tmp_path / "opt-dbs"
        db_dir.mkdir()
        embedder = _make_mock_embedder()

        run_optimize(
            manifest_path=str(manifest_path),
            docs_dir=str(docs_dir),
            db_dir=str(db_dir),
            embedder=embedder,
            chunk_sizes=[512, 1024],
            chunk_overlaps=[64],
            top_ks=[3],
            num_questions=2,
        )

        db_files = sorted(f.name for f in db_dir.glob("opt-*.db"))
        assert "opt-512-64.db" in db_files
        assert "opt-1024-64.db" in db_files
        assert len(db_files) >= 2

    def test_no_glob_mtime_dependency(self, tmp_path):
        """E10.07: optimize doesn't use glob+st_mtime to find .db files."""
        from lore_mcp.eval import _optimize_ingest

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "doc.md").write_text("Content for test. " * 30)

        db_dir = tmp_path / "opt-dbs"
        db_dir.mkdir()

        # Plant a decoy .db with a future mtime
        decoy = db_dir / "decoy-should-not-be-selected.db"
        decoy.write_text("not a real db")
        import time
        future = time.time() + 9999
        os.utime(str(decoy), (future, future))

        embedder = _make_mock_embedder()
        result_path = _optimize_ingest(
            db_dir, None, str(docs_dir), embedder, 1024, 128
        )

        assert "opt-1024-128.db" in result_path
        assert "decoy" not in result_path
