"""Format conversion to markdown. See docs/studies/grooming-E6.06.md.

4-tier cascade:
1. .md → passthrough
2. .html → trafilatura (Apache 2.0)
3. .pdf/.docx/.pptx/.xlsx/.epub/images → Docling (MIT)
4. .csv/.json/.xml → markitdown (MIT)

Docling handles picture description natively via API.
Multi-model: parse once → save JSON → caption N times.
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
    """Classify parse result quality. Returns: 'text_ok', 'empty', or 'poor'."""
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


# ── Docling-native captioning ────────────────────────────────

def caption_with_docling(doc_json_path: str, api_url: str, model_name: str,
                          prompt: str = "", timeout: int = 180) -> str:
    """Load a serialized Docling document, apply captioning via API, return markdown.

    Parse-once, caption-N: the document was parsed and saved as JSON
    in phase 1. This function loads it, applies picture description
    via a remote VLM API, and exports to markdown.
    """
    from docling_core.types.doc.document import DoclingDocument
    from docling_core.types.doc.base import ImageRefMode
    from docling.models.stages.picture_description.picture_description_api_model import PictureDescriptionApiModel
    from docling.datamodel.pipeline_options import PictureDescriptionApiOptions
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import ItemAndImageEnrichmentElement

    doc = DoclingDocument.load_from_json(doc_json_path)

    if not doc.pictures:
        return doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)

    elements = []
    for pic in doc.pictures:
        if pic.image and pic.image.pil_image:
            elements.append(ItemAndImageEnrichmentElement(item=pic, image=pic.image.pil_image))

    if not elements:
        return doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)

    url = api_url
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"

    opts = PictureDescriptionApiOptions(
        url=url,
        params={"model": model_name} if model_name else {},
        prompt=prompt or (
            "Describe this image in detail: subject, scene, "
            "visible objects, text, and any information it conveys."
        ),
        timeout=timeout,
    )

    caption_model = PictureDescriptionApiModel(
        enabled=True,
        enable_remote_services=True,
        artifacts_path=None,
        options=opts,
        accelerator_options=AcceleratorOptions(),
    )

    logger.info("Captioning %d images via %s (%s)", len(elements), model_name, api_url)
    list(caption_model(doc, elements))

    return doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)


# ── Standalone image captioning (E12.45) ────────────────────

def caption_standalone_image(image_path: str, api_url: str, model_name: str,
                              prompt: str = "", timeout: int = 180) -> str:
    """Caption a standalone image via VLM API. Fallback when Docling produces empty output."""
    import base64
    import json as _json
    import urllib.request

    img_bytes = Path(image_path).read_bytes()
    b64 = base64.b64encode(img_bytes).decode("ascii")

    suffix = Path(image_path).suffix.lower()
    media_type = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".tiff": "image/tiff", ".bmp": "image/bmp", ".gif": "image/gif",
    }.get(suffix, "image/png")

    url = api_url
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"

    caption_prompt = prompt or (
        "Describe this image in detail: subject, scene, "
        "visible objects, text, and any information it conveys."
    )

    payload = _json.dumps({
        "model": model_name,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {
                    "url": f"data:{media_type};base64,{b64}",
                }},
                {"type": "text", "text": caption_prompt},
            ],
        }],
        "max_tokens": 1024,
    }).encode()

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
    )

    logger.info("Standalone image captioning via %s (%s)", model_name, api_url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = _json.loads(resp.read())

    description = result["choices"][0]["message"]["content"]
    title = Path(image_path).stem.replace("-", " ").replace("_", " ")
    return f"# {title}\n\n{description}\n"


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

# ── Audio transcription (E12.48) ─────────────────────────────

def _to_iso639_1(code: str) -> str:
    """Convert any language code to ISO 639-1."""
    if len(code) == 2:
        return code
    from langcodes import Language
    return Language.get(code).language


def _get_audio_duration(path: str) -> float:
    """Get audio duration in seconds via ffprobe."""
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 0.0
    except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
        return 0.0


def _format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def transcribe_audio(audio_path: str, api_url: str, model_name: str,
                     language: str = "", timeout: int = 600) -> dict:
    """Transcribe audio via STT API. Returns dict with 'text' (markdown) and 'language' (detected)."""
    import json as _json
    import urllib.request

    url = api_url
    if not url.endswith("/audio/transcriptions"):
        url = url.rstrip("/") + "/audio/transcriptions"

    audio_bytes = Path(audio_path).read_bytes()
    filename = Path(audio_path).name
    api_lang = _to_iso639_1(language) if language else ""

    boundary = "----LoreMCPBoundary"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    body.extend(audio_bytes)
    body.extend(f"\r\n--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="model"\r\n\r\n')
    body.extend(model_name.encode())
    body.extend(f"\r\n--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="response_format"\r\n\r\n')
    body.extend(b"verbose_json")
    if api_lang:
        body.extend(f"\r\n--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="language"\r\n\r\n')
        body.extend(api_lang.encode())
    body.extend(f"\r\n--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        url, data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    logger.info("Transcribing %s via %s (%s)", filename, model_name, api_url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = _json.loads(resp.read())

    detected_lang = result.get("language", "")
    duration = result.get("duration", 0)
    segments = result.get("segments", [])
    title = Path(audio_path).stem.replace("-", " ").replace("_", " ")
    lines = [f"# {title}\n"]

    if segments:
        for seg in segments:
            ts = _format_timestamp(seg["start"])
            lines.append(f"\n## [{ts}]\n")
            lines.append(seg["text"].strip() + "\n")
    else:
        lines.append(result.get("text", "") + "\n")

    logger.info("Transcription: %s, lang=%s, duration=%.0fs", filename, detected_lang, duration)
    return {"text": "\n".join(lines), "language": detected_lang}


# ── Video parsing (E12.49) ───────────────────────────────────

def parse_video(video_path: str, stt_url: str, stt_model: str,
                language: str = "", scene_threshold: float = 0.3,
                timeout: int = 600) -> dict:
    """Parse video: extract audio transcription + scene change frames as inline base64.

    Requires ffmpeg (system). Returns dict with 'text' (markdown) and 'language' (detected).
    """
    import base64
    import json as _json
    import subprocess
    import tempfile

    vpath = Path(video_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Extract audio
        audio_file = tmp / "audio.wav"
        subprocess.run(
            ["ffmpeg", "-i", str(vpath), "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", str(audio_file), "-y"],
            capture_output=True, timeout=300,
        )

        # Transcribe
        detected_lang = ""
        if audio_file.exists() and audio_file.stat().st_size > 0:
            audio_duration = _get_audio_duration(str(audio_file))
            effective_timeout = max(timeout, int(audio_duration * 2)) if audio_duration else timeout
            stt_result = transcribe_audio(
                str(audio_file), stt_url, stt_model,
                language=language, timeout=effective_timeout,
            )
            transcription = stt_result["text"]
            video_title = vpath.stem.replace("-", " ").replace("_", " ")
            transcription = transcription.replace("# audio\n", f"# {video_title}\n", 1)
            detected_lang = stt_result.get("language", "")
        else:
            logger.warning("No audio track extracted from %s", vpath.name)
            transcription = ""

        # Extract scene change frames with timestamps
        frame_dir = tmp / "frames"
        frame_dir.mkdir()
        result = subprocess.run(
            ["ffmpeg", "-i", str(vpath),
             "-vf", f"select=gt(scene\\,{scene_threshold}),showinfo",
             "-fps_mode", "vfr", str(frame_dir / "frame_%04d.png"), "-y"],
            capture_output=True, text=True, timeout=300,
        )

        # Parse frame timestamps from ffmpeg showinfo
        frame_times = []
        for line in result.stderr.split("\n"):
            if "pts_time:" in line:
                try:
                    pts = float(line.split("pts_time:")[1].split()[0])
                    frame_times.append(pts)
                except (ValueError, IndexError):
                    pass

        # Read frames as base64
        frames = {}
        for i, frame_file in enumerate(sorted(frame_dir.glob("frame_*.png"))):
            ts = frame_times[i] if i < len(frame_times) else i * 30.0
            b64 = base64.b64encode(frame_file.read_bytes()).decode("ascii")
            frames[ts] = b64

    if not transcription and not frames:
        return {"text": f"# {vpath.stem}\n\nNo content extracted.\n", "language": detected_lang}

    # Merge transcription + frames
    if not transcription:
        title = vpath.stem.replace("-", " ").replace("_", " ")
        lines = [f"# {title}\n"]
        for ts, b64 in sorted(frames.items()):
            lines.append(f"\n## [{_format_timestamp(ts)}]\n")
            lines.append(f"![frame](data:image/png;base64,{b64})\n")
        return {"text": "\n".join(lines), "language": detected_lang}

    # Insert frames into transcription at matching positions
    trans_lines = transcription.split("\n")
    output = []
    used_frames = set()

    for line in trans_lines:
        output.append(line)
        if line.startswith("## [") and frames:
            try:
                ts_str = line.split("[")[1].split("]")[0]
                parts = ts_str.split(":")
                section_time = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except (IndexError, ValueError):
                continue
            for fts, b64 in sorted(frames.items()):
                if fts not in used_frames and abs(fts - section_time) < 15:
                    output.append(f"\n![frame](data:image/png;base64,{b64})\n")
                    used_frames.add(fts)
                    break

    return {"text": "\n".join(output), "language": detected_lang}


class FormatNotSupported(ValueError):
    """Raised when file extension is not recognized."""


_BACKEND_MAP = {
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
    """Detect conversion backend from file extension or mime type."""
    import mimetypes
    ext = Path(filename).suffix.lower()
    if ext in _BACKEND_MAP:
        return _BACKEND_MAP[ext]
    mime, _ = mimetypes.guess_type(filename)
    if mime:
        if mime.startswith("audio/"):
            return "audio"
        if mime.startswith("video/"):
            return "video"
    raise FormatNotSupported(
        f"Unsupported format: {ext} ({filename})"
    )


def _create_docling_converter(ocr_engine: str = "", ocr_lang: list[str] | None = None):
    """Create a DocumentConverter with optional Tesseract OCR config."""
    if ocr_engine == "tesseract":
        _ensure_tessdata_prefix()
        try:
            from docling.datamodel.pipeline_options import TesseractCliOcrOptions
            ocr_options = TesseractCliOcrOptions(lang=ocr_lang or ["eng"], scale=4.0)
            logger.info("Docling with Tesseract CLI OCR, lang=%s", ocr_lang)
        except ImportError:
            logger.warning("TesseractCliOcrOptions not available, falling back to default OCR")
            return DocumentConverter()

        from docling.datamodel.pipeline_options import PdfPipelineOptions
        opts = PdfPipelineOptions()
        opts.ocr_options = ocr_options

        from docling.document_converter import FormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
        from docling.backend.image_backend import ImageDocumentBackend

        try:
            from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
        except ImportError:
            from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend as DoclingParseDocumentBackend

        return DocumentConverter(
            format_options={
                InputFormat.IMAGE: FormatOption(
                    pipeline_options=opts,
                    pipeline_cls=StandardPdfPipeline,
                    backend=ImageDocumentBackend,
                ),
                InputFormat.PDF: FormatOption(
                    pipeline_options=opts,
                    pipeline_cls=StandardPdfPipeline,
                    backend=DoclingParseDocumentBackend,
                ),
            }
        )
    return DocumentConverter()


def _ensure_tessdata_prefix() -> None:
    """Set TESSDATA_PREFIX if not already set."""
    import os
    if "TESSDATA_PREFIX" not in os.environ:
        for p in ["/usr/share/tesseract/tessdata", "/usr/share/tessdata"]:
            if os.path.isdir(p):
                os.environ["TESSDATA_PREFIX"] = p
                break


def parse_to_markdown(file_path: str, docling_json_path: str = "",
                      ocr_engine: str = "", ocr_lang: list[str] | None = None) -> str:
    """Convert a file to markdown using the appropriate backend.

    If docling_json_path is provided and the file is parsed via Docling,
    the Docling document is saved as JSON for later captioning.
    ocr_engine: 'tesseract' to use Tesseract instead of RapidOCR.
    ocr_lang: language codes for OCR (e.g. ['fra', 'eng']).
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
            _docling_converter = _create_docling_converter(ocr_engine, ocr_lang)
        from docling_core.types.doc.base import ImageRefMode
        doc = _docling_converter.convert(str(path)).document
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            _reorder_columns(doc)

        if docling_json_path:
            doc.save_as_json(docling_json_path)

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

    if backend == "audio":
        logger.info("Audio file detected: %s (needs STT service)", path.name)
        return f"# {path.stem}\n\n[Audio file — requires STT service for transcription]\n"

    if backend == "video":
        logger.info("Video file detected: %s (needs STT + ffmpeg)", path.name)
        return f"# {path.stem}\n\n[Video file — requires STT service + ffmpeg for transcription]\n"
