# AI-assisted development guidelines

This document defines the rules governing AI-assisted
development in lore-mcp. It operationalizes principles
from Red Hat's public and internal guidance on
responsible AI use.

Public reference:
[AI-assisted development: Supercharging the open source way](https://www.redhat.com/en/blog/ai-assisted-development-supercharging-open-source-way)
(Chris Wright, Red Hat CTO, September 2025)

## 1. Principles

### Human oversight

AI augments human work — it does not replace it.
Every line of code, whether written by a human or
with AI assistance, must be reviewed, tested, and
validated by a human before being committed.

### Transparency

AI involvement in producing project content must
be disclosed. Users, contributors, and reviewers
must be able to identify which content was
AI-assisted.

### Quality parity

AI-generated code is held to the same standards
as human-written code: correctness, security,
test coverage, style, and licensing compliance.
There is no lower bar for AI output.

### Accountability

The human who commits AI-assisted content takes
full responsibility for it — its correctness, its
security, its licensing, and its fitness for
purpose.

## 2. Data protection

### Forbidden inputs to AI tools

Never provide the following as input to any
AI tool:

- Confidential or proprietary information
- Personal information (PII)
- Customer or partner data
- Access-controlled documentation
- Credentials, tokens, API keys
- Third-party intellectual property not covered
  by a compatible license

### Corpus and index files

The `.db` index files and the source corpus must
never be fed into AI tools. They may contain
content subject to third-party rights.

## 3. Provenance and licensing

### Output review

Treat all AI output as coming from an unreliable
source. Before incorporating AI output:

1. **Review** for correctness and security
2. **Check** whether the output appears to
   reproduce specific existing content
3. If it resembles existing copyrighted material,
   **verify** it is covered by a compatible
   license before using it
4. If license compliance is not possible,
   **discard** the output

### Training data

Do not attempt to use AI tools to extract or
reproduce training data.

### Upstream policies

Before contributing AI-assisted code to any
upstream open source project, check whether that
project has a policy on AI-generated
contributions. Comply with any such policy.

## 4. Marking conventions

### Commits

All commits containing nontrivial AI-assisted
content must include a `Co-Authored-By` trailer
identifying the AI model used:

```
Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

This applies to code, documentation, and
configuration alike.

### Documents and content

Nontrivial documents substantially produced with
AI assistance (ADRs, studies, technical docs)
must include a notice, for example:

```
> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by [author].
```

### Copyright notices

Copyright notices may be applied to AI-assisted
content when the human author has provided
substantial creative input and modification.
Do not apply copyright to content that is
substantially AI-generated with little or no
human creative input — in such cases, mark the
content as AI-generated instead.

## 5. Pre-commit checklist

Before every commit containing AI-assisted
content:

- [ ] Output reviewed for correctness
- [ ] No confidential or personal data included
- [ ] No apparent reproduction of copyrighted
      third-party content
- [ ] Security: no hardcoded credentials, no
      injection vulnerabilities, no unsafe patterns
- [ ] Tests pass (or are written, for TDD)
- [ ] `Co-Authored-By` trailer present
- [ ] `git diff --cached` inspected for
      unintended content
