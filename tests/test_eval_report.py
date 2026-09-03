"""Tests for E10.28: detailed eval report in markdown."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_questions():
    return [
        {
            "question": "Embedding engine",
            "ground_truth": "The embedding engine supports GPU, API, and CPU backends.",
            "source_file": "architecture.md",
        },
        {
            "question": "Vector storage",
            "ground_truth": "SQLite with sqlite-vec provides single-file portable storage.",
            "source_file": "architecture.md",
        },
    ]


@pytest.fixture
def sample_results():
    return [
        {
            "model_name": "granite",
            "chunk_size": 512, "chunk_overlap": 64, "top_k": 3,
            "scores": {"hit": 1.0, "mrr": 1.0, "ndcg@5": 1.0, "recall@5": 1.0, "word_overlap": 0.92},
            "avg_score": 0.48,
            "details": [
                {
                    "question": "Embedding engine",
                    "ground_truth": "The embedding engine supports GPU, API, and CPU backends.",
                    "contexts": ["The embedding engine supports GPU, API, and CPU backends with fallback."],
                    "sources": ["architecture.md"],
                    "scores": {"hit": 1.0, "mrr": 1.0, "ndcg@5": 1.0, "recall@5": 1.0, "word_overlap": 0.92},
                },
                {
                    "question": "Vector storage",
                    "ground_truth": "SQLite with sqlite-vec provides single-file portable storage.",
                    "contexts": ["SQLite with sqlite-vec provides portable storage."],
                    "sources": ["architecture.md"],
                    "scores": {"hit": 1.0, "mrr": 0.5, "ndcg@5": 0.63, "recall@5": 1.0, "word_overlap": 0.85},
                },
            ],
        },
        {
            "model_name": "nomic",
            "chunk_size": 512, "chunk_overlap": 64, "top_k": 5,
            "scores": {"hit": 1.0, "mrr": 1.0, "ndcg@5": 1.0, "recall@5": 1.0, "word_overlap": 0.97},
            "avg_score": 0.55,
            "details": [
                {
                    "question": "Embedding engine",
                    "ground_truth": "The embedding engine supports GPU, API, and CPU backends.",
                    "contexts": ["The embedding engine supports GPU, API, and CPU backends with automatic fallback."],
                    "sources": ["architecture.md"],
                    "scores": {"hit": 1.0, "mrr": 1.0, "ndcg@5": 1.0, "recall@5": 1.0, "word_overlap": 0.95},
                },
                {
                    "question": "Vector storage",
                    "ground_truth": "SQLite with sqlite-vec provides single-file portable storage.",
                    "contexts": ["SQLite with sqlite-vec provides single-file portable vector storage."],
                    "sources": ["architecture.md"],
                    "scores": {"hit": 1.0, "mrr": 1.0, "ndcg@5": 1.0, "recall@5": 1.0, "word_overlap": 0.97},
                },
            ],
        },
    ]


class TestGenerateEvalReportMd:
    def test_creates_file(self, tmp_path, sample_questions, sample_results):
        from lore_mcp.eval import generate_eval_report_md
        path = str(tmp_path / "eval-report.md")
        generate_eval_report_md(sample_questions, sample_results, sample_results[1], 42.0, path)
        assert Path(path).exists()

    def test_contains_questions_chapter(self, tmp_path, sample_questions, sample_results):
        from lore_mcp.eval import generate_eval_report_md
        path = str(tmp_path / "eval-report.md")
        generate_eval_report_md(sample_questions, sample_results, sample_results[1], 42.0, path)
        content = Path(path).read_text()
        assert "## 1. Reference questions" in content
        assert "Embedding engine" in content
        assert "The embedding engine supports GPU" in content

    def test_contains_generation_method(self, tmp_path, sample_questions, sample_results):
        from lore_mcp.eval import generate_eval_report_md
        path = str(tmp_path / "eval-report.md")
        generate_eval_report_md(sample_questions, sample_results, sample_results[1], 42.0, path)
        content = Path(path).read_text()
        assert "heading" in content.lower() or "before chunking" in content.lower()

    def test_contains_model_chapters(self, tmp_path, sample_questions, sample_results):
        from lore_mcp.eval import generate_eval_report_md
        path = str(tmp_path / "eval-report.md")
        generate_eval_report_md(sample_questions, sample_results, sample_results[1], 42.0, path)
        content = Path(path).read_text()
        assert "## 2. granite" in content
        assert "## 3. nomic" in content

    def test_contains_scores_table(self, tmp_path, sample_questions, sample_results):
        from lore_mcp.eval import generate_eval_report_md
        path = str(tmp_path / "eval-report.md")
        generate_eval_report_md(sample_questions, sample_results, sample_results[1], 42.0, path)
        content = Path(path).read_text()
        assert "| hit |" in content or "hit" in content
        assert "0.92" in content

    def test_contains_blockquote_answers(self, tmp_path, sample_questions, sample_results):
        from lore_mcp.eval import generate_eval_report_md
        path = str(tmp_path / "eval-report.md")
        generate_eval_report_md(sample_questions, sample_results, sample_results[1], 42.0, path)
        content = Path(path).read_text()
        assert "**Q1. Embedding engine**" in content
        assert "> The embedding engine" in content

    def test_best_config_marked(self, tmp_path, sample_questions, sample_results):
        from lore_mcp.eval import generate_eval_report_md
        path = str(tmp_path / "eval-report.md")
        generate_eval_report_md(sample_questions, sample_results, sample_results[1], 42.0, path)
        content = Path(path).read_text()
        assert "★" in content

    def test_contains_appendix(self, tmp_path, sample_questions, sample_results):
        from lore_mcp.eval import generate_eval_report_md
        path = str(tmp_path / "eval-report.md")
        generate_eval_report_md(sample_questions, sample_results, sample_results[1], 42.0, path)
        content = Path(path).read_text()
        assert "Appendix" in content
        assert "ndcg" in content.lower()
        assert "word_overlap" in content

    def test_aggregate_has_min_max(self, tmp_path, sample_questions, sample_results):
        from lore_mcp.eval import generate_eval_report_md
        path = str(tmp_path / "eval-report.md")
        generate_eval_report_md(sample_questions, sample_results, sample_results[1], 42.0, path)
        content = Path(path).read_text()
        assert "Min" in content
        assert "Max" in content
