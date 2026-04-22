BEGIN;

ALTER TABLE personal.record
    RENAME COLUMN body_path TO path;

ALTER TABLE personal.record
    ADD COLUMN IF NOT EXISTS subspace TEXT,
    ADD COLUMN IF NOT EXISTS content_hash TEXT,
    ADD COLUMN IF NOT EXISTS version INTEGER,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS asset_refs_json JSONB;

UPDATE personal.record
SET asset_refs_json = '[]'::jsonb
WHERE asset_refs_json IS NULL;

UPDATE personal.record
SET created_at = updated_at
WHERE created_at IS NULL;

UPDATE personal.record
SET version = 1
WHERE version IS NULL OR version <= 0;

UPDATE personal.record
SET subspace = CASE
    WHEN path LIKE '%/documents/wiki/%' THEN 'wiki'
    WHEN path LIKE '%/answers/%' THEN 'wiki'
    ELSE 'raw'
END
WHERE subspace IS NULL;

UPDATE personal.record
SET subspace = COALESCE(provenance_json->'_personal_document'->>'subspace', subspace, 'raw')
WHERE provenance_json ? '_personal_document';

UPDATE personal.record
SET version = GREATEST(
    version,
    COALESCE(NULLIF(provenance_json->'_personal_document'->>'version', '')::INTEGER, version, 1)
)
WHERE provenance_json ? '_personal_document';

UPDATE personal.record
SET created_at = COALESCE(
    NULLIF(provenance_json->'_personal_document'->>'created_at', '')::timestamptz,
    created_at
)
WHERE provenance_json ? '_personal_document';

UPDATE personal.record
SET asset_refs_json = COALESCE(
    provenance_json->'_personal_document'->'asset_refs',
    asset_refs_json,
    '[]'::jsonb
)
WHERE provenance_json ? '_personal_document';

UPDATE personal.record
SET content_hash = ''
WHERE content_hash IS NULL;

ALTER TABLE personal.record
    ALTER COLUMN asset_refs_json SET DEFAULT '[]'::jsonb;

COMMIT;
