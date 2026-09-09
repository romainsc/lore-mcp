"""Tests for lore_mcp.preprocess.dedup. See docs/studies/grooming-E12.01.md."""

import pytest

from lore_mcp.preprocess.dedup import find_exact_duplicates, find_near_duplicates, DedupReport


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


try:
    import datasketch
    _HAS_DATASKETCH = True
except ImportError:
    _HAS_DATASKETCH = False


@pytest.mark.skipif(not _HAS_DATASKETCH, reason="datasketch not installed")
class TestFindNearDuplicates:
    """MinHash+LSH near-duplicate detection via datasketch."""

    def test_no_duplicates(self):
        a = "This document covers machine learning algorithms and neural networks in depth. " * 5
        b = "Database optimization techniques include indexing query planning and caching. " * 5
        report = find_near_duplicates({"a.md": a, "b.md": b}, threshold=0.8)
        assert report.duplicates == []

    def test_detects_near_identical(self):
        base = "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. "
        a = base * 5
        b = base * 5 + "Additional sentence."
        report = find_near_duplicates({"a.md": a, "b.md": b}, threshold=0.5)
        assert len(report.duplicates) >= 1

    def test_empty_input(self):
        report = find_near_duplicates({}, threshold=0.8)
        assert report.duplicates == []

    def test_uses_academic_defaults(self):
        from lore_mcp.preprocess.dedup import SHINGLE_K, NUM_PERM, DEFAULT_NEAR_THRESHOLD
        assert SHINGLE_K == 5
        assert NUM_PERM == 128
        assert DEFAULT_NEAR_THRESHOLD == 0.8


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
