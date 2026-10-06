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

from lore_mcp.preprocess.service import run_with_interrupt
from charset_normalizer import from_path as detect_encoding


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

try:
    from markitdown import MarkItDown
    _HAVE_MARKITDOWN = True
except ImportError:
    _HAVE_MARKITDOWN = False

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"}

_BASE64_FRAME_RE = re.compile(
    r"!\[([^\]]*)\]\(data:image/[^;]+;base64,[A-Za-z0-9+/=\n]+\)"
)


class FormatNotSupported(ValueError):
    """Raised when file extension is not recognized."""


class Parser:
    """Multi-format document parser. See docs/architecture.md."""

    def __init__(self, ocr_engine: str = "", ocr_lang: list[str] | None = None):
        self.ocr_engine = ocr_engine
        self.ocr_lang = ocr_lang or []
        self._converter = None

    # ── Private utilities (static) ─────────────────────────────

    @staticmethod
    def _fetch_api(req, timeout, verify_ssl=True):
        """Fetch an API endpoint, interruptible by SIGINT."""
        import json as _json
        import urllib.request
        kwargs = {"timeout": timeout}
        if not verify_ssl:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            kwargs["context"] = ctx
        def _do_fetch():
            with urllib.request.urlopen(req, **kwargs) as resp:
                return _json.loads(resp.read())
        return run_with_interrupt(_do_fetch)

    @staticmethod
    def _read_text(path: Path) -> str:
        """Read a text file with detected encoding."""
        result = detect_encoding(path)
        best = result.best()
        if best is None:
            return path.read_text(encoding="utf-8", errors="replace")
        return str(best)

    @staticmethod
    def _convert_text_data(path: Path) -> str:
        """Convert JSON/CSV/XML to readable markdown when markitdown fails."""
        import json as _json

        content = Parser._read_text(path)
        ext = path.suffix.lower()

        if ext == ".json":
            try:
                data = _json.loads(content)
                return Parser._json_to_markdown(data, path.stem)
            except _json.JSONDecodeError:
                return content

        return content

    @staticmethod
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
                    lines.append(Parser._json_to_markdown(value))
                elif isinstance(value, dict):
                    lines.append(f"\n## {key}\n")
                    for k, v in value.items():
                        lines.append(f"- **{k}**: {v}")
                else:
                    lines.append(f"- **{key}**: {value}")

        return "\n".join(lines)

    @staticmethod
    def _reorder_columns(doc) -> None:
        """Reorder document body children by column layout (left->right, top->bottom)."""
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

    @staticmethod
    def _to_iso639_1(code: str) -> str:
        """Convert any language code to ISO 639-1."""
        if len(code) == 2:
            return code
        from langcodes import Language
        return Language.get(code).language

    @staticmethod
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

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def _vtt_to_markdown(vtt_text: str, title: str = "Video") -> str:
        """Convert WebVTT subtitle text to markdown with timestamp headings."""
        lines_out = [f"# {title}\n"]
        segment_window = 120

        current_block_start = 0.0
        current_texts = []

        for line in vtt_text.split("\n"):
            line = line.strip()
            if "-->" in line:
                parts = line.split("-->")[0].strip().split(":")
                try:
                    if len(parts) == 3:
                        secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                    elif len(parts) == 2:
                        secs = int(parts[0]) * 60 + float(parts[1])
                    else:
                        continue
                except (ValueError, IndexError):
                    continue

                if secs - current_block_start >= segment_window and current_texts:
                    ts = Parser._format_timestamp(current_block_start)
                    lines_out.append(f"\n## [{ts}]\n")
                    lines_out.append(" ".join(current_texts) + "\n")
                    current_block_start = secs
                    current_texts = []
            elif line and not line.startswith("WEBVTT") and not line.startswith("NOTE") and not line.isdigit():
                text = re.sub(r"<[^>]+>", "", line)
                if text.strip():
                    current_texts.append(text.strip())

        if current_texts:
            ts = Parser._format_timestamp(current_block_start)
            lines_out.append(f"\n## [{ts}]\n")
            lines_out.append(" ".join(current_texts) + "\n")

        return "\n".join(lines_out)

    @staticmethod
    def _extract_frames_scene(vpath, frame_dir, threshold=0.3):
        """Extract frames at scene changes."""
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-i", str(vpath),
             "-vf", f"select=gt(scene\\,{threshold}),showinfo",
             "-fps_mode", "vfr", str(frame_dir / "frame_%04d.png"), "-y"],
            capture_output=True, text=True, timeout=300,
        )
        frame_times = []
        for line in result.stderr.split("\n"):
            if "pts_time:" in line:
                try:
                    frame_times.append(float(line.split("pts_time:")[1].split()[0]))
                except (ValueError, IndexError):
                    pass
        return frame_times

    @staticmethod
    def _extract_frames_interval(vpath, frame_dir, interval=30):
        """Extract frames at fixed interval."""
        import subprocess
        subprocess.run(
            ["ffmpeg", "-i", str(vpath),
             "-vf", f"fps=1/{interval}",
             "-fps_mode", "vfr", str(frame_dir / "frame_%04d.png"), "-y"],
            capture_output=True, text=True, timeout=300,
        )
        return [i * interval for i in range(len(list(frame_dir.glob("frame_*.png"))))]

    @staticmethod
    def _extract_frames_ocr_guided(vpath, frame_dir, interval=30,
                                    change_threshold=0.3, ocr_lang="eng"):
        """Extract frames where OCR text changes significantly."""
        import subprocess
        # Step 1: extract at interval
        all_dir = frame_dir / "_all"
        all_dir.mkdir()
        subprocess.run(
            ["ffmpeg", "-i", str(vpath),
             "-vf", f"fps=1/{interval}",
             "-fps_mode", "vfr", str(all_dir / "frame_%04d.png"), "-y"],
            capture_output=True, text=True, timeout=300,
        )

        # Step 2: OCR each frame, compare with previous
        prev_text = ""
        kept_times = []
        kept_idx = 0
        all_frames = sorted(all_dir.glob("frame_*.png"))
        total = len(all_frames)
        for i, frame in enumerate(all_frames):
            try:
                ocr_result = subprocess.run(
                    ["tesseract", str(frame), "stdout", "-l", ocr_lang],
                    capture_output=True, text=True, timeout=30,
                )
                text = ocr_result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                text = ""

            changed = i == 0 or Parser._text_change_ratio(prev_text, text) > change_threshold
            if changed:
                kept_idx += 1
                dest = frame_dir / f"frame_{kept_idx:04d}.png"
                frame.rename(dest)
                kept_times.append(i * interval)
                prev_text = text
            logger.info("  OCR frame %d/%d: %s", i + 1, total, "kept" if changed else "skip")

        return kept_times

    @staticmethod
    def _text_change_ratio(old: str, new: str) -> float:
        """Ratio of changed words between two texts."""
        old_words = set(old.lower().split())
        new_words = set(new.lower().split())
        if not old_words and not new_words:
            return 0.0
        union = old_words | new_words
        if not union:
            return 0.0
        diff = old_words.symmetric_difference(new_words)
        return len(diff) / len(union)

    @staticmethod
    def _ensure_tessdata_prefix() -> None:
        """Set TESSDATA_PREFIX if not already set."""
        import os
        if "TESSDATA_PREFIX" not in os.environ:
            for p in ["/usr/share/tesseract/tessdata", "/usr/share/tessdata"]:
                if os.path.isdir(p):
                    os.environ["TESSDATA_PREFIX"] = p
                    break

    @staticmethod
    def _transcribe_video(vpath: Path, stt_url: str, stt_model: str,
                           language: str, timeout: int) -> tuple[str, str]:
        """Extract audio and transcribe. Returns (transcription, detected_lang)."""
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_file = Path(tmpdir) / "audio.wav"
            subprocess.run(
                ["ffmpeg", "-i", str(vpath), "-vn", "-acodec", "pcm_s16le",
                 "-ar", "16000", "-ac", "1", str(audio_file), "-y"],
                capture_output=True, timeout=300,
            )

            if audio_file.exists() and audio_file.stat().st_size > 0:
                audio_duration = Parser._get_audio_duration(str(audio_file))
                effective_timeout = max(timeout, int(audio_duration * 3)) if audio_duration else timeout
                stt_result = Parser.transcribe_audio(
                    str(audio_file), stt_url, stt_model,
                    language=language, timeout=effective_timeout,
                )
                transcription = stt_result["text"]
                video_title = vpath.stem.replace("-", " ").replace("_", " ")
                transcription = transcription.replace("# audio\n", f"# {video_title}\n", 1)
                return transcription, stt_result.get("language", "")
            else:
                logger.warning("No audio track extracted from %s", vpath.name)
                return "", ""

    # ── Public methods ─────────────────────────────────────────

    def unload(self) -> None:
        """Free the cached Docling converter and release GPU VRAM."""
        self._converter = None
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    @staticmethod
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

    @staticmethod
    def detect_format(filename: str) -> str:
        """Detect conversion backend from content then extension."""
        from lore_mcp.format_registry import get_format_registry
        return get_format_registry().detect(filename)

    def _create_converter(self):
        """Create a DocumentConverter with optional Tesseract OCR config."""
        if self.ocr_engine == "tesseract":
            self._ensure_tessdata_prefix()
            try:
                from docling.datamodel.pipeline_options import TesseractCliOcrOptions
                ocr_options = TesseractCliOcrOptions(lang=self.ocr_lang or ["eng"], scale=4.0)
                logger.info("Docling with Tesseract CLI OCR, lang=%s", self.ocr_lang)
            except ImportError:
                logger.warning("TesseractCliOcrOptions not available, falling back to default OCR")
                return DocumentConverter()

            from docling.datamodel.pipeline_options import PdfPipelineOptions
            opts = PdfPipelineOptions()
            opts.ocr_options = ocr_options
            try:
                from docling.datamodel.pipeline_options import HeadingHierarchyOptions
                opts.heading_hierarchy_options = HeadingHierarchyOptions(
                    enabled=True,
                    use_bookmarks=True,
                    use_numbering=True,
                )
            except ImportError:
                pass

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

    def _get_converter(self):
        """Get or create the Docling converter (lazy singleton per Parser)."""
        if self._converter is None:
            self._converter = self._create_converter()
        return self._converter

    def parse_to_markdown(self, file_path: str, docling_json_path: str = "") -> str:
        """Convert a file to markdown using the appropriate backend."""
        path = Path(file_path)
        backend = self.detect_format(str(path))

        if backend == "markdown":
            return path.read_text(encoding="utf-8", errors="replace")

        if backend == "code":
            return path.read_text(encoding="utf-8", errors="replace")

        if backend == "html":
            if not _HAVE_TRAFILATURA:
                raise ImportError(
                    "trafilatura is required for HTML conversion. "
                    "Install: pip install lore-mcp[html]"
                )
            html = self._read_text(path)
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
            converter = self._get_converter()
            from docling_core.types.doc.base import ImageRefMode
            conv_result = converter.convert(str(path))
            if hasattr(conv_result, 'status'):
                status_name = getattr(conv_result.status, 'name', str(conv_result.status))
                if status_name == "FAILURE":
                    error_msgs = [str(e) for e in getattr(conv_result, 'errors', [])]
                    raise RuntimeError(f"Docling conversion failed: {'; '.join(error_msgs) or 'unknown error'}")
                if status_name == "PARTIAL_SUCCESS":
                    error_msgs = [str(e) for e in getattr(conv_result, 'errors', [])]
                    logger.warning("Docling partial conversion for %s: %s", path.name, "; ".join(error_msgs) or "some pages failed")
            doc = conv_result.document
            if path.suffix.lower() in IMAGE_EXTENSIONS:
                self._reorder_columns(doc)

            if docling_json_path:
                doc.save_as_json(docling_json_path)

            result = doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED, compact_tables=True)
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
                return self._convert_text_data(path)

        if backend == "audio":
            logger.info("Audio file detected: %s (needs STT service)", path.name)
            return f"# {path.stem}\n\n[Audio file — requires STT service for transcription]\n"

        if backend == "video":
            logger.info("Video file detected: %s (needs STT + ffmpeg)", path.name)
            return f"# {path.stem}\n\n[Video file — requires STT service + ffmpeg for transcription]\n"

    def parse_batch_docling(self, paths: list[str],
                            docling_json_paths: list[str]) -> dict[str, dict]:
        """Batch-parse multiple documents via Docling convert_all()."""
        if not paths:
            return {}

        if not _HAVE_DOCLING:
            raise ImportError(
                "docling is required for batch PDF/DOCX/PPTX conversion. "
                "Install: pip install lore-mcp[pdf]"
            )

        converter = self._get_converter()
        from docling_core.types.doc.base import ImageRefMode

        path_to_json = dict(zip(paths, docling_json_paths))
        results = {}

        for conv_result in converter.convert_all([Path(p) for p in paths], raises_on_error=False):
            src_path = str(conv_result.input.file) if hasattr(conv_result.input, 'file') else ""
            if not src_path:
                continue

            if hasattr(conv_result, 'status'):
                status_name = getattr(conv_result.status, 'name', str(conv_result.status))
                if status_name == "FAILURE":
                    error_msgs = [str(e) for e in getattr(conv_result, 'errors', [])]
                    results[src_path] = {
                        "text": None,
                        "error": f"Docling conversion failed: {'; '.join(error_msgs) or 'unknown error'}",
                    }
                    continue
                if status_name == "PARTIAL_SUCCESS":
                    error_msgs = [str(e) for e in getattr(conv_result, 'errors', [])]
                    logger.warning("Docling partial conversion for %s: %s",
                                   Path(src_path).name,
                                   "; ".join(error_msgs) or "some pages failed")

            doc = conv_result.document
            if Path(src_path).suffix.lower() in IMAGE_EXTENSIONS:
                self._reorder_columns(doc)

            docling_json = path_to_json.get(src_path, "")
            if docling_json:
                doc.save_as_json(docling_json)

            text = doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED, compact_tables=True)
            results[src_path] = {
                "text": text,
                "docling_json": docling_json if docling_json and Path(docling_json).exists() else "",
            }

        return results

    # ── Captioning ─────────────────────────────────────────────

    @staticmethod
    def caption_with_docling(doc_json_path: str, api_url: str, model_name: str,
                              prompt: str = "", timeout: int = 180,
                              concurrency: int = 1,
                              checkpoint=None, phase_name: str = "",
                              source_key: str = "") -> str:
        """Load a serialized Docling document, apply captioning via API, return markdown."""
        from docling_core.types.doc.document import DoclingDocument
        from docling_core.types.doc.base import ImageRefMode

        doc = DoclingDocument.load_from_json(doc_json_path)

        if not doc.pictures:
            text = doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED, compact_tables=True)
            if not text.strip():
                return ""
            return text

        try:
            from docling.datamodel.pipeline_options import PictureDescriptionApiOptions
        except ImportError:
            logger.warning("PictureDescriptionApiOptions not available, skipping captioning")
            return doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED, compact_tables=True)

        total_pics = len(doc.pictures)
        start_idx = 0
        if checkpoint and phase_name and source_key:
            completed = checkpoint.get_completed_count(phase_name, source_key)
            if completed > 0 and completed < total_pics:
                start_idx = completed
                logger.info("Resuming captioning at image %d/%d", start_idx + 1, total_pics)

        img = doc.pictures[0].image if doc.pictures else None
        if img and hasattr(img, 'mode') and img.mode == 'P':
            has_transparency = getattr(img.info, 'get', lambda k, d=None: d)('transparency', None) is not None
            if has_transparency:
                for pic in doc.pictures:
                    if pic.image and hasattr(pic.image, 'mode') and pic.image.mode == 'P':
                        pic.image = pic.image.convert("RGBA")

        api_options = PictureDescriptionApiOptions(
            url=api_url,
            params={"model": model_name, "max_tokens": 4096},
            prompt=prompt or "Describe this image in detail.",
            timeout=timeout,
            concurrency=concurrency,
        )

        for i, pic in enumerate(doc.pictures):
            if i < start_idx:
                continue
            try:
                from docling.models.picture_description_api_model import PictureDescriptionApiModel
                model = PictureDescriptionApiModel(
                    enabled=True,
                    options=api_options,
                )
                model.draw(doc, [pic])
                logger.info("Captioned image %d/%d via %s", i + 1, total_pics, model_name)
            except Exception as e:
                logger.warning("Failed to caption image %d/%d: %s", i + 1, total_pics, e)

            if checkpoint and phase_name and source_key:
                checkpoint.mark_sub_completed(phase_name, source_key, i + 1)

        return doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED, compact_tables=True)

    @staticmethod
    def caption_standalone_image(image_path: str, api_url: str, model_name: str,
                                  prompt: str = "", timeout: int = 180,
                                  verify_ssl: bool = True) -> str:
        """Caption a standalone image via VLM API."""
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
        result = Parser._fetch_api(req, timeout, verify_ssl=verify_ssl)

        description = result["choices"][0]["message"]["content"]
        title = Path(image_path).stem.replace("-", " ").replace("_", " ")
        return f"# {title}\n\n{description}\n"

    @staticmethod
    def caption_inline_frames(text: str, api_url: str, model_name: str,
                               timeout: int = 600, verify_ssl: bool = True,
                               intermediate_path: str = "") -> str:
        """Replace base64 inline frames with VLM descriptions using transcript context."""
        import json as _json
        import urllib.request
        import base64
        import tempfile
        import subprocess as _sp

        if intermediate_path and Path(intermediate_path).exists():
            saved = Path(intermediate_path).read_text(encoding="utf-8")
            remaining = len(list(_BASE64_FRAME_RE.finditer(saved)))
            original = len(list(_BASE64_FRAME_RE.finditer(text)))
            if remaining < original:
                logger.info("Resuming frame captioning (%d/%d frames remaining)", remaining, original)
                text = saved

        matches = list(_BASE64_FRAME_RE.finditer(text))
        if not matches:
            return text

        url = api_url
        result_text = text
        total_frames = len(matches)
        logger.info("Captioning %d inline images via %s", total_frames, model_name)
        min_ocr_chars = 20

        for frame_idx, match in enumerate(reversed(matches), 1):
            full_data_url = match.group(0).split("(")[1].rstrip(")")
            b64_part = full_data_url.split("base64,")[1] if "base64," in full_data_url else ""

            if not b64_part:
                continue

            try:
                frame_bytes = base64.b64decode(b64_part)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp_frame:
                    tmp_frame.write(frame_bytes)
                    tmp_frame.flush()
                    ocr_result = _sp.run(
                        ["tesseract", tmp_frame.name, "stdout"],
                        capture_output=True, text=True, timeout=10,
                    )
                    ocr_text = ocr_result.stdout.strip()
            except Exception:
                ocr_text = ""

            if len(ocr_text) < min_ocr_chars:
                logger.info("  Frame %d/%d skipped (no text)", frame_idx, total_frames)
                result_text = result_text[:match.start()] + "[frame]" + result_text[match.end():]
                if intermediate_path:
                    Path(intermediate_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(intermediate_path).write_text(result_text, encoding="utf-8")
                continue

            pos = match.start()
            before_text = text[max(0, pos - 1000):pos].strip()
            after_text = text[match.end():match.end() + 500].strip()
            context = before_text[-500:] + " " + after_text[:300]
            context = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", context).strip()

            prompt = (
                f"This image appears in a recorded talk. "
                f"The speaker is saying: {context[:600]}\n\n"
                f"Describe what the slide or visual shows: diagrams, text, "
                f"key information visible."
            )

            try:
                media_type = "image/png"
                payload = _json.dumps({
                    "model": model_name,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {
                                "url": f"data:{media_type};base64,{b64_part}",
                            }},
                            {"type": "text", "text": prompt},
                        ],
                    }],
                    "max_tokens": 512,
                }).encode()

                req = urllib.request.Request(
                    url, data=payload,
                    headers={"Content-Type": "application/json"},
                )
                api_result = Parser._fetch_api(req, timeout, verify_ssl=verify_ssl)

                description = api_result["choices"][0]["message"]["content"]
                result_text = result_text[:match.start()] + description + result_text[match.end():]
                logger.info("  Frame %d/%d captioned (%d chars)", frame_idx, total_frames, len(description))
            except Exception as e:
                logger.warning("  Frame %d/%d failed: %s", frame_idx, total_frames, e)
                result_text = result_text[:match.start()] + "[frame]" + result_text[match.end():]

            if intermediate_path:
                Path(intermediate_path).parent.mkdir(parents=True, exist_ok=True)
                Path(intermediate_path).write_text(result_text, encoding="utf-8")

        return result_text

    # ── Judge for multi-model selection ────────────────────────

    @staticmethod
    def judge_captions(
        ocr_text: str,
        alt_text: str,
        captions: dict[str, str],
        llm_url: str,
        llm_model: str,
        llm_key: str = "",
        verify_ssl: bool = True,
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
        data = Parser._fetch_api(req, 60, verify_ssl=verify_ssl)

        answer = data["choices"][0]["message"]["content"].strip().lower()
        logger.info("Judge selected: %s", answer)

        for name in captions:
            if name.lower() in answer:
                return captions[name]

        return next(iter(captions.values()))

    # ── Audio/Video ────────────────────────────────────────────

    @staticmethod
    def transcribe_audio(audio_path: str, api_url: str, model_name: str,
                         language: str = "", timeout: int = 600,
                         verify_ssl: bool = True) -> dict:
        """Transcribe audio via STT API. Returns dict with 'text' and 'language'."""
        import json as _json
        import urllib.request

        url = api_url
        audio_bytes = Path(audio_path).read_bytes()
        filename = Path(audio_path).name
        api_lang = Parser._to_iso639_1(language) if language else ""

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

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        req = urllib.request.Request(url, data=bytes(body), headers=headers)
        data = Parser._fetch_api(req, timeout, verify_ssl=verify_ssl)

        detected_lang = data.get("language", "")
        duration = data.get("duration", 0)
        segments = data.get("segments", [])

        title = Path(audio_path).stem.replace("-", " ").replace("_", " ")
        lines = [f"# {title}\n"]

        segment_window = 120
        current_block_start = 0.0
        current_texts = []

        for seg in segments:
            start = seg.get("start", 0)
            text = seg.get("text", "").strip()
            if not text:
                continue

            if start - current_block_start >= segment_window and current_texts:
                ts = Parser._format_timestamp(current_block_start)
                lines.append(f"\n## [{ts}]\n")
                lines.append(" ".join(current_texts) + "\n")
                current_block_start = start
                current_texts = []
            current_texts.append(text)

        if current_texts:
            ts = Parser._format_timestamp(current_block_start)
            lines.append(f"\n## [{ts}]\n")
            lines.append(" ".join(current_texts) + "\n")

        return {"text": "\n".join(lines), "language": detected_lang}

    @staticmethod
    def download_video(url: str, output_dir: str, lang: str = "") -> dict:
        """Download video via yt-dlp. Returns metadata + optional captions."""
        try:
            import yt_dlp
        except (ImportError, ModuleNotFoundError):
            return {"error": "yt-dlp not installed (pip install lore-mcp[video])"}

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        sub_langs = [lang] if lang else ["en", "fr"]

        opts = {
            "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": sub_langs,
            "subtitlesformat": "vtt",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_id = info.get("id", "video")
            title = info.get("title", "")
            ydl.download([url])

        captions_text = None
        captions_source = "none"
        subs = info.get("subtitles", {})
        auto_subs = info.get("automatic_captions", {})

        for sl in sub_langs:
            vtt_files = list(out_dir.glob(f"{video_id}*.{sl}*.vtt"))
            if vtt_files:
                captions_text = Parser._vtt_to_markdown(
                    vtt_files[0].read_text(encoding="utf-8", errors="replace"),
                    title=title or video_id,
                )
                captions_source = "manual" if sl in subs else "auto"
                break

        video_files = [
            f for f in out_dir.glob(f"{video_id}.*")
            if f.suffix.lower() in (".mp4", ".webm", ".mkv", ".avi", ".mov")
        ]

        return {
            "video_path": str(video_files[0]) if video_files else None,
            "captions_text": captions_text,
            "title": title,
            "author": info.get("uploader", ""),
            "duration": info.get("duration", 0),
            "upload_date": info.get("upload_date", ""),
            "language": lang or info.get("language", ""),
            "captions_source": captions_source,
        }

    @staticmethod
    def parse_video(video_path: str, stt_url: str, stt_model: str,
                    language: str = "", scene_threshold: float = 0.3,
                    timeout: int = 600, frame_strategy: str = "scene",
                    frame_interval: int = 30,
                    ocr_change_threshold: float = 0.3,
                    cache_dir: str = "") -> dict:
        """Parse video: extract audio transcription + frames as inline base64."""
        import base64
        import json as _json
        import subprocess
        import tempfile

        vpath = Path(video_path)
        stt_cache = Path(cache_dir) / f"{vpath.stem}.stt.json" if cache_dir else None

        if stt_cache and stt_cache.exists():
            cached = _json.loads(stt_cache.read_text(encoding="utf-8"))
            transcription = cached["text"]
            detected_lang = cached.get("language", "")
            logger.info("STT cache hit: %s", stt_cache.name)
        else:
            transcription, detected_lang = Parser._transcribe_video(
                vpath, stt_url, stt_model, language, timeout,
            )
            if stt_cache and transcription:
                stt_cache.parent.mkdir(parents=True, exist_ok=True)
                stt_cache.write_text(
                    _json.dumps({"text": transcription, "language": detected_lang},
                                ensure_ascii=False),
                    encoding="utf-8",
                )
                logger.info("STT cache saved: %s", stt_cache.name)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            frame_dir = tmp / "frames"
            frame_dir.mkdir()
            ocr_lang = language if len(language) == 3 else "eng"

            if frame_strategy == "interval":
                frame_times = Parser._extract_frames_interval(vpath, frame_dir, frame_interval)
            elif frame_strategy == "ocr":
                frame_times = Parser._extract_frames_ocr_guided(
                    vpath, frame_dir, frame_interval,
                    ocr_change_threshold, ocr_lang,
                )
            elif frame_strategy == "hybrid":
                scene_times = Parser._extract_frames_scene(vpath, frame_dir, scene_threshold)
                interval_dir = tmp / "frames_interval"
                interval_dir.mkdir()
                interval_times = Parser._extract_frames_interval(vpath, interval_dir, frame_interval)
                existing = set(int(t) for t in scene_times)
                for i, ft in enumerate(interval_times):
                    if int(ft) not in existing:
                        src = interval_dir / f"frame_{i+1:04d}.png"
                        if src.exists():
                            idx = len(list(frame_dir.glob("frame_*.png"))) + 1
                            src.rename(frame_dir / f"frame_{idx:04d}.png")
                            scene_times.append(ft)
                frame_times = sorted(scene_times)
            else:
                frame_times = Parser._extract_frames_scene(vpath, frame_dir, scene_threshold)

            frames = {}
            for i, frame_file in enumerate(sorted(frame_dir.glob("frame_*.png"))):
                ts = frame_times[i] if i < len(frame_times) else i * 30.0
                b64 = base64.b64encode(frame_file.read_bytes()).decode("ascii")
                frames[ts] = b64

        if not transcription and not frames:
            return {"text": f"# {vpath.stem}\n\nNo content extracted.\n", "language": detected_lang}

        if not transcription:
            title = vpath.stem.replace("-", " ").replace("_", " ")
            lines = [f"# {title}\n"]
            for ts, b64 in sorted(frames.items()):
                lines.append(f"\n## [{Parser._format_timestamp(ts)}]\n")
                lines.append(f"![frame](data:image/png;base64,{b64})\n")
            return {"text": "\n".join(lines), "language": detected_lang}

        trans_lines = transcription.split("\n")
        section_times = []
        section_indices = []
        for i, line in enumerate(trans_lines):
            if line.startswith("## ["):
                try:
                    ts_str = line.split("[")[1].split("]")[0]
                    parts = ts_str.split(":")
                    t = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    section_times.append(t)
                    section_indices.append(i)
                except (IndexError, ValueError):
                    pass

        output = list(trans_lines)
        inserted = 0
        for fts, b64 in sorted(frames.items(), reverse=True):
            best_idx = None
            best_dist = float("inf")
            for j, st in enumerate(section_times):
                if fts >= st and fts - st < best_dist:
                    best_dist = fts - st
                    best_idx = section_indices[j]
            if best_idx is None and section_indices:
                best_idx = section_indices[0]
            if best_idx is not None:
                insert_at = best_idx + 1
                output.insert(insert_at, f"\n![frame](data:image/png;base64,{b64})\n")
                inserted += 1

        return {"text": "\n".join(output), "language": detected_lang}


# ══════════════════════════════════════════════════════════════
# Module-level aliases for backward compatibility
# ══════════════════════════════════════════════════════════════

_default_parser = None


def _get_default_parser(ocr_engine="", ocr_lang=None) -> Parser:
    """Get or create the default module-level parser."""
    global _default_parser
    if _default_parser is None or (ocr_engine and _default_parser.ocr_engine != ocr_engine):
        _default_parser = Parser(ocr_engine, ocr_lang)
    return _default_parser


def unload_docling() -> None:
    """Free the cached Docling converter and release GPU VRAM."""
    global _default_parser
    if _default_parser:
        _default_parser.unload()
    _default_parser = None


def classify_parse_result(text: str, orig_format: str) -> str:
    """Classify parse result quality. Returns: 'text_ok', 'empty', or 'poor'."""
    return Parser.classify_parse_result(text, orig_format)


def detect_format(filename: str) -> str:
    """Detect conversion backend from content then extension."""
    return Parser.detect_format(filename)


def parse_to_markdown(file_path: str, docling_json_path: str = "",
                      ocr_engine: str = "", ocr_lang: list[str] | None = None) -> str:
    """Convert a file to markdown using the appropriate backend."""
    return _get_default_parser(ocr_engine, ocr_lang).parse_to_markdown(file_path, docling_json_path)


def parse_batch_docling(paths: list[str], docling_json_paths: list[str],
                        ocr_engine: str = "", ocr_lang: list[str] | None = None) -> dict[str, dict]:
    """Batch-parse multiple documents via Docling convert_all()."""
    return _get_default_parser(ocr_engine, ocr_lang).parse_batch_docling(paths, docling_json_paths)


def caption_with_docling(doc_json_path: str, api_url: str, model_name: str,
                          prompt: str = "", timeout: int = 180,
                          concurrency: int = 1,
                          checkpoint=None, phase_name: str = "",
                          source_key: str = "") -> str:
    """Load a serialized Docling document, apply captioning via API, return markdown."""
    return Parser.caption_with_docling(doc_json_path, api_url, model_name,
                                        prompt, timeout, concurrency,
                                        checkpoint, phase_name, source_key)


def caption_standalone_image(image_path: str, api_url: str, model_name: str,
                              prompt: str = "", timeout: int = 180,
                              verify_ssl: bool = True) -> str:
    """Caption a standalone image via VLM API."""
    return Parser.caption_standalone_image(image_path, api_url, model_name,
                                            prompt, timeout, verify_ssl)


def caption_inline_frames(text: str, api_url: str, model_name: str,
                           timeout: int = 600, verify_ssl: bool = True,
                           intermediate_path: str = "") -> str:
    """Replace base64 inline frames with VLM descriptions using transcript context."""
    return Parser.caption_inline_frames(text, api_url, model_name,
                                         timeout, verify_ssl, intermediate_path)


def judge_captions(ocr_text: str, alt_text: str, captions: dict[str, str],
                   llm_url: str, llm_model: str, llm_key: str = "",
                   verify_ssl: bool = True) -> str:
    """Select the best caption by asking judge LLM to pick by name."""
    return Parser.judge_captions(ocr_text, alt_text, captions,
                                  llm_url, llm_model, llm_key, verify_ssl)


def transcribe_audio(audio_path: str, api_url: str, model_name: str,
                     language: str = "", timeout: int = 600,
                     verify_ssl: bool = True) -> dict:
    """Transcribe audio via STT API."""
    return Parser.transcribe_audio(audio_path, api_url, model_name,
                                    language, timeout, verify_ssl)


def download_video(url: str, output_dir: str, lang: str = "") -> dict:
    """Download video via yt-dlp."""
    return Parser.download_video(url, output_dir, lang)


def parse_video(video_path: str, stt_url: str, stt_model: str,
                language: str = "", scene_threshold: float = 0.3,
                timeout: int = 600, frame_strategy: str = "scene",
                frame_interval: int = 30,
                ocr_change_threshold: float = 0.3,
                cache_dir: str = "") -> dict:
    """Parse video: extract audio transcription + frames as inline base64."""
    return Parser.parse_video(video_path, stt_url, stt_model,
                               language, scene_threshold, timeout,
                               frame_strategy, frame_interval,
                               ocr_change_threshold, cache_dir)


def _create_docling_converter(ocr_engine: str = "", ocr_lang: list[str] | None = None):
    """Create a DocumentConverter with optional Tesseract OCR config."""
    return _get_default_parser(ocr_engine, ocr_lang)._create_converter()


def _get_audio_duration(path: str) -> float:
    """Get audio duration in seconds via ffprobe."""
    return Parser._get_audio_duration(path)


def _fetch_api(req, timeout, verify_ssl=True):
    """Fetch an API endpoint, interruptible by SIGINT."""
    return Parser._fetch_api(req, timeout, verify_ssl)


def _vtt_to_markdown(vtt_text: str, title: str = "Video") -> str:
    """Convert WebVTT subtitle text to markdown with timestamp headings."""
    return Parser._vtt_to_markdown(vtt_text, title)


def _reorder_columns(doc) -> None:
    """Reorder document body children by column layout."""
    return Parser._reorder_columns(doc)


def _transcribe_video_impl(vpath, stt_url, stt_model, language, timeout):
    """Extract audio and transcribe. Returns (transcription, detected_lang)."""
    return Parser._transcribe_video(vpath, stt_url, stt_model, language, timeout)
