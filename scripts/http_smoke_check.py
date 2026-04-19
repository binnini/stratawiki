from __future__ import annotations

import json
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    auth_token: str | None = None,
) -> dict[str, Any]:
    payload = None
    headers = {"Accept": "application/json"}
    if body is not None:
        payload = json.dumps(body, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=payload,
        headers=headers,
        method=method,
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_http(
    base_url: str,
    *,
    attempts: int,
    delay_seconds: float,
) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            payload = _request(base_url, "/healthz")
            if payload.get("ok") is True:
                return
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = exc
        time.sleep(delay_seconds)
    raise RuntimeError(f"HTTP runtime never became ready at {base_url}: {last_error}")


def _assert_ok(payload: dict[str, Any], *, label: str) -> dict[str, Any]:
    if payload.get("ok") is not True:
        raise RuntimeError(f"{label} did not return ok=true: {payload}")
    result = payload.get("result")
    if not isinstance(result, dict | list):
        raise RuntimeError(f"{label} returned unexpected result payload: {payload}")
    return {"result": result}


def main() -> int:
    base_url = os.environ.get("STRATAWIKI_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    auth_token = os.environ.get("STRATAWIKI_HTTP_AUTH_TOKEN") or None
    retries = int(os.environ.get("STRATAWIKI_HTTP_SMOKE_RETRIES", "20"))
    delay_seconds = float(os.environ.get("STRATAWIKI_HTTP_SMOKE_DELAY_SECONDS", "1"))

    _wait_for_http(base_url, attempts=retries, delay_seconds=delay_seconds)

    health = _assert_ok(_request(base_url, "/healthz"), label="healthz")["result"]
    if not isinstance(health, dict) or health.get("status") != "ok":
        raise RuntimeError(f"healthz returned unexpected payload: {health}")

    ready = _assert_ok(_request(base_url, "/readyz"), label="readyz")["result"]
    if not isinstance(ready, dict) or ready.get("status") != "ready":
        raise RuntimeError(f"readyz returned unexpected payload: {ready}")

    tools = _assert_ok(
        _request(base_url, "/api/v1/tools", auth_token=auth_token),
        label="tools",
    )["result"]
    if not isinstance(tools, list) or not tools:
        raise RuntimeError(f"/api/v1/tools returned no tools: {tools}")

    with open("/app/examples/integration/recruiting-domain-proposal-batch.json", "r", encoding="utf-8") as handle:
        proposal_batch = json.load(handle)
    validation = _assert_ok(
        _request(
            base_url,
            "/api/v1/domain-proposals/validate",
            method="POST",
            body=proposal_batch,
            auth_token=auth_token,
        ),
        label="proposal validate",
    )["result"]
    if not isinstance(validation, dict) or validation.get("committed") is not False:
        raise RuntimeError(f"proposal validation returned unexpected payload: {validation}")

    snapshot_path = "/api/v1/snapshot-status?" + urlencode({"domain": "recruiting"})
    snapshot = _assert_ok(
        _request(base_url, snapshot_path, auth_token=auth_token),
        label="snapshot status",
    )["result"]
    if not isinstance(snapshot, dict) or not snapshot.get("fact_snapshot"):
        raise RuntimeError(f"snapshot status returned unexpected payload: {snapshot}")

    print("HTTP smoke passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
