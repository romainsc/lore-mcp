"""Unified format detection and backend routing. See grooming-E12.114.md."""

import logging
import mimetypes
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWN_BACKENDS = {"markdown", "html", "docling", "markitdown", "code", "audio", "video"}

_CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".rb", ".sh", ".bash", ".lua", ".php",
    ".yml", ".yaml", ".toml", ".cfg", ".ini",
}

_DOCKERFILE_NAMES = {"Dockerfile", "Containerfile"}

_TS_CANDIDATES = {
    ".py": ("tree_sitter_python", "python"),
    ".js": ("tree_sitter_javascript", "javascript"),
    ".jsx": ("tree_sitter_javascript", "javascript"),
    ".ts": ("tree_sitter_typescript", "typescript"),
    ".tsx": ("tree_sitter_typescript", "tsx"),
    ".c": ("tree_sitter_c", "c"),
    ".h": ("tree_sitter_c", "c"),
    ".cpp": ("tree_sitter_c", "c"),
    ".hpp": ("tree_sitter_c", "c"),
    ".java": ("tree_sitter_java", "java"),
    ".go": ("tree_sitter_go", "go"),
    ".rs": ("tree_sitter_rust", "rust"),
    ".rb": ("tree_sitter_ruby", "ruby"),
    ".sh": ("tree_sitter_bash", "bash"),
    ".bash": ("tree_sitter_bash", "bash"),
    ".lua": ("tree_sitter_lua", "lua"),
    ".php": ("tree_sitter_php", "php"),
}


class FormatRegistry:
    """Unified format detection and backend routing."""

    def __init__(self):
        self._ext_map: dict[str, str] = {}
        self._mime_map: dict[str, str] = {}
        self._ts_map: dict[str, tuple[str, str]] = {}
        self._load_defaults()
        self._detect_treesitter()

    def _load_defaults(self):
        self._ext_map.update({
            ".md": "markdown",
            ".html": "html", ".htm": "html",
            ".pdf": "docling", ".docx": "docling",
            ".pptx": "docling", ".xlsx": "docling",
            ".epub": "docling",
            ".png": "docling", ".jpg": "docling",
            ".jpeg": "docling", ".tiff": "docling",
            ".csv": "markitdown",
            ".json": "markitdown",
            ".xml": "markitdown",
        })
        for ext in _CODE_EXTENSIONS:
            self._ext_map[ext] = "code"

        self._mime_map.update({
            "application/pdf": "docling",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docling",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "docling",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "docling",
            "application/epub+zip": "docling",
            "text/html": "html",
            "image/png": "docling",
            "image/jpeg": "docling",
            "image/tiff": "docling",
            "image/gif": "docling",
            "image/bmp": "docling",
            "image/webp": "docling",
        })

    def _detect_treesitter(self):
        for ext, (module_name, lang_name) in _TS_CANDIDATES.items():
            try:
                __import__(module_name)
                self._ts_map[ext] = (module_name, lang_name)
            except ImportError:
                pass
        if self._ts_map:
            langs = sorted({v[1] for v in self._ts_map.values()})
            logger.debug("tree-sitter languages: %s", ", ".join(langs))

    def apply_config(self, overrides: dict):
        """Apply format overrides from config.yaml."""
        for ext, backend in overrides.items():
            if not ext.startswith("."):
                ext = f".{ext}"
            if not backend:
                self._ext_map.pop(ext, None)
                continue
            if backend not in KNOWN_BACKENDS:
                raise ValueError(
                    f"Unknown backend '{backend}' for {ext}. "
                    f"Valid: {', '.join(sorted(KNOWN_BACKENDS))}"
                )
            self._ext_map[ext] = backend

    def detect(self, filename: str) -> str:
        """Detect backend for a file. Content-based then extension."""
        from lore_mcp.preprocess.parse import FormatNotSupported
        ext = Path(filename).suffix.lower()

        if Path(filename).exists():
            try:
                import puremagic
                mime = puremagic.from_file(filename, mime=True)
                if mime in self._mime_map:
                    return self._mime_map[mime]
                if mime.startswith("audio/"):
                    return "audio"
                if mime.startswith("video/"):
                    return "video"
                if mime == "text/plain":
                    head = Path(filename).read_text(
                        encoding="utf-8", errors="replace"
                    )[:512].lstrip()
                    if head.startswith("<!DOCTYPE") or head.startswith("<html"):
                        return "html"
                    if head.startswith("{") or head.startswith("["):
                        return "markitdown"
            except Exception:
                pass

        if ext in self._ext_map:
            return self._ext_map[ext]

        name = Path(filename).name
        if name in _DOCKERFILE_NAMES:
            return "code"

        mime, _ = mimetypes.guess_type(filename)
        if mime:
            if mime.startswith("audio/"):
                return "audio"
            if mime.startswith("video/"):
                return "video"

        raise FormatNotSupported(
            f"Unsupported format: {ext} ({filename})"
        )

    def is_supported(self, filename: str) -> bool:
        """Check if a file can be processed (no I/O)."""
        name = Path(filename).name
        if name in _DOCKERFILE_NAMES:
            return True
        ext = Path(filename).suffix.lower()
        if ext in self._ext_map:
            return True
        mime, _ = mimetypes.guess_type(filename)
        if mime and (mime.startswith("audio/") or mime.startswith("video/")):
            return True
        return False

    def has_structural_parser(self, ext: str) -> bool:
        """Check if a code extension has AST-based narration."""
        if ext == ".py":
            return True
        return ext in self._ts_map

    def get_treesitter(self, ext: str) -> tuple[str, str] | None:
        """Get (module_name, language) for tree-sitter parsing."""
        return self._ts_map.get(ext)

    def list_formats(self) -> dict:
        """Return all supported formats with availability info."""
        result = {}
        for ext, backend in sorted(self._ext_map.items()):
            info = {"backend": backend}
            if backend == "code":
                info["structural_parser"] = self.has_structural_parser(ext)
                ts = self._ts_map.get(ext)
                if ext == ".py":
                    info["parser"] = "ast (stdlib)"
                elif ts:
                    info["parser"] = f"tree-sitter-{ts[1]}"
            result[ext] = info
        return result


_registry: FormatRegistry | None = None


def get_format_registry(config=None) -> FormatRegistry:
    """Get or create the singleton FormatRegistry."""
    global _registry
    if _registry is None:
        _registry = FormatRegistry()
        if config and hasattr(config, "format_overrides") and config.format_overrides:
            _registry.apply_config(config.format_overrides)
    return _registry


def reset_registry():
    """Reset singleton (for tests)."""
    global _registry
    _registry = None
