"""Tests for lore_mcp.preprocess.parse. See docs/studies/grooming-E6.06.md."""

import pytest

from lore_mcp.preprocess.parse import parse_to_markdown, detect_format, FormatNotSupported


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
