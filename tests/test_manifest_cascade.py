"""Tests for manifest field cascade (v2). See docs/studies/grooming-E12.01.md."""

import pytest

from lore_mcp.manifest import resolve_source_fields


class TestResolveSourceFields:
    """Test the field cascade: orig → path → title generation."""

    def test_orig_only(self):
        source = {"file": "architecture.pdf"}
        result = resolve_source_fields(source)
        assert result["file"] == "architecture.pdf"
        assert result["path"] == "architecture.md"

    def test_orig_md_keeps_extension(self):
        source = {"file": "notes.md"}
        result = resolve_source_fields(source)
        assert result["path"] == "notes.md"

    def test_orig_html(self):
        source = {"file": "guide.html"}
        result = resolve_source_fields(source)
        assert result["path"] == "guide.md"

    def test_orig_docx(self):
        source = {"file": "report.docx"}
        result = resolve_source_fields(source)
        assert result["path"] == "report.md"

    def test_explicit_path_overrides(self):
        source = {"file": "guide-v2.html", "path": "project-guide.md"}
        result = resolve_source_fields(source)
        assert result["file"] == "guide-v2.html"
        assert result["path"] == "project-guide.md"

    def test_url_derives_orig(self):
        source = {"url": "https://example.com/spec.pdf"}
        result = resolve_source_fields(source)
        assert result["file"] == "spec.pdf"
        assert result["path"] == "spec.md"

    def test_url_with_query_params(self):
        source = {"url": "https://example.com/doc.pdf?v=2&token=abc"}
        result = resolve_source_fields(source)
        assert result["file"] == "doc.pdf"
        assert result["path"] == "doc.md"

    def test_url_with_explicit_orig(self):
        source = {"url": "https://example.com/doc.pdf", "file": "local.pdf"}
        result = resolve_source_fields(source)
        assert result["file"] == "local.pdf"
        assert result["path"] == "local.md"

    def test_no_orig_no_url_raises(self):
        source = {"title": "Orphan doc"}
        with pytest.raises(ValueError, match="file.*url"):
            resolve_source_fields(source)

    def test_preserves_existing_fields(self):
        source = {
            "file": "doc.pdf",
            "title": "My Document",
            "author": "RC",
            "license": "Apache-2.0",
        }
        result = resolve_source_fields(source)
        assert result["title"] == "My Document"
        assert result["author"] == "RC"
        assert result["license"] == "Apache-2.0"

    def test_orig_with_subdirectory(self):
        source = {"file": "sub/deep.pdf"}
        result = resolve_source_fields(source)
        assert result["file"] == "sub/deep.pdf"
        assert result["path"] == "sub/deep.md"

    def test_url_preserves_url(self):
        source = {"url": "https://example.com/doc.pdf"}
        result = resolve_source_fields(source)
        assert result["url"] == "https://example.com/doc.pdf"
