# ADR-003: License migration — AGPL-3.0-or-later

- **Status:** Accepted
- **Date:** 2026-08-30
- **Decision:** Migrate from GPL-3.0-or-later to AGPL-3.0-or-later. License studies and original documentation under CC-BY-SA 4.0.
- **Supersedes:** ADR-001 (license choice)

## Context

ADR-001 selected GPL-3.0-or-later based on an
evaluation of FSF, APRIL, and OSI positions,
patent protection, and MCP ecosystem
compatibility. That analysis remains valid — AGPL
v3 is a strict superset of GPL v3.

Since ADR-001, lore-mcp added SSE/HTTP transport
(`--transport sse`), making it deployable as a
network service. This creates a scenario the GPL
does not cover: a third party could fork
lore-mcp, modify it, deploy it as a hosted
service, and serve users without releasing the
modified source code. The GPL's copyleft triggers
only on distribution of the software, not on
providing access over a network.

The decision was made during cross-workspace
synchronization with the openshift project
(2026-08-30).

## Options evaluated

### Option A: Stay on GPL-3.0-or-later

- **Pros:** No migration effort. Already analyzed
  and documented.
- **Cons:** Does not protect against the SaaS
  loophole. A fork deployed as a hosted RAG
  service could diverge without contributing
  back.

### Option B: Migrate to AGPL-3.0-or-later

- **Pros:** Section 13 (Remote Network
  Interaction) requires that users interacting
  with the software over a network receive the
  source code. Closes the SaaS loophole. Same
  patent grant (§11) and copyleft as GPL v3.
  All existing dependencies (MIT, Apache 2.0)
  are compatible.
- **Cons:** Slightly more restrictive for
  organizations that deploy internal services
  — they must make source available to their
  own users (not publicly, just to users of the
  service). Some organizations have policies
  against AGPL.

## Decision

**AGPL-3.0-or-later.**

Rationale:
1. **Network clause closes the SaaS loophole:**
   lore-mcp is now deployable as an HTTP service.
   Without the network clause, a hosted fork
   could serve users without releasing
   modifications.
2. **No additional burden for the primary use
   case:** local workstation use (stdio transport)
   is unaffected by section 13 — there is no
   network interaction.
3. **Full backward compatibility:** AGPL v3 is a
   superset of GPL v3. All code previously
   licensed under GPL v3 can be relicensed under
   AGPL v3 by the copyright holder.
4. **Dependency compatibility:** MIT and Apache
   2.0 are compatible with AGPL v3, same as with
   GPL v3.
5. **Ecosystem precedent:** the FSF recommends
   AGPL for server software. The MCP ecosystem
   uses separate-process communication, so the
   AGPL does not propagate to MCP clients.

### Documentation license

Studies, ADRs, and original documentation are
additionally licensed under **CC-BY-SA 4.0**
(Creative Commons Attribution-ShareAlike). This
provides copyleft for content while using a
license designed for non-software works.

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by Romain Chantereau.

## Consequences

- The LICENSE file contains the full AGPL v3 text
- All references updated: pyproject.toml, README,
  CONTRIBUTING.md, CLAUDE.md
- ADR-001 retains its original GPL v3 analysis
  with an addendum noting the migration
- Contributors implicitly grant a patent license
  under AGPL v3 §11
- Forks deployed as network services must provide
  source code to users (section 13)
- The `--transport sse` deployment mode is now
  explicitly covered by the license's network
  clause
