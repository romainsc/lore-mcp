# Research: MCP Long-Running Operations (E3.09)

> Date: 2026-09-28
> Status: Verified (web research)

## 1. MCP Spec — Current State

### Progress Notifications (Core)

The core spec supports `notifications/progress` with
a `progressToken`. Either party can send progress
updates with `progress`, `total`, and `message`
fields. Available since early MCP versions.

### Tasks Extension (SEP-2663, 2026-07-28)

Tasks graduated from experimental to official
extension in the 2026-07-28 spec. Contributed by AWS.

**Lifecycle**: `tools/call` returns a task handle
(`taskId`, `status`, `ttl`, `pollingInterval`).
Client drives with `tasks/get`, `tasks/update`,
`tasks/cancel`. States: `working`, `input_required`,
`completed`, `failed`, `cancelled`.

**Design principle**: stateless. `tasks/list` removed
(unsafe without sessions). Tasks scoped to
originating session and auth context.

**Future**: push notifications being explored
(webhook-style callbacks instead of polling).

### Python SDK Status (mcp 2.2.0, Sep 2026)

**Not implemented yet.** The v2.2.0 release notes
list Tasks as "not implemented yet" (ROADMAP.md).
The old experimental version was deleted.

The SDK does provide an **Extension framework**:
subclass `Extension`, override `identifier` +
tools/resources/methods. Fixed at construction.

## 2. Community Patterns

### Pattern A: Custom polling tools

**mcp-background-job** (dylan-gluck), **mcp-bgtask**
(nanoseil): shell commands as background jobs. Tools:
`start_job(command)` → job_id, `get_job_status(id)`,
`get_job_output(id)`, `stop_job(id)`.

Simple, works with any MCP client. No Tasks extension
needed. The LLM polls `get_job_status` in a loop.

### Pattern B: Tasks extension (SEP-2663)

**long-running-mcp-tools** (suneetnangia): Python
server with `task=True` on tools. Uses FastMCP 4 +
`TasksExtension`. Client polls `tasks/get` until
terminal state.

**Azure Durable Functions sample**: .NET server with
budgeted start + poll. Returns `status: running` +
`workflow_id` + `next` instruction. Client calls
`get_result(id)` until `completed`.

**FastMCP tasks** (Prefect/PrefectHQ): production
distributed task scheduler via Docket. One decorator
change. But requires FastMCP, not official SDK.

### Pattern C: SDK Extension subclass

Build Tasks yourself on the official SDK. Tutorial
at nerdleveltech.com demonstrates end-to-end.
Subclass `Extension`, add `tasks/get` etc. as
custom methods via `MethodBinding`.

### Pattern D: AWS Bedrock AgentCore

Four patterns demonstrated: progress reporting,
background timer, async task management, and
memory-integrated async.

## 3. Config Passing

### Best practice: task-oriented parameters

Design tool params for what the user wants to
accomplish, not what the API supports.

Bad: `build(chunk_size=1024, overlap=128, model="nomic", ...)`
Good: `build(manifest="/path/to/manifest.yaml", build_dir="/path/to/build/")`

Complex config → reference a config file path.
Inline params for common overrides only.

### Path parameters

Canonicalize and scope-check all paths. Prevent
path traversal attacks. Apply to every parameter
that touches a filesystem.

## 4. Security & Rate Limiting

### Rate limiting

Apply at three layers: client edge, tool router,
integration boundary. Use token bucket algorithm.
Tighten on expensive operations (inference, build).

MCP-compatible error response (not HTTP error):
"Rate limit exceeded: N requests per minute.
Wait M seconds before retrying."

### Authentication

Per-request auth context. Tasks scoped to session.
No token passthrough (anti-pattern).

### Sandboxing

Foundational for enterprise. Isolate agent actions
from resources beyond intended scope. Critical for
build/preprocess operations that touch filesystem.

## 5. Comparison — Approaches for lore-mcp

| Approach | Pros | Cons | Effort |
|----------|------|------|--------|
| **A: Custom polling tools** | Works now, any client, simple | Non-standard, manual poll loop | Low |
| **B: Tasks extension (FastMCP)** | Standard, production-ready | Requires FastMCP (Redis dep) | Medium |
| **C: Tasks via SDK Extension** | Standard, official SDK | SDK doesn't implement yet, build from scratch | High |
| **D: Wait for SDK** | Zero effort | Unknown timeline, blocks E3.09 | Zero |

## 6. Recommendation for lore-mcp

### Short term: Pattern A (custom polling tools)

Implement simple background job tools using the
existing MCP SDK:

```python
@mcp.tool()
def start_build(manifest: str, build_dir: str, ...) -> str:
    """Start a build in background. Returns task ID."""
    task_id = _launch_background_build(...)
    return f"Build started: {task_id}. Poll with get_task_status()"

@mcp.tool()
def get_task_status(task_id: str) -> str:
    """Check status of a background task."""
    return _get_task_info(task_id)

@mcp.tool()
def cancel_task(task_id: str) -> str:
    """Cancel a running background task."""
    return _cancel_task(task_id)
```

**Why**: works with current SDK (mcp 2.2.0), any
MCP client, no external dependencies. Claude Code
and Claude Desktop can poll `get_task_status`.

### Medium term: migrate to Tasks extension

When the official Python SDK ships Tasks support,
migrate from custom tools to the standard extension.
The internal background job mechanism stays the same;
only the MCP interface changes.

### Design rules

1. Short operations (lint, state, search) → regular
   blocking tools (return result directly)
2. Long operations (build, preprocess, eval, optimize)
   → background task tools (return task_id)
3. Config → file path reference, not inline params
4. Progress → stored per task, queryable via status
5. Rate limiting → one build at a time (semaphore)

## References

- [MCP Specification 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28)
- [MCP 2026-07-28 Blog Post](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [MCP Roadmap](https://blog.modelcontextprotocol.io/posts/mcp-roadmap/)
- [Long Running Tasks: Call-Now, Fetch-Later](https://agnost.ai/blog/long-running-tasks-mcp/)
- [MCP Python SDK Extensions](https://py.sdk.modelcontextprotocol.io/advanced/extensions/)
- [Tasks Extension Tutorial (Python)](https://nerdleveltech.com/mcp-tasks-extension-python-tutorial)
- [mcp-background-job (GitHub)](https://github.com/dylan-gluck/mcp-background-job)
- [Azure Durable Functions MCP sample](https://github.com/Azure-Samples/mcp-functions-long-running-tools)
- [AWS Bedrock AgentCore MCP sample](https://github.com/aws-samples/sample-mcp-for-long-runing-tasks-with-amazon-bedrock-agentcore)
- [MCP Architecture Patterns (IBM)](https://ibm.github.io/mcp-context-forge/1.0.0-RC3/best-practices/mcp-architecture-patterns/)
- [MCP Security Best Practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices)
- [MCP Rate Limiting Guide](https://fast.io/resources/mcp-server-rate-limiting/)
- [OWASP MCP Security (Microsoft)](https://microsoft.github.io/mcp-azure-security-guide/adoption/development-best-practices/)
