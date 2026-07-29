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
git clone https://github.com/romainsc/lore-mcp.git
cd lore-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Developer Certificate of Origin (DCO)

This project uses the [Developer Certificate of
Origin v1.1](https://developercertificate.org/)
to certify that contributors have the right to
submit their contributions under the project
license.

By adding a `Signed-off-by` trailer to your
commit messages, you certify that you wrote the
contribution or have the right to pass it on as
open source, and that you agree to the DCO terms.

Add it automatically with `git commit -s`:

```
Signed-off-by: Your Name <your.email@example.com>
```

Every commit must include this trailer.

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
- No secrets, credentials, or internal paths.

## AI-assisted development

This project accepts AI-assisted contributions
under strict conditions. All contributors must
follow the guidelines in
[`docs/ai-guidelines.md`](docs/ai-guidelines.md).

### Requirements

- **Human ownership**: you must fully understand,
  review, test, and validate all AI output before
  committing. You bear full responsibility for
  AI-assisted contributions.
- **Marking**: commits with AI-assisted content
  must include both trailers:

  ```
  Assisted-by: Claude:claude-opus-4-6
  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
  ```

  `Assisted-by` follows the
  [Linux kernel convention](https://docs.kernel.org/process/coding-assistants.html)
  — the AI is a tool, not an author.
  `Co-Authored-By` provides GitHub UI rendering.

- **No confidential data**: never input
  confidential, personal, or access-controlled
  information into AI tools.
- **Provenance**: if AI output appears to
  reproduce existing copyrighted content, verify
  the license before incorporating it. Discard
  the output if compliance is not possible.
- **AI tools cannot be authors**: do not list
  AI tools as authors or copyright holders.
  The `Signed-off-by` trailer is for humans
  only — AI tools must not sign the DCO.

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
