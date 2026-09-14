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
    import torch  # noqa: F401 — preload CUDA libs before onnxruntime
except ImportError:
    pass

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


def _convert_text_data(path: Path) -> str:
    """Convert JSON/CSV/XML to readable markdown when markitdown fails."""
    import json as _json

    content = _read_text(path)
    ext = path.suffix.lower()

    if ext == ".json":
        try:
            data = _json.loads(content)
            return _json_to_markdown(data, path.stem)
        except _json.JSONDecodeError:
            return content

    return content


def _json_to_markdown(data, title: str = "") -> str:
    """Convert JSON data to readable markdown."""
    lines = []
    if title:
        lines.append(f"# {title}\n")

    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            keys = list(data[0].keys())
            lines.append("| " + " | ".join(keys) + " |")
            lines.append("| " + " | ".join("---" for _ in keys) + " |")
            for row in data:
                vals = [str(row.get(k, ""))[:80] for k in keys]
                lines.append("| " + " | ".join(vals) + " |")
        else:
            for item in data:
                lines.append(f"- {item}")

    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                lines.append(f"\n## {key}\n")
                lines.append(_json_to_markdown(value))
            elif isinstance(value, dict):
                lines.append(f"\n## {key}\n")
                for k, v in value.items():
                    lines.append(f"- **{k}**: {v}")
            else:
                lines.append(f"- **{key}**: {value}")

    return "\n".join(lines)


_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"}

_CLASSIFY_PROMPT = (
    "What type of image is this? Answer with exactly one word: "
    "photo, chart, diagram, table, screenshot, scan, infographic, or other."
)

_CAPTION_PROMPTS = {
    "chart": (
        "Transcribe all data visible in this chart: axes labels, "
        "data series names, values, units, title, and legend entries."
    ),
    "diagram": (
        "Describe all components, connections, and labels visible "
        "in this diagram. Include text labels and relationships."
    ),
    "table": (
        "Transcribe this table into markdown format. Include all "
        "headers, rows, and cell values."
    ),
    "scan": (
        "Transcribe all text visible in this scanned document. "
        "Preserve paragraph structure and headings."
    ),
    "screenshot": (
        "Describe what this screenshot shows: application, visible "
        "UI elements, text content, and data displayed."
    ),
    "infographic": (
        "Describe all information presented in this infographic: "
        "data, labels, categories, statistics, and key messages."
    ),
}

_CAPTION_DEFAULT = (
    "Describe this image in detail: subject, scene, visible objects, "
    "text, and any information it conveys."
)


def classify_parse_result(text: str, orig_format: str) -> str:
    """Classify parse result quality.

    Returns: 'text_ok', 'empty', or 'poor'.
    """
    if not text or not text.strip():
        return "empty"

    words = text.split()
    if len(words) < 10:
        return "empty"

    alpha = sum(1 for c in text if c.isalpha())
    density = alpha / max(len(text), 1)

    if density < 0.3:
        return "poor"

    return "text_ok"


def _vlm_call(
    image_path: Path,
    prompt: str,
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
) -> str:
    """Send image + prompt to a VLM via OpenAI-compatible API."""
    import base64
    import json
    import urllib.request

    if not llm_url:
        return ""

    img_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    ext = image_path.suffix.lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "tiff": "image/tiff", "bmp": "image/bmp", "gif": "image/gif"}.get(ext, "image/png")

    url = llm_url
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"

    body = json.dumps({
        "model": llm_model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_data}"}},
            ],
        }],
        "temperature": 0.3,
        "max_tokens": 1024,
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if llm_key:
        headers["Authorization"] = f"Bearer {llm_key}"

    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""


def _caption_image(
    image_path: Path,
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
    context: str = "",
    description: str = "",
) -> str:
    """Two-step image captioning: classify type, then specialized prompt."""
    if not llm_url:
        return ""

    # Step 1: classify image type
    img_type = _vlm_call(image_path, _CLASSIFY_PROMPT, llm_url, llm_model, llm_key)
    img_type = img_type.lower().strip().rstrip(".")

    # Step 2: specialized prompt with context
    base_prompt = _CAPTION_PROMPTS.get(img_type, _CAPTION_DEFAULT)

    parts = []
    if context:
        parts.append(f"Context from surrounding text:\n{context}\n")
    if description:
        parts.append(f"Source description: {description}\n")
    parts.append(base_prompt)
    parts.append("\nWrite in English. Be factual and specific.")

    full_prompt = "\n".join(parts)
    return _vlm_call(image_path, full_prompt, llm_url, llm_model, llm_key)


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


def parse_to_markdown(
    file_path: str,
    vlm_url: str = "",
    vlm_model: str = "",
    vlm_key: str = "",
    context: str = "",
    description: str = "",
) -> str:
    """Convert a file to markdown using the appropriate backend.

    If the result is empty and a VLM is configured, generates an
    image caption instead.
    """
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
        result = doc.export_to_markdown()

        if path.suffix.lower() in _IMAGE_EXTENSIONS:
            quality = classify_parse_result(result, path.suffix)
            if quality == "empty" and vlm_url:
                caption = _caption_image(path, vlm_url, vlm_model, vlm_key,
                                         context=context, description=description)
                if caption:
                    return caption
        return result

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
            return _convert_text_data(path)
