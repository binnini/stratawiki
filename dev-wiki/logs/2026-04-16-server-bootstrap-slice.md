# Server Bootstrap Slice

## Context

The repository already had:

- a write-side application entrypoint for ingestion
- a read-side application entrypoint for rendered page reads
- a placeholder `server.py` with no reusable bootstrap structure

The next useful step was not a full MCP transport implementation.
It was a thin bootstrap layer that makes the current entrypoints composable from one place.

## Current Question

What is the smallest server bootstrap structure that makes the existing internal/application-facing entrypoints visibly wireable, without pretending the full MCP protocol already exists?

## Observations

- `connect_postgres(...)` lived inside the ingestion entrypoint module even though both read and write slices need connection bootstrap.
- `server.py` had no runtime object, no bundled dependencies, and no place to mount an eventual tool layer.
- The docs consistently separate MCP/tool interface concerns from internal service interfaces, so the next layer should stay thin and orchestration-focused.
- Current real capabilities are still limited to ingestion and rendered page reads.
- The first local tool registry shape exposed names and placeholder status, but it did not yet make tool grouping, entrypoint ownership, or argument-level contract intent visible.
- For the next MCP-facing slice, the useful preparation work is contract clarity, not a fake session/transport/runtime abstraction.

## Options

- Keep `server.py` as a placeholder until a real MCP SDK/runtime is introduced.
- Add a thin bootstrap context plus a local tool registry that directly wraps current entrypoints.

## Decision or Working Direction

Take the thin bootstrap route now.

The implemented shape is:

- `bootstrap.py`
  - `connect_postgres(...)`
  - `build_application_entrypoints(...)`
  - `bootstrap_application(...)`
  - `BootstrapContext`
- `server.py`
  - `build_server(...)`
  - `StrataWikiServer`
- `tools/`
  - `ToolRegistry`
  - default wired tools for current ingestion/page-read entrypoints
  - explicit placeholder tool registrations for future MCP contracts
  - grouped tool metadata with entrypoint ownership and thin argument contracts

This keeps the transport boundary honest:

- current internal entrypoints are actually wired
- future MCP tool families are visible as placeholders
- local tool registration now exposes enough metadata to map present tools to future MCP contracts
- no fake JSON-RPC/session/protocol runtime is introduced yet

## Implementation Update

The current bootstrap/tool slice is now a bit more contract-oriented:

- `ToolDefinition` now carries:
  - `group`
  - `entrypoint`
  - `arguments`
  - `result_fields`
  - `error_codes`
  - `status`
- `ToolRegistry` now:
  - rejects duplicate registrations
  - returns a stable grouped listing for server/bootstrap inspection
  - validates required arguments and thin primitive/object types before dispatch
  - exports a public schema shape that a future MCP adapter can reuse
- `build_default_tool_definitions(...)` now expresses the default tool layer as an explicit registration list before registry construction
- `server.main()` now reports tools grouped by contract family instead of only printing one flat available/placeholder split

This is still intentionally thin:

- no MCP transport
- no fake runtime/session abstraction
- no full schema-validator framework
- no attempt to hide that most future tool families are still placeholders

## Open Questions

- Whether the eventual MCP runtime should reuse the current tool registry shape directly or only reuse the tool definitions.
- Whether more application-facing entrypoints should be added before introducing a transport adapter.
- Whether argument validation should stay lightweight here or move fully into a future MCP adapter layer.

## Next Actions

- Add the first real MCP transport/runtime adapter only after more tool families are backed by real services.
- Decide whether tool metadata should expose richer schemas once external callers depend on it.
- Fold additional internal entrypoints into the same bootstrap context as new vertical slices land.
- When the MCP adapter is introduced, reuse the grouped tool definitions and metadata, but keep request validation and transport concerns outside the internal entrypoint layer.
