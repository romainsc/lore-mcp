"""Tests for lore_mcp.preprocess.parse. See docs/studies/grooming-E6.06.md."""

from unittest.mock import patch

import pytest

from lore_mcp.preprocess.parse import (
    parse_to_markdown, detect_format, FormatNotSupported,
    caption_inline_images, unload_docling, classify_parse_result,
    IMAGE_EXTENSIONS,
)


class TestDetectFormat:
    """Format detection by file extension."""

    def test_markdown(self):
        assert detect_format("doc.md") == "markdown"

    def test_html(self):
        assert detect_format("page.html") == "html"
        assert detect_format("page.htm") == "html"

    def test_pdf(self):
        assert detect_format("paper.pdf") == "docling"

    def test_docx(self):
        assert detect_format("report.docx") == "docling"

    def test_pptx(self):
        assert detect_format("slides.pptx") == "docling"

    def test_xlsx(self):
        assert detect_format("data.xlsx") == "docling"

    def test_epub(self):
        assert detect_format("book.epub") == "docling"

    def test_image_formats(self):
        for ext in ("png", "jpg", "jpeg", "tiff"):
            assert detect_format(f"img.{ext}") == "docling"

    def test_csv(self):
        assert detect_format("data.csv") == "markitdown"

    def test_json(self):
        assert detect_format("config.json") == "markitdown"

    def test_xml(self):
        assert detect_format("feed.xml") == "markitdown"

    def test_unknown_raises(self):
        with pytest.raises(FormatNotSupported):
            detect_format("file.xyz")

    def test_case_insensitive(self):
        assert detect_format("DOC.PDF") == "docling"
        assert detect_format("page.HTML") == "html"


class TestParseMarkdown:
    """Markdown passthrough — returns content as-is."""

    def test_passthrough(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("## Title\n\nContent.\n")

        result = parse_to_markdown(str(f))
        assert "Title" in result
        assert "Content." in result

    def test_reads_utf8(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("Café résumé\n", encoding="utf-8")

        result = parse_to_markdown(str(f))
        assert "Café" in result


class TestParseHTML:
    """HTML conversion via trafilatura."""

    def test_extracts_article_content(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("""
        <html><head><title>Test</title></head>
        <body>
        <nav>Navigation menu</nav>
        <article>
        <h1>Main Title</h1>
        <p>This is the main article content with enough
        text to be considered substantial by trafilatura
        extraction heuristics which need a minimum amount
        of content to work properly.</p>
        </article>
        <footer>Footer stuff</footer>
        </body></html>
        """, encoding="utf-8")

        result = parse_to_markdown(str(f))
        assert "Main Title" in result
        assert "main article content" in result

    def test_strips_html_tags(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("""
        <html><body>
        <article>
        <p>This is a paragraph with <b>bold</b> text and
        enough content to pass trafilatura minimum length
        requirements for extraction.</p>
        </article>
        </body></html>
        """, encoding="utf-8")

        result = parse_to_markdown(str(f))
        assert "<p>" not in result
        assert "<b>" not in result

    def test_missing_trafilatura_raises(self, tmp_path, monkeypatch):
        f = tmp_path / "page.html"
        f.write_text("<html><body><p>Content</p></body></html>")

        import lore_mcp.preprocess.parse as parse_mod
        monkeypatch.setattr(parse_mod, "_HAVE_TRAFILATURA", False)

        with pytest.raises(ImportError, match="trafilatura"):
            parse_to_markdown(str(f))


class TestParsePDF:
    """PDF conversion via Docling."""

    def test_missing_docling_raises(self, tmp_path, monkeypatch):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4 fake")

        import lore_mcp.preprocess.parse as parse_mod
        monkeypatch.setattr(parse_mod, "_HAVE_DOCLING", False)

        with pytest.raises(ImportError, match="docling"):
            parse_to_markdown(str(f))


class TestParseCSV:
    """CSV/data conversion via markitdown."""

    def test_missing_markitdown_raises(self, tmp_path, monkeypatch):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n1,2,3\n")

        import lore_mcp.preprocess.parse as parse_mod
        monkeypatch.setattr(parse_mod, "_HAVE_MARKITDOWN", False)

        with pytest.raises(ImportError, match="markitdown"):
            parse_to_markdown(str(f))


class TestUnloadDocling:

    def test_unload_clears_converter(self, monkeypatch):
        import lore_mcp.preprocess.parse as parse_mod
        monkeypatch.setattr(parse_mod, "_docling_converter", "fake")
        unload_docling()
        assert parse_mod._docling_converter is None


class TestImageExtensions:

    def test_common_extensions_present(self):
        for ext in (".png", ".jpg", ".jpeg", ".tiff"):
            assert ext in IMAGE_EXTENSIONS


class TestCaptionInlineImages:

    _BIG_B64 = "A" * 14000  # > _MIN_IMAGE_SIZE_B64

    def test_no_vlm_returns_unchanged(self):
        text = "![](data:image/png;base64,abc123)"
        assert caption_inline_images(text, "", "", "") == text

    def test_existing_alt_text_used_as_context(self):
        """Real alt text is passed as context to VLM, not skipped."""
        text = f"![architecture diagram](data:image/png;base64,{self._BIG_B64})"
        with patch("lore_mcp.preprocess.parse._vlm_api_call",
                   side_effect=["diagram", "Network architecture with 3 layers"]) as mock:
            result = caption_inline_images(text, "http://x", "m", "")
        assert "Network architecture" in result
        classify_prompt = mock.call_args_list[0][0][2]
        assert "architecture diagram" in classify_prompt

    def test_empty_alt_replaced_by_vlm(self):
        text = f"Some text\n![](data:image/png;base64,{self._BIG_B64})\nMore text"
        with patch("lore_mcp.preprocess.parse._vlm_api_call",
                   side_effect=["photo", "A red circle"]):
            result = caption_inline_images(text, "http://vlm:8090/v1", "model", "")
        assert "![A red circle]" in result

    def test_brackets_in_caption_escaped(self):
        text = f"![](data:image/png;base64,{self._BIG_B64})"
        with patch("lore_mcp.preprocess.parse._vlm_api_call",
                   side_effect=["photo", "A [test] image"]):
            result = caption_inline_images(text, "http://vlm:8090/v1", "model", "")
        assert "![A (test) image]" in result

    def test_multiple_images_captioned(self):
        b1 = "B" * 14000
        b2 = "C" * 14000
        text = f"![](data:image/png;base64,{b1})\ntext\n![](data:image/jpeg;base64,{b2})"
        call_count = 0
        def mock_vlm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:
                return "photo"
            return f"Caption {call_count // 2}"
        with patch("lore_mcp.preprocess.parse._vlm_api_call", side_effect=mock_vlm):
            result = caption_inline_images(text, "http://vlm:8090/v1", "model", "")
        assert "![Caption 1]" in result
        assert "![Caption 2]" in result

    def test_small_images_skipped(self):
        text = "![](data:image/png;base64,tiny)"
        with patch("lore_mcp.preprocess.parse._vlm_api_call") as mock:
            result = caption_inline_images(text, "http://vlm:8090/v1", "model", "")
        mock.assert_not_called()
        assert result == text
