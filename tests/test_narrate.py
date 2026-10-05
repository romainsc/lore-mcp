"""Tests for E3.31 MVP1: structured data to knowledge. See grooming-E3.31.md."""

import json
import pytest


class TestJsonNarration:
    """JSON array of records → markdown with headings."""

    def test_adds_collection_heading(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        data = json.dumps({"name": "World Cup 2022", "matches": [
            {"team1": "Qatar", "team2": "Ecuador", "score": "0-2"},
        ]})
        result = narrate_structured(data, "json")
        assert "## " in result or "# " in result

    def test_records_as_sections(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        data = json.dumps({"items": [
            {"name": "Alpha", "value": 1},
            {"name": "Beta", "value": 2},
        ]})
        result = narrate_structured(data, "json")
        assert "Alpha" in result
        assert "Beta" in result

    def test_flat_object_as_key_value(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        data = json.dumps({"title": "Report", "author": "Jane", "year": 2026})
        result = narrate_structured(data, "json")
        assert "Report" in result
        assert "# " in result

    def test_passthrough_non_json(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        text = "Just regular markdown text\n\n## Heading\n\nContent."
        result = narrate_structured(text, "json")
        assert result == text


class TestCsvNarration:
    """CSV/table content → markdown with headings."""

    def test_adds_heading_to_table(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        table = "| Name | Score |\n| - | - |\n| Alice | 95 |\n| Bob | 87 |"
        result = narrate_structured(table, "markitdown")
        assert "## " in result or "# " in result

    def test_preserves_table_content(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        table = "| Name | Score |\n| - | - |\n| Alice | 95 |"
        result = narrate_structured(table, "markitdown")
        assert "Alice" in result
        assert "95" in result


class TestXlsxNarration:
    """XLSX Docling output → markdown with headings."""

    def test_adds_heading_to_docling_table(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        table = "| Août 2026 Calendrier |\n| - |\n| Lundi | Mardi |"
        result = narrate_structured(table, "docling")
        assert "## " in result or "# " in result


class TestPythonCodeNarration:
    """E3.42: Python source code → headed markdown with preserved code."""

    _SAMPLE_CODE = '''"""Example module for testing."""

import os
from pathlib import Path


TIMEOUT = 30


class Processor:
    """Process documents."""

    def __init__(self, config: dict):
        """Initialize with config."""
        self.config = config

    def run(self, path: str) -> dict:
        """Run processing on a file."""
        return {"path": path, "status": "ok"}


def validate(path: str) -> bool:
    """Check if path is valid."""
    return Path(path).exists()
'''

    def test_produces_headings(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        result = narrate_structured(self._SAMPLE_CODE, "code", filename="processor.py")
        assert "# " in result
        assert "## " in result

    def test_extracts_module_docstring(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        result = narrate_structured(self._SAMPLE_CODE, "code", filename="processor.py")
        assert "Example module for testing" in result

    def test_extracts_class(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        result = narrate_structured(self._SAMPLE_CODE, "code", filename="processor.py")
        assert "Processor" in result
        assert "Process documents" in result

    def test_extracts_methods(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        result = narrate_structured(self._SAMPLE_CODE, "code", filename="processor.py")
        assert "run" in result
        assert "Run processing" in result

    def test_extracts_functions(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        result = narrate_structured(self._SAMPLE_CODE, "code", filename="processor.py")
        assert "validate" in result
        assert "Check if path is valid" in result

    def test_preserves_code_in_blocks(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        result = narrate_structured(self._SAMPLE_CODE, "code", filename="processor.py")
        assert "```python" in result
        assert "self.config = config" in result

    def test_extracts_imports(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        result = narrate_structured(self._SAMPLE_CODE, "code", filename="processor.py")
        assert "import os" in result
        assert "from pathlib import Path" in result

    def test_extracts_constants(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        result = narrate_structured(self._SAMPLE_CODE, "code", filename="processor.py")
        assert "TIMEOUT" in result

    def test_javascript_narration(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        js_code = """
class UserService {
  constructor(db) {
    this.db = db;
  }

  /** Get user by ID. */
  async getUser(id) {
    return await this.db.find(id);
  }
}

function validateEmail(email) {
  return email.includes('@');
}
"""
        result = narrate_structured(js_code, "code", filename="service.js")
        assert "## " in result or "### " in result
        assert "UserService" in result
        assert "getUser" in result
        assert "validateEmail" in result

    def test_c_narration(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        c_code = """
#include <stdio.h>

int add(int a, int b) {
    return a + b;
}

int main() {
    printf("%d\\n", add(1, 2));
    return 0;
}
"""
        result = narrate_structured(c_code, "code", filename="main.c")
        assert "# main" in result
        assert "add" in result
        assert "main" in result

    def test_java_narration(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        java_code = """
public class Calculator {
    /** Add two numbers. */
    public int add(int a, int b) {
        return a + b;
    }

    public static void main(String[] args) {
        Calculator c = new Calculator();
        System.out.println(c.add(1, 2));
    }
}
"""
        result = narrate_structured(java_code, "code", filename="Calculator.java")
        assert "Calculator" in result
        assert "add" in result
        assert "main" in result
        assert "## " in result

    def test_bash_narration(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        bash_code = """#!/bin/bash

function deploy() {
    echo "Deploying..."
    rsync -avz ./dist/ server:/app/
}

function rollback() {
    echo "Rolling back..."
}

deploy
"""
        result = narrate_structured(bash_code, "code", filename="deploy.sh")
        assert "deploy" in result
        assert "rollback" in result
        assert "## " in result

    def test_unsupported_language_fallback(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        code = "some unknown language code"
        result = narrate_structured(code, "code", filename="script.awk")
        assert "# script" in result
        assert "```" in result

    def test_quality_gate_passes(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        from lore_mcp.preprocess.validate import quality_gate
        import tempfile
        from pathlib import Path as P

        result = narrate_structured(self._SAMPLE_CODE, "code", filename="processor.py")
        tmp = P(tempfile.mktemp(suffix=".md"))
        tmp.write_text(result)
        qg = quality_gate(str(tmp))
        tmp.unlink()
        assert qg["heading_count"] > 0
        assert qg["structure_score"] > 0


class TestYamlNarration:
    def test_headings_per_section(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        yaml = "database:\n  dir: /data\n\nembedding:\n  model: nomic\n"
        result = narrate_structured(yaml, "code", filename="config.yaml")
        assert "## database" in result or "## Database" in result
        assert "## embedding" in result or "## Embedding" in result
        assert "nomic" in result


class TestTomlNarration:
    def test_headings_per_table(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        toml = '[project]\nname = "lore"\n\n[build-system]\nrequires = ["hatch"]\n'
        result = narrate_structured(toml, "code", filename="pyproject.toml")
        assert "## project" in result or "## Project" in result
        assert "lore" in result


class TestDockerfileNarration:
    def test_headings_per_stage(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        df = "FROM python:3.14 AS builder\nRUN pip install .\n\nFROM python:3.14 AS runtime\nCOPY . .\n"
        result = narrate_structured(df, "code", filename="Containerfile")
        assert "builder" in result
        assert "runtime" in result
        assert "## " in result


class TestQualityGateImprovement:
    """Narrated output should pass quality gate."""

    def test_json_narrated_has_headings(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        from lore_mcp.preprocess.validate import quality_gate
        import tempfile
        from pathlib import Path

        data = json.dumps({"name": "World Cup 2022", "matches": [
            {"round": "Matchday 1", "team1": "Qatar", "team2": "Ecuador",
             "score": "0-2", "date": "2022-11-20"},
            {"round": "Matchday 2", "team1": "England", "team2": "Iran",
             "score": "6-2", "date": "2022-11-21"},
        ]})
        result = narrate_structured(data, "json")
        tmp = Path(tempfile.mktemp(suffix=".md"))
        tmp.write_text(result)
        qg = quality_gate(str(tmp))
        tmp.unlink()
        assert qg["heading_count"] > 0, f"No headings: {qg}"
        assert qg["structure_score"] > 0, f"Zero structure: {qg}"
