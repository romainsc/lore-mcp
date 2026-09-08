"""Tests for lore_mcp.preprocess. See docs/preprocessing.md."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lore_mcp.preprocess import clean_text, preprocess_file, preprocess_sources


class TestCleanText:
    """Unit tests for the clean_text function."""

    def test_strips_nul(self):
        assert "\x00" not in clean_text("hello\x00world")
        assert "helloworld" in clean_text("hello\x00world")

    def test_nfc_normalization(self):
        decomposed = "é"  # é as e + combining acute
        composed = "é"     # é as single codepoint
        result = clean_text(decomposed)
        assert result == composed

    def test_nfc_preserves_already_composed(self):
        text = "café résumé naïve"
        assert clean_text(text) == text

    def test_strips_html_div(self):
        text = "before <div>content</div> after"
        result = clean_text(text)
        assert "<div>" not in result
        assert "</div>" not in result
        assert "content" in result

    def test_strips_html_span_with_class(self):
        text = 'the <span class="highlight">word</span> here'
        result = clean_text(text)
        assert "<span" not in result
        assert "</span>" not in result
        assert "word" in result

    def test_strips_nbsp(self):
        text = "word1&nbsp;word2"
        result = clean_text(text)
        assert "&nbsp;" not in result
        assert "word1" in result
        assert "word2" in result

    def test_preserves_markdown_formatting(self):
        text = "## Heading\n\nParagraph with **bold**.\n"
        result = clean_text(text)
        assert "Heading" in result
        assert "**bold**" in result

    def test_replaces_image_with_alt(self):
        text = "![architecture diagram](img/arch.png)"
        result = clean_text(text)
        assert "img/arch.png" not in result
        assert "architecture diagram" in result

    def test_replaces_base64_image(self):
        text = "![diagram](data:image/png;base64,iVBOR...)"
        result = clean_text(text)
        assert "base64" not in result
        assert "diagram" in result

    def test_nested_brackets_in_alt(self):
        text = "![chart [2024]](chart.png)"
        result = clean_text(text)
        assert "chart [2024]" in result
        assert "chart.png" not in result

    def test_strips_heading_hashes(self):
        text = "## Authentication\n\nSome content.\n"
        result = clean_text(text)
        assert "## " not in result
        assert "Authentication" in result
        assert "Some content." in result

    def test_strips_all_heading_levels(self):
        text = "# H1\n## H2\n### H3\n#### H4\n"
        result = clean_text(text)
        assert "# " not in result
        assert "## " not in result
        assert "### " not in result
        assert "#### " not in result
        assert "H1" in result
        assert "H2" in result
        assert "H3" in result
        assert "H4" in result

    def test_heading_hash_only_at_line_start(self):
        text = "Use C# for development.\n## Heading\n"
        result = clean_text(text)
        assert "C#" in result
        assert "Heading" in result

    def test_empty_input(self):
        assert clean_text("") == ""

    def test_preserves_code_blocks(self):
        text = "```python\n# comment\nprint('hello')\n```\n"
        result = clean_text(text)
        assert "# comment" in result
        assert "print('hello')" in result

    def test_combined_cleaning(self):
        text = "é <div>hello\x00</div> ![img](x.png)\n## Title\n"
        result = clean_text(text)
        assert "é" in result
        assert "<div>" not in result
        assert "\x00" not in result
        assert "img" in result
        assert "x.png" not in result
        assert "## " not in result
        assert "Title" in result


class TestPreprocessFile:
    """Tests for single-file preprocessing."""

    def test_writes_cleaned_output(self, tmp_path):
        src = tmp_path / "input.md"
        src.write_text("## Title\n\nhello\x00world\n", encoding="utf-8")
        out = tmp_path / "output"
        out.mkdir()

        result = preprocess_file(str(src), str(out))

        output_file = out / "input.md"
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "\x00" not in content
        assert "Title" in content

    def test_preserves_filename(self, tmp_path):
        src = tmp_path / "my-doc.md"
        src.write_text("content", encoding="utf-8")
        out = tmp_path / "output"
        out.mkdir()

        preprocess_file(str(src), str(out))
        assert (out / "my-doc.md").exists()

    def test_returns_report(self, tmp_path):
        src = tmp_path / "doc.md"
        src.write_text("## Heading\n\nSome text.\n", encoding="utf-8")
        out = tmp_path / "output"
        out.mkdir()

        report = preprocess_file(str(src), str(out))
        assert report["file"] == "doc.md"
        assert "status" in report


class TestPreprocessSources:
    """Tests for manifest-driven preprocessing with --orig-dir."""

    def _write_manifest(self, path, sources):
        import yaml
        data = {"collection": "test", "level": "libre", "sources": sources}
        path.write_text(yaml.dump(data), encoding="utf-8")

    def test_orig_field_reads_from_orig_dir(self, tmp_path):
        orig = tmp_path / "orig"
        orig.mkdir()
        (orig / "raw-a.md").write_text("## Doc A\n\nContent A.\n")
        (orig / "raw-b.md").write_text("## Doc B\n\nContent B.\n")
        manifest = tmp_path / "manifest.yaml"
        self._write_manifest(manifest, [
            {"path": "a.md", "orig": "raw-a.md"},
            {"path": "b.md", "orig": "raw-b.md"},
        ])
        out = tmp_path / "output"

        reports = preprocess_sources(str(manifest), str(orig), str(out))

        assert len(reports) == 2
        assert (out / "a.md").exists()
        assert (out / "b.md").exists()
        assert all(r["status"] == "ok" for r in reports)

    def test_orig_same_as_path(self, tmp_path):
        orig = tmp_path / "orig"
        orig.mkdir()
        (orig / "doc.md").write_text("## Title\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        self._write_manifest(manifest, [{"path": "doc.md", "orig": "doc.md"}])
        out = tmp_path / "output"

        reports = preprocess_sources(str(manifest), str(orig), str(out))

        assert reports[0]["status"] == "ok"
        assert (out / "doc.md").exists()

    def test_no_orig_no_url_raises_error(self, tmp_path):
        orig = tmp_path / "orig"
        orig.mkdir()
        manifest = tmp_path / "manifest.yaml"
        self._write_manifest(manifest, [{"path": "doc.md"}])
        out = tmp_path / "output"

        reports = preprocess_sources(str(manifest), str(orig), str(out))

        assert reports[0]["status"] == "error"
        assert "no orig" in reports[0]["message"].lower()

    def test_orig_missing_file(self, tmp_path):
        orig = tmp_path / "orig"
        orig.mkdir()
        manifest = tmp_path / "manifest.yaml"
        self._write_manifest(manifest, [{"path": "doc.md", "orig": "gone.md"}])
        out = tmp_path / "output"

        reports = preprocess_sources(str(manifest), str(orig), str(out))

        assert reports[0]["status"] == "missing"

    def test_creates_output_dir(self, tmp_path):
        orig = tmp_path / "orig"
        orig.mkdir()
        (orig / "doc.md").write_text("content\n")
        manifest = tmp_path / "manifest.yaml"
        self._write_manifest(manifest, [{"path": "doc.md", "orig": "doc.md"}])
        out = tmp_path / "output"

        preprocess_sources(str(manifest), str(orig), str(out))
        assert out.exists()

    def test_preserves_subdirectory_in_path(self, tmp_path):
        orig = tmp_path / "orig"
        orig.mkdir()
        (orig / "deep.md").write_text("## Deep\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        self._write_manifest(manifest, [{"path": "sub/deep.md", "orig": "deep.md"}])
        out = tmp_path / "output"

        reports = preprocess_sources(str(manifest), str(orig), str(out))

        assert (out / "sub" / "deep.md").exists()

    def test_orig_in_subdirectory(self, tmp_path):
        orig = tmp_path / "orig"
        sub = orig / "raw"
        sub.mkdir(parents=True)
        (sub / "doc.md").write_text("## Title\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        self._write_manifest(manifest, [{"path": "doc.md", "orig": "raw/doc.md"}])
        out = tmp_path / "output"

        reports = preprocess_sources(str(manifest), str(orig), str(out))

        assert (out / "doc.md").exists()

    def test_empty_manifest(self, tmp_path):
        orig = tmp_path / "orig"
        orig.mkdir()
        manifest = tmp_path / "manifest.yaml"
        self._write_manifest(manifest, [])
        out = tmp_path / "output"

        reports = preprocess_sources(str(manifest), str(orig), str(out))
        assert reports == []

    def test_cleans_content(self, tmp_path):
        orig = tmp_path / "orig"
        orig.mkdir()
        (orig / "dirty.md").write_text(
            "## Title\n\nhello\x00 <div>html</div> ![img](x.png)\n"
        )
        manifest = tmp_path / "manifest.yaml"
        self._write_manifest(manifest, [{"path": "clean.md", "orig": "dirty.md"}])
        out = tmp_path / "output"

        preprocess_sources(str(manifest), str(orig), str(out))

        content = (out / "clean.md").read_text(encoding="utf-8")
        assert "\x00" not in content
        assert "<div>" not in content
        assert "## " not in content
        assert "Title" in content
        assert "img" in content

    def test_url_field_without_orig(self, tmp_path):
        orig = tmp_path / "orig"
        orig.mkdir()
        manifest = tmp_path / "manifest.yaml"
        self._write_manifest(manifest, [
            {"path": "doc.md", "url": "https://example.com/doc.md"},
        ])
        out = tmp_path / "output"

        reports = preprocess_sources(str(manifest), str(orig), str(out))
        assert reports[0]["status"] == "url"
        assert "fetch" in reports[0]["message"].lower()
