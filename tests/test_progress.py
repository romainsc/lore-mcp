"""Tests for E10.20: observability — structured progress output."""

import pytest


class TestProgressHeader:
    def test_header_shows_collection_and_models(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(
            collection="ia-libre",
            models=["nomic-v2-moe", "granite-r2"],
            total_configs=36,
        )
        r.print_header()
        out = capsys.readouterr().out
        assert "ia-libre" in out
        assert "nomic-v2-moe" in out
        assert "36" in out


class TestProgressTable:
    def test_row_format(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["m"], total_configs=10)
        r.print_table_header()
        r.print_row(1, "nomic-v2-moe", 512, 64, 3, 0.4821, is_best=False)
        out = capsys.readouterr().out
        assert "1" in out
        assert "nomic-v2-moe" in out
        assert "512/64" in out
        assert "0.4821" in out

    def test_best_row_has_star(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["m"], total_configs=10)
        r.print_row(5, "granite-r2", 1024, 128, 5, 0.6543, is_best=True)
        out = capsys.readouterr().out
        assert "★" in out

    def test_non_best_row_no_star(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["m"], total_configs=10)
        r.print_row(1, "model", 512, 64, 3, 0.5, is_best=False)
        out = capsys.readouterr().out
        assert "★" not in out


class TestProgressSections:
    def test_section_header(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["m"], total_configs=1)
        r.print_section("Pre-flight")
        out = capsys.readouterr().out
        assert "Pre-flight" in out
        assert "──" in out

    def test_step_timing(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["m"], total_configs=1)
        r.print_step("Indexing", elapsed=3.2)
        out = capsys.readouterr().out
        assert "3.2" in out
        assert "Indexing" in out

    def test_check_mark(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["m"], total_configs=1)
        r.print_check("ia-libre.db (18.2 MB)")
        out = capsys.readouterr().out
        assert "✓" in out


class TestProgressSummary:
    def test_summary_markdown_table(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="ia-libre", models=["m"], total_configs=1)
        r.print_summary(
            files=87, chunks=4231, configs_tested=36,
            elapsed=263.0, report_path="output/build-report.json",
        )
        out = capsys.readouterr().out
        assert "87" in out
        assert "4231" in out
        assert "36" in out
        assert "|" in out  # markdown table


class TestFullResultsTable:
    def test_renders_with_best_marked(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["a", "b"], total_configs=4)
        results = [
            {"model_name": "a", "chunk_size": 512, "chunk_overlap": 64, "top_k": 3, "avg_score": 0.48},
            {"model_name": "a", "chunk_size": 1024, "chunk_overlap": 128, "top_k": 5, "avg_score": 0.55},
            {"model_name": "b", "chunk_size": 512, "chunk_overlap": 64, "top_k": 3, "avg_score": 0.62},
            {"model_name": "b", "chunk_size": 1024, "chunk_overlap": 128, "top_k": 5, "avg_score": 0.59},
        ]
        r.print_results_table(results)
        out = capsys.readouterr().out
        assert "★" in out
        lines = [l for l in out.split("\n") if "★" in l]
        assert "0.62" in lines[0]  # best score
