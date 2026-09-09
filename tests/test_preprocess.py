"""Tests for lore_mcp.preprocess. See docs/preprocessing.md."""

import pytest
import yaml

from lore_mcp.preprocess import clean_text, preprocess_file, preprocess_sources


class TestCleanText:
    """Unit tests for the clean_text function."""

    def test_strips_nul(self):
        assert "\x00" not in clean_text("hello\x00world")
        assert "helloworld" in clean_text("hello\x00world")

    def test_nfc_normalization(self):
        decomposed = "é"  # é as e + combining acute
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

    def test_preserves_heading_hashes(self):
        text = "## Authentication\n\nSome content.\n"
        result = clean_text(text)
        assert "## Authentication" in result

    def test_preserves_all_heading_levels(self):
        text = "# H1\n## H2\n### H3\n#### H4\n"
        result = clean_text(text)
        assert "# H1" in result
        assert "## H2" in result
        assert "### H3" in result
        assert "#### H4" in result

    def test_empty_input(self):
        assert clean_text("") == ""

    def test_preserves_code_blocks(self):
        text = "```python\n# comment\nprint('hello')\n```\n"
        result = clean_text(text)
        assert "# comment" in result

    def test_combined_cleaning(self):
        text = "é <div>hello\x00</div> ![img](x.png)\n## Title\n"
        result = clean_text(text)
        assert "é" in result
        assert "<div>" not in result
        assert "\x00" not in result
        assert "img" in result
        assert "x.png" not in result
        assert "## Title" in result


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

    def test_returns_report(self, tmp_path):
        src = tmp_path / "doc.md"
        src.write_text("## Heading\n\nSome text.\n", encoding="utf-8")
        out = tmp_path / "output"
        out.mkdir()

        report = preprocess_file(str(src), str(out))
        assert report["file"] == "doc.md"
        assert report["status"] == "ok"


def _write_manifest(path, sources, collection="test", level="libre"):
    data = {"collection": collection, "level": level, "sources": sources}
    path.write_text(yaml.dump(data), encoding="utf-8")


class TestPreprocessSources:
    """Tests for manifest-driven preprocessing v2."""

    def test_orig_field_reads_and_cleans(self, tmp_path):
        orig = tmp_path / "orig"
        orig.mkdir()
        (orig / "doc.md").write_text("## Title\n\nhello\x00world\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        reports = preprocess_sources(
            str(manifest), str(tmp_path), orig_subdir="orig"
        )

        assert reports[0]["status"] == "ok"
        assert (tmp_path / "doc.md").exists()

    def test_path_generated_from_orig(self, tmp_path):
        orig = tmp_path / "raw"
        orig.mkdir()
        (orig / "guide.md").write_text("content\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "guide.md"}])

        preprocess_sources(
            str(manifest), str(tmp_path), orig_subdir="raw"
        )

        assert (tmp_path / "guide.md").exists()

    def test_explicit_path_overrides(self, tmp_path):
        (tmp_path / "doc.md").write_text("content\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md", "path": "renamed.md"}])

        preprocess_sources(str(manifest), str(tmp_path))

        assert (tmp_path / "renamed.md").exists()

    def test_prep_subdir(self, tmp_path):
        (tmp_path / "doc.md").write_text("content\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        preprocess_sources(
            str(manifest), str(tmp_path), prep_subdir="clean"
        )

        assert (tmp_path / "clean" / "doc.md").exists()

    def test_orig_and_prep_subdirs(self, tmp_path):
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        preprocess_sources(
            str(manifest), str(tmp_path),
            orig_subdir="raw", prep_subdir="clean",
        )

        assert (tmp_path / "clean" / "doc.md").exists()
        content = (tmp_path / "clean" / "doc.md").read_text()
        assert "## Title" in content

    def test_no_orig_no_url_reports_error(self, tmp_path):
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"title": "orphan"}])

        reports = preprocess_sources(str(manifest), str(tmp_path))

        assert reports[0]["status"] == "error"

    def test_missing_orig_file(self, tmp_path):
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "gone.md"}])

        reports = preprocess_sources(str(manifest), str(tmp_path))

        assert reports[0]["status"] == "missing"

    def test_url_without_local_file(self, tmp_path):
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [
            {"url": "https://example.com/doc.pdf"},
        ])

        reports = preprocess_sources(str(manifest), str(tmp_path))

        assert reports[0]["status"] == "url"

    def test_enriched_manifest_default_name(self, tmp_path):
        (tmp_path / "doc.md").write_text("---\ntitle: Hello\n---\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        preprocess_sources(str(manifest), str(tmp_path))

        prep_manifest = tmp_path / "manifest-prep.yaml"
        assert prep_manifest.exists()
        data = yaml.safe_load(prep_manifest.read_text())
        assert data["sources"][0]["orig"] == "doc.md"
        assert data["sources"][0]["path"] == "doc.md"

    def test_enriched_manifest_custom_name(self, tmp_path):
        (tmp_path / "doc.md").write_text("content\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])
        custom = tmp_path / "custom.yaml"

        preprocess_sources(
            str(manifest), str(tmp_path), manifest_out=str(custom)
        )

        assert custom.exists()

    def test_enriched_manifest_extracts_title(self, tmp_path):
        (tmp_path / "doc.md").write_text(
            "---\ntitle: My Document\nauthor: RC\nlicense: Apache-2.0\n---\n\nContent.\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        preprocess_sources(str(manifest), str(tmp_path))

        data = yaml.safe_load((tmp_path / "manifest-prep.yaml").read_text())
        src = data["sources"][0]
        assert src["title"] == "My Document"
        assert src["author"] == "RC"
        assert src["license"] == "Apache-2.0"

    def test_manifest_declared_title_wins(self, tmp_path):
        (tmp_path / "doc.md").write_text(
            "---\ntitle: From Frontmatter\n---\nContent.\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md", "title": "Override"}])

        preprocess_sources(str(manifest), str(tmp_path))

        data = yaml.safe_load((tmp_path / "manifest-prep.yaml").read_text())
        assert data["sources"][0]["title"] == "Override"

    def test_empty_manifest(self, tmp_path):
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [])

        reports = preprocess_sources(str(manifest), str(tmp_path))
        assert reports == []

    def test_preserves_collection_and_level(self, tmp_path):
        (tmp_path / "doc.md").write_text("content\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}],
                        collection="my-col", level="nda")

        preprocess_sources(str(manifest), str(tmp_path))

        data = yaml.safe_load((tmp_path / "manifest-prep.yaml").read_text())
        assert data["collection"] == "my-col"
        assert data["level"] == "nda"
