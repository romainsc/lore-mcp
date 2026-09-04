"""Tests for E6.07: source quality analysis (lint)."""

import pytest
from pathlib import Path


@pytest.fixture
def good_doc(tmp_path):
    f = tmp_path / "good.md"
    f.write_text("""# Architecture

## Embedding engine

The embedding engine supports GPU, API, and CPU
backends with automatic fallback. Models are loaded
lazily on first query. The fallback chain tries GPU
first, then remote API, then CPU as last resort.

## Vector storage

SQLite with sqlite-vec provides single-file portable
vector storage. The vec0 virtual table stores float
arrays for cosine distance search. No server needed.
""")
    return f


@pytest.fixture
def poor_doc(tmp_path):
    f = tmp_path / "poor.md"
    f.write_text("""# Slides

## Slide 1

P

## Slide 2

282 256 308 360 334 386 438 412 464 490
597 24 51 50 77 129 103 155 207 181 233
285 259 311 363 337 389 441 415 467 519

## Slide 3

f
""")
    return f


@pytest.fixture
def manifest(tmp_path, good_doc, poor_doc):
    m = tmp_path / "manifest.yaml"
    m.write_text(f"""
collection: test
level: libre
sources:
  - path: good.md
    title: Good Doc
  - path: poor.md
    title: Poor Doc
""")
    return m


class TestAnalyzeFile:
    def test_good_file_metrics(self, good_doc):
        from lore_mcp.lint import analyze_file
        report = analyze_file(good_doc)
        assert report["text_density"] > 0.7
        assert report["heading_count"] >= 2
        assert report["empty_sections"] == 0
        assert report["noise_sections"] == 0
        assert report["word_count"] > 30

    def test_poor_file_metrics(self, poor_doc):
        from lore_mcp.lint import analyze_file
        report = analyze_file(poor_doc)
        assert report["text_density"] < 0.5
        assert report["noise_sections"] > 0

    def test_verdict_good(self, good_doc):
        from lore_mcp.lint import analyze_file
        report = analyze_file(good_doc)
        assert report["verdict"] == "good"

    def test_verdict_poor(self, poor_doc):
        from lore_mcp.lint import analyze_file
        report = analyze_file(poor_doc)
        assert report["verdict"] == "poor"

    def test_includes_filename(self, good_doc):
        from lore_mcp.lint import analyze_file
        report = analyze_file(good_doc)
        assert report["file"] == str(good_doc)


class TestLintSources:
    def test_reads_manifest(self, tmp_path, manifest):
        from lore_mcp.lint import lint_sources
        reports = lint_sources(str(tmp_path), str(manifest))
        files = [r["file"] for r in reports]
        assert any("good.md" in f for f in files)
        assert any("poor.md" in f for f in files)
        assert len(reports) == 2

    def test_exit_code_with_poor(self, tmp_path, manifest):
        from lore_mcp.lint import lint_sources
        reports = lint_sources(str(tmp_path), str(manifest))
        has_poor = any(r["verdict"] == "poor" for r in reports)
        assert has_poor

    def test_sorted_by_density(self, tmp_path, manifest):
        from lore_mcp.lint import lint_sources
        reports = lint_sources(str(tmp_path), str(manifest))
        densities = [r["text_density"] for r in reports]
        assert densities == sorted(densities)


class TestFormatReport:
    def test_table_output(self, tmp_path, manifest):
        from lore_mcp.lint import lint_sources, format_lint_report
        reports = lint_sources(str(tmp_path), str(manifest))
        output = format_lint_report(reports)
        assert "good.md" in output
        assert "poor.md" in output
        assert "good" in output
        assert "poor" in output
        assert "|" in output
