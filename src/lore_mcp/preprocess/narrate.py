"""Structured data narration for RAG. See docs/studies/grooming-E3.31.md.

Transforms raw JSON/CSV/XLSX/code output into markdown with headings
and readable text for better vector search quality.
"""

import json
import re
from pathlib import Path


def narrate_structured(text: str, format_hint: str, filename: str = "") -> str:
    """Add headings and structure to raw structured data output.

    format_hint: 'json', 'markitdown', 'docling', 'code'.
    Returns the text unchanged if it already has headings or is not structured data.
    """
    if format_hint != "code" and re.search(r"^#{1,3}\s+", text, re.MULTILINE):
        return text

    if format_hint == "json":
        return _narrate_json(text)
    elif format_hint in ("markitdown", "docling"):
        return _narrate_table(text, format_hint)
    elif format_hint == "code":
        return _narrate_code(text, filename)

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


def _narrate_code(text: str, filename: str = "") -> str:
    """Convert source code to headed markdown. See grooming-E3.42.md."""
    ext = Path(filename).suffix.lower() if filename else ""
    if ext == ".py":
        return _narrate_python(text, filename)
    from lore_mcp.format_registry import get_format_registry
    ts_info = get_format_registry().get_treesitter(ext)
    if ts_info:
        result = _narrate_treesitter(text, filename, ext)
        if result:
            return result
    name = Path(filename).stem if filename else "Code"
    return f"# {name}\n\n```\n{text}\n```\n"


def _narrate_python(text: str, filename: str = "") -> str:
    """Parse Python source via ast and produce headed markdown."""
    import ast
    import textwrap

    try:
        tree = ast.parse(text)
    except SyntaxError:
        name = Path(filename).stem if filename else "Code"
        return f"# {name}\n\n```python\n{text}\n```\n"

    lines = []
    module_name = Path(filename).stem if filename else "module"
    source_lines = text.split("\n")

    module_doc = ast.get_docstring(tree)
    if module_doc:
        lines.append(f"# {module_name}\n")
        lines.append(f"{module_doc}\n")
    else:
        lines.append(f"# {module_name}\n")

    imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    if imports:
        lines.append("## Imports\n")
        for imp in imports:
            if isinstance(imp, ast.ImportFrom):
                names = ", ".join(a.name for a in imp.names)
                lines.append(f"- from {imp.module} import {names}")
            else:
                names = ", ".join(a.name for a in imp.names)
                lines.append(f"- import {names}")
        lines.append("")

    constants = [
        n for n in tree.body
        if isinstance(n, ast.Assign)
        and all(isinstance(t, ast.Name) and t.id.isupper() for t in n.targets)
    ]
    if constants:
        lines.append("## Constants\n")
        for c in constants:
            name_str = c.targets[0].id if isinstance(c.targets[0], ast.Name) else "?"
            value_src = ast.get_source_segment(text, c.value) or "..."
            lines.append(f"- `{name_str}` = {value_src}")
        lines.append("")

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            lines.append(f"## Class {node.name}\n")
            class_doc = ast.get_docstring(node)
            if class_doc:
                lines.append(f"{class_doc}\n")
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sig = _format_signature(item)
                    is_prop = any(
                        isinstance(d, ast.Name) and d.id == "property"
                        or isinstance(d, ast.Attribute) and d.attr == "property"
                        for d in item.decorator_list
                    )
                    if is_prop:
                        lines.append(f"### {item.name} (property)\n")
                    else:
                        lines.append(f"### {sig}\n")
                    fdoc = ast.get_docstring(item)
                    if fdoc:
                        lines.append(f"{fdoc}\n")
                    code_block = _extract_source(source_lines, item)
                    lines.append(f"```python\n{code_block}\n```\n")

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = _format_signature(node)
            lines.append(f"## {sig}\n")
            fdoc = ast.get_docstring(node)
            if fdoc:
                lines.append(f"{fdoc}\n")
            code_block = _extract_source(source_lines, node)
            lines.append(f"```python\n{code_block}\n```\n")

    return "\n".join(lines)


def _format_signature(node) -> str:
    """Build a readable function signature from an AST node."""
    import ast
    parts = []
    for arg in node.args.args:
        name = arg.arg
        if arg.annotation:
            try:
                ann = ast.unparse(arg.annotation)
                name = f"{name}: {ann}"
            except Exception:
                pass
        parts.append(name)

    sig = f"{node.name}({', '.join(parts)})"

    if node.returns:
        try:
            ret = ast.unparse(node.returns)
            sig += f" -> {ret}"
        except Exception:
            pass

    return sig


