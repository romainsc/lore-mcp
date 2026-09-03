# Contributing to lore-mcp

## Rules

1. One topic per branch, one branch per PR.
2. If fixing a bug, open an issue first describing the problem. Link the issue in your PR.
3. Tests first. This project uses TDD — write failing tests, then implement. PRs without tests will not be merged.
4. If using AI to write your changes, you must understand every line. Vibe-coded contributions without understanding by the submitter take up review time and will be deprioritized.
5. Fix all CI errors and warnings before requesting review. PRs with clean CI are prioritized.
6. Do not force push unless necessary for conflict resolution.
7. Keep PR descriptions concise and factual. Do not paste AI-generated walls of text.
8. Every commit must include a `Signed-off-by` trailer (DCO). Use `git commit -s`.
9. AI-assisted commits must include both `Assisted-by` and `Co-Authored-By` trailers.
10. All code, comments, docstrings, documentation, and commit messages in English.

## Developer Certificate of Origin

This project uses [DCO v1.1](https://developercertificate.org/). By signing off your commits, you certify you have the right to submit the code under the AGPL-3.0-or-later license.

```
Signed-off-by: Your Name <your.email@example.com>
```

AI tools must not sign the DCO — only humans.

## Setup

```bash
git clone https://github.com/romainsc/lore-mcp.git
cd lore-mcp
git config core.hooksPath .githooks
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Git workflow

- `main` is stable. Never commit directly to main (enforced by git hook).
- Branch naming: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`.
- Sub-branches for sub-topics (e.g. `feat/store/meta-table`).
- Merge with `--no-ff`. Merge only when the topic is closed.
- Do not delete branches after merge.
- Run `git config core.hooksPath .githooks` after cloning.

## AI-assisted contributions

See [`docs/ai-guidelines.md`](docs/ai-guidelines.md) for the full guidelines.

Commit trailers for AI-assisted work:

```
Assisted-by: Claude:claude-opus-4-6
Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

## License

By contributing, you agree that your contributions will be licensed under [AGPL-3.0-or-later](LICENSE).
