"""Tests for lore_mcp.preprocess.dedup. See docs/studies/grooming-E12.01.md."""

import pytest

from lore_mcp.preprocess.dedup import find_exact_duplicates, DedupReport


class TestFindExactDuplicates:
    """SHA-256 hash deduplication."""

    def test_no_duplicates(self):
        files = {
            "a.md": "Content A",
            "b.md": "Content B",
        }
        report = find_exact_duplicates(files)
        assert report.duplicates == []
        assert report.unique_count == 2

    def test_detects_identical_content(self):
        files = {
            "a.md": "Same content",
            "b.md": "Same content",
        }
        report = find_exact_duplicates(files)
        assert len(report.duplicates) == 1
        dup = report.duplicates[0]
        assert set(dup["files"]) == {"a.md", "b.md"}

    def test_keeps_first_occurrence(self):
        files = {
            "a.md": "Same content",
            "b.md": "Same content",
            "c.md": "Different",
        }
        report = find_exact_duplicates(files)
        assert report.unique_count == 2
        assert len(report.duplicates) == 1
        assert len(report.to_skip) == 1

    def test_multiple_duplicate_groups(self):
        files = {
            "a.md": "Content 1",
            "b.md": "Content 1",
            "c.md": "Content 2",
            "d.md": "Content 2",
            "e.md": "Unique",
        }
        report = find_exact_duplicates(files)
        assert len(report.duplicates) == 2
        assert report.unique_count == 3
        assert len(report.to_skip) == 2

    def test_empty_input(self):
        report = find_exact_duplicates({})
        assert report.duplicates == []
        assert report.unique_count == 0

    def test_whitespace_differences_not_duplicate(self):
        files = {
            "a.md": "Content",
            "b.md": "Content ",
        }
        report = find_exact_duplicates(files)
        assert report.duplicates == []

    def test_three_way_duplicate(self):
        files = {
            "a.md": "Same",
            "b.md": "Same",
            "c.md": "Same",
        }
        report = find_exact_duplicates(files)
        assert len(report.duplicates) == 1
        assert len(report.duplicates[0]["files"]) == 3
        assert len(report.to_skip) == 2


class TestDedupReport:
    """Report formatting."""

    def test_format_empty(self):
        report = DedupReport(duplicates=[], unique_count=3)
        text = report.format()
        assert "3" in text
        assert "no duplicates" in text.lower() or "0" in text

    def test_format_with_duplicates(self):
        report = DedupReport(
            duplicates=[{"files": ["a.md", "b.md"], "hash": "abc123"}],
            unique_count=1,
        )
        text = report.format()
        assert "a.md" in text
        assert "b.md" in text
