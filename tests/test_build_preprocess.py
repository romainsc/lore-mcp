"""Tests for build --preprocess integration. See E12.10."""

import yaml
import pytest
from unittest.mock import patch, MagicMock

from lore_mcp.build import run_build
from lore_mcp.config import LoreConfig


def _write_manifest(path, sources, collection="test", level="libre"):
    data = {"collection": collection, "level": level, "sources": sources}
    path.write_text(yaml.dump(data), encoding="utf-8")


class TestBuildWithPreprocess:
    """Build with --preprocess runs preprocess first."""

    def test_preprocess_creates_prep_dir_and_manifest(self, tmp_path):
        orig = tmp_path / "orig"
        orig.mkdir()
        (orig / "doc.md").write_text(
            "---\ntitle: Test Doc\n---\n\n## Section\n\n"
            + "Content for testing. " * 20 + "\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])
        output = tmp_path / "output"

        embedder = MagicMock()
        embedder.model_name = "test-model"
        embedder.model_dim = 768
        embedder.embed.return_value = [[0.1] * 768]
        embedder.embed_batch.return_value = [[0.1] * 768]

        cfg = LoreConfig(
            skip_optimize=True, output_level="quiet",
            preprocess=True, preprocess_orig_dir=".",
            preprocess_prep_dir="prep",
        )
        run_build(str(manifest), str(orig), str(output), cfg,
                  embedder=embedder)

        prep_dir = tmp_path / "orig" / "prep"
        assert prep_dir.exists()
        assert (prep_dir / "doc.md").exists()

    def test_preprocess_false_skips(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "doc.md").write_text(
            "---\ntitle: Test Doc\n---\n\n## Section\n\n"
            + "Content for testing. " * 20 + "\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"path": "doc.md", "orig": "doc.md"}])
        output = tmp_path / "output"

        embedder = MagicMock()
        embedder.model_name = "test-model"
        embedder.model_dim = 768
        embedder.embed.return_value = [[0.1] * 768]
        embedder.embed_batch.return_value = [[0.1] * 768]

        cfg = LoreConfig(skip_optimize=True, output_level="quiet")
        run_build(str(manifest), str(docs), str(output), cfg,
                  embedder=embedder)

        assert not (docs / "prep").exists()
