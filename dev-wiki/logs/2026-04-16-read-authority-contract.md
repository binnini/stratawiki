# Read Authority Contract For Rendered Pages

## Context

The repository already has a `DefaultPageReadEntrypoint` that exposes rendered
Personal and shared Interpretation pages as the first WAS-facing read slice.

The existing response envelope was still too loose for external dependency use:

- `read_model_state` was behaving like a mixed success/not-found flag
- projection family metadata was missing
- `page_not_found` was being mapped to `not_applicable`

## Current Question

What is the minimum page-read response contract that an external WAS can depend
on today without pretending broader read-model visibility exists?

## Observations

- The current entrypoint is authoritative only for one projection family:
  document-shaped rendered pages.
- A missing rendered page is not the same as a projection family being
  inapplicable.
- The current implementation does not track worker lag, stale state, or partial
  visibility for this slice, so emitting those states would be fake.
- WAS callers still need stable metadata describing which projection family and
  layer produced the response.

## Options

- Keep `not_applicable` on page miss and defer cleanup.
- Treat page lookup as an authoritative document projection read and make
  `page_not_found` a separate outcome inside an `applied` envelope.

## Decision or Working Direction

Take the second option.

The current contract is tightened as follows:

- every page-read response now carries `projection` metadata
- `projection.family` is fixed to `document` for this slice
- `projection.layer` carries `personal` or `interpretation` when requested
- `projection.scope` carries `shared`, `tenant`, or `user`
- `read_model_state` is narrowed to `applied` because that is the only state the
  current entrypoint can report authoritatively
- `page_not_found` remains an error outcome, but it now sits under
  `read_model_state = applied`

## Open Questions

- Whether future list/read slices should expose a richer projection key than
  `{family, layer, scope}` once search/tree/graph reads are added.
- Whether `not_applicable` should be introduced later only after a caller can
  ask for a projection family that the read authority explicitly knows it does
  not serve.
- Whether document projection responses should later include projection version
  tokens once rendered-page publication versioning exists.

## Next Actions

- Keep the current contract limited to rendered document pages.
- Avoid widening `read_model_state` until real pending/stale/not-applicable
  detection exists.
- Reuse the same envelope shape when the next WAS-facing document read route is
  added.
