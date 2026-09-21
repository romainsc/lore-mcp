"""Format conversion to markdown. See docs/studies/grooming-E6.06.md.

4-tier cascade:
1. .md → passthrough
2. .html → trafilatura (Apache 2.0)
3. .pdf/.docx/.pptx/.xlsx/.epub/images → Docling (MIT)
4. .csv/.json/.xml → markitdown (MIT)

Docling handles picture description natively via API when configured.
See docs/studies/design-architecture-refonte-docling.md.
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
    from docling.document_converter import DocumentConverter, FormatOption
    _HAVE_DOCLING = True
except ImportError:
    _HAVE_DOCLING = False

_docling_converter = None
_docling_caption_url = ""

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


def configure_docling_caption(api_url: str = "", model: str = "",
                               timeout: int = 180) -> None:
    """Configure Docling to use a remote VLM for picture description."""
    global _docling_converter, _docling_caption_url
    _docling_converter = None
    _docling_caption_url = api_url


def _get_docling_converter(caption_api_url: str = "",
                           caption_model: str = "",
                           caption_timeout: int = 180):
    """Get or create the Docling converter with optional captioning."""
    global _docling_converter

    if _docling_converter is not None:
        return _docling_converter

    if caption_api_url:
        try:
            from docling.datamodel.pipeline_options import (
                PdfPipelineOptions,
                PictureDescriptionApiOptions,
            )
            from docling.datamodel.base_models import InputFormat
            from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
            from docling.backend.image_backend import ImageDocumentBackend
            from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend

            opts = PdfPipelineOptions()
            opts.do_picture_description = True
            opts.generate_picture_images = True
            opts.enable_remote_services = True

            api_opts = PictureDescriptionApiOptions(
                url=caption_api_url,
                params={"model": caption_model} if caption_model else {},
                prompt=(
                    "Describe this image in detail: subject, scene, "
                    "visible objects, text, and any information it conveys."
                ),
                timeout=caption_timeout,
            )
            opts.picture_description_options = api_opts
            logger.info("Docling captioning via %s", caption_api_url)

            _docling_converter = DocumentConverter(
                format_options={
                    InputFormat.IMAGE: FormatOption(
                        pipeline_options=opts,
                        pipeline_cls=StandardPdfPipeline,
                        backend=ImageDocumentBackend,
                    ),
                    InputFormat.PDF: FormatOption(
                        pipeline_options=opts,
                        pipeline_cls=StandardPdfPipeline,
                        backend=DoclingParseV4DocumentBackend,
                    ),
                }
            )
        except (ImportError, TypeError, Exception) as e:
            logger.warning("Docling captioning config failed (%s), using default", e)
            _docling_converter = DocumentConverter()
    else:
        _docling_converter = DocumentConverter()

    return _docling_converter


def unload_docling() -> None:
    """Free the cached Docling converter and release GPU VRAM."""
    global _docling_converter
    _docling_converter = None
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


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


# ── VLM API for phase 2 additional models ───────────────────

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

    from lore_mcp.preprocess.service import _log_vram
    payload_kb = len(b64_data) // 1024
    logger.debug("VLM call: %s payload=%dKB mime=%s prompt=%d chars",
                 llm_url.split("/")[2], payload_kb, mime_type, len(prompt))
    _log_vram()

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
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")[:500]
        _log_vram()
        logger.error("VLM HTTP %d: %s", e.code, error_body)
        raise


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


def _log_image_info(image_path: Path) -> None:
    """Log image dimensions and mode for diagnostic."""
    try:
        from PIL import Image
        img = Image.open(image_path)
        logger.debug("Image: %s %dx%d mode=%s size=%dKB",
                      image_path.name, img.width, img.height, img.mode,
                      image_path.stat().st_size // 1024)
    except Exception:
        pass


_CAPTION_DEFAULT = (
    "Describe this image in detail: subject, scene, visible objects, "
    "text, and any information it conveys."
)


def caption_image(
    image_path: Path,
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
    context: str = "",
    description: str = "",
) -> str:
    """Caption a standalone image for phase 2 additional models."""
    if not llm_url:
        return ""

    _log_image_info(image_path)

    parts = []
    if context:
        parts.append(f"Context from surrounding text:\n{context}\n")
    if description:
        parts.append(f"Source description: {description}\n")
    parts.append(_CAPTION_DEFAULT)
    parts.append("\nWrite in English. Be factual and specific.")

    full_prompt = "\n".join(parts)
    return _vlm_call(image_path, full_prompt, llm_url, llm_model, llm_key)


_VLM_META_RE = re.compile(
    r"(?:^|\. )"
    r"(?:The OCR (?:text |has )|"
    r"[Ii]t(?:'s| is) worth noting|"
    r"[Ii]t should be noted|"
    r"[Nn]ote that the OCR|"
    r"Overall,? the (?:comic|slide|screenshot|image|chart|infographic)|"
    r"In (?:summary|conclusion),? the|"
    r"Some words may be slightly|"
    r"The absence of)"
    r"[^.]*\.",
    re.MULTILINE,
)


def _clean_vlm_output(text: str) -> str:
    """Remove VLM meta-commentary about OCR quality and generic summaries."""
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        cleaned = _VLM_META_RE.sub("", line).strip()
        if cleaned:
            cleaned_lines.append(cleaned)
    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# ── Column reorder for OCR'd images ─────────────────────────

def _reorder_columns(doc) -> None:
    """Reorder document body children by column layout (left→right, top→bottom)."""
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


# ── Judge for multi-model selection ─────────────────────────

def judge_captions(
    ocr_text: str,
    alt_text: str,
    captions: dict[str, str],
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
) -> str:
    """Select the best caption by asking judge LLM to pick by name."""
    import json
    import urllib.request

    if not llm_url or not captions:
        return next((v for v in captions.values() if v), "")

    if len(captions) == 1:
        return next(iter(captions.values()))

    parts = [
        "You are evaluating image descriptions from multiple sources.",
        "Pick the BEST candidate. Criteria (in priority order):",
        "1. No repetition: reject any candidate that contains "
        "repeated text blocks or loops",
        "2. Completeness: the candidate that preserves the most "
        "content from the source wins",
        "3. Source language: prefer candidates in the original "
        "language of the document (do not prefer a translation "
        "over the original)",
        "4. Faithfulness: no hallucinated or fabricated content",
        "5. Structure: clear, well-organized for search indexing",
        "",
        "Candidates:",
    ]
    for name, caption in captions.items():
        char_count = len(caption)
        preview = caption[:2000]
        if char_count > 2000:
            preview += f"... [{char_count} chars total]"
        parts.append(f"--- {name} ({char_count} chars) ---\n{preview}\n")

    parts.append(
        "Reply with ONLY the candidate name "
        f"(one of: {', '.join(captions.keys())}) "
        "and a one-sentence rationale. "
        "Do NOT reproduce the candidate text."
    )
    prompt = "\n".join(parts)

    url = llm_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"

    body = json.dumps({
        "model": llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 200,
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if llm_key:
        headers["Authorization"] = f"Bearer {llm_key}"

    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    answer = data["choices"][0]["message"]["content"].strip().lower()
    logger.info("Judge selected: %s", answer)

    for name in captions:
        if name.lower() in answer:
            return captions[name]

    return next(iter(captions.values()))


# ── Format detection and parsing ────────────────────────────

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


def parse_to_markdown(file_path: str, caption_api_url: str = "",
                       caption_model: str = "",
                       caption_timeout: int = 180) -> str:
    """Convert a file to markdown using the appropriate backend.

    If caption_api_url is provided, Docling will caption images
    via the remote VLM API during parsing.
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
        converter = _get_docling_converter(
            caption_api_url=caption_api_url,
            caption_model=caption_model,
            caption_timeout=caption_timeout,
        )
        from docling_core.types.doc.base import ImageRefMode
        doc = converter.convert(str(path)).document
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
