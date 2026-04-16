# Local CLI Direct Tool Runner

## Context

The project already had a thin bootstrap server plus a local tool registry, but
there was still no obvious operator-facing path for trying the current system
directly.

Recent work improved retrieval and personal query behavior, but the easiest way
to understand the system remained “read tests” rather than “run the current
surface yourself”.

## Current Question

What is the smallest implementation that makes the current StrataWiki slice
directly runnable without leaking product-specific logic into core services?

## Observations

- `StrataWikiServer` already exposes a stable local seam:
  `list_tools`, `export_tool_schemas`, `call_tool`, and
  `call_tool_with_envelope`.
- The tool registry already carries the right contract metadata for direct
  inspection.
- The missing piece was not more retrieval logic but a local execution surface
  that stays aligned with the wired bootstrap/runtime.
- Adding domain-specific demo flows would overfit the current recruiting slice.
- A generic tool runner stays aligned with the MCP direction because it exposes
  the current tool contract rather than inventing a parallel product API.

## Options

### Option 1

Add a recruiting-specific demo script that hardcodes a few end-to-end scenarios.

### Option 2

Add a generic local CLI that exposes the current tool registry and direct tool
invocation.

### Option 3

Wait for the full MCP transport/runtime before adding any local operator path.

## Decision or Working Direction

Choose Option 2.

Implement a thin CLI around the existing server bootstrap so a developer can:

- list the currently wired tools
- inspect one tool schema
- call any current tool with inline JSON or a JSON file

This keeps retrieval, answer projection, and domain logic unchanged while making
the current system directly testable by hand.

## Open Questions

- Should the next runtime slice expose a scripted end-to-end walkthrough for
  ingestion plus projection workers, or should that wait for a more complete MCP
  transport?
- Should the CLI stay a pure developer surface, or later become the basis for
  admin/operator tasks?
- When the real MCP transport lands, how much of the CLI should remain as a
  local debug surface?

## Next Actions

- Keep the CLI generic and contract-driven.
- Use it as the default direct-try path while the MCP transport is still absent.
- Decide whether the next completion slice is projection-worker operation,
  stronger admin/runtime commands, or the actual transport layer.
