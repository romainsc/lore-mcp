"""Tests for E10.16: leave the place as you found it."""

from pathlib import Path
from unittest.mock import MagicMock, call

import numpy as np
import pytest

from conftest import DIMS, make_embedding


def _make_mock_embedder(name="test-model"):
    from lore_mcp.embedder import Embedder
    emb = Embedder(model_name=name, mode="builtin:cpu")
    mock_model = MagicMock()
    mock_model.get_embedding_dimension.return_value = DIMS
    def encode_side_effect(input_data, normalize_embeddings=True):
        if isinstance(input_data, str):
            seed = hash(f"{name}:{input_data}") % (2**31)
            return np.random.RandomState(seed).randn(DIMS).astype(np.float32)
        vecs = [np.random.RandomState(hash(f"{name}:{t}") % (2**31)).randn(DIMS).astype(np.float32)
                for t in input_data]
        return np.array(vecs, dtype=np.float32)
    mock_model.encode.side_effect = encode_side_effect
    emb._model = mock_model
    return emb


class TestBuildCleansUp:
    def test_unload_all_before_final_reindex(self, tmp_path):
        """build.py: all embedders unloaded before final indexing."""
        from lore_mcp.build import run_build

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "doc.md").write_text("Content for testing. " * 30)

        manifest = tmp_path / "manifest.yaml"
        manifest.write_text("""
collection: test
level: libre
sources:
  - path: doc.md
    title: Test
""")

        emb_a = _make_mock_embedder("model-a")
        emb_b = _make_mock_embedder("model-b")
        unload_calls = []
        orig_unload_a = emb_a.unload
        orig_unload_b = emb_b.unload
        emb_a.unload = lambda: (unload_calls.append("a"), None)
        emb_b.unload = lambda: (unload_calls.append("b"), None)

        run_build(
            manifest_path=str(manifest),
            docs_dir=str(docs_dir),
            output_dir=str(tmp_path / "out"),
            embedders={"model-a": emb_a, "model-b": emb_b},
            skip_optimize=False,
            chunk_sizes=[1024],
            chunk_overlaps=[64],
            top_ks=[3],
            num_questions=2,
        )

        assert "a" in unload_calls
        assert "b" in unload_calls

    def test_final_embedder_unloaded_after_build(self, tmp_path):
        """build.py: winning embedder unloaded after final indexing."""
        from lore_mcp.build import run_build

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "doc.md").write_text("Content for testing. " * 30)

        manifest = tmp_path / "manifest.yaml"
        manifest.write_text("""
collection: test
level: libre
sources:
  - path: doc.md
    title: Test
""")

        emb = _make_mock_embedder()
        unloaded = []
        emb.unload = lambda: unloaded.append(True)

        run_build(
            manifest_path=str(manifest),
            docs_dir=str(docs_dir),
            output_dir=str(tmp_path / "out"),
            embedder=emb,
            skip_optimize=True,
        )

        assert len(unloaded) >= 1


class TestOptimizeCleansUp:
    def test_last_model_unloaded(self, tmp_path):
        """run_optimize: last model is unloaded at end."""
        from lore_mcp.eval import run_optimize

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "doc.md").write_text("Content for testing. " * 30)

        emb = _make_mock_embedder()
        unloaded = []
        emb.unload = lambda: unloaded.append(True)

        run_optimize(
            embedder=emb,
            source_dir=str(docs_dir),
            db_dir=str(tmp_path / "dbs"),
            chunk_sizes=[1024],
            chunk_overlaps=[64],
            top_ks=[3],
            num_questions=2,
        )

        assert len(unloaded) >= 1
