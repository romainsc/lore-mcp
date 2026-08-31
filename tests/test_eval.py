"""Tests for E10.02: RAG evaluation. See docs/architecture.md."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from conftest import DIMS, make_embedding
from lore_mcp.store import create_tables, insert_chunk, open_db, upsert_source


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


@pytest.fixture
def eval_db(tmp_path):
    """Create a populated database for eval tests."""
    db_path = str(tmp_path / "test.db")
    db = open_db(db_path)
    create_tables(db, "test-model", DIMS, chunk_size=1024, chunk_overlap=128)
    chunks = [
        ("c1", "intro.md", 0, "lore-mcp uses sqlite-vec for vector storage in a single portable file."),
        ("c2", "intro.md", 1, "Embedding generation falls back automatically: GPU, API, then CPU."),
        ("c3", "config.md", 0, "Set LORE_DB_PATH to configure the database location."),
        ("c4", "config.md", 1, "Set LORE_EMBED_MODE to auto, gpu, api, or cpu."),
        ("c5", "arch.md", 0, "The store layer uses cosine distance for KNN search."),
    ]
    for cid, src, idx, content in chunks:
        insert_chunk(db, cid, src, idx, content, make_embedding(hash(content) % 100 * 0.01))
    upsert_source(db, "intro.md", title="Introduction", author="RC")
    upsert_source(db, "config.md", title="Configuration", author="RC")
    upsert_source(db, "arch.md", title="Architecture", author="RC")
    db.close()
    return db_path


class TestEvalConfig:
    def test_eval_config_from_env(self):
        from lore_mcp.eval import EvalConfig
        with patch.dict(os.environ, {
            "LORE_LLM_URL": "http://localhost:8000/v1",
            "LORE_LLM_MODEL": "granite-8b",
        }):
            config = EvalConfig.from_env()
            assert config.llm_url == "http://localhost:8000/v1"
            assert config.llm_model == "granite-8b"

    def test_eval_config_missing_llm_url(self):
        from lore_mcp.eval import EvalConfig
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LORE_LLM_URL", None)
            with pytest.raises(ValueError, match="LORE_LLM_URL"):
                EvalConfig.from_env()


class TestGenerateTestset:
    def test_generate_questions_from_db(self, eval_db):
        """Generate Q&A pairs from indexed chunks (mocked LLM)."""
        from lore_mcp.eval import generate_questions_from_db
        questions = generate_questions_from_db(
            eval_db, num_questions=3, llm=MagicMock()
        )
        assert len(questions) == 3
        assert all("question" in q for q in questions)
        assert all("contexts" in q for q in questions)


class TestRetrievalEval:
    def test_evaluate_retrieval(self, eval_db):
        """Evaluate retrieval quality with mock scoring."""
        from lore_mcp.eval import evaluate_retrieval
        embedder = _make_mock_embedder()
        questions = [
            {"question": "How does vector storage work?", "ground_truth": "sqlite-vec"},
            {"question": "What is the embedding fallback?", "ground_truth": "GPU then API then CPU"},
        ]
        results = evaluate_retrieval(eval_db, embedder, questions, top_k=3)
        assert "scores" in results
        assert "details" in results
        assert len(results["details"]) == 2
        assert all("question" in d for d in results["details"])
        assert all("contexts" in d for d in results["details"])


class TestEvalReport:
    def test_generate_report_json(self, tmp_path):
        from lore_mcp.eval import generate_eval_report
        results = {
            "db_path": "/tmp/test.db",
            "num_questions": 2,
            "top_k": 5,
            "scores": {"context_precision": 0.85, "context_recall": 0.72},
            "details": [
                {"question": "Q1", "contexts": ["c1"], "scores": {"precision": 0.9}},
                {"question": "Q2", "contexts": ["c2"], "scores": {"precision": 0.8}},
            ],
        }
        report_path = generate_eval_report(results, str(tmp_path / "report.json"))
        assert Path(report_path).exists()
        data = json.loads(Path(report_path).read_text())
        assert data["scores"]["context_precision"] == 0.85
