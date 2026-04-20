from __future__ import annotations

from typing import Any

from wiki_mcp.server import StrataWikiServer


INTERPRETATION_SNAPSHOT_BUILD_REQUESTED = "interpretation_snapshot_build_requested"


def run_worker_once(server: StrataWikiServer, *, limit: int) -> dict[str, object]:
    outbox_repository = server.bootstrap.outbox_repository
    if outbox_repository is None:
        raise ValueError("Outbox repository is not configured for this runtime.")

    claimed = outbox_repository.claim_pending(
        limit=limit,
        event_types=[INTERPRETATION_SNAPSHOT_BUILD_REQUESTED],
    )
    processed = 0
    failed = 0
    jobs: list[dict[str, Any]] = []

    for event in claimed:
        try:
            payload = dict(event["payload"])
            payload.pop("execution_mode", None)
            result = server.call_tool("build_interpretation_snapshot", payload)
            outbox_repository.mark_processed(event["id"])
            processed += 1
            jobs.append(
                {
                    "job_id": event["id"],
                    "event_type": event["event_type"],
                    "status": "processed",
                    "result": result,
                }
            )
        except Exception as exc:
            outbox_repository.mark_failed(event["id"], str(exc))
            failed += 1
            jobs.append(
                {
                    "job_id": event["id"],
                    "event_type": event["event_type"],
                    "status": "failed",
                    "error": {
                        "type": exc.__class__.__name__,
                        "message": str(exc),
                    },
                }
            )

    return {
        "status": "ok",
        "claimed": len(claimed),
        "processed": processed,
        "failed": failed,
        "jobs": jobs,
    }
