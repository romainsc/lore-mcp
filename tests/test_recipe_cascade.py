"""Tests for recipe field cascade. See docs/studies/grooming-E12.01.md."""

import pytest
import yaml

from lore_mcp.recipe import resolve_source_fields, parse_recipe


class TestDefaultsCascade:
    """Test the defaults section with options cascade."""

    def test_defaults_applied_to_sources(self, tmp_path):
        recipe = tmp_path / "recipe.yaml"
        recipe.write_text(yaml.dump({
            "collection": "test",
            "defaults": {"lang": "fra", "license": "CC-BY-SA-4.0"},
            "sources": [
                {"file": "doc1.pdf", "title": "Doc 1"},
                {"file": "doc2.pdf", "title": "Doc 2", "lang": "eng"},
            ],
        }))
        result = parse_recipe(str(recipe))
        assert result["sources"][0]["lang"] == "fra"
        assert result["sources"][0]["license"] == "CC-BY-SA-4.0"
        assert result["sources"][1]["lang"] == "eng"
        assert result["sources"][1]["license"] == "CC-BY-SA-4.0"

    def test_options_cascade(self, tmp_path):
        recipe = tmp_path / "recipe.yaml"
        recipe.write_text(yaml.dump({
            "collection": "test",
            "defaults": {"options": {"chunk_size": 1024, "enrich": ["context", "qa"]}},
            "sources": [
                {"file": "doc1.pdf"},
                {"file": "doc2.pdf", "options": {"chunk_size": 512}},
            ],
        }))
        result = parse_recipe(str(recipe))
        assert result["sources"][0]["options"]["chunk_size"] == 1024
        assert result["sources"][0]["options"]["enrich"] == ["context", "qa"]
        assert result["sources"][1]["options"]["chunk_size"] == 512
        assert result["sources"][1]["options"]["enrich"] == ["context", "qa"]

    def test_no_defaults_unchanged(self, tmp_path):
        recipe = tmp_path / "recipe.yaml"
        recipe.write_text(yaml.dump({
            "collection": "test",
            "sources": [{"file": "doc.pdf", "lang": "eng"}],
        }))
        result = parse_recipe(str(recipe))
        assert result["sources"][0]["lang"] == "eng"
        assert "options" not in result["sources"][0]

    def test_source_overrides_default_metadata(self, tmp_path):
        recipe = tmp_path / "recipe.yaml"
        recipe.write_text(yaml.dump({
            "collection": "test",
            "defaults": {"author": "Default Author"},
            "sources": [
                {"file": "doc1.pdf"},
                {"file": "doc2.pdf", "author": "Specific Author"},
            ],
        }))
        result = parse_recipe(str(recipe))
        assert result["sources"][0]["author"] == "Default Author"
        assert result["sources"][1]["author"] == "Specific Author"

    def test_empty_options_no_key(self, tmp_path):
        recipe = tmp_path / "recipe.yaml"
        recipe.write_text(yaml.dump({
            "collection": "test",
            "defaults": {"lang": "fra"},
            "sources": [{"file": "doc.pdf"}],
        }))
        result = parse_recipe(str(recipe))
        assert "options" not in result["sources"][0]


class TestResolveSourceFields:
    """Test the field cascade: file → path generation."""

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
