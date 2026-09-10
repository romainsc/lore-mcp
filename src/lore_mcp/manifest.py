"""Manifest parsing and source metadata extraction. See docs/architecture.md."""

import re
from pathlib import Path

import yaml


def parse_manifest(manifest_path: str) -> dict:
    """Parse a YAML collection manifest."""
    with open(manifest_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {
        "collection": data.get("collection", ""),
        "level": data.get("level", ""),
        "sources": data.get("sources", []),
    }


def resolve_source_fields(source: dict) -> dict:
    """Apply field cascade to a manifest source entry.

    Cascade: orig from url basename, path from orig with .md extension.
    Raises ValueError if neither orig nor url is present.
    """
    from pathlib import PurePosixPath
    from urllib.parse import urlparse

    result = dict(source)

    if "orig" not in result:
        url = result.get("url")
        if not url:
            raise ValueError(
                "Source entry must have 'orig' or 'url': "
                f"{source}"
            )
        parsed = urlparse(url)
        result["orig"] = PurePosixPath(parsed.path).name

    if "path" not in result:
        orig_path = PurePosixPath(result["orig"])
        if orig_path.suffix == ".md":
            result["path"] = result["orig"]
        else:
            result["path"] = str(orig_path.with_suffix(".md"))

    return result


def extract_source_metadata(text: str, filename: str) -> dict:
    """Extract bibliographic metadata from Markdown front matter or headings."""
    meta = {"title": None, "author": None, "url": None, "date": None, "license": None}

    fm = _extract_front_matter(text)
    if fm:
        meta["title"] = fm.get("title")
        meta["author"] = fm.get("author")
        meta["url"] = fm.get("url")
        meta["date"] = fm.get("date")
        meta["license"] = fm.get("license")

    if not meta["title"]:
        heading = _extract_first_heading(text)
        if heading:
            meta["title"] = heading

    if not meta["title"]:
        meta["title"] = Path(filename).stem

    return meta


def _extract_front_matter(text: str) -> dict | None:
    """Extract YAML front matter from Markdown text."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None


def _extract_first_heading(text: str) -> str | None:
    """Extract the first # heading from Markdown text."""
    for line in text.split("\n"):
        match = re.match(r"^#\s+(.+)$", line)
        if match:
            return match.group(1).strip()
    return None


_SUPPORTED_EXTENSIONS = {
    ".md", ".html", ".htm", ".pdf", ".docx", ".pptx", ".xlsx",
    ".epub", ".png", ".jpg", ".jpeg", ".tiff",
    ".csv", ".json", ".xml",
}


def scan_directory(docs_dir: str) -> dict:
    """Scan a directory and generate a manifest from found files."""
    from pathlib import Path
    docs = Path(docs_dir)
    sources = []
    for f in sorted(docs.rglob("*")):
        if f.is_file() and f.suffix.lower() in _SUPPORTED_EXTENSIONS:
            rel = str(f.relative_to(docs))
            sources.append({"orig": rel})
    return {
        "collection": docs.name,
        "level": "libre",
        "sources": sources,
    }
