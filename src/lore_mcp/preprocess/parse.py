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

_CLASSIFY_PROMPT_BASE = (
    "What type of image is this? Answer with exactly one word: "
    "photo, chart, diagram, table, screenshot, scan, infographic, "
    "slide, timeline, comic, or other."
)


def _build_classify_prompt(ocr_text: str = "") -> str:
    """Build classification prompt, optionally with OCR context."""
    if not ocr_text:
        return _CLASSIFY_PROMPT_BASE
    return (
        f"OCR extracted this text from the image:\n{ocr_text}\n\n"
        f"{_CLASSIFY_PROMPT_BASE}"
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
    "slide": (
        "Describe this presentation slide: headings, bullet points, "
        "highlighted or emphasized elements, layout structure, and "
        "colors used for emphasis."
    ),
    "timeline": (
        "Describe this timeline: milestones, dates, stages, sequence "
        "of events, and relationships between steps."
    ),
    "comic": (
        "Describe each panel of this comic or illustration: characters, "
        "dialogue, actions, and narrative sequence."
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
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip()


_VLM_MAX_PIXELS = 2048


def _resize_image_bytes(img_bytes: bytes, max_px: int = _VLM_MAX_PIXELS) -> tuple[bytes, str]:
    """Resize image if larger than max_px on longest edge. Returns (bytes, mime)."""
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(img_bytes))
    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif",
            "TIFF": "image/tiff", "BMP": "image/bmp"}.get(img.format, "image/png")
    fmt = img.format or "PNG"

    w, h = img.size
    if max(w, h) <= max_px:
        return img_bytes, mime

    scale = max_px / max(w, h)
    new_size = (int(w * scale), int(h * scale))
    img = img.resize(new_size, Image.LANCZOS)
    logger.info("Resized %dx%d → %dx%d for VLM", w, h, *new_size)

    buf = io.BytesIO()
    if fmt == "JPEG":
        img.save(buf, format="JPEG", quality=85)
    else:
        img.save(buf, format="PNG")
        mime = "image/png"
    return buf.getvalue(), mime


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
    ocr_text: str = "",
    alt_text: str = "",
) -> str:
    """Caption a standalone image. See design-captioning-pipeline.md.

    OCR-first: ocr_text enriches classify and caption prompts.
    Alt text enriches prompts (never skip).
    """
    if not llm_url:
        return ""

    # Step 1: classify with OCR + alt text context
    classify_ctx = ""
    if alt_text:
        classify_ctx += f"Alt text: {alt_text}\n"
    if ocr_text:
        classify_ctx += ocr_text
    classify_prompt = _build_classify_prompt(classify_ctx)
    img_type = _vlm_call(image_path, classify_prompt, llm_url, llm_model, llm_key)
    img_type = img_type.lower().strip().rstrip(".")

    # Step 2: caption with OCR as reference
    base_prompt = _CAPTION_PROMPTS.get(img_type, _CAPTION_DEFAULT)

    parts = []
    if context:
        parts.append(f"Context from surrounding text:\n{context}\n")
    if description:
        parts.append(f"Source description: {description}\n")
    if alt_text:
        parts.append(f"Original alt text: {alt_text}\n")
    if ocr_text:
        parts.append(f"OCR extracted this text from the image:\n---\n{ocr_text}\n---\n")
        parts.append(f"Image type: {img_type}. {base_prompt}")
        parts.append(
            "Use the OCR text as reference for printed text. "
            "Produce a unified description that positions the "
            "text in its visual context. Add any text the OCR "
            "may have missed (stylized, handwritten, embedded "
            "in graphics). Describe layout, colors, highlighting. "
            "Do NOT comment on the OCR quality or accuracy. "
            "Do NOT produce meta-analysis. Only describe the image."
        )
    else:
        parts.append(base_prompt)
    parts.append("\nWrite in English. Be factual and specific.")

    full_prompt = "\n".join(parts)
    result = _vlm_call(image_path, full_prompt, llm_url, llm_model, llm_key)
    return _clean_vlm_output(result)


