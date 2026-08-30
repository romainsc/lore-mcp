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
