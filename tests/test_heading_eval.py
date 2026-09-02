"""Tests for E10.27: heading-based evaluation."""

import pytest
from pathlib import Path


@pytest.fixture
def docs_dir(tmp_path):
    doc1 = tmp_path / "architecture.md"
    doc1.write_text("""# Architecture

## Embedding engine

The embedding engine supports GPU, API, and CPU
backends with automatic fallback. Models are
loaded lazily on first query.

## Vector storage

SQLite with sqlite-vec provides single-file
portable vector storage. The vec0 virtual table
stores float arrays for cosine distance search.

## Chunking strategy

Documents are split using recursive character
splitting with configurable size and overlap
parameters for optimal retrieval quality.
""")

    doc2 = tmp_path / "configuration.md"
    doc2.write_text("""# Configuration

## Environment variables

LORE_DB_PATH sets the database file path.
LORE_MODEL configures the embedding model name.
LORE_EMBED_MODE selects between builtin and api.

## Build config YAML

The build config uses the embedding key to list
models with their mode and API URL for multi-model
optimization and comparison workflows.
""")
    return str(tmp_path)


class TestGenerateQuestionsFromSources:
    def test_extracts_heading_section_pairs(self, docs_dir):
        from lore_mcp.eval import generate_questions_from_sources
        questions = generate_questions_from_sources(docs_dir)
        assert len(questions) >= 4
        headings = [q["question"] for q in questions]
        assert any("Embedding engine" in h for h in headings)
        assert any("Vector storage" in h for h in headings)

    def test_ground_truth_is_section_content(self, docs_dir):
        from lore_mcp.eval import generate_questions_from_sources
        questions = generate_questions_from_sources(docs_dir)
        emb_q = [q for q in questions if "Embedding engine" in q["question"]][0]
        assert "GPU" in emb_q["ground_truth"]
        assert "automatic fallback" in emb_q["ground_truth"]

    def test_source_file_tracked(self, docs_dir):
        from lore_mcp.eval import generate_questions_from_sources
        questions = generate_questions_from_sources(docs_dir)
        sources = {q["source_file"] for q in questions}
        assert "architecture.md" in sources
        assert "configuration.md" in sources

    def test_num_questions_limit(self, docs_dir):
        from lore_mcp.eval import generate_questions_from_sources
        questions = generate_questions_from_sources(docs_dir, num_questions=2)
        assert len(questions) == 2

    def test_skips_top_level_heading(self, docs_dir):
        from lore_mcp.eval import generate_questions_from_sources
        questions = generate_questions_from_sources(docs_dir)
        headings = [q["question"] for q in questions]
        assert not any(h == "Architecture" for h in headings)
        assert not any(h == "Configuration" for h in headings)

    def test_skips_empty_sections(self, tmp_path):
        doc = tmp_path / "sparse.md"
        doc.write_text("""# Title

## Empty section

## Real section

This section has actual content that can be
used for retrieval evaluation purposes.
""")
        from lore_mcp.eval import generate_questions_from_sources
        questions = generate_questions_from_sources(str(tmp_path))
        headings = [q["question"] for q in questions]
        assert "Empty section" not in headings
        assert "Real section" in headings


class TestNdcgAtK:
    def test_perfect_ranking(self):
        from lore_mcp.eval import ndcg_at_k
        relevances = [1, 1, 0, 0, 0]
        assert ndcg_at_k(relevances, k=5) == pytest.approx(1.0)

    def test_reversed_ranking(self):
        from lore_mcp.eval import ndcg_at_k
        relevances = [0, 0, 0, 1, 1]
        assert ndcg_at_k(relevances, k=5) < 0.7

    def test_no_relevant(self):
        from lore_mcp.eval import ndcg_at_k
        relevances = [0, 0, 0]
        assert ndcg_at_k(relevances, k=3) == 0.0

    def test_single_relevant_first(self):
        from lore_mcp.eval import ndcg_at_k
        relevances = [1, 0, 0]
        assert ndcg_at_k(relevances, k=3) == pytest.approx(1.0)


class TestRecallAtK:
    def test_all_found(self):
        from lore_mcp.eval import recall_at_k
        relevances = [1, 1, 0]
        assert recall_at_k(relevances, total_relevant=2, k=3) == pytest.approx(1.0)

    def test_partial(self):
        from lore_mcp.eval import recall_at_k
        relevances = [1, 0, 0]
        assert recall_at_k(relevances, total_relevant=2, k=3) == pytest.approx(0.5)

    def test_none_found(self):
        from lore_mcp.eval import recall_at_k
        relevances = [0, 0, 0]
        assert recall_at_k(relevances, total_relevant=2, k=3) == pytest.approx(0.0)