_INLINE_IMAGE_RE = re.compile(
    r"!\[([^\]]*)\]\((data:image/([^;]+);base64,([A-Za-z0-9+/=\s]+))\)"
)

_GENERIC_ALT = {"image", "figure", "picture", "img", "photo"}

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


_MIN_IMAGE_SIZE_B64 = 13000  # ~10KB raw ≈ 13KB base64


def _b64_hash(b64_data: str) -> str:
    """Hash base64 image data for dedup."""
    import hashlib
    return hashlib.md5(b64_data[:2000].encode()).hexdigest()


def _ocr_from_b64(b64_data: str) -> str:
    """Run OCR on a base64-encoded image, return extracted text."""
    import base64
    try:
        from rapidocr import RapidOCR
    except ImportError:
        return ""
    try:
        img_bytes = base64.b64decode(b64_data)
        engine = RapidOCR()
        result = engine(img_bytes)
        if result and result.txts:
            return "\n".join(result.txts)
    except Exception:
        pass
    return ""


def caption_inline_images(
    text: str,
    vlm_url: str,
    vlm_model: str,
    vlm_key: str = "",
    context: str = "",
    description: str = "",
    on_progress=None,
    ocr_cache: dict | None = None,
) -> str:
    """Replace inline base64 images with VLM-generated alt text.

    Iterates images one by one (finditer). Skips images <10KB,
    dedup by content hash, circuit breaker after 5 consecutive
    failures. Calls on_progress(text_so_far) after each image
    for progressive output. ocr_cache shared across models.
    """
    if not vlm_url:
        return text

    if ocr_cache is None:
        ocr_cache = {}
    caption_cache = {}
    consecutive_failures = 0
    stats = {"captioned": 0, "skipped_small": 0, "skipped_dedup": 0,
             "failed": 0, "circuit_break": 0}

    matches = list(_INLINE_IMAGE_RE.finditer(text))
    if not matches:
        return text

    logger.info("Found %d inline images to process", len(matches))
    result_parts = []
    last_end = 0

    for img_idx, match in enumerate(matches, 1):
        result_parts.append(text[last_end:match.start()])
        last_end = match.end()

        alt = match.group(1)
        data_url = match.group(2)
        mime_subtype = match.group(3)
        b64_data = match.group(4).replace("\n", "").replace(" ", "")
        b64_kb = len(b64_data) // 1024

        real_alt = ""
        if alt.strip() and alt.strip().lower() not in _GENERIC_ALT:
            real_alt = alt.strip()

        if len(b64_data) < _MIN_IMAGE_SIZE_B64:
            stats["skipped_small"] += 1
            logger.debug("[%d/%d] skip (small: %dKB)", img_idx, len(matches), b64_kb)
            result_parts.append(match.group(0))
            continue

        if consecutive_failures >= 5:
            stats["circuit_break"] += 1
            logger.debug("[%d/%d] skip (circuit breaker)", img_idx, len(matches))
            result_parts.append(match.group(0))
            continue

        img_hash = _b64_hash(b64_data)
        if img_hash in caption_cache:
            stats["skipped_dedup"] += 1
            cached = caption_cache[img_hash]
            logger.debug("[%d/%d] dedup hit (%dKB)", img_idx, len(matches), b64_kb)
            result_parts.append(f"![{cached}]({data_url})")
            continue

        mime = f"image/{mime_subtype}"

        # Step 1: OCR — extract text faithfully (cached across models)
        if img_hash in ocr_cache:
            ocr_text = ocr_cache[img_hash]
        else:
            ocr_text = _ocr_from_b64(b64_data)
            ocr_cache[img_hash] = ocr_text
            if ocr_text:
                logger.info("[%d/%d] OCR extracted %d chars (%dKB)", img_idx, len(matches), len(ocr_text), b64_kb)

        # Step 2: VLM — classify and describe visual structure
        logger.info("[%d/%d] captioning (%dKB, hash=%s)", img_idx, len(matches), b64_kb, img_hash[:8])

        try:
            classify_ctx = ocr_text
            if real_alt:
                classify_ctx = f"Alt text: {real_alt}\n{ocr_text}" if ocr_text else f"Alt text: {real_alt}"
            classify_prompt = _build_classify_prompt(classify_ctx)
            img_type = _vlm_api_call(
                b64_data, mime, classify_prompt, vlm_url, vlm_model, vlm_key
            )
            img_type = img_type.lower().strip().rstrip(".")

            base_prompt = _CAPTION_PROMPTS.get(img_type, _CAPTION_DEFAULT)
            parts = []
            if context:
                parts.append(f"Context from surrounding text:\n{context}\n")
            if description:
                parts.append(f"Source description: {description}\n")
            if real_alt:
                parts.append(f"Original alt text: {real_alt}\n")
            if ocr_text:
                parts.append(f"OCR extracted this text from the image:\n---\n{ocr_text}\n---\n")
                parts.append(f"Image type: {img_type}. {base_prompt}")
                parts.append(
                    "Use the OCR text as reference for printed text. "
                    "Produce a unified description that positions the "
                    "text in its visual context. Add any text the OCR "
                    "may have missed (stylized, handwritten, embedded "
                    "in graphics). Describe layout, colors, highlighting. "
                    "Do NOT comment on the OCR quality or accuracy. "
                    "Do NOT produce meta-analysis. Only describe the image."
                )
            else:
                parts.append(base_prompt)
            parts.append("\nWrite in English. Be factual and specific.")
            full_prompt = "\n".join(parts)

            caption = _vlm_api_call(b64_data, mime, full_prompt, vlm_url, vlm_model, vlm_key)
            caption = _clean_vlm_output(caption)
        except Exception as e:
            consecutive_failures += 1
            stats["failed"] += 1
            logger.warning("[%d/%d] VLM failed (%d/5, %dKB, hash=%s): %s",
                           img_idx, len(matches), consecutive_failures, b64_kb, img_hash[:8], e)
            if ocr_text:
                caption_cache[img_hash] = ocr_text
                stats["captioned"] += 1
                result_parts.append(f"![{ocr_text.replace('[', '(').replace(']', ')')}]({data_url})")
            else:
                result_parts.append(match.group(0))
            continue

        consecutive_failures = 0
        # VLM produces unified description with OCR text in context
        combined = caption or ocr_text or ""

        if combined:
            combined = combined.replace("[", "(").replace("]", ")")
            caption_cache[img_hash] = combined
            stats["captioned"] += 1
            logger.info("[%d/%d] captioned: %s", img_idx, len(matches), combined[:60])
            result_parts.append(f"![{combined}]({data_url})")
        else:
            result_parts.append(match.group(0))

        if on_progress:
            on_progress("".join(result_parts) + text[last_end:])

    result_parts.append(text[last_end:])
    logger.info("Inline captions done: %s", stats)
    return "".join(result_parts)


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


def judge_captions(
    ocr_text: str,
    alt_text: str,
    captions: dict[str, str],
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
) -> str:
    """Select the best caption by asking judge LLM to pick by name.

    The judge selects a candidate label (not reproduce text).
    The winning text is retrieved from the captions dict.
    """
    import json
    import urllib.request

    if not llm_url or not captions:
        return next((v for v in captions.values() if v), "")

    if len(captions) == 1:
        return next(iter(captions.values()))

    parts = [
        "You are evaluating image descriptions from multiple sources.",
        "Pick the BEST candidate. Criteria:",
        "- Completeness: preserves all content from the source",
        "- Faithfulness: no hallucinated or incorrect details",
        "- Language: prefer the source language if content is in that language",
        "- Structure: clear, well-organized for search indexing",
        "",
        "Candidates:",
    ]
    for name, caption in captions.items():
        preview = caption[:2000]
        if len(caption) > 2000:
            preview += f"... [{len(caption)} chars total]"
        parts.append(f"--- {name} ---\n{preview}\n")

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


