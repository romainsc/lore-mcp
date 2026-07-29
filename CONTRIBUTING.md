# Contributing to lore-mcp

Thank you for your interest in contributing to
lore-mcp. This document explains how to
contribute effectively.

## Prerequisites

- Python ≥ 3.10
- Git
- (Optional) NVIDIA GPU with CUDA

## Setting up the development environment

```bash
git clone https://github.com/rchanter/lore-mcp.git
cd lore-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Git workflow

### Branches

- `main` is the stable branch. **Never commit
  directly to main.**
- Create a topic branch for your work:
  `feat/<topic>`, `fix/<topic>`, or
  `docs/<topic>`.
- If a topic has sub-topics, use sub-branches
  (e.g. `feat/store/meta-table`).
- Merge with `--no-ff` when the topic is closed.
- Do not delete branches after merge.

### Commits

- Messages in English, imperative form
  (e.g. "Add search result capping", not
  "Added" or "Adds").
- Reference backlog item IDs when applicable
  (e.g. "Implement E1.01: storage backend").
- No secrets, credentials, or internal paths
  in commits.

## AI-assisted development

This project uses AI-assisted development.
All contributors must follow the guidelines
in [`docs/ai-guidelines.md`](docs/ai-guidelines.md).

Key requirements:

- **Review**: all AI output must be reviewed,
  tested, and validated by a human before commit.
- **Marking**: commits with substantial AI-assisted
  content must include a `Co-Authored-By` trailer
  identifying the AI tool used.
- **No confidential data**: never input
  confidential, personal, or access-controlled
  information into AI tools.
- **Provenance**: if AI output appears to
  reproduce existing copyrighted content, verify
  the license before incorporating it.

## Testing

This project follows TDD (Test-Driven
Development). Write tests before implementation.

```bash
pytest
```

## License

By contributing, you agree that your
contributions will be licensed under the
[GPL-3.0-or-later](LICENSE) license.

All contributions — whether human-written or
AI-assisted — are subject to the same license
terms, quality standards, and review requirements.
