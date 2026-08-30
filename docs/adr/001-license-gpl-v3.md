# ADR-001: License — GPL-3.0-or-later

- **Status:** Accepted
- **Date:** 2026-07-29
- **Decision:** License the project under the GNU General Public License v3 or later (GPL-3.0-or-later)

## Context

lore-mcp is a standalone MCP server and CLI tool for local semantic search over technical documents. It is not a library — no third-party code links against it. It runs as a separate process communicating with MCP clients (Claude Code, Claude Desktop, Cursor, etc.) via stdio or HTTP.

The project needs a license that:
1. Protects users against software patent claims
2. Ensures derivative works (forks) remain free software
3. Is compatible with all project dependencies
4. Aligns with the values of the free software ecosystem

## Options evaluated

### MIT (Expat)

- **Pros:** Shortest text, universally understood, dominant in the MCP ecosystem (the MCP Python SDK is MIT-licensed), no friction for corporate contributors.
- **Cons:** No patent grant — a contributor could patent a technique, contribute code implementing it, then sue downstream users. The FSF explicitly stopped recommending MIT for new projects in favor of Apache 2.0. Allows proprietary forks without reciprocity.

### Apache License 2.0

- **Pros:** Explicit patent grant (§3), well-established, praised by the FSF as "the best non-copyleft license" for mitigating patent threats. Compatible with GPL v3. Standard in the Red Hat ecosystem.
- **Cons:** No copyleft — forks can be made proprietary. Not compatible with GPL v2 (the patent clause creates an incompatibility). Longer and more complex than MIT without providing the reciprocity guarantee.

### GPL v3 or later

- **Pros:** Strong copyleft — derivative works must remain free software. Explicit patent grant (§11) — contributors automatically grant a patent license, and any contributor who initiates patent litigation loses their rights. Recommended by the FSF as the primary license for all software. Recommended by the APRIL (the French association for the promotion of free software). Compatible with Apache 2.0 code (one-way: Apache 2.0 code can be incorporated into GPL v3 projects).
- **Cons:** Some corporate contributors have policies against contributing to GPL projects. Atypical in the MCP ecosystem (most servers are MIT/Apache 2.0). Not compatible with GPL v2.

## Institutional positions

### FSF (Free Software Foundation)

The FSF recommends GPL v3+ as the primary license for all software. For cases where copyleft is not desired, they recommend Apache 2.0 — explicitly not MIT. Quote: *"Apache License 2.0 is the best non-copyleft license that does what a copyright license can to mitigate threats from software patents."* They no longer recommend MIT/Expat for new projects.

Source: [FSF license recommendations guide](https://www.fsf.org/blogs/licensing/new-license-recommendations-guide)

### APRIL (Association pour la Promotion et la Recherche en Informatique Libre)

APRIL aligns with the FSF position. They actively promote copyleft and the GPL as the mechanism that guarantees software freedom is preserved in derivative works. APRIL contributed to the French translation of the GPL and to the drafting of CeCILL (the GPL adaptation for French law).

Source: [APRIL — Licences, du copyright au copyleft](https://www.april.org/licences-du-copyright-au-copyleft)

### OSI (Open Source Initiative)

The OSI takes a neutral position between permissive and copyleft licenses. Both MIT, Apache 2.0, and GPL are among their recommended "popular and widely used" licenses. The choice depends on project goals.

Source: [OSI — Licenses](https://opensource.org/licenses)

## MCP ecosystem compatibility

The MCP ecosystem uses:
- **MCP Python SDK** (`mcp` package): MIT
- **MCP reference servers** (`modelcontextprotocol/servers`): MIT + Apache 2.0
- **MCP specification**: open standard, hosted by the Linux Foundation

**GPL v3 compatibility is confirmed in both directions:**

1. **Inbound (dependencies we use):** MIT and Apache 2.0 code can be incorporated into a GPL v3 project. All our dependencies are compatible:

   | Dependency | License | GPL v3 compatible |
   |---|---|---|
   | mcp (MCPServer v2) | MIT | Yes |
   | sentence-transformers | Apache 2.0 | Yes |
   | sqlite-vec | MIT | Yes |
   | langchain-text-splitters | MIT | Yes |
   | BAAI/bge-m3 (model) | MIT | Yes |

2. **Outbound (interaction with MCP clients):** An MCP server runs as a **separate process** communicating via a defined protocol (stdio/HTTP). There is no code linking. The GPL's copyleft applies to derivative works that incorporate the GPL code, not to separate programs that communicate via a protocol. A proprietary MCP client (Claude Desktop, Cursor) can invoke a GPL v3 MCP server without any licensing obligation — exactly as a proprietary web browser can access a GPL-licensed web server.

## Patent grant comparison

| License | Patent grant | Defensive termination |
|---|---|---|
| MIT | None | None |
| Apache 2.0 | Explicit (§3) | Contributor loses grant if they sue (§3) |
| GPL v3 | Explicit (§11) | Contributor loses grant if they sue (§11); additional "liberty or death" clause |

Both Apache 2.0 and GPL v3 provide patent protection. GPL v3 goes further with its "liberty or death" provision: if patent litigation makes it impossible to distribute the software freely, distribution must cease entirely rather than continue under restricted terms.

## Decision

**GPL-3.0-or-later.**

Rationale:
1. **Patent protection:** GPL v3 provides the strongest patent grant and defensive termination among the three options.
2. **Freedom preservation:** As a standalone tool (not a library), the copyleft requirement costs nothing to legitimate users while ensuring forks remain free.
3. **No ecosystem friction:** MCP servers are separate processes; the GPL does not propagate to MCP clients.
4. **Institutional alignment:** Follows the primary recommendation of both the FSF and APRIL.
5. **Dependency compatibility:** All dependencies are GPL v3 compatible.

The "or later" clause follows the FSF recommendation to allow future GPL versions to protect against threats not yet anticipated.

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by Romain Chantereau.

## Consequences

- The LICENSE file contains the full AGPL v3 text
- All source files should include a brief copyright and license header (or reference the LICENSE file)
- Contributors implicitly grant a patent license under AGPL v3 §11
- Forks must remain AGPL v3+ — proprietary derivatives are not permitted
- Corporate contributors with anti-GPL policies cannot contribute (acceptable trade-off for a community-oriented tool)

## Addendum: migration to AGPL-3.0 (2026-08-30)

The license was migrated from GPL-3.0-or-later to
**AGPL-3.0-or-later** per openshift cross-workspace
sync decision. The AGPL adds section 13 (Remote
Network Interaction): if someone forks lore-mcp
and deploys it as a network service, they must
provide the source code to users of that service.

This closes the "SaaS loophole" present in GPL v3
where a forked version could be deployed as a
hosted service without releasing modifications.

All dependencies remain compatible (MIT, Apache
2.0 are compatible with AGPL v3). The original
GPL v3 analysis in this ADR remains valid — AGPL
v3 is a superset of GPL v3 with the network
clause added.

Studies and original documentation are additionally
licensed under **CC-BY-SA 4.0** (share-alike,
copyleft content).
