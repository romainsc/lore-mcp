"""Tests for lore_mcp.server. See docs/architecture.md for design context."""

from unittest.mock import MagicMock, patch

import pytest

from lore_mcp.server import format_search_results, format_sources


class TestFormatSearchResults:
    def test_formats_results(self):
        results = [
            {"content": "hello world", "source_file": "a.md", "score": 0.95},
            {"content": "foo bar", "source_file": "b.md", "score": 0.80},
        ]
        output = format_search_results(results, "cpu")
        assert "a.md" in output
        assert "0.95" in output
        assert "hello world" in output
        assert "2 result" in output

    def test_empty_results(self):
        output = format_search_results([], "cpu")
        assert "no result" in output.lower() or "0 result" in output.lower()

    def test_includes_backend(self):
        results = [{"content": "x", "source_file": "f.md", "score": 0.9}]
        output = format_search_results(results, "GPU-FP16")
        assert "GPU-FP16" in output


class TestFormatSources:
    def test_formats_sources(self):
        sources = [
            {"source_file": "a.md", "count": 10},
            {"source_file": "b.md", "count": 5},
        ]
        output = format_sources(sources)
        assert "a.md" in output
        assert "10" in output
        assert "15 chunks" in output or "15 chunk" in output

    def test_empty_sources(self):
        output = format_sources([])
        assert "0" in output or "empty" in output.lower() or "no" in output.lower()
