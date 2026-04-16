# Outbox Retry Policy

## Context

The repository already had a working outbox table and synchronous workers for:

- Fact to Interpretation projection
- Interpretation to Personal stale marking

But failures still terminated immediately, which meant temporary worker or database issues would require manual intervention.

## Current Question

What is the smallest retry policy that improves operational resilience without adding new tables, a scheduler, or a more complex job framework?

## Observations

- ops.outbox_event already stores status, attempt_count, available_at, and last_error.
- claim_pending() already increments attempt_count when one worker claims an event.
- The current worker code can distinguish some permanent failures from retryable ones at the exception type level.
- The project still does not need a separate queueing system for the current vertical slice depth.

## Options

- Keep every failure terminal and depend on manual replay.
- Requeue all failures unconditionally.
- Requeue retryable failures with backoff and stop after a max-attempt threshold.

## Decision or Working Direction

Take the third option.

The implemented baseline is:

- ValueError is treated as terminal and marks the event failed.
- Other exceptions are treated as retryable.
- Retryable failures move the event back to pending.
- Requeued events use exponential backoff via available_at.
- Retries stop after the max-attempt threshold and then end in failed.

Current repository constants are:

- max attempts: 3
- base delay: 30 seconds

This keeps the policy simple and uses only fields that already exist in the baseline schema.

## Open Questions

- Whether retry classification should stay exception-type based or move to explicit domain error classes.
- Whether max attempts and base delay should remain hard-coded or move into configuration.
- Whether terminal failures should emit a separate audit or admin event for operator visibility.
- Whether future workers should support jitter to avoid synchronized retries under load.

## Next Actions

- Add a small explicit error taxonomy for retryable vs terminal worker failures.
- Decide whether retry policy belongs in repository code or a higher-level worker policy object.
- Add DB-backed verification of the retry path when a reachable Postgres instance is available.
- Continue with Personal regeneration or rendered-page refresh on top of the more resilient outbox flow.
