"""Tests for lore_mcp.preprocess.validate. See docs/studies/grooming-E12.01.md."""

import pytest

from lore_mcp.preprocess.validate import quality_gate


class TestQualityGate:
    """Lint-based quality gate on preprocessed files."""

    def test_good_file_passes(self, tmp_path):
        f = tmp_path / "good.md"
        f.write_text(
            "## Introduction\n\n"
            + "This is a well-written document with enough "
            + "textual content to pass quality checks. " * 10
            + "\n\n## Conclusion\n\n"
            + "The document concludes with sufficient prose "
            + "to demonstrate good text density. " * 5
        )

        report = quality_gate(str(f))
        assert report["verdict"] == "good"
        assert report["passed"] is True

    def test_poor_file_fails(self, tmp_path):
        f = tmp_path / "poor.md"
        f.write_text("0.234 0.567 0.891\n" * 50)

        report = quality_gate(str(f))
        assert report["verdict"] == "poor"
        assert report["passed"] is False

    def test_poor_file_passes_with_force(self, tmp_path):
        f = tmp_path / "poor.md"
        f.write_text("0.234 0.567 0.891\n" * 50)

        report = quality_gate(str(f), force=True)
        assert report["verdict"] == "poor"
        assert report["passed"] is True

    def test_warn_file_passes(self, tmp_path):
        f = tmp_path / "warn.md"
        f.write_text(
            "## Section\n\n"
            + "Some content here. " * 20
            + "\n\n## Empty\n\n"
        )

        report = quality_gate(str(f))
        assert report["passed"] is True

    def test_returns_lint_metrics(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text(
            "## Title\n\n"
            + "Content with words. " * 20
        )

        report = quality_gate(str(f))
        assert "text_density" in report
        assert "word_count" in report
