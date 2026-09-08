"""Text normalization and sanitization. See docs/preprocessing.md."""

import re
import unicodedata


def clean_text(text: str) -> str:
    """Normalize and clean markdown text for RAG indexing."""
    text = text.replace("\x00", "")
    text = unicodedata.normalize("NFC", text)
    text = _strip_images(text)
    text = _strip_html(text)
    text = _strip_heading_hashes(text)
    return text


def _strip_images(text: str) -> str:
    """Replace ![alt](src) with alt text."""
    return re.sub(
        r"!\[((?:[^\[\]]|\[[^\]]*\])*)\]\([^)]+\)",
        lambda m: m.group(1),
        text,
    )


_HTML_TAG_RE = re.compile(r"</?(?:div|span|p|br|a|em|strong|ul|ol|li|table|tr|td|th|thead|tbody|blockquote|section|article|nav|header|footer|aside|main|figure|figcaption|details|summary|mark|small|del|ins|sub|sup|abbr|cite|code|pre|hr|img|iframe|object|embed|source|video|audio|canvas|form|input|button|select|textarea|label|fieldset|legend)\b[^>]*>", re.IGNORECASE)

_HTML_ENTITY_RE = re.compile(r"&(?:nbsp|lt|gt|amp|quot|apos|#\d+|#x[0-9a-fA-F]+);")


def _strip_html(text: str) -> str:
    """Remove residual HTML tags and entities."""
    text = _HTML_TAG_RE.sub("", text)
    text = _HTML_ENTITY_RE.sub(" ", text)
    return text


def _strip_heading_hashes(text: str) -> str:
    """Strip markdown heading markers (#) from line starts, preserving content."""
    lines = text.split("\n")
    result = []
    in_code_block = False
    for line in lines:
        if line.startswith("```"):
            in_code_block = not in_code_block
        if not in_code_block:
            line = re.sub(r"^#{1,6}\s+", "", line)
        result.append(line)
    return "\n".join(result)
