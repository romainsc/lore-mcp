"""Structured data narration for RAG. See docs/studies/grooming-E3.31.md.

Transforms raw JSON/CSV/XLSX output into markdown with headings
and readable text for better vector search quality.
"""

import json
import re


def narrate_structured(text: str, format_hint: str) -> str:
    """Add headings and structure to raw structured data output.

    format_hint: 'json', 'markitdown', 'docling' — guides narration strategy.
    Returns the text unchanged if it already has headings or is not structured data.
    """
    if re.search(r"^#{1,3}\s+", text, re.MULTILINE):
        return text

    if format_hint == "json":
        return _narrate_json(text)
    elif format_hint in ("markitdown", "docling"):
        return _narrate_table(text, format_hint)

    return text


def _narrate_json(text: str) -> str:
    """Convert JSON text to headed markdown."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text

    lines = []

    if isinstance(data, dict):
        title = data.get("name") or data.get("title") or data.get("collection") or "Data"
        lines.append(f"# {title}\n")

        array_key = _find_array_key(data)
        if array_key:
            lines.append(f"## {array_key.replace('_', ' ').title()}\n")
            for i, record in enumerate(data[array_key]):
                record_title = _record_title(record, i)
                lines.append(f"### {record_title}\n")
                lines.append(_record_to_text(record))
                lines.append("")
        else:
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"## {key.replace('_', ' ').title()}\n")
                    if isinstance(value, list):
                        for item in value:
                            lines.append(f"- {item}")
                    else:
                        lines.append(_record_to_text(value))
                    lines.append("")

        scalar_fields = {k: v for k, v in data.items()
                         if not isinstance(v, (dict, list))}
        if scalar_fields and array_key:
            pass
        elif scalar_fields:
            for key, value in scalar_fields.items():
                lines.append(f"**{key.replace('_', ' ').title()}**: {value}\n")

    elif isinstance(data, list):
        lines.append("# Data\n")
        for i, record in enumerate(data):
            if isinstance(record, dict):
                record_title = _record_title(record, i)
                lines.append(f"## {record_title}\n")
                lines.append(_record_to_text(record))
                lines.append("")
            else:
                lines.append(f"- {record}")

    return "\n".join(lines)


def _narrate_table(text: str, format_hint: str) -> str:
    """Add heading to table-only markdown content."""
    lines = text.strip().split("\n")

    title = "Data"
    for line in lines[:5]:
        cleaned = line.strip().strip("|").strip()
        if cleaned and not re.match(r"^[\s:-]+$", cleaned):
            title = cleaned
            break

    return f"## {title}\n\n{text}"


def _find_array_key(data: dict) -> str | None:
    """Find the main array field in a JSON object."""
    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return key
    return None


def _record_title(record: dict, index: int) -> str:
    """Generate a title for a record from its key fields."""
    for key in ("name", "title", "round", "label", "id", "date"):
        if key in record and record[key]:
            return str(record[key])
    first_two = list(record.values())[:2]
    parts = [str(v) for v in first_two if v and not isinstance(v, (dict, list))]
    return " — ".join(parts) if parts else f"Record {index + 1}"


def _record_to_text(record: dict) -> str:
    """Convert a dict record to readable key-value lines."""
    lines = []
    for key, value in record.items():
        if isinstance(value, dict):
            sub = ", ".join(f"{k}: {v}" for k, v in value.items())
            lines.append(f"- **{key.replace('_', ' ').title()}**: {sub}")
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                items = "; ".join(
                    ", ".join(f"{k}: {v}" for k, v in item.items())
                    for item in value
                )
                lines.append(f"- **{key.replace('_', ' ').title()}**: {items}")
            else:
                lines.append(f"- **{key.replace('_', ' ').title()}**: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"- **{key.replace('_', ' ').title()}**: {value}")
    return "\n".join(lines)
