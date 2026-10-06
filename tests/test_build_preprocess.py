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
            preprocess=True,
            orig_dir=str(orig),
            build_dir=str(output),
            force=True,
            keep_intermediates=True,
        )
        run_build(str(manifest), str(orig), str(output), cfg,
                  embedder=embedder)

        prep_base = output / "prep"
        assert prep_base.exists()
        md_files = list(prep_base.rglob("doc*.md"))
        assert len(md_files) >= 1, f"Expected preprocessed doc.md, found: {list(prep_base.iterdir()) if prep_base.exists() else 'dir missing'}"

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
            preprocess=True,
            orig_dir=str(orig),
            build_dir=str(output),
            force=True,
        )

        with patch("lore_mcp.build.preprocess_sources", mock_preprocess), \
             patch("lore_mcp.build._start_embedders", mock_start_embedders):
            run_build(str(manifest), str(orig), str(output), cfg)

        assert call_order == ["preprocess", "start_embedders"]


class TestBuildDirModel:
    """E12.90: --build-dir harmonized directory structure."""

    def test_build_dir_creates_structure(self, tmp_path):
        """build_dir creates prep/, .work/ during build (keep_intermediates to inspect)."""
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
            keep_intermediates=True,
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
            keep_intermediates=True,
        )
        run_build(str(manifest), str(orig), str(build), cfg,
                  embedder=embedder)

        checkpoint = build / ".work" / "checkpoint.json"
        assert checkpoint.exists(), f"Checkpoint not in .work/: {list((build / '.work').iterdir())}"


class TestChunkParamsFromConfig:
    """E12.105: skip_optimize must use config chunk params, not optimize defaults."""

    def test_skip_optimize_uses_config_chunk_size(self, tmp_path):
        from lore_mcp.store import open_db

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
            chunk_size=1024, chunk_overlap=128,
        )
        result = run_build(str(manifest), str(orig), str(build), cfg,
                           embedder=embedder)

        db = open_db(str(build / "test.db"))
        meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
        db.close()

        assert meta["chunk_size"] == "1024", f"Expected 1024, got {meta['chunk_size']}"
        assert meta["chunk_overlap"] == "128", f"Expected 128, got {meta['chunk_overlap']}"


class TestCollectionOverride:
    """E12.103: collection override from config must be used by run_build."""

    def test_collection_override_names_db(self, tmp_path):
        from lore_mcp.store import open_db

        orig = tmp_path / "file"
        orig.mkdir()
        (orig / "doc.md").write_text(
            "---\ntitle: Test\n---\n\n## Section\n\n"
            + "Content for testing. " * 20 + "\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"file": "doc.md"}], collection="original")
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
            collection_override="custom-name",
        )
        result = run_build(str(manifest), str(orig), str(build), cfg,
                           embedder=embedder)

        assert (build / "custom-name.db").exists(), (
            f"Expected custom-name.db, found: {list(build.glob('*.db'))}"
        )
