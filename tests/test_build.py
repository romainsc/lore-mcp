"""Tests for E11.01: lore-mcp build workflow."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from conftest import DIMS, make_embedding


def _make_mock_embedder(model_name="test-model", dim=DIMS):
    from lore_mcp.embedder import Embedder
    emb = Embedder(model_name=model_name, mode="builtin:cpu")
    mock_model = MagicMock()
    mock_model.get_embedding_dimension.return_value = dim
    def encode_side_effect(input_data, normalize_embeddings=True):
        if isinstance(input_data, str):
            seed = hash(f"{model_name}:{input_data}") % (2**31)
            rng = np.random.RandomState(seed)
            vec = rng.randn(dim).astype(np.float32)
            return vec / np.linalg.norm(vec)
        vecs = []
        for t in input_data:
            seed = hash(f"{model_name}:{t}") % (2**31)
            rng = np.random.RandomState(seed)
            vec = rng.randn(dim).astype(np.float32)
            vecs.append(vec / np.linalg.norm(vec))
        return np.array(vecs, dtype=np.float32)
    mock_model.encode.side_effect = encode_side_effect
    emb._model = mock_model
    return emb


@pytest.fixture
def build_env(tmp_path):
    """Create docs, manifest, and output dir for build tests."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "intro.md").write_text("""---
title: Introduction
author: RC
license: CC-BY-SA-4.0
---

# Introduction

This is an introduction to the system. """ + "More content. " * 30)
    (docs_dir / "config.md").write_text("""---
title: Configuration Guide
author: RC
---

# Configuration

Set LORE_DB_PATH to configure. """ + "More content. " * 30)

    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("""
collection: test-libre
level: libre
sources:
  - path: intro.md
    title: Introduction
    author: RC
    license: CC-BY-SA-4.0
  - path: config.md
    title: Configuration Guide
    author: RC
""")

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    return {
        "docs_dir": str(docs_dir),
        "manifest": str(manifest),
        "output_dir": str(output_dir),
        "tmp_path": tmp_path,
    }


# --- MVP1: build --skip-optimize ---


class TestPreflightValidation:
    def test_validate_local_model_cached(self):
        """Model in HF cache passes validation."""
        from lore_mcp.build import validate_models
        emb = _make_mock_embedder()
        configs = [{"name": "test-model", "mode": "cpu"}]
        errors = validate_models(configs, embedders={"test-model": emb})
        assert errors == []

    def test_validate_api_unreachable(self):
        """Unreachable API endpoint fails validation."""
        from lore_mcp.build import validate_models
        configs = [{"name": "remote-model", "mode": "api",
                     "api_url": "http://localhost:99999/v1/embeddings"}]
        errors = validate_models(configs)
        assert len(errors) == 1
        assert "remote-model" in errors[0]

    def test_validate_reports_all_failures(self):
        """All failures reported at once, not one by one."""
        from lore_mcp.build import validate_models
        configs = [
            {"name": "bad1", "mode": "api", "api_url": "http://localhost:99998/v1/embeddings"},
            {"name": "bad2", "mode": "api", "api_url": "http://localhost:99997/v1/embeddings"},
        ]
        errors = validate_models(configs)
        assert len(errors) == 2


class TestBuildSkipOptimize:
    def test_produces_db_and_metadata(self, build_env):
        """build --skip-optimize produces .db + .json + .bib + .md."""
        from lore_mcp.build import run_build

        emb = _make_mock_embedder()
        result = run_build(
            manifest_path=build_env["manifest"],
            docs_dir=build_env["docs_dir"],
            output_dir=build_env["output_dir"],
            embedder=emb,
            skip_optimize=True,
        )

        output = Path(build_env["output_dir"])
        assert (output / "test-libre.db").exists()
        assert (output / "test-libre.json").exists()
        assert (output / "test-libre.bib").exists()
        assert (output / "test-libre.md").exists()
        assert result["collection"] == "test-libre"
        assert result["file_count"] >= 2

    def test_build_report_written(self, build_env):
        """Build report JSON is written."""
        from lore_mcp.build import run_build

        emb = _make_mock_embedder()
        result = run_build(
            manifest_path=build_env["manifest"],
            docs_dir=build_env["docs_dir"],
            output_dir=build_env["output_dir"],
            embedder=emb,
            skip_optimize=True,
        )

        report_path = Path(build_env["output_dir"]) / "build-report.json"
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert report["collection"] == "test-libre"
        assert "model_name" in report


# --- MVP2: build with optimization ---


class TestBuildWithOptimize:
    def test_produces_optimized_db(self, build_env):
        """build with optimize selects best config and produces final .db."""
        from lore_mcp.build import run_build

        emb = _make_mock_embedder()
        result = run_build(
            manifest_path=build_env["manifest"],
            docs_dir=build_env["docs_dir"],
            output_dir=build_env["output_dir"],
            embedder=emb,
            skip_optimize=False,
            chunk_sizes=[512, 1024],
            chunk_overlaps=[64],
            top_ks=[3],
            num_questions=2,
        )

        output = Path(build_env["output_dir"])
        assert (output / "test-libre.db").exists()
        assert "optimization" in result
        assert "best" in result["optimization"]

    def test_build_multi_model(self, build_env):
        """build with multiple models selects best model+config."""
        from lore_mcp.build import run_build
        from unittest.mock import patch

        embedders = {
            "model-a": _make_mock_embedder("model-a"),
            "model-b": _make_mock_embedder("model-b"),
        }
        # Prevent unload from destroying mocks in test
        for emb in embedders.values():
            emb.unload = lambda: None
        result = run_build(
            manifest_path=build_env["manifest"],
            docs_dir=build_env["docs_dir"],
            output_dir=build_env["output_dir"],
            embedders=embedders,
            skip_optimize=False,
            chunk_sizes=[1024],
            chunk_overlaps=[64],
            top_ks=[3],
            num_questions=2,
        )

        assert "optimization" in result
        assert result["optimization"]["best"]["model_name"] in ("model-a", "model-b")


# --- MVP3: resumability ---


class TestResumability:
    def test_resume_skips_completed(self, build_env):
        """Second run skips already-completed optimization configs."""
        from lore_mcp.build import run_build

        emb = _make_mock_embedder()
        kwargs = dict(
            manifest_path=build_env["manifest"],
            docs_dir=build_env["docs_dir"],
            output_dir=build_env["output_dir"],
            embedder=emb,
            skip_optimize=False,
            chunk_sizes=[512, 1024],
            chunk_overlaps=[64],
            top_ks=[3],
            num_questions=2,
            work_dir=str(build_env["tmp_path"] / "work"),
        )

        result1 = run_build(**kwargs)
        result2 = run_build(**kwargs)

        assert result1["collection"] == result2["collection"]
        assert result2.get("resumed", False) is True

    def test_force_ignores_cache(self, build_env):
        """--force reruns everything."""
        from lore_mcp.build import run_build

        emb = _make_mock_embedder()
        kwargs = dict(
            manifest_path=build_env["manifest"],
            docs_dir=build_env["docs_dir"],
            output_dir=build_env["output_dir"],
            embedder=emb,
            skip_optimize=False,
            chunk_sizes=[1024],
            chunk_overlaps=[64],
            top_ks=[3],
            num_questions=2,
            work_dir=str(build_env["tmp_path"] / "work"),
        )

        run_build(**kwargs)
        result2 = run_build(**kwargs, force=True)

        assert result2.get("resumed", False) is False
