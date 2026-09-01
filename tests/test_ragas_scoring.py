"""Tests for E10.15: RAGAS scoring actually wired."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from conftest import DIMS, make_embedding
from lore_mcp.store import create_tables, insert_chunk, open_db


def _make_mock_embedder():
    from lore_mcp.embedder import Embedder
    emb = Embedder(model_name="test-model", mode="builtin:cpu")
    mock_model = MagicMock()
    mock_model.get_embedding_dimension.return_value = DIMS
    def encode_side_effect(input_data, normalize_embeddings=True):
        if isinstance(input_data, str):
            seed = hash(input_data) % (2**31)
            return np.random.RandomState(seed).randn(DIMS).astype(np.float32)
        return np.array([
            np.random.RandomState(hash(t) % (2**31)).randn(DIMS).astype(np.float32)
            for t in input_data
        ])
    mock_model.encode.side_effect = encode_side_effect
    emb._model = mock_model
    return emb


@pytest.fixture
def eval_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = open_db(db_path)
    create_tables(db, "test-model", DIMS)
    insert_chunk(db, "c1", "doc.md", 0, "Python is a programming language.",
                 make_embedding(0.1))
    insert_chunk(db, "c2", "doc.md", 1, "SQLite stores data in a single file.",
                 make_embedding(0.2))
    db.close()
    return db_path


class TestRagasScoringWired:
    def test_ragas_metrics_returned_when_requested(self, eval_db):
        """When RAGAS metrics requested + judge configured → scores include them."""
        from lore_mcp.eval import evaluate_retrieval, _apply_ragas_stub
        _apply_ragas_stub()

        embedder = _make_mock_embedder()
        questions = [
            {"question": "What is Python?", "ground_truth": "a programming language"},
        ]

        with patch("lore_mcp.eval._score_with_ragas") as mock_ragas:
            mock_ragas.return_value = {
                "faithfulness": 0.85,
                "context_recall": 0.90,
            }
            results = evaluate_retrieval(
                eval_db, embedder, questions, top_k=2,
                metrics=["faithfulness", "context_recall"],
                judge_url="http://localhost:11434/v1",
                judge_model="granite-8b",
            )

        assert "faithfulness" in results["details"][0]["scores"]
        assert "context_recall" in results["details"][0]["scores"]
        mock_ragas.assert_called_once()

    def test_non_ragas_metrics_still_work_without_judge(self, eval_db):
        """Non-RAGAS metrics work without judge, as before."""
        from lore_mcp.eval import evaluate_retrieval

        embedder = _make_mock_embedder()
        questions = [
            {"question": "What is SQLite?", "ground_truth": "stores data"},
        ]

        results = evaluate_retrieval(
            eval_db, embedder, questions, top_k=2,
            metrics=["hit", "word_overlap", "mrr"],
        )

        assert "hit" in results["details"][0]["scores"]
        assert "word_overlap" in results["details"][0]["scores"]
        assert "mrr" in results["details"][0]["scores"]

    def test_mixed_metrics(self, eval_db):
        """Both RAGAS and non-RAGAS metrics in same request."""
        from lore_mcp.eval import evaluate_retrieval, _apply_ragas_stub
        _apply_ragas_stub()

        embedder = _make_mock_embedder()
        questions = [
            {"question": "What is Python?", "ground_truth": "a programming language"},
        ]

        with patch("lore_mcp.eval._score_with_ragas") as mock_ragas:
            mock_ragas.return_value = {"faithfulness": 0.85}
            results = evaluate_retrieval(
                eval_db, embedder, questions, top_k=2,
                metrics=["hit", "mrr", "faithfulness"],
                judge_url="http://localhost:11434/v1",
                judge_model="granite-8b",
            )

        scores = results["details"][0]["scores"]
        assert "hit" in scores
        assert "mrr" in scores
        assert "faithfulness" in scores
