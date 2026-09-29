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
        orig = tmp_path / "file"
        orig.mkdir()
        (orig / "doc.md").write_text(
            "---\ntitle: Test Doc\n---\n\n## Section\n\n"
            + "Content for testing. " * 20 + "\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"file": "doc.md"}])
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
            force=True,
        )
        run_build(str(manifest), str(orig), str(output), cfg,
                  embedder=embedder)

        prep_base = tmp_path / "file" / "prep"
        assert prep_base.exists()
        final_dir = prep_base / "file"
        md_files = list(final_dir.glob("doc*.md"))
        assert len(md_files) >= 1, f"Expected preprocessed doc.md, found: {list(final_dir.iterdir()) if final_dir.exists() else 'dir missing'}"

    def test_preprocess_false_skips(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "doc.md").write_text(
            "---\ntitle: Test Doc\n---\n\n## Section\n\n"
            + "Content for testing. " * 20 + "\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"path": "doc.md", "file": "doc.md"}])
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

    def test_embedders_created_after_preprocess(self, tmp_path):
        """E12.68: embedding service must not start before preprocessing."""
        orig = tmp_path / "file"
        orig.mkdir()
        (orig / "doc.md").write_text(
            "---\ntitle: Test Doc\n---\n\n## Section\n\n"
            + "Content for testing. " * 20 + "\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"file": "doc.md"}])
        output = tmp_path / "output"

        call_order = []

        real_preprocess = None
        try:
            from lore_mcp.preprocess import preprocess_sources as _real
            real_preprocess = _real
        except ImportError:
            pass

        def mock_preprocess(recipe_path, docs_dir, config):
            call_order.append("preprocess")
            if real_preprocess:
                real_preprocess(recipe_path, docs_dir, config)

        def mock_start_embedders(config):
            call_order.append("start_embedders")
            embedder = MagicMock()
            embedder.model_name = "test-model"
            embedder.model_dim = 768
            embedder.embed.return_value = [[0.1] * 768]
            embedder.embed_batch.return_value = [[0.1] * 768]
            embedder.unload = MagicMock()
            return {"test-model": embedder}

        cfg = LoreConfig(
            skip_optimize=True, output_level="quiet",
            preprocess=True, preprocess_orig_dir=".",
            preprocess_prep_dir="prep",
            force=True,
        )

        with patch("lore_mcp.build.preprocess_sources", mock_preprocess), \
             patch("lore_mcp.build._start_embedders", mock_start_embedders):
            run_build(str(manifest), str(orig), str(output), cfg)

        assert call_order == ["preprocess", "start_embedders"]


class TestBuildDirModel:
    """E12.90: --build-dir harmonized directory structure."""

    def test_build_dir_creates_structure(self, tmp_path):
        """build_dir creates prep/, .work/ and outputs."""
        from lore_mcp.build import run_build

        orig = tmp_path / "file"
        orig.mkdir()
        (orig / "doc.md").write_text(
            "---\ntitle: Test\n---\n\n## Section\n\n"
            + "Content for testing. " * 20 + "\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"file": "doc.md"}])
        build = tmp_path / "build"

        embedder = MagicMock()
        embedder.model_name = "test-model"
        embedder.model_dim = 768
        embedder.embed.return_value = [[0.1] * 768]
        embedder.embed_batch.return_value = [[0.1] * 768]

        cfg = LoreConfig(
            skip_optimize=True, output_level="quiet",
            preprocess=True, force=True,
            build_dir=str(build),
            orig_dir=str(orig),
        )
        result = run_build(str(manifest), str(orig), str(build), cfg,
                           embedder=embedder)

        assert (build / "prep").exists(), "prep/ not created"
        assert (build / ".work").exists(), "work/ not created"
        md_files = list((build / "prep").glob("*.md"))
        assert len(md_files) >= 1, f"No preprocessed files: {list((build / 'prep').iterdir())}"
        assert result["file_count"] >= 1
        assert result["chunk_count"] > 0

    def test_build_dir_checkpoint_in_work(self, tmp_path):
        """Checkpoint is in build-dir/.work/ not ~/.local/state/."""
        from lore_mcp.build import run_build

        orig = tmp_path / "file"
        orig.mkdir()
        (orig / "doc.md").write_text(
            "---\ntitle: Test\n---\n\n## Section\n\n"
            + "Content for testing. " * 20 + "\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"file": "doc.md"}])
        build = tmp_path / "build"

        embedder = MagicMock()
        embedder.model_name = "test-model"
        embedder.model_dim = 768
        embedder.embed.return_value = [[0.1] * 768]
        embedder.embed_batch.return_value = [[0.1] * 768]

        cfg = LoreConfig(
            skip_optimize=True, output_level="quiet",
            preprocess=True, force=True,
            build_dir=str(build),
            orig_dir=str(orig),
        )
        run_build(str(manifest), str(orig), str(build), cfg,
                  embedder=embedder)

        checkpoint = build / ".work" / "checkpoint.json"
        assert checkpoint.exists(), f"Checkpoint not in .work/: {list((build / '.work').iterdir())}"
