"""Format conversion to markdown. See docs/studies/grooming-E6.06.md.

4-tier cascade:
1. .md → passthrough
2. .html → trafilatura (Apache 2.0)
3. .pdf/.docx/.pptx/.xlsx/.epub/images → Docling (MIT)
4. .csv/.json/.xml → markitdown (MIT)
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

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


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"}


def unload_docling() -> None:
    """Free the cached Docling converter."""
    global _docling_converter
    _docling_converter = None

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


def _vlm_api_call(
    b64_data: str,
    mime_type: str,
    prompt: str,
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
) -> str:
    """Send base64 image + prompt to a VLM via OpenAI-compatible API."""
    import json
    import urllib.request

    if not llm_url:
        return ""

    url = llm_url
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"

    body = json.dumps({
        "model": llm_model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}},
            ],
        }],
        "temperature": 0.3,
        "max_tokens": 1024,
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if llm_key:
        headers["Authorization"] = f"Bearer {llm_key}"

    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip()


def _vlm_call(
    image_path: Path,
    prompt: str,
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
) -> str:
    """Send image file + prompt to a VLM via OpenAI-compatible API."""
    import base64

    if not llm_url:
        return ""

    img_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    ext = image_path.suffix.lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "tiff": "image/tiff", "bmp": "image/bmp", "gif": "image/gif"}.get(ext, "image/png")

    return _vlm_api_call(img_data, mime, prompt, llm_url, llm_model, llm_key)


def caption_image(
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


_INLINE_IMAGE_RE = re.compile(
    r"!\[([^\]]*)\]\((data:image/([^;]+);base64,([A-Za-z0-9+/=\s]+))\)"
)

_GENERIC_ALT = {"image", "figure", "picture", "img", "photo"}


_MIN_IMAGE_SIZE_B64 = 13000  # ~10KB raw ≈ 13KB base64


def _b64_hash(b64_data: str) -> str:
    """Hash base64 image data for dedup."""
    import hashlib
    return hashlib.md5(b64_data[:2000].encode()).hexdigest()


def caption_inline_images(
    text: str,
    vlm_url: str,
    vlm_model: str,
    vlm_key: str = "",
    context: str = "",
    description: str = "",
) -> str:
    """Replace inline base64 images with VLM-generated alt text.

    Two-step: classify image type, then use specialized prompt.
    Skips images <10KB (icons/logos), dedup by content hash,
    circuit breaker after 3 consecutive failures.
    """
    if not vlm_url:
        return text

    caption_cache = {}
    consecutive_failures = 0
    stats = {"captioned": 0, "skipped_small": 0, "skipped_dedup": 0,
             "skipped_alt": 0, "failed": 0}

    def _replace(match):
        nonlocal consecutive_failures
        alt = match.group(1)
        data_url = match.group(2)
        mime_subtype = match.group(3)
        b64_data = match.group(4).replace("\n", "").replace(" ", "")

        if alt.strip() and alt.strip().lower() not in _GENERIC_ALT:
            stats["skipped_alt"] += 1
            return match.group(0)

        if len(b64_data) < _MIN_IMAGE_SIZE_B64:
            stats["skipped_small"] += 1
            return match.group(0)

        if consecutive_failures >= 3:
            stats["failed"] += 1
            return match.group(0)

        img_hash = _b64_hash(b64_data)
        if img_hash in caption_cache:
            stats["skipped_dedup"] += 1
            cached = caption_cache[img_hash]
            return f"![{cached}]({data_url})"

        mime = f"image/{mime_subtype}"

        try:
            img_type = _vlm_api_call(
                b64_data, mime, _CLASSIFY_PROMPT, vlm_url, vlm_model, vlm_key
            )
            img_type = img_type.lower().strip().rstrip(".")

            base_prompt = _CAPTION_PROMPTS.get(img_type, _CAPTION_DEFAULT)
            parts = []
            if context:
                parts.append(f"Context from surrounding text:\n{context}\n")
            if description:
                parts.append(f"Source description: {description}\n")
            parts.append(base_prompt)
            parts.append("\nWrite in English. Be factual and specific.")
            full_prompt = "\n".join(parts)

            caption = _vlm_api_call(b64_data, mime, full_prompt, vlm_url, vlm_model, vlm_key)
        except Exception as e:
            consecutive_failures += 1
            stats["failed"] += 1
            logger.warning("VLM caption failed (%d/3): %s", consecutive_failures, e)
            return match.group(0)

        consecutive_failures = 0
        if caption:
            caption = caption.replace("[", "(").replace("]", ")")
            caption_cache[img_hash] = caption
            stats["captioned"] += 1
            return f"![{caption}]({data_url})"
        return match.group(0)

    result = _INLINE_IMAGE_RE.sub(_replace, text)
    if any(v > 0 for v in stats.values()):
        logger.info("Inline captions: %s", stats)
    return result


def _reorder_columns(doc) -> None:
    """Reorder document body children by column layout (left→right, top→bottom).

    Operates on the Docling document object in-place before export_to_markdown().
    Only useful for OCR'd images where reading order is wrong.
    """
    if not hasattr(doc, 'body') or doc.body is None or not doc.body.children:
        return

    indexed = []
    for ref in doc.body.children:
        cref = ref.cref if hasattr(ref, 'cref') else str(ref)
        parts = cref.split('/')
        if len(parts) >= 3 and parts[1] == 'texts':
            try:
                idx = int(parts[2])
                item = doc.texts[idx]
                if item.prov:
                    bbox = item.prov[0].bbox
                    indexed.append((ref, bbox.l, bbox.t))
                    continue
            except (IndexError, ValueError):
                pass
        indexed.append((ref, 0, 0))

    if not indexed:
        return

    xs = sorted(set(x for _, x, _ in indexed if x > 0))
    if len(xs) < 2:
        return

    columns = []
    current = [xs[0]]
    for x in xs[1:]:
        if x - current[-1] > 50:
            columns.append(current)
            current = [x]
        else:
            current.append(x)
    columns.append(current)

    if len(columns) < 2:
        return

    def _col_index(x):
        for i, col in enumerate(columns):
            if col[0] - 30 <= x <= col[-1] + 30:
                return i
        return 0

    doc.body.children = [
        ref for ref, _, _ in sorted(
            indexed,
            key=lambda t: (_col_index(t[1]), -t[2]),
        )
    ]


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
        from docling_core.types.doc.base import ImageRefMode
        doc = _docling_converter.convert(str(path)).document
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            _reorder_columns(doc)
        result = doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)

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


