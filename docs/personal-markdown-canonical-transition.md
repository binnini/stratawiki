# Personal Markdown Canonical Transition

This change makes Personal markdown files the canonical body and reduces
`personal.record` to metadata needed to find, validate, and index that file.

## What Changed

- Personal canonical body now lives in the markdown file at `personal.record.path`.
- `personal.record` stores metadata such as `path`, `subspace`, `asset_refs_json`,
  `content_hash`, `version`, `created_at`, and `updated_at`.
- `body_markdown` is no longer treated as an implicit DB-canonical field.
- New Personal writes no longer inject StrataWiki comment metadata into markdown bodies.
- Runtime code now assumes Personal bodies are already canonical markdown files.

## Compatibility

- Legacy comment parsing and `_personal_document` provenance handling now live only in
  the migration helper, not in the runtime read path.
- `PersonalRecord.path` is now the only canonical location field for Personal
  records.

## Existing Database Migration

For an already-initialized database, use the SQL migration first:

`config/postgres/migrations/20260422_personal_markdown_canonical.sql`

Then run the app-level backfill to normalize existing markdown files, compute
canonical `content_hash`, and optionally prune legacy provenance:

```bash
python -m wiki_mcp.personal_markdown_migration \
  --database-url "$DATABASE_URL" \
  --render-root data \
  --rewrite-files \
  --prune-legacy-provenance
```

Then backfill:

- `subspace` from legacy provenance or from path conventions
- `version` and `created_at` from legacy provenance
- `content_hash` from the canonical markdown body after legacy comment removal

After backfill, enforce `NOT NULL` constraints to match `config/postgres/bootstrap.sql`.
