"""Integration tests verifying pipeline wiring.

These tests verify that functions are actually CALLED from
the pipeline, not just that they exist. Every broken/partial
item from the audit gets a wiring test here.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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
        return np.array([
            np.random.RandomState(hash(f"{name}:{t}") % (2**31)).randn(DIMS).astype(np.float32)
            for t in input_data
        ])
    mock_model.encode.side_effect = encode_side_effect
    emb._model = mock_model
    emb.unload = lambda: None
    return emb


@pytest.fixture
def build_env(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "doc.md").write_text("Test document content. " * 30)
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("""
collection: test
level: libre
sources:
  - path: doc.md
    title: Test Doc
""")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return {"docs_dir": str(docs_dir), "manifest": str(manifest),
            "output_dir": str(output_dir), "tmp_path": tmp_path}


class TestE10_19_RagasGuardCalled:
    """E10.19: check_ragas_guard must be called in the pipeline."""

    def test_guard_called_in_run_eval(self, build_env):
        from lore_mcp.eval import run_eval, EvalConfig
        from lore_mcp.store import create_tables, insert_chunk, open_db

        db_path = str(build_env["tmp_path"] / "eval.db")
        db = open_db(db_path)
        create_tables(db, "test-model", DIMS)
        insert_chunk(db, "c1", "doc.md", 0, "content", make_embedding(0.1))
        db.close()

        emb = _make_mock_embedder()
        config = EvalConfig(llm_url="http://judge:11434/v1", llm_model="granite-8b")

        with patch("lore_mcp.eval.check_ragas_guard") as mock_guard:
            run_eval(db_path, emb, config)
            mock_guard.assert_called_once()


class TestE10_20_ProgressReporterCalled:
    """E10.20: ProgressReporter must be used in run_optimize."""

    def test_reporter_used_in_optimize(self, build_env):
        from lore_mcp.eval import run_optimize

        emb = _make_mock_embedder()

        with patch("lore_mcp.eval.ProgressReporter") as MockReporter:
            mock_instance = MagicMock()
            MockReporter.return_value = mock_instance
            run_optimize(
                embedder=emb,
                source_dir=build_env["docs_dir"],
                db_dir=str(build_env["tmp_path"] / "dbs"),
                chunk_sizes=[1024], chunk_overlaps=[64],
                top_ks=[3], num_questions=2,
            )
            MockReporter.assert_called_once()


class TestE10_09_EmbeddingMetricsStored:
    """E10.09: compute_embedding_metrics result must be stored."""

    def test_embedding_metrics_in_results(self, build_env):
        from lore_mcp.eval import run_optimize

        emb = _make_mock_embedder()
        results = run_optimize(
            embedder=emb,
            source_dir=build_env["docs_dir"],
            db_dir=str(build_env["tmp_path"] / "dbs"),
            chunk_sizes=[1024], chunk_overlaps=[64],
            top_ks=[3], num_questions=2,
        )

        assert "score_spread" in results["all"][0]["scores"]


class TestE10_14_MetricsPassedThrough:
    """E10.14: BuildConfig metrics/judge must reach evaluate_retrieval."""

    def test_config_metrics_reach_evaluate(self, build_env):
        from lore_mcp.eval import run_optimize

        config_path = build_env["tmp_path"] / "config.yaml"
        config_path.write_text("""
embedding:
  - name: test-model
    mode: builtin:cpu
judge:
  model: granite-8b
  api_url: http://localhost:11434/v1
metrics: [score_spread, mrr, faithfulness]
optimize:
  chunk_sizes: [1024]
  chunk_overlaps: [64]
  top_ks: [3]
  num_questions: 2
""")

        emb = _make_mock_embedder()

        with patch("lore_mcp.eval._probe_judge"), \
             patch("lore_mcp.eval.evaluate_retrieval", wraps=None) as mock_eval:
            mock_eval.return_value = {
                "scores": {"mrr": 0.5}, "details": [],
                "db_path": "", "model_name": "test", "num_questions": 2, "top_k": 3,
            }
            from lore_mcp.build_config import BuildConfig
            bc = BuildConfig.from_file(str(config_path))
            run_optimize(
                embedder=emb,
                source_dir=build_env["docs_dir"],
                db_dir=str(build_env["tmp_path"] / "dbs"),
                chunk_sizes=bc.chunk_sizes,
                chunk_overlaps=bc.chunk_overlaps,
                top_ks=bc.top_ks,
                num_questions=bc.num_questions,
                metrics=bc.metrics,
                judge_url=bc.judge_api_url,
                judge_model=bc.judge_model,
            )
            args, kwargs = mock_eval.call_args
            assert "metrics" in kwargs or len(args) > 4


class TestE10_18_ConsecutiveThresholdUsed:
    """E10.18: ConsecutiveErrorThreshold must be used in ingest."""

    def test_threshold_used_in_ingest(self, build_env):
        from lore_mcp.ingest import ingest_directory

        emb = _make_mock_embedder()

        with patch("lore_mcp.ingest.ConsecutiveErrorThreshold") as MockThreshold:
            mock_instance = MagicMock()
            MockThreshold.return_value = mock_instance
            ingest_directory(
                build_env["docs_dir"],
                str(build_env["tmp_path"] / "test.db"),
                emb,
            )
            MockThreshold.assert_called_once()


class TestE10_13_DefaultsUsed:
    """E10.13: BuildConfig defaults used in skip-optimize mode."""

    def test_defaults_used_when_skip_optimize(self, build_env):
        from lore_mcp.build import run_build

        config_path = build_env["tmp_path"] / "config.yaml"
        config_path.write_text("""
embedding:
  - name: test-model
    mode: builtin:cpu
defaults:
  chunk_size: 512
  chunk_overlap: 32
""")

        from lore_mcp.build_config import BuildConfig
        bc = BuildConfig.from_file(str(config_path))
        emb = _make_mock_embedder()

        result = run_build(
            manifest_path=build_env["manifest"],
            docs_dir=build_env["docs_dir"],
            output_dir=build_env["output_dir"],
            embedder=emb,
            skip_optimize=True,
            chunk_sizes=[bc.default_chunk_size],
            chunk_overlaps=[bc.default_chunk_overlap],
        )

        assert result["chunk_size"] == 512
