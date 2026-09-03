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

    def test_single_star_in_table(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["a"], total_configs=3)
        results = [
            {"model_name": "a", "chunk_size": 512, "chunk_overlap": 64, "top_k": 3, "avg_score": 0.48},
            {"model_name": "a", "chunk_size": 1024, "chunk_overlap": 128, "top_k": 5, "avg_score": 0.55},
            {"model_name": "a", "chunk_size": 2048, "chunk_overlap": 128, "top_k": 5, "avg_score": 0.50},
        ]
        r.print_results_table(results)
        out = capsys.readouterr().out
        assert out.count("★") == 1


class TestOutputLevels:
    def test_quiet_suppresses_all(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["a"], total_configs=3, level="quiet")
        r.print_header()
        r.print_section("Test")
        r.print_step("step1", elapsed=1.0)
        r.print_check("ok")
        r.print_milestone(config_num=1, msg="m1")
        r.print_results_table([
            {"model_name": "a", "chunk_size": 512, "chunk_overlap": 64, "top_k": 3, "avg_score": 0.5},
        ])
        r.print_summary(files=1, chunks=10, elapsed=5.0)
        out = capsys.readouterr().out
        assert out == ""

    def test_progress_compact(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["a"], total_configs=2, level="progress")
        r.print_header()
        r.print_milestone(config_num=1, msg="[1/2] a chunk=512/64 top_k=3: avg=0.50")
        r.print_milestone(config_num=2, msg="[2/2] a chunk=1024/128 top_k=5: avg=0.60")
        results = [
            {"model_name": "a", "chunk_size": 512, "chunk_overlap": 64, "top_k": 3, "avg_score": 0.50},
            {"model_name": "a", "chunk_size": 1024, "chunk_overlap": 128, "top_k": 5, "avg_score": 0.60},
        ]
        r.print_results_table(results)
        out = capsys.readouterr().out
        assert "Best:" in out
        assert "╔" not in out
        assert "★" not in out
        assert "%" in out  # progress bar with percentage
        assert "ETA" in out

    def test_default_shows_table(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["a"], total_configs=1, level="default")
        r.print_header()
        results = [
            {"model_name": "a", "chunk_size": 512, "chunk_overlap": 64, "top_k": 3, "avg_score": 0.50},
        ]
        r.print_results_table(results)
        out = capsys.readouterr().out
        assert "╔" in out
        assert "★" in out

    def test_verbose_shows_file_detail(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["a"], total_configs=1, level="verbose")
        r.print_file("doc.md", 12)
        out = capsys.readouterr().out
        assert "doc.md" in out
        assert "12" in out

    def test_default_hides_file_detail(self, capsys):
        from lore_mcp.progress import ProgressReporter
        r = ProgressReporter(collection="test", models=["a"], total_configs=1, level="default")
        r.print_file("doc.md", 12)
        out = capsys.readouterr().out
        assert out == ""


class TestConfigureLogging:
    def test_debug_sets_lore_mcp_debug(self):
        import logging
        from lore_mcp.progress import configure_logging
        configure_logging("debug")
        assert logging.getLogger("lore_mcp").level == logging.DEBUG
        assert logging.getLogger("httpx").level == logging.INFO
        assert logging.getLogger("httpcore").level == logging.WARNING

    def test_quiet_sets_root_error(self):
        import logging
        from lore_mcp.progress import configure_logging
        configure_logging("quiet")
        assert logging.getLogger().level == logging.ERROR

    def test_default_sets_root_warning(self):
        import logging
        from lore_mcp.progress import configure_logging
        configure_logging("default")
        assert logging.getLogger().level == logging.WARNING


class TestOutputLevelFromArgs:
    def test_quiet_flag(self):
        from lore_mcp.progress import output_level_from_args
        from types import SimpleNamespace
        args = SimpleNamespace(quiet=True, progress=False, verbose=False, debug=False)
        assert output_level_from_args(args) == "quiet"

    def test_progress_flag(self):
        from lore_mcp.progress import output_level_from_args
        from types import SimpleNamespace
        args = SimpleNamespace(quiet=False, progress=True, verbose=False, debug=False)
        assert output_level_from_args(args) == "progress"

    def test_verbose_flag(self):
        from lore_mcp.progress import output_level_from_args
        from types import SimpleNamespace
        args = SimpleNamespace(quiet=False, progress=False, verbose=True, debug=False)
        assert output_level_from_args(args) == "verbose"

    def test_debug_flag(self):
        from lore_mcp.progress import output_level_from_args
        from types import SimpleNamespace
        args = SimpleNamespace(quiet=False, progress=False, verbose=False, debug=True)
        assert output_level_from_args(args) == "debug"

    def test_default_no_flag(self):
        from lore_mcp.progress import output_level_from_args
        from types import SimpleNamespace
        args = SimpleNamespace(quiet=False, progress=False, verbose=False, debug=False)
        assert output_level_from_args(args) == "default"
