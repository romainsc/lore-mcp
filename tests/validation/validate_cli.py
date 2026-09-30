#!/usr/bin/env python3
"""E12.95: CLI end-to-end validation.

Validates the full lore-mcp CLI pipeline on a fast subset
of sources. Requires IS scripts in scripts/ and podman.

Usage:
    python tests/validation/validate_cli.py [--skip-preprocess]

Prerequisites:
    - podman installed
    - TEI model cached (~/.cache/huggingface)
    - pip install -e .
"""

import subprocess
import sys
import json
from pathlib import Path

BUILD_DIR = "/tmp/lore-mcp-validation"
RECIPE = "tests/validation/recipe-validation.yaml"
CONFIG = "tests/validation/config-validation.yaml"
ORIG_DIR = "tests/fixtures/orig"

errors = []


def run(cmd, timeout=600):
    """Run a shell command and return stdout."""
    print(f"  $ {cmd}")
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        errors.append(f"FAILED: {cmd}\n{result.stderr[-500:]}")
        print(f"  FAILED (exit {result.returncode})")
        return ""
    return result.stdout


def main():
    skip_preprocess = "--skip-preprocess" in sys.argv

    print("=== E12.95: CLI Validation ===\n")

    # Clean previous run
    Path(BUILD_DIR).mkdir(parents=True, exist_ok=True)

    # 1. Preprocess
    if not skip_preprocess:
        print("[1/5] Preprocess")
        run(
            f"lore-mcp preprocess {RECIPE} "
            f"--orig-dir {ORIG_DIR} --build-dir {BUILD_DIR} "
            f"--config {CONFIG} --allow-download --force --verbose",
            timeout=300,
        )
        prep_dir = Path(BUILD_DIR) / "prep"
        md_files = list(prep_dir.glob("*.md")) if prep_dir.exists() else []
        print(f"  → {len(md_files)} prep files")
        if not md_files:
            errors.append("Preprocess produced 0 files")
    else:
        print("[1/5] Preprocess (skipped)")

    # 2. Build
    print("[2/5] Build (skip-optimize)")
    run(
        f"lore-mcp build {RECIPE} "
        f"--orig-dir {ORIG_DIR} --build-dir {BUILD_DIR} "
        f"--config {CONFIG} --skip-optimize --verbose",
        timeout=300,
    )
    db_files = list(Path(BUILD_DIR).glob("*.db"))
    if db_files:
        print(f"  → .db: {db_files[0].name} ({db_files[0].stat().st_size // 1024} KB)")
    else:
        errors.append("Build produced no .db file")

    # 3. Eval
    print("[3/5] Eval")
    db_path = db_files[0] if db_files else Path(BUILD_DIR) / "test-validation.db"
    output = run(
        f"lore-mcp eval --db {db_path} "
        f"--config {CONFIG} --verbose",
        timeout=120,
    )
    if output:
        print(f"  → {output.strip()[-200:]}")

    # 4. Lint (exit 1 = poor files detected, not a validation failure)
    print("[4/5] Lint")
    prep_recipe = Path(RECIPE).parent / f"{Path(RECIPE).stem}-prep.yaml"
    if prep_recipe.exists():
        lint_cmd = (
            f"lore-mcp lint {prep_recipe} "
            f"--docs-dir {BUILD_DIR}/prep"
        )
    else:
        lint_cmd = (
            f"lore-mcp lint {RECIPE} "
            f"--docs-dir {ORIG_DIR}"
        )
    print(f"  $ {lint_cmd}")
    lint_result = subprocess.run(
        lint_cmd, shell=True, capture_output=True, text=True, timeout=60,
    )
    if lint_result.returncode == 0:
        print(f"  → All files pass quality gate")
    elif lint_result.returncode == 1 and "poor" in lint_result.stdout.lower():
        print(f"  → Lint ran OK (some files rated poor — expected for CSV/data)")
    else:
        errors.append(f"FAILED: {lint_cmd}\n{lint_result.stderr[-500:]}")
        print(f"  FAILED (exit {lint_result.returncode})")
    if lint_result.stdout:
        for line in lint_result.stdout.strip().split("\n")[-3:]:
            print(f"  {line.strip()}")

    # 5. State
    print("[5/5] State")
    output = run("lore-mcp state --list")
    if output:
        print(f"  → {output.strip()[:100]}")

    # Report
    print(f"\n{'='*40}")
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        for e in errors:
            print(f"  ✗ {e[:200]}")
        sys.exit(1)
    else:
        print("CLI validation PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
