"""Source quality analysis. See docs/studies/grooming-E6.07.md."""

import re
from pathlib import Path

from lore_mcp.manifest import parse_manifest


def analyze_file(path: Path | str) -> dict:
    """Analyze a markdown file for indexing quality."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")

    total_chars = len(text)
    alpha_chars = sum(1 for c in text if c.isalpha())
    text_density = alpha_chars / max(total_chars, 1)

    words = text.split()
    word_count = len(words)

    headings = re.findall(r"^#{2,3}\s+.+$", text, flags=re.MULTILINE)
    heading_count = len(headings)

    sections = _split_sections(text)
    empty_sections = 0
    noise_sections = 0
    section_lengths = []

    for heading, body in sections:
        body_words = body.split()
        section_lengths.append(len(body_words))
        if len(body_words) == 0:
            pass
        elif len(body_words) < 5:
            body_alpha = sum(1 for c in body if c.isalpha())
            if body_alpha / max(len(body), 1) < 0.5:
                noise_sections += 1
            else:
                empty_sections += 1
        else:
            body_alpha = sum(1 for c in body if c.isalpha())
            if body_alpha / max(len(body), 1) < 0.3:
                noise_sections += 1

    avg_section_length = (
        sum(section_lengths) / max(len(section_lengths), 1)
        if section_lengths else word_count
    )

    verdict = _compute_verdict(text_density, noise_sections, empty_sections, len(sections))

    return {
        "file": str(path),
        "text_density": round(text_density, 2),
        "heading_count": heading_count,
        "avg_section_length": round(avg_section_length, 1),
        "empty_sections": empty_sections,
        "noise_sections": noise_sections,
        "word_count": word_count,
        "verdict": verdict,
    }


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) pairs."""
    parts = re.split(r"^(#{2,3}\s+.+)$", text, flags=re.MULTILINE)
    sections = []
    i = 1
    while i < len(parts) - 1:
        heading = parts[i].strip()
        body = parts[i + 1].strip()
        sections.append((heading, body))
        i += 2
    return sections


def _compute_verdict(
    text_density: float,
    noise_sections: int,
    empty_sections: int,
    total_sections: int,
) -> str:
    """Compute quality verdict."""
    if text_density < 0.5:
        return "poor"
    problem_sections = noise_sections + empty_sections
    if total_sections > 0:
        problem_ratio = problem_sections / total_sections
        if problem_ratio > 0.5:
            return "poor"
        if problem_ratio > 0.1:
            return "warn"
    if noise_sections > 0 or text_density < 0.7:
        return "warn"
    return "good"


def lint_sources(
    docs_dir: str,
    manifest_path: str,
) -> list[dict]:
    """Analyze all manifest sources with quality, PII, and dedup checks."""
    from lore_mcp.preprocess.pii import detect_pii
    from lore_mcp.preprocess.dedup import find_exact_duplicates, find_near_duplicates

    docs_path = Path(docs_dir)
    manifest = parse_manifest(manifest_path)

    reports = []
    contents = {}
    for source in manifest["sources"]:
        src_path = source.get("path", source.get("orig", ""))
        file_path = docs_path / src_path
        if file_path.exists():
            report = analyze_file(file_path)
            text = file_path.read_text(encoding="utf-8", errors="replace")
            pii = detect_pii(text)
            if pii:
                report["pii"] = pii
            contents[src_path] = text
            reports.append(report)

    if contents:
        exact = find_exact_duplicates(contents)
        for group in exact.duplicates:
            for f in group["files"][1:]:
                for r in reports:
                    if Path(r["file"]).name == Path(f).name or r["file"] == f:
                        r["duplicate"] = "exact"
        near = find_near_duplicates(contents)
        for group in near.duplicates:
            for f in group["files"][1:]:
                for r in reports:
                    if (Path(r["file"]).name == Path(f).name or r["file"] == f) and "duplicate" not in r:
                        r["duplicate"] = "near"

    reports.sort(key=lambda r: r["text_density"])
    return reports


def format_lint_report(reports: list[dict]) -> str:
    """Format lint results as a markdown table."""
    lines = []
    lines.append(
        f"| {'File':<40} | {'Density':>7} | {'Headings':>8} | {'Words':>6} "
        f"| {'Empty':>5} | {'Noise':>5} | {'Verdict':<6} |"
    )
    lines.append(
        f"|{'-' * 42}|{'-' * 9}|{'-' * 10}|{'-' * 8}"
        f"|{'-' * 7}|{'-' * 7}|{'-' * 8}|"
    )
    for r in reports:
        name = Path(r["file"]).name[:38]
        lines.append(
            f"| {name:<40} | {r['text_density']:>7.2f} | {r['heading_count']:>8} "
            f"| {r['word_count']:>6} | {r['empty_sections']:>5} "
            f"| {r['noise_sections']:>5} | {r['verdict']:<6} |"
        )

    poor_count = sum(1 for r in reports if r["verdict"] == "poor")
    warn_count = sum(1 for r in reports if r["verdict"] == "warn")
    good_count = sum(1 for r in reports if r["verdict"] == "good")
    lines.append("")
    lines.append(f"{len(reports)} files: {good_count} good, {warn_count} warn, {poor_count} poor")

    return "\n".join(lines)
