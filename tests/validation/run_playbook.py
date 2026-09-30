#!/usr/bin/env python3
"""E12.97: MCP LLM validation playbook runner.

Loads playbook-mcp.yaml and executes each scenario through a
local LLM MCP client. Compares before/after answers to validate
that indexing improves search quality.

STATUS: placeholder — full implementation requires a local LLM
MCP client (e.g., ollama with MCP support, or a custom client).

Usage:
    python tests/validation/run_playbook.py [--playbook playbook-mcp.yaml]

The playbook format:
  - phase: name
    steps:
      - scenario: "description"
        user: "natural language question"
        expect_tools: [tool1, tool2]
        save_answer_as: variable_name
        expect_better_than: other_variable
        expect_same_as: other_variable
        wait_until: status
        expect_behavior: behavior_name
"""

import sys
import yaml
from pathlib import Path


def load_playbook(path="tests/validation/playbook-mcp.yaml"):
    """Load and validate the playbook YAML."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    phases = data.get("playbook", [])
    total_steps = sum(len(p.get("steps", [])) for p in phases)
    print(f"Playbook: {len(phases)} phases, {total_steps} steps")

    for phase in phases:
        print(f"  Phase: {phase['phase']}")
        for step in phase.get("steps", []):
            markers = []
            if step.get("save_answer_as"):
                markers.append(f"save:{step['save_answer_as']}")
            if step.get("expect_better_than"):
                markers.append(f"better:{step['expect_better_than']}")
            if step.get("expect_same_as"):
                markers.append(f"same:{step['expect_same_as']}")
            if step.get("expect_tools"):
                markers.append(f"tools:{step['expect_tools']}")
            marker_str = f" [{', '.join(markers)}]" if markers else ""
            print(f"    - {step['scenario']}{marker_str}")

    return phases


def main():
    playbook_path = "tests/validation/playbook-mcp.yaml"
    if "--playbook" in sys.argv:
        idx = sys.argv.index("--playbook")
        playbook_path = sys.argv[idx + 1]

    print("=== E12.97: MCP LLM Playbook ===\n")

    phases = load_playbook(playbook_path)

    print("\n" + "=" * 40)
    print("Playbook loaded and validated.")
    print("Full execution requires a local LLM MCP client.")
    print("See docs/studies/grooming-E12.95-97.md for details.")


if __name__ == "__main__":
    main()
