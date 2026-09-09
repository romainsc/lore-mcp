"""Quality gate for preprocessing pipeline. See docs/studies/grooming-E12.01.md."""

from lore_mcp.lint import analyze_file


def quality_gate(file_path: str, force: bool = False) -> dict:
    """Run lint quality check on a file.

    Returns a report dict with lint metrics and a 'passed' flag.
    Files with 'poor' verdict fail unless force=True.
    """
    report = analyze_file(file_path)
    passed = report["verdict"] != "poor" or force
    report["passed"] = passed
    return report