def _extract_source(source_lines: list[str], node) -> str:
    """Extract source code for a function/method from source lines."""
    start = node.lineno - 1
    end = node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else start + 1
    block = source_lines[start:end]
    doc_node = node.body[0] if node.body and isinstance(node.body[0], __import__("ast").Expr) else None
    if doc_node and isinstance(doc_node.value, __import__("ast").Constant) and isinstance(doc_node.value.value, str):
        doc_end = doc_node.end_lineno - start if hasattr(doc_node, "end_lineno") else 1
        block = block[:1] + block[doc_end:]
    return "\n".join(block)


def _narrate_treesitter(text: str, filename: str, ext: str) -> str | None:
    """Parse source code via tree-sitter and produce headed markdown."""
    try:
        from tree_sitter import Language, Parser
    except ImportError:
        return None

    from lore_mcp.format_registry import get_format_registry
    ts_info = get_format_registry().get_treesitter(ext)
    if not ts_info:
        return None

    module_name, lang_name = ts_info
    try:
        mod = __import__(module_name)
        if lang_name == "typescript":
            language = Language(mod.language_typescript())
        elif lang_name == "tsx":
            language = Language(mod.language_tsx())
        else:
            language = Language(mod.language())
    except (ImportError, AttributeError):
        return None

    parser = Parser(language)
    source = text.encode("utf-8")
    tree = parser.parse(source)
    root = tree.root_node

    file_stem = Path(filename).stem if filename else "module"
    lang_label = lang_name if lang_name != "tsx" else "tsx"
    lines = [f"# {file_stem}\n"]

    _CLASS_TYPES = {"class_definition", "class_declaration"}
    _FUNC_TYPES = {
        "function_definition", "function_declaration",
        "method_definition", "method_declaration",
    }
    _COMMENT_TYPES = {"comment", "block_comment"}

    def _node_name(node) -> str:
        name_node = node.child_by_field_name("name")
        if name_node:
            return source[name_node.start_byte:name_node.end_byte].decode()
        return "?"

    def _node_source(node) -> str:
        return source[node.start_byte:node.end_byte].decode()

    def _preceding_comment(node) -> str:
        prev = node.prev_named_sibling
        if prev and prev.type in _COMMENT_TYPES:
            comment = _node_source(prev).strip()
            for prefix in ("//", "/*", "*/", "/**", "*"):
                comment = comment.removeprefix(prefix)
            for suffix in ("*/",):
                comment = comment.removesuffix(suffix)
            return comment.strip()
        return ""

    def _body_comment(node) -> str:
        body = node.child_by_field_name("body")
        if not body or not body.children:
            return ""
        first = body.children[0]
        if first.type in _COMMENT_TYPES:
            comment = _node_source(first).strip()
            for prefix in ("//", "/*", "*/", "/**", "*"):
                comment = comment.removeprefix(prefix)
            for suffix in ("*/",):
                comment = comment.removesuffix(suffix)
            return comment.strip()
        return ""

    for node in root.children:
        if node.type in _CLASS_TYPES:
            name = _node_name(node)
            comment = _preceding_comment(node) or _body_comment(node)
            lines.append(f"## Class {name}\n")
            if comment:
                lines.append(f"{comment}\n")

            for child in node.children:
                body = child if child.type in ("class_body", "block") else None
                if not body:
                    if child.type in _FUNC_TYPES:
                        body_nodes = [child]
                    else:
                        continue
                else:
                    body_nodes = body.children

                for member in body_nodes:
                    if member.type in _FUNC_TYPES:
                        mname = _node_name(member)
                        mcomment = _preceding_comment(member) or _body_comment(member)
                        lines.append(f"### {mname}\n")
                        if mcomment:
                            lines.append(f"{mcomment}\n")
                        lines.append(f"```{lang_label}\n{_node_source(member)}\n```\n")

        elif node.type in _FUNC_TYPES:
            name = _node_name(node)
            comment = _preceding_comment(node) or _body_comment(node)
            lines.append(f"## {name}\n")
            if comment:
                lines.append(f"{comment}\n")
            lines.append(f"```{lang_label}\n{_node_source(node)}\n```\n")

    if len(lines) <= 1:
        return None

    return "\n".join(lines)
