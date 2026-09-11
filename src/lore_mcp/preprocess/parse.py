"""Format conversion to markdown. See docs/studies/grooming-E6.06.md.

4-tier cascade:
1. .md → passthrough
2. .html → trafilatura (Apache 2.0)
3. .pdf/.docx/.pptx/.xlsx/.epub/images → Docling (MIT)
4. .csv/.json/.xml → markitdown (MIT)
"""

from pathlib import Path

from charset_normalizer import from_path as detect_encoding


def _read_text(path: Path) -> str:
    """Read a text file with detected encoding."""
    result = detect_encoding(path)
    best = result.best()
    if best is None:
        return path.read_text(encoding="utf-8", errors="replace")
    return str(best)

try:
    import trafilatura
    _HAVE_TRAFILATURA = True
except ImportError:
    _HAVE_TRAFILATURA = False

try:
    from docling.document_converter import DocumentConverter
    _HAVE_DOCLING = True
except ImportError:
    _HAVE_DOCLING = False

_docling_converter = None

try:
    from markitdown import MarkItDown
    _HAVE_MARKITDOWN = True
except ImportError:
    _HAVE_MARKITDOWN = False


class FormatNotSupported(ValueError):
    """Raised when file extension is not recognized."""


_FORMAT_MAP = {
    ".md": "markdown",
    ".html": "html",
    ".htm": "html",
    ".pdf": "docling",
    ".docx": "docling",
    ".pptx": "docling",
    ".xlsx": "docling",
    ".epub": "docling",
    ".png": "docling",
    ".jpg": "docling",
    ".jpeg": "docling",
    ".tiff": "docling",
    ".csv": "markitdown",
    ".json": "markitdown",
    ".xml": "markitdown",
}


def detect_format(filename: str) -> str:
    """Detect conversion backend from file extension."""
    ext = Path(filename).suffix.lower()
    if ext not in _FORMAT_MAP:
        raise FormatNotSupported(
            f"Unsupported format: {ext} ({filename})"
        )
    return _FORMAT_MAP[ext]


def parse_to_markdown(file_path: str) -> str:
    """Convert a file to markdown using the appropriate backend."""
    path = Path(file_path)
    backend = detect_format(path.name)

    if backend == "markdown":
        return _read_text(path)

    if backend == "html":
        if not _HAVE_TRAFILATURA:
            raise ImportError(
                "trafilatura is required for HTML conversion. "
                "Install: pip install lore-mcp[html]"
            )
        html = _read_text(path)
        result = trafilatura.extract(
            html,
            output_format="markdown",
            include_tables=True,
            include_links=True,
        )
        if result is None:
            return html
        return result

    if backend == "docling":
        if not _HAVE_DOCLING:
            raise ImportError(
                "docling is required for PDF/DOCX/PPTX/XLSX/EPUB conversion. "
                "Install: pip install lore-mcp[pdf]"
            )
        global _docling_converter
        if _docling_converter is None:
            _docling_converter = DocumentConverter()
        doc = _docling_converter.convert(str(path)).document
        return doc.export_to_markdown()

    if backend == "markitdown":
        if not _HAVE_MARKITDOWN:
            raise ImportError(
                "markitdown is required for CSV/JSON/XML conversion. "
                "Install: pip install lore-mcp[office]"
            )
        md = MarkItDown()
        try:
            result = md.convert(str(path))
            return result.text_content
        except UnicodeDecodeError:
            return _read_text(path)
