"""Recipe parsing and source metadata extraction. See docs/architecture.md."""

import re
from pathlib import Path

import yaml


def parse_recipe(recipe_path: str) -> dict:
    """Parse a YAML recipe file with defaults cascade.

    Recipe structure:
        collection: name
        level: libre
        defaults:          # optional, applied to all sources
          lang: fra
          options:
            chunk_size: 1024
        sources:
          - file: doc.pdf
            options:       # per-source override
              chunk_size: 512
    """
    with open(recipe_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    defaults = data.get("defaults", {})
    default_options = defaults.pop("options", {})
    sources = data.get("sources", [])
    orig_dir = data.get("orig_dir", "")

    resolved_sources = []
    for source in sources:
        merged = dict(defaults)
        merged.update({k: v for k, v in source.items() if k != "options"})
        source_options = source.get("options", {})
        merged_options = dict(default_options)
        merged_options.update(source_options)
        if merged_options:
            merged["options"] = merged_options
        resolved_sources.append(merged)

    return {
        "collection": data.get("collection", ""),
        "level": data.get("level", ""),
        "orig_dir": orig_dir,
        "sources": resolved_sources,
    }


def resolve_source_fields(source: dict) -> dict:
    """Apply field cascade to a recipe source entry.

    Cascade: file from url basename, path from file with .md extension.
    Raises ValueError if neither file nor url is present.
    """
    from pathlib import PurePosixPath
    from urllib.parse import urlparse

    result = dict(source)

    if "file" not in result:
        url = result.get("url")
        if not url:
            raise ValueError(
                "Source entry must have 'file' or 'url': "
                f"{source}"
            )
        parsed = urlparse(url)
        if "youtube.com" in (parsed.netloc or "") or "youtu.be" in (parsed.netloc or ""):
            from urllib.parse import parse_qs
            if "youtu.be" in parsed.netloc:
                vid = parsed.path.strip("/")
            else:
                vid = parse_qs(parsed.query).get("v", [""])[0]
            result["file"] = vid if vid else PurePosixPath(parsed.path).name
        else:
            result["file"] = PurePosixPath(parsed.path).name

    if "path" not in result:
        file_path = PurePosixPath(result["file"])
        if file_path.suffix == ".md":
            result["path"] = result["file"]
        else:
            result["path"] = str(file_path.with_suffix(".md"))

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


def _is_supported(filename: str) -> bool:
    """Check if a file is supported. Delegates to FormatRegistry."""
    from lore_mcp.format_registry import get_format_registry
    return get_format_registry().is_supported(filename)


def expand_directory_entries(recipe: dict, base_dir: str) -> dict:
    """Expand directory entries in recipe to individual file entries.

    A source with file ending in '/' is a directory entry.
    It is replaced by all supported files found recursively,
    inheriting the directory entry's metadata as defaults.
    File entries in the recipe override directory defaults.
    """
    base = Path(base_dir)
    file_entries = {}
    dir_entries = []

    for source in recipe.get("sources", []):
        orig = source.get("file", "")
        if not orig:
            file_entries[source.get("url", "")] = source
            continue
        if orig.endswith("/") or (base / orig).is_dir():
            dir_entries.append(source)
        else:
            file_entries[orig] = source

    if not dir_entries:
        return recipe

    expanded = []
    seen = set()

    for entry in dir_entries:
        dir_path = base / entry["file"]
        if not dir_path.is_dir():
            continue
        defaults = {k: v for k, v in entry.items() if k != "file"}
        for f in sorted(dir_path.rglob("*")):
            if not f.is_file():
                continue
            if not _is_supported(f.name):
                continue
            rel = str(f.relative_to(base))
            if rel in file_entries:
                if rel not in seen:
                    expanded.append(file_entries[rel])
                    seen.add(rel)
            elif rel not in seen:
                file_source = dict(defaults)
                file_source["file"] = rel
                expanded.append(file_source)
                seen.add(rel)

    for orig, source in file_entries.items():
        if orig not in seen:
            expanded.append(source)
            seen.add(orig)

    result = dict(recipe)
    result["sources"] = expanded
    return result


def scan_directory(docs_dir: str) -> dict:
    """Scan a directory and generate a manifest from found files."""
    import logging
    _logger = logging.getLogger(__name__)
    docs = Path(docs_dir)
    sources = []
    for f in sorted(docs.rglob("*")):
        if not f.is_file():
            continue
        if _is_supported(f.name):
            from lore_mcp.format_registry import get_format_registry
            _reg = get_format_registry()
            ext = f.suffix.lower()
            try:
                backend = _reg.detect(f.name)
            except Exception:
                backend = ""
            if backend == "code" and not _reg.has_structural_parser(ext):
                _logger.warning(
                    "No structural parser for %s (%s) — will index as raw code block. "
                    "Install tree-sitter-%s for structural narration.",
                    f.name, ext, ext.lstrip("."),
                )
            rel = str(f.relative_to(docs))
            sources.append({"file": rel, "path": rel})
    return {
        "collection": docs.name,
        "level": "libre",
        "sources": sources,
    }
