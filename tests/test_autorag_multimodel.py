"""Tests for E10.09: AutoRAG multi-model optimization."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from conftest import DIMS, make_embedding
from lore_mcp.store import create_tables, insert_chunk, open_db, upsert_source


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


class TestEmbeddingMetrics:
    """Level 1 metrics: no LLM, no ground truth."""

    def test_score_spread(self):
        from lore_mcp.eval import compute_embedding_metrics
        results = [
            {"score": 0.9, "source_file": "a.md", "content": "text a"},
            {"score": 0.7, "source_file": "b.md", "content": "text b"},
            {"score": 0.3, "source_file": "c.md", "content": "text c"},
        ]
        metrics = compute_embedding_metrics(results)
        assert abs(metrics["score_spread"] - 0.6) < 0.01

    def test_source_diversity(self):
        from lore_mcp.eval import compute_embedding_metrics
        results = [
            {"score": 0.9, "source_file": "a.md", "content": "t1"},
            {"score": 0.8, "source_file": "a.md", "content": "t2"},
            {"score": 0.7, "source_file": "b.md", "content": "t3"},
        ]
        metrics = compute_embedding_metrics(results)
        assert abs(metrics["source_diversity"] - 2/3) < 0.01

    def test_source_diversity_all_unique(self):
        from lore_mcp.eval import compute_embedding_metrics
        results = [
            {"score": 0.9, "source_file": "a.md", "content": "t1"},
            {"score": 0.8, "source_file": "b.md", "content": "t2"},
        ]
        metrics = compute_embedding_metrics(results)
        assert metrics["source_diversity"] == 1.0

    def test_empty_results(self):
        from lore_mcp.eval import compute_embedding_metrics
        metrics = compute_embedding_metrics([])
        assert metrics["score_spread"] == 0.0
        assert metrics["source_diversity"] == 0.0


class TestRetrievalMetricsMRR:
    """Level 2 metrics: with ground truth, no LLM."""

    def test_mrr_first_result(self):
        from lore_mcp.eval import compute_retrieval_metrics
        contexts = ["the answer is here", "other text"]
        metrics = compute_retrieval_metrics(contexts, "the answer is here")
        assert metrics["mrr"] == 1.0

    def test_mrr_second_result(self):
        from lore_mcp.eval import compute_retrieval_metrics
        contexts = ["irrelevant", "the answer is here"]
        metrics = compute_retrieval_metrics(contexts, "the answer is here")
        assert metrics["mrr"] == 0.5

    def test_mrr_not_found(self):
        from lore_mcp.eval import compute_retrieval_metrics
        contexts = ["irrelevant", "also irrelevant"]
        metrics = compute_retrieval_metrics(contexts, "the answer")
        assert metrics["mrr"] == 0.0


class TestSelectableMetrics:
    """User selects which metrics to compute."""

    def test_select_level1_only(self):
        from lore_mcp.eval import METRIC_LEVELS
        assert "score_spread" in METRIC_LEVELS["embedding"]
        assert "source_diversity" in METRIC_LEVELS["embedding"]
        assert "result_diversity" in METRIC_LEVELS["embedding"]

    def test_select_level2(self):
        from lore_mcp.eval import METRIC_LEVELS
        assert "hit" in METRIC_LEVELS["retrieval"]
        assert "mrr" in METRIC_LEVELS["retrieval"]
        assert "word_overlap" in METRIC_LEVELS["retrieval"]

    def test_all_metrics_listed(self):
        from lore_mcp.eval import METRIC_LEVELS
        assert "embedding" in METRIC_LEVELS
        assert "retrieval" in METRIC_LEVELS


class TestModelConfig:
    """Parse model configurations for multi-model optimize."""

    def test_parse_models_yaml(self, tmp_path):
        from lore_mcp.eval import parse_model_configs
        config_path = tmp_path / "models.yaml"
        config_path.write_text("""
models:
  - name: BAAI/bge-m3
    mode: builtin
  - name: nomic-embed-text-v1.5
    mode: api
    api_url: https://vllm-nomic/v1/embeddings
""")
        configs = parse_model_configs(str(config_path))
        assert len(configs) == 2
        assert configs[0]["name"] == "BAAI/bge-m3"
        assert configs[1]["mode"] == "api"
        assert configs[1]["api_url"] == "https://vllm-nomic/v1/embeddings"

    def test_parse_models_cli(self):
        from lore_mcp.eval import parse_model_configs_from_cli
        configs = parse_model_configs_from_cli("BAAI/bge-m3,nomic-embed-text-v1.5")
        assert len(configs) == 2
        assert configs[0]["name"] == "BAAI/bge-m3"
        assert configs[1]["name"] == "nomic-embed-text-v1.5"


class TestMultiModelOptimize:
    def test_optimize_multiple_models(self, tmp_path):
        from lore_mcp.eval import run_optimize

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "doc.md").write_text("Document content for testing optimization. " * 30)

        db_dir = tmp_path / "opt-dbs"
        db_dir.mkdir()

        embedders = {
            "model-a": _make_mock_embedder("model-a", DIMS),
            "model-b": _make_mock_embedder("model-b", DIMS),
        }

        results = run_optimize(
            embedder=None,
            embedders=embedders,
            source_dir=str(docs_dir),
            db_dir=str(db_dir),
            chunk_sizes=[512, 1024],
            chunk_overlaps=[64],
            top_ks=[3],
            num_questions=2,
        )

        assert "best" in results
        assert "all" in results
        models_in_results = {r["model_name"] for r in results["all"]}
        assert "model-a" in models_in_results
        assert "model-b" in models_in_results
        assert len(results["all"]) == 4  # 2 models × 2 sizes × 1 overlap × 1 top_k
